"""OF4 — Gemini P1/P2 OrçaFacil (modelo 3.6, exemplo estruturado, prompt do usuário)."""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any, Callable

logger = logging.getLogger(__name__)

ProgressCb = Callable[[str, int, str], None]

# Modelo obrigatório OrçaFacil (pedido do produto)
ORCA_FACIL_GEMINI_MODEL = "gemini-3.6-flash"


def resolve_orca_facil_model() -> str:
    """Sempre preferir 3.6; permite override só via ORCA_FACIL_GEMINI_MODEL."""
    override = (os.getenv("ORCA_FACIL_GEMINI_MODEL") or "").strip()
    if override:
        return override
    from core.inspection_report.gemini_client import resolve_gemini_model

    model = resolve_gemini_model()
    # Se env global apontar para algo sem 3.6, força 3.6-flash
    if "3.6" not in (model or ""):
        logger.warning("GEMINI_MODEL=%s sem 3.6 — OrçaFacil força %s", model, ORCA_FACIL_GEMINI_MODEL)
        return ORCA_FACIL_GEMINI_MODEL
    return model or ORCA_FACIL_GEMINI_MODEL


def _extract_json(text: str) -> dict[str, Any]:
    from core.inspection_report.gemini_client import _extract_json as _ex

    return _ex(text)


def _mime_for(path: Path) -> str:
    suffix = path.suffix.lower()
    return {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
        ".gif": "image/gif",
        ".pdf": "application/pdf",
        ".tif": "image/tiff",
        ".tiff": "image/tiff",
    }.get(suffix, "application/octet-stream")


def _call_multimodal_json(
    *,
    instruction: str,
    file_paths: list[Path],
    temperature: float = 0.2,
    max_output_tokens: int = 32768,
) -> dict[str, Any]:
    from core.inspection_report.gemini_client import resolve_gemini_api_key

    api_key = resolve_gemini_api_key()
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY não configurada")

    from google import genai
    from google.genai import types

    client = genai.Client(api_key=api_key)
    model = resolve_orca_facil_model()
    logger.info("OrçaFacil Gemini model=%s files=%s", model, [p.name for p in file_paths])

    parts: list[Any] = [instruction]
    for path in file_paths:
        if not path.is_file():
            continue
        mime = _mime_for(path)
        if mime == "application/octet-stream":
            continue
        try:
            data = path.read_bytes()
            if len(data) > 18_000_000:
                logger.warning("Arquivo grande ignorado no Gemini: %s", path.name)
                continue
            parts.append(types.Part.from_bytes(data=data, mime_type=mime))
        except Exception as exc:
            logger.warning("Falha ao anexar %s: %s", path, exc)

    response = client.models.generate_content(
        model=model,
        contents=parts,
        config=types.GenerateContentConfig(
            temperature=temperature,
            max_output_tokens=max_output_tokens,
            response_mime_type="application/json",
        ),
    )
    text = getattr(response, "text", None) or ""
    if not text and getattr(response, "candidates", None):
        try:
            text = response.candidates[0].content.parts[0].text
        except Exception:
            text = ""
    return _extract_json(text)


