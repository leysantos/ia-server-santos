"""L16 — Resultados medidos de ensaios instrumentados (pós-campo/laboratório)."""

from __future__ import annotations

import re
import uuid
from datetime import date, datetime
from typing import Any

STATUS_VALUES = frozenset({"executado", "pendente", "cancelado"})

ASSAY_RESULT_FIELDS = (
    "id",
    "test_code",
    "ensaio",
    "local",
    "valor",
    "unidade",
    "valor_nominal",
    "data_ensaio",
    "laboratorio",
    "responsavel",
    "conclusao",
    "pathology_refs",
    "norma_ref",
    "status",
    "observacoes",
    "created_at",
    "updated_at",
)


def _now_iso() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


def _parse_date(value: Any) -> str | None:
    if value is None or value == "":
        return None
    s = str(value).strip()
    if re.match(r"^\d{4}-\d{2}-\d{2}$", s):
        return s
    for fmt in ("%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(s, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def _norm_pathology_refs(raw: Any) -> list[str]:
    if not raw:
        return []
    if isinstance(raw, str):
        parts = re.split(r"[,;\s]+", raw.strip())
    elif isinstance(raw, list):
        parts = [str(x) for x in raw]
    else:
        return []
    out: list[str] = []
    seen: set[str] = set()
    for p in parts:
        code = str(p).strip().upper()
        if not code:
            continue
        if not re.match(r"^P\d+$", code, re.I):
            m = re.search(r"(P\d+)", code, re.I)
            code = m.group(1).upper() if m else code
        if code not in seen:
            seen.add(code)
            out.append(code)
    return out


def normalize_assay_result(raw: dict[str, Any] | None, *, existing_id: str | None = None) -> dict[str, Any]:
    """Normaliza um registro L16."""
    data = dict(raw or {})
    rid = str(data.get("id") or existing_id or uuid.uuid4())
    status = str(data.get("status") or "executado").strip().lower()
    if status not in STATUS_VALUES:
        status = "executado"

    test_code = str(data.get("test_code") or data.get("codigo") or "").strip().upper()
    ensaio = str(data.get("ensaio") or data.get("name") or "").strip()
    valor = str(data.get("valor") or data.get("value") or "").strip()
    unidade = str(data.get("unidade") or data.get("unit") or "").strip()

    created = str(data.get("created_at") or _now_iso())
    updated = _now_iso()

    return {
        "id": rid,
        "test_code": test_code,
        "ensaio": ensaio,
        "local": str(data.get("local") or data.get("location") or "").strip(),
        "valor": valor,
        "unidade": unidade,
        "valor_nominal": str(data.get("valor_nominal") or data.get("nominal") or "").strip() or None,
        "data_ensaio": _parse_date(data.get("data_ensaio") or data.get("date")),
        "laboratorio": str(data.get("laboratorio") or data.get("lab") or "").strip() or None,
        "responsavel": str(data.get("responsavel") or data.get("responsible") or "").strip() or None,
        "conclusao": str(data.get("conclusao") or data.get("conclusion") or "").strip() or None,
        "pathology_refs": _norm_pathology_refs(data.get("pathology_refs")),
        "norma_ref": str(data.get("norma_ref") or "").strip() or None,
        "status": status,
        "observacoes": str(data.get("observacoes") or data.get("notes") or "").strip() or None,
        "created_at": created,
        "updated_at": updated,
    }


def validate_assay_result(item: dict[str, Any]) -> list[str]:
    """Retorna lista de erros de validação (vazia = ok)."""
    errors: list[str] = []
    if not str(item.get("ensaio") or "").strip() and not str(item.get("test_code") or "").strip():
        errors.append("Informe o código ou o nome do ensaio")
    status = str(item.get("status") or "executado")
    if status not in STATUS_VALUES:
        errors.append(f"Status inválido: {status}")
    if status == "executado" and not str(item.get("valor") or "").strip():
        errors.append("Valor medido é obrigatório para ensaio executado")
    d = item.get("data_ensaio")
    if d is not None and d != "" and _parse_date(d) is None:
        errors.append("Data do ensaio inválida (use AAAA-MM-DD ou DD/MM/AAAA)")
    return errors


def validate_assay_results(items: list[dict[str, Any]]) -> list[str]:
    errors: list[str] = []
    seen_ids: set[str] = set()
    for i, raw in enumerate(items):
        if not isinstance(raw, dict):
            errors.append(f"Item {i + 1}: formato inválido")
            continue
        item = normalize_assay_result(raw, existing_id=str(raw.get("id") or "") or None)
        for err in validate_assay_result(item):
            errors.append(f"Item {i + 1}: {err}")
        rid = item["id"]
        if rid in seen_ids:
            errors.append(f"ID duplicado: {rid}")
        seen_ids.add(rid)
    return errors


def list_assay_results(content: dict[str, Any] | None) -> list[dict[str, Any]]:
    raw = (content or {}).get("instrumented_test_results")
    if not isinstance(raw, list):
        return []
    return [normalize_assay_result(x) for x in raw if isinstance(x, dict)]


def suggested_tests_from_content(content: dict[str, Any] | None) -> list[dict[str, Any]]:
    tests = (content or {}).get("instrumented_tests")
    if not isinstance(tests, list):
        return []
    out: list[dict[str, Any]] = []
    for t in tests:
        if not isinstance(t, dict):
            continue
        code = str(t.get("codigo") or t.get("test_code") or "").strip()
        ensaio = str(t.get("ensaio") or t.get("name") or "").strip()
        if not code and not ensaio:
            continue
        out.append(
            {
                "test_code": code,
                "ensaio": ensaio,
                "norma_ref": t.get("norma_ref"),
                "pathology_refs": t.get("pathology_refs") or [],
                "gravidade_alvo": t.get("gravidade_alvo"),
                "necessidade_pct": t.get("necessidade_pct"),
            }
        )
    return out


def pathologies_from_content(content: dict[str, Any] | None) -> list[dict[str, str]]:
    paths = (content or {}).get("pathologies")
    if not isinstance(paths, list):
        return []
    out: list[dict[str, str]] = []
    for p in paths:
        if not isinstance(p, dict):
            continue
        code = str(p.get("code") or p.get("codigo") or "").strip().upper()
        name = str(p.get("name") or p.get("nome") or "").strip()
        if code or name:
            out.append({"code": code or "—", "name": name or "—"})
    return out


def build_assay_results_view(report: Any) -> dict[str, Any]:
    content = report.content if hasattr(report, "content") else {}
    items = list_assay_results(content)
    suggested = suggested_tests_from_content(content)
    return {
        "items": items,
        "suggested_tests": suggested,
        "pathologies": pathologies_from_content(content),
        "count_executed": sum(1 for i in items if i.get("status") == "executado"),
        "count_total": len(items),
        "report_status": getattr(report, "status", None),
    }


def merge_assay_results(
    content: dict[str, Any],
    items: list[dict[str, Any]],
) -> dict[str, Any]:
    """Persiste lista normalizada em ``content.instrumented_test_results``."""
    normalized = [normalize_assay_result(x) for x in items if isinstance(x, dict)]
    out = dict(content or {})
    out["instrumented_test_results"] = normalized
    out["assay_results_meta"] = {
        "updated_at": _now_iso(),
        "count": len(normalized),
        "count_executed": sum(1 for i in normalized if i.get("status") == "executado"),
    }
    return out


def assay_results_table(results: list[dict[str, Any]]) -> dict[str, Any]:
    executed = [r for r in results if r.get("status") == "executado"]
    shown = executed or results
    rows: list[list[str]] = []
    for r in shown:
        val = str(r.get("valor") or "—")
        unit = str(r.get("unidade") or "").strip()
        if unit and val != "—":
            val = f"{val} {unit}"
        nom = r.get("valor_nominal")
        if nom:
            val += f" (nom. {nom})"
        refs = ", ".join(r.get("pathology_refs") or []) or "—"
        rows.append(
            [
                r.get("test_code") or "—",
                r.get("ensaio") or "—",
                r.get("local") or "—",
                val,
                r.get("data_ensaio") or "—",
                r.get("laboratorio") or r.get("responsavel") or "—",
                r.get("conclusao") or "—",
                refs,
                r.get("norma_ref") or "—",
            ]
        )
    if not rows:
        rows = [["—", "—", "—", "Sem resultados cadastrados", "—", "—", "—", "—", "—"]]
    return {
        "caption": "Resultados de ensaios instrumentados executados (L16)",
        "headers": [
            "Código",
            "Ensaio",
            "Local / elemento",
            "Resultado",
            "Data",
            "Lab. / responsável",
            "Conclusão",
            "Patologias",
            "Norma",
        ],
        "rows": rows,
    }


def pathology_refs_with_executed_results(content: dict[str, Any]) -> set[str]:
    linked: set[str] = set()
    for r in list_assay_results(content):
        if r.get("status") != "executado":
            continue
        if not str(r.get("valor") or "").strip():
            continue
        for ref in r.get("pathology_refs") or []:
            linked.add(str(ref).strip().upper())
    return linked


def apply_assay_results_to_content(content: dict[str, Any]) -> dict[str, Any]:
    """
    Injeta tabela L16 no capítulo de ensaios e atualiza menções em conclusões.
    """
    out = dict(content or {})
    results = list_assay_results(out)
    if not results:
        return out

    table = assay_results_table(results)
    executed_n = sum(1 for r in results if r.get("status") == "executado")

    chapters = list(out.get("chapters") or [])
    found = False
    for ch in chapters:
        if not isinstance(ch, dict):
            continue
        cid = str(ch.get("id") or "").lower()
        title_l = str(ch.get("title") or "").lower()
        if cid != "ensaios_instrumentados" and "ensaios instrumentados" not in title_l:
            continue
        paras = [str(p) for p in (ch.get("paragraphs") or [])]
        intro = (
            f"Foram registrados {executed_n} resultado(s) medido(s) de ensaio(s) instrumentado(s) "
            f"(campanha complementar à vistoria inicial)."
        )
        if not any("resultado(s) medido(s)" in p for p in paras):
            paras.append(intro)
        tables = [
            t
            for t in (ch.get("tables") or [])
            if "resultados de ensaios" not in str(t.get("caption") or "").lower()
        ]
        tables.append(table)
        ch["paragraphs"] = paras
        ch["tables"] = tables
        found = True
        break

    if not found:
        insert_at = len(chapters)
        for i, ch in enumerate(chapters):
            cid = str(ch.get("id") or "").lower()
            if cid in ("conclusao", "referencias", "fotografico", "cronograma", "interdicao"):
                insert_at = i
                break
        chapters.insert(
            insert_at,
            {
                "id": "ensaios_instrumentados",
                "title": "Ensaios instrumentados — resultados",
                "paragraphs": [
                    (
                        f"Resultados medidos de {executed_n} ensaio(s) executado(s) "
                        "(L16 — complemento ao laudo de vistoria)."
                    ),
                ],
                "tables": [table],
                "charts": [],
            },
        )
    out["chapters"] = chapters

    if executed_n:
        note = (
            f"Campanha de ensaios instrumentados: {executed_n} resultado(s) medido(s) "
            f"registrado(s) — ver tabela L16 no capítulo de ensaios."
        )
        conclusions = list(out.get("conclusions") or [])
        if not any("resultado(s) medido(s)" in str(c).lower() for c in conclusions):
            conclusions.append(note)
        out["conclusions"] = conclusions

    return out


def enrich_test_from_suggestion(
    suggestion: dict[str, Any],
    *,
    local: str = "",
) -> dict[str, Any]:
    """Pré-preenche formulário a partir de ensaio sugerido."""
    return normalize_assay_result(
        {
            "test_code": suggestion.get("test_code") or suggestion.get("codigo"),
            "ensaio": suggestion.get("ensaio"),
            "norma_ref": suggestion.get("norma_ref"),
            "pathology_refs": suggestion.get("pathology_refs") or [],
            "local": local,
            "status": "executado",
        }
    )
