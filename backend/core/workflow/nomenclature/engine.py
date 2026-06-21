"""Motor de nomenclatura — padrão {DISC}-FL{nn}-{TIPO}-{DESC}-{REV}."""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path
from typing import Any

from core.workflow.nomenclature.standards import (
    DISCIPLINE_CODES,
    DOCUMENT_FOLDERS,
    DRAWING_TYPE_LABELS,
    NATIVES_FOLDER,
    SHEET_FOLDER,
)

_SLUG_RE = re.compile(r"[^\w\-]+", re.UNICODE)
_REV_SUFFIX_RE = re.compile(r"[\s_\-]?r(\d{2})\b", re.I)
_FOLHA_RE = re.compile(r"fl[\s_\-]?(\d{2})", re.I)


def slugify(text: str, *, max_len: int = 40) -> str:
    normalized = unicodedata.normalize("NFKD", text)
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    cleaned = _SLUG_RE.sub("-", ascii_text.upper().strip())
    cleaned = re.sub(r"-+", "-", cleaned).strip("-")
    return cleaned[:max_len] or "DESENHO"


def discipline_code(disciplina: str | None) -> str:
    key = (disciplina or "geral").lower()
    return DISCIPLINE_CODES.get(key, key[:3].upper() if key else "GER")


def drawing_type_label(classificacao: str, subtipo: str | None = None) -> str:
    for candidate in (classificacao, subtipo or ""):
        key = candidate.lower().replace("-", "_")
        if key in DRAWING_TYPE_LABELS:
            return DRAWING_TYPE_LABELS[key]
        for rule_key, label in DRAWING_TYPE_LABELS.items():
            if rule_key in key:
                return label
    return "DESENHO"


def extract_revision(filename: str, default: str = "R00") -> str:
    match = _REV_SUFFIX_RE.search(filename)
    if match:
        return f"R{match.group(1)}"
    return default


def extract_folha_hint(filename: str) -> int | None:
    match = _FOLHA_RE.search(filename)
    if match:
        return int(match.group(1))
    return None


def build_drawing_code(
    *,
    disciplina: str,
    folha: int,
    tipo: str,
    descricao: str,
    revisao: str,
) -> str:
    disc = discipline_code(disciplina)
    tipo_seg = slugify(tipo, max_len=20)
    desc_seg = slugify(descricao, max_len=30)
    rev = revisao.upper().replace("REV", "R") if revisao.upper().startswith("REV") else revisao.upper()
    if not rev.startswith("R"):
        rev = f"R{rev}"
    parts = [disc, f"FL{folha:02d}", tipo_seg]
    if desc_seg and desc_seg not in (tipo_seg, "DESENHO"):
        parts.append(desc_seg)
    parts.append(rev)
    return "-".join(parts)


def destination_folder(
    *,
    role: str,
    disciplina: str,
    subtipo: str | None = None,
) -> str:
    if role == "prancha":
        return f"{SHEET_FOLDER}/{discipline_code(disciplina)}"
    if role == "nativo":
        return f"{NATIVES_FOLDER}/{discipline_code(disciplina)}"
    sub = (subtipo or "documento_tecnico").lower()
    folder = DOCUMENT_FOLDERS.get(sub, "05_RELATORIOS")
    return folder


def infer_description(filename: str, classificacao: str) -> str:
    stem = Path(filename).stem
    lower = stem.lower()
    for token in (
        "planta", "corte", "fachada", "detalhe", "fundacao", "forma",
        "terreo", "térreo", "cobertura", "subsolo", "pavimento",
    ):
        if token in lower:
            return slugify(token, max_len=24)
    if classificacao and classificacao != "desenho_tecnico":
        return slugify(classificacao.replace("_", " "), max_len=24)
    return slugify(stem, max_len=24)


def propose_item_nomenclature(
    *,
    filename: str,
    role: str,
    disciplina: str,
    classificacao: str,
    subtipo: str | None,
    folha: int,
    revisao_emissao: str,
    titulo: str | None = None,
) -> dict[str, Any]:
    rev_doc = extract_revision(filename, default=revisao_emissao.replace("REV", "R"))
    tipo = drawing_type_label(classificacao, subtipo)
    desc = infer_description(filename, classificacao)
    codigo = build_drawing_code(
        disciplina=disciplina,
        folha=folha,
        tipo=tipo,
        descricao=desc,
        revisao=rev_doc if role == "prancha" else revisao_emissao.replace("REV", "R"),
    )
    pasta = destination_folder(role=role, disciplina=disciplina, subtipo=subtipo)
    ext = Path(filename).suffix.lower()
    arquivo_final = f"{codigo}{ext or '.pdf'}"

    return {
        "codigo_sugerido": codigo,
        "codigo_aprovado": codigo,
        "arquivo_final": arquivo_final,
        "folha_numero": folha,
        "tipo_desenho": tipo,
        "titulo": titulo or Path(filename).stem,
        "descricao": desc,
        "revisao_documento": rev_doc,
        "pasta_destino": pasta,
        "disciplina_codigo": discipline_code(disciplina),
    }