def run_p1_project_info(
    *,
    prancha_paths: list[Path],
    foto_paths: list[Path],
    premissas: dict[str, Any],
    user_prompt: str = "",
    progress: ProgressCb | None = None,
) -> dict[str, Any]:
    if progress:
        progress("vision_project_info", 25, "Lendo pranchas e fotos (Gemini 3.6 P1)…")

    files = [p for p in (list(prancha_paths) + list(foto_paths)) if p.is_file()][:12]
    user_block = (user_prompt or "").strip()
    prompt = f"""Você é engenheiro orçamentista SEMINF/PPD (Gemini 3.6).
Analise as pranchas/PDF e fotos anexadas e EXTRAIA dados da obra com máximo de precisão.

INSTRUÇÕES ADICIONAIS DO ENGENHEIRO (prioridade alta):
{user_block or "(nenhuma)"}

Premissas do formulário (fallback se a prancha não trouxer):
{json.dumps(premissas, ensure_ascii=False)}

Responda APENAS JSON:
{{
  "project_info": {{
    "projeto": "tipologia curta (ex: CONTENÇÕES)",
    "objeto": "objeto completo da obra",
    "local": "endereço / localidade",
    "endereco": "mesmo ou mais específico",
    "orcamento": "título curto do orçamento",
    "processo": "nº processo se legível senão null",
    "obra_type": "ED|RF|FIE|…"
  }},
  "quantities": [
    {{
      "key": "corte|aterro|gabiao|tc600|cc6030|n_cx|area_interv|…",
      "value": 0,
      "unit": "m3|m|un|m2",
      "source_sheet": "FL01",
      "evidence": "citação da legenda/cota",
      "confidence": 0.0
    }}
  ]
}}

Regras:
- Prefira valores lidos nas pranchas (legendas de volume, comprimentos, contagens).
- Campos ilegíveis → null (não inventar endereço).
- Se o engenheiro descreveu quantitativos no prompt, use-os com evidence="prompt_usuario".
"""
    try:
        data = _call_multimodal_json(instruction=prompt, file_paths=files, temperature=0.15)
    except Exception as exc:
        logger.warning("Gemini P1 falhou: %s", exc)
        data = {
            "project_info": {
                "projeto": "",
                "objeto": "",
                "local": "",
                "endereco": "",
                "orcamento": "",
                "processo": None,
                "obra_type": premissas.get("obra_type") or "ED",
            },
            "quantities": [],
            "fallback": True,
            "error": str(exc),
        }
    if not isinstance(data.get("project_info"), dict):
        data["project_info"] = {}
    if not isinstance(data.get("quantities"), list):
        data["quantities"] = []
    data["gemini_model"] = resolve_orca_facil_model()
    return data


