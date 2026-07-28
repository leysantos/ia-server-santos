"""L14 — Cobertura fotográfica estratificada para a passagem 1 do laudo.

Evita o teto cego uniforme de N fotos: seleciona âncoras (primeira/última),
fotos com legenda do usuário, diversidade de orientação e amostra uniforme
dos restantes. Quando há muitas fotos, agenda ondas extras de cobertura
(diagnóstico leve só de patologias) sobre o que não entrou na onda principal.
"""

from __future__ import annotations

from typing import Any

# Onda principal (diagnóstico completo) — acima do antigo hard-cap 16
DIAG_SOFT_CAP = 24
# Máximo absoluto na onda 1 (proteção de tokens/API)
DIAG_HARD_CAP = 32
# Fotos por onda de cobertura complementar
COVERAGE_BATCH_SIZE = 10
# Limite de ondas extras (protege custo/latência em laudos com 100+ fotos)
MAX_COVERAGE_WAVES = 6


def select_diagnostic_indices(
    n: int,
    photo_meta: list[dict[str, Any]] | None = None,
    *,
    soft_cap: int = DIAG_SOFT_CAP,
    hard_cap: int = DIAG_HARD_CAP,
) -> list[int]:
    """
    Índices 0..n-1 para a passagem 1 (diagnóstico).

    Estratégia:
    1. Se n ≤ soft_cap → todas
    2. Senão: âncoras (0, n-1) + legendadas + diversidade de orientação
       + preenchimento uniforme até soft_cap (clamp hard_cap)
    """
    if n <= 0:
        return []
    cap = max(2, min(int(soft_cap), int(hard_cap)))
    if n <= cap:
        return list(range(n))

    meta = list(photo_meta or [])
    selected: set[int] = {0, n - 1}

    # Preferir fotos com caption do usuário
    captioned: list[int] = []
    for i in range(n):
        m = meta[i] if i < len(meta) else {}
        cap_txt = str(m.get("caption") or "").strip()
        if cap_txt and not cap_txt.lower().startswith("registro"):
            captioned.append(i)
    # Espaça legendadas se muitas
    if captioned:
        if len(captioned) <= cap // 2:
            selected.update(captioned)
        else:
            step = max(1, len(captioned) // (cap // 2))
            selected.update(captioned[::step][: cap // 2])

    # Diversidade de orientação
    by_orient: dict[str, list[int]] = {}
    for i in range(n):
        m = meta[i] if i < len(meta) else {}
        orient = str(m.get("orientation") or "n/d").lower()[:20]
        by_orient.setdefault(orient, []).append(i)
    for idxs in by_orient.values():
        mid = idxs[len(idxs) // 2]
        selected.add(mid)
        if len(selected) >= cap:
            break

    # Preenchimento uniforme
    if len(selected) < cap:
        need = cap - len(selected)
        step = (n - 1) / max(1, need + 1)
        for k in range(1, need + 3):
            idx = min(n - 1, int(round(k * step)))
            selected.add(idx)
            if len(selected) >= cap:
                break

    ordered = sorted(selected)[:cap]
    # Garantir extremos
    if 0 not in ordered:
        ordered = [0] + ordered[:-1]
    if n - 1 not in ordered:
        ordered = ordered[:-1] + [n - 1]
    return sorted(set(ordered))[:cap]


def coverage_remainder_batches(
    n: int,
    sampled: list[int],
    *,
    batch_size: int = COVERAGE_BATCH_SIZE,
    max_waves: int = MAX_COVERAGE_WAVES,
) -> list[list[int]]:
    """Índices não amostrados, em lotes para ondas de cobertura."""
    sampled_set = set(sampled)
    rest = [i for i in range(n) if i not in sampled_set]
    if not rest:
        return []
    # Se rest é grande, reamostra uniformemente até max_waves * batch_size
    max_photos = max_waves * batch_size
    if len(rest) > max_photos:
        step = (len(rest) - 1) / max(1, max_photos - 1)
        rest = sorted({rest[min(len(rest) - 1, int(round(i * step)))] for i in range(max_photos)})
    batches: list[list[int]] = []
    for i in range(0, len(rest), batch_size):
        batches.append(rest[i : i + batch_size])
    return batches[:max_waves]


def coverage_prompt(
    *,
    objeto: str,
    photo_meta_batch: list[dict[str, Any]],
    existing_pathology_codes: list[str],
) -> str:
    photos_block = "\n".join(
        f"- Foto {p.get('photo_number'):02d}: arquivo={p.get('filename')} "
        f"orientação={p.get('orientation') or 'n/d'} legenda_usuario={p.get('caption') or '—'}"
        for p in photo_meta_batch
    )
    codes = ", ".join(existing_pathology_codes) or "(nenhuma ainda)"
    return f"""Você é engenheiro civil em ONDA DE COBERTURA FOTOGRÁFICA (L14).
Analise as imagens anexadas que AINDA NÃO entraram no diagnóstico principal.

Objeto: {objeto or 'obra vistoriada'}
Patologias já registradas (não duplique sem necessidade): {codes}

FOTOS DESTA ONDA:
{photos_block}

Objetivo: detectar anomalias adicionais ou confirmar as existentes.
Se a foto só reforça uma patologia já listada, referencie o código em pathology_refs.
Se houver dano NOVO relevante, crie nova patologia com próximo código livre (P0N).

Responda APENAS JSON:
{{
  "pathologies_delta": [
    {{
      "code": "P07",
      "name": "…",
      "location": "…",
      "element": "…",
      "element_id": "",
      "severity": "crítica|alta|média|baixa",
      "score": 4,
      "description": "…",
      "cause": "…",
      "solution": "…",
      "urgency": "…",
      "photo_refs": [12, 15]
    }}
  ],
  "photo_notes": [
    {{
      "photo_number": 12,
      "severity": "alta",
      "element_hint": "longarina",
      "pathology_refs": ["P01"],
      "note": "confirma corrosão já descrita"
    }}
  ]
}}
"""


def merge_coverage_into_content(
    content: dict[str, Any],
    wave: dict[str, Any],
) -> dict[str, Any]:
    """Mescla pathologies_delta e anotações de foto da onda de cobertura."""
    out = dict(content or {})
    paths = [dict(p) for p in (out.get("pathologies") or []) if isinstance(p, dict)]
    existing_codes = {
        str(p.get("code") or p.get("codigo") or "").strip().upper()
        for p in paths
        if p.get("code") or p.get("codigo")
    }

    for raw in wave.get("pathologies_delta") or []:
        if not isinstance(raw, dict):
            continue
        code = str(raw.get("code") or raw.get("codigo") or "").strip().upper()
        if not code:
            # gera próximo
            nums = []
            for c in existing_codes:
                if c.startswith("P") and c[1:].isdigit():
                    nums.append(int(c[1:]))
            code = f"P{max(nums, default=0) + 1:02d}"
        if code in existing_codes:
            # reforço: só anexa photo_refs na existente
            for p in paths:
                pc = str(p.get("code") or "").strip().upper()
                if pc == code:
                    refs = list(p.get("photo_refs") or [])
                    for pr in raw.get("photo_refs") or []:
                        try:
                            n = int(pr)
                        except (TypeError, ValueError):
                            continue
                        if n not in refs:
                            refs.append(n)
                    p["photo_refs"] = refs
                    break
            continue
        item = dict(raw)
        item["code"] = code
        paths.append(item)
        existing_codes.add(code)

    out["pathologies"] = paths

    # Anotações leves no photographic_report
    notes_by_num = {
        int(n.get("photo_number") or 0): n
        for n in (wave.get("photo_notes") or [])
        if isinstance(n, dict) and n.get("photo_number") is not None
    }
    photos = []
    for ph in out.get("photographic_report") or []:
        if not isinstance(ph, dict):
            continue
        item = dict(ph)
        try:
            num = int(item.get("photo_number") or 0)
        except (TypeError, ValueError):
            num = 0
        note = notes_by_num.get(num)
        if note:
            if note.get("severity") and not item.get("severity"):
                item["severity"] = note["severity"]
            refs = list(item.get("pathology_refs") or [])
            for r in note.get("pathology_refs") or []:
                rs = str(r).strip()
                if rs and rs not in refs:
                    refs.append(rs)
            item["pathology_refs"] = refs
            if note.get("element_hint") and not item.get("element_id"):
                item["element_hint"] = note["element_hint"]
        photos.append(item)
    if photos:
        out["photographic_report"] = photos
    return out


def build_coverage_stats(
    *,
    total: int,
    sampled: list[int],
    coverage_batches: list[list[int]],
) -> dict[str, Any]:
    covered = set(sampled)
    for b in coverage_batches:
        covered.update(b)
    return {
        "total_photos": total,
        "diagnostic_sample": len(sampled),
        "diagnostic_indices": list(sampled),
        "coverage_batches": len(coverage_batches),
        "coverage_photos": sum(len(b) for b in coverage_batches),
        "fully_covered": len(covered) >= total and total > 0,
        "strategy": "stratified+waves" if coverage_batches else "stratified_or_full",
    }
