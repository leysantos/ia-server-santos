"""Roteamento de modelo LLM com base nos anexos (modo auto)."""

from __future__ import annotations

from pathlib import Path

from core.project_review.vision_analysis_service import IMAGE_SUFFIXES, is_visual_file

# Extensões tratadas como engenharia / BIM / CAD
_CAD_BIM_SUFFIXES = frozenset({".dxf", ".dwg", ".ifc"})

# Planilhas e dados tabulares
_SPREADSHEET_SUFFIXES = frozenset({".xlsx", ".xls", ".csv"})

# Código / configuração
_CODE_SUFFIXES = frozenset({
    ".py", ".js", ".ts", ".tsx", ".jsx", ".java", ".go", ".rs", ".cpp", ".c", ".h",
    ".sql", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".xml", ".html", ".css", ".sh",
})

_VISION_MODEL_CANDIDATES = ("gemma3:12b", "gemma4:latest", "gemma3:latest")
_CODER_MODEL_CANDIDATES = ("qwen3-coder", "qwen2.5-coder", "deepseek-coder")
_ENGINEERING_MODEL_CANDIDATES = ("qwen3:14b", "gemma4:latest", "qwen3:8b", "mistral:7b")
_REASONING_MODEL_CANDIDATES = ("deepseek-r1:14b", "qwen3:14b", "gemma4:latest")


def _pick_installed(candidates: tuple[str, ...], installed: set[str]) -> str | None:
    if not installed:
        return candidates[0] if candidates else None
    for candidate in candidates:
        if candidate in installed:
            return candidate
        base = candidate.split(":")[0]
        for name in installed:
            if name == candidate or name.startswith(f"{base}:"):
                return name
    return None


def resolve_auto_llm_model_for_attachments(
    paths: list[Path],
    *,
    installed_models: set[str] | None = None,
    user_text: str = "",
) -> str | None:
    """
    Escolhe modelo quando o usuário deixou modo Auto.
    Prioridade: visão > CAD/BIM > código > planilha > reasoning (PDF longo).
    """
    if not paths:
        return None

    installed = installed_models or set()
    suffixes = {p.suffix.lower() for p in paths}
    names = " ".join(p.name.lower() for p in paths)
    combined = f"{user_text} {names}".lower()

    has_visual = any(is_visual_file(p) for p in paths) or bool(suffixes & {".pdf"})
    has_cad = bool(suffixes & _CAD_BIM_SUFFIXES)
    has_code = bool(suffixes & _CODE_SUFFIXES)
    has_sheet = bool(suffixes & _SPREADSHEET_SUFFIXES)

    if has_visual:
        return _pick_installed(_VISION_MODEL_CANDIDATES, installed)

    if has_cad or any(k in combined for k in ("estrutural", "planta", "fundacao", "fundação", "ifc", "dxf", "dwg")):
        return _pick_installed(_ENGINEERING_MODEL_CANDIDATES, installed)

    if has_code or any(k in combined for k in ("código", "codigo", "script", "api", "bug", "função", "funcao")):
        return _pick_installed(_CODER_MODEL_CANDIDATES, installed)

    if has_sheet or any(k in combined for k in ("orçamento", "orcamento", "planilha", "sinapi", "cpu", "custo")):
        return _pick_installed(_ENGINEERING_MODEL_CANDIDATES, installed)

    if any(s in suffixes for s in (".pdf", ".docx")) and len(paths) >= 2:
        return _pick_installed(_REASONING_MODEL_CANDIDATES, installed)

    # Imagens sem pipeline visual explícito
    if suffixes & IMAGE_SUFFIXES:
        return _pick_installed(_VISION_MODEL_CANDIDATES, installed)

    return None