def run_p2_plan(
    *,
    etapas_seed: list[dict[str, Any]],
    project_info: dict[str, Any],
    quantities: list[dict[str, Any]],
    premissas: dict[str, Any],
    base_sample: list[dict[str, str]],
    example_tree: dict[str, Any] | None = None,
    example_mapped: dict[str, Any] | None = None,
    user_prompt: str = "",
    prancha_paths: list[Path] | None = None,
    search_fn: Callable[[str, int], list[dict[str, Any]]] | None = None,
    progress: ProgressCb | None = None,
) -> dict[str, Any]:
    if progress:
        progress("plan", 45, "Planejando composições (Gemini 3.6 P2 + exemplo)…")

    catalog_hints: dict[str, list[dict[str, Any]]] = {}
    if search_fn:
        for etapa in etapas_seed:
            name = str(etapa.get("name") or "")
            if not name:
                continue
            # buscas mais ricas por etapa
            queries = [name]
            low = name.lower()
            if "admin" in low:
                queries += ["engenheiro civil obra", "encarregado geral", "vigia", "topografo"]
            if "preliminar" in low:
                queries += ["placa obra", "tapume", "container", "limpeza mecanizada", "sondagem"]
            if "terra" in low:
                queries += ["escavacao", "aterro compactacao", "transporte caminhao", "espalhamento"]
            if "dren" in low:
                queries += [
                    "tubo concreto 600",
                    "canaleta concreto grelha",
                    "106012",
                    "poco visita drenagem",
                    "dissipador energia DED",
                    "tampa poco visita",
                ]
            if "conten" in low or "gabi" in low:
                queries += [
                    "muro gabiao",
                    "geotextil",
                    "102713",
                    "concretagem sapata corrida",
                    "104924",
                    "forma sapata corrida",
                    "104928",
                    "armacao ca 50 sapata",
                    "104918",
                ]
            if "paisag" in low:
                queries += ["grama batatais", "terra vegetal"]
            if "final" in low:
                queries += ["limpeza final", "remocao tapume"]
            hits_all: list[dict[str, Any]] = []
            seen: set[str] = set()
            for q in queries:
                for h in search_fn(q, 4):
                    c = str(h.get("code") or "")
                    if c and c not in seen:
                        seen.add(c)
                        hits_all.append(h)
            catalog_hints[name] = hits_all[:10]

    user_block = (user_prompt or "").strip()
    ex_json = json.dumps(example_mapped or example_tree or {"stages": []}, ensure_ascii=False)[:14000]

    # Códigos preferidos CONT_DREN / SEMINF (quando existirem na base do modelo)
    preferred_codes = {
        "DRENAGEM": [
            {"code": "92212", "papel": "tubo concreto Ø600"},
            {"code": "100091.3.9.SEMINF", "papel": "poço de visita / CX"},
            {"code": "106012", "papel": "canaleta concreto com grelha (preferir este, não substitutos genéricos)"},
            {"code": "106970.5.9.SEMINF", "papel": "dissipador DED"},
            {"code": "103753.3.9.SEMINF", "papel": "tampa PV"},
        ],
        "CONTENÇÃO / CONTENÇÕES": [
            {"code": "92743", "papel": "muro de gabião"},
            {"code": "102713", "papel": "geotêxtil / manta"},
            {"code": "104924", "papel": "concretagem sapata corrida fck 30"},
            {"code": "104928", "papel": "fôrma sapata corrida"},
            {"code": "104918", "papel": "armação CA-50 sapata"},
        ],
    }

    prompt = f"""Você é engenheiro orçamentista SEMINF (Gemini 3.6).
Monte a árvore COMPLETA de orçamento — códigos da BASE DO MODELO + memória detalhada.

INSTRUÇÕES DO ENGENHEIRO (OBRIGATÓRIO seguir):
{user_block or "(nenhuma instrução extra)"}

Cabeçalho da obra:
{json.dumps(project_info, ensure_ascii=False)}

Quantitativos do projeto (pranchas/OCR/prompt):
{json.dumps(quantities, ensure_ascii=False)}

Premissas:
{json.dumps(premissas, ensure_ascii=False)}

Etapas seed (use ESTAS etapas; preencha muitas composições DENTRO):
{json.dumps(etapas_seed, ensure_ascii=False)}

PLANILHA EXEMPLO (few-shot OBRIGATÓRIO — espelhe a DENSIDADE e TIPOS de serviço por etapa;
depois escolha códigos na BASE DO MODELO; se o exemplo tiver código que existe na base, reutilize):
{ex_json}

CÓDIGOS PREFERIDOS (CONT_DREN / SEMINF) — se existirem na base do modelo, USE-OS
(não troque por sinônimos genéricos quando estes códigos cobrem o serviço):
{json.dumps(preferred_codes, ensure_ascii=False)}

Amostra / catálogo da base do modelo:
{json.dumps(base_sample, ensure_ascii=False)}

Sugestões search_base por etapa:
{json.dumps(catalog_hints, ensure_ascii=False)}

Responda APENAS JSON:
{{
  "stages": [
    {{
      "name": "NOME DA ETAPA",
      "subetapas": [],
      "items": [
        {{
          "code": "código da base do modelo",
          "description": "descrição curta",
          "unit": "M3",
          "qty": 0,
          "qty_basis": "origem",
          "memory": "Título\\nConforme Prancha…\\nConta explícita…\\nTotal = X UN",
          "needs_match": false,
          "confidence": 0.0
        }}
      ]
    }}
  ]
}}

Regras:
1. NÃO inventar PU. Código deve existir na base do modelo quando possível.
2. Memória detalhada obrigatória (título + evidência + conta + Total).
3. Completeza: tipicamente 30–45 serviços no total para contenção+drenagem.
4. USE a planilha exemplo: se o exemplo tem 5 serviços em DRENAGEM, a sua etapa DRENAGEM
   deve ter densidade similar (não 1 serviço).
5. Admin: engenheiro, encarregado, vigia, topógrafo, auxiliar…
6. Preliminares: placa, tapume, containers, ligação água/energia, limpeza, transporte entulho, ensaios…
7. Terra: corte, espalhamento, jazida, carga, transporte DMT, compactação…
8. Drenagem: TC Ø600 (92212), CX/PV (100091…), canaleta COM GRELHA (106012 — obrigatório se na base),
   dissipador (106970…), tampa (103753…). NÃO substituir 106012 por outros códigos de canaleta
   se 106012 existir na base.
9. Contenção: gabião (92743), geotêxtil (102713), kit sapata corrida (104924 + 104928 + 104918)
   quando a base tiver esses códigos — não inventar kit alternativo sem necessidade.
10. Paisagismo: terra vegetal + grama; Finais: remoção tapume + limpeza.
11. Quantitativos: preferir volumes/áreas das pranchas (ex.: área intervenção, grama); não reduzir
    arbitrariamente áreas de paisagismo/contenção se a prancha/premissa indicar valor maior.
12. Siga o prompt do engenheiro acima com prioridade.
"""
    files = [p for p in (prancha_paths or []) if p.is_file()][:6]
    try:
        data = _call_multimodal_json(
            instruction=prompt,
            file_paths=files,
            temperature=0.12,
            max_output_tokens=49152,
        )
    except Exception as exc:
        logger.warning("Gemini P2 falhou: %s — usando exemplo mapeado / heurística", exc)
        data = _plan_from_example_or_heuristic(
            etapas_seed, quantities, premissas, search_fn, example_mapped
        )
        data["fallback"] = True
        data["error"] = str(exc)

    if not isinstance(data.get("stages"), list) or not data["stages"]:
        data = _plan_from_example_or_heuristic(
            etapas_seed, quantities, premissas, search_fn, example_mapped
        )
        data["repaired"] = True
    data["gemini_model"] = resolve_orca_facil_model()
    return data


def _plan_from_example_or_heuristic(
    etapas_seed: list[dict[str, Any]],
    quantities: list[dict[str, Any]],
    premissas: dict[str, Any],
    search_fn: Callable[[str, int], list[dict[str, Any]]] | None,
    example_mapped: dict[str, Any] | None,
) -> dict[str, Any]:
    """Se Gemini falhar: usa exemplo mapeado; senão heurística pobre."""
    if example_mapped and example_mapped.get("stages"):
        # alinhar nomes de etapa ao seed
        by_name = {str(s.get("name") or "").upper(): s for s in example_mapped["stages"]}
        stages = []
        for seed in etapas_seed:
            name = str(seed.get("name") or "").strip()
            src = by_name.get(name.upper())
            if not src:
                # fuzzy contains
                for k, v in by_name.items():
                    if name.upper() in k or k in name.upper():
                        src = v
                        break
            items = []
            for it in (src or {}).get("items") or []:
                code = it.get("code")
                if not code:
                    continue
                qty = it.get("qty") or 1
                unit = it.get("unit") or "UN"
                desc = it.get("description") or code
                memory = (
                    f"{desc}\n"
                    f"Conforme planilha exemplo (fallback)\n"
                    f"Qtd = {qty} {unit}\n"
                    f"Total = {qty} {unit}"
                )
                items.append(
                    {
                        "code": code,
                        "description": desc,
                        "unit": unit,
                        "qty": qty,
                        "qty_basis": "exemplo",
                        "memory": memory,
                        "needs_match": bool(it.get("needs_match")),
                        "confidence": 0.55,
                    }
                )
            if not items and search_fn:
                for h in search_fn(name, 3)[:2]:
                    items.append(
                        {
                            "code": h.get("code"),
                            "description": h.get("description"),
                            "unit": h.get("unit") or "UN",
                            "qty": float(premissas.get("prazo_meses") or 1),
                            "qty_basis": "heuristica",
                            "memory": f"{h.get('description')}\\nFallback\\nTotal = 1",
                            "needs_match": False,
                            "confidence": 0.2,
                        }
                    )
            stages.append({"name": name, "subetapas": [], "items": items})
        return {"stages": stages, "source": "example_mapped"}

    # heurística mínima
    stages = []
    prazo = float(premissas.get("prazo_meses") or 6)
    for etapa in etapas_seed:
        name = str(etapa.get("name") or "ETAPA").strip()
        items = []
        for h in (search_fn(name, 3) if search_fn else [])[:2]:
            items.append(
                {
                    "code": h.get("code"),
                    "description": h.get("description"),
                    "unit": h.get("unit") or "UN",
                    "qty": prazo,
                    "qty_basis": "heuristica",
                    "memory": f"{h.get('description')}\\nHeurística\\nTotal = {prazo}",
                    "needs_match": False,
                    "confidence": 0.2,
                }
            )
        stages.append({"name": name, "subetapas": [], "items": items})
    return {"stages": stages, "source": "heuristic"}
