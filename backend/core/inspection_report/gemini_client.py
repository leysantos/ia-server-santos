"""Cliente Gemini para geração multimodal de laudos (análise detalhada de imagens)."""

from __future__ import annotations

import io
import json
import logging
import os
import re
from pathlib import Path
from typing import Any, Callable

logger = logging.getLogger(__name__)

ProgressCb = Callable[[str, int, str], None]

# Diagnóstico: amostra de imagens na 1ª passagem; legendas em lotes na 2ª.
_DIAG_IMAGE_LIMIT = 16
_PHOTO_BATCH_SIZE = 8
_IMAGE_MAX_SIDE = 1600


def resolve_gemini_model() -> str:
    from config.settings import get_settings

    settings = get_settings()
    return getattr(settings, "gemini_model", None) or os.getenv(
        "GEMINI_MODEL", "gemini-3.6-flash"
    )


def resolve_gemini_api_key() -> str | None:
    from config.settings import get_settings

    settings = get_settings()
    key = getattr(settings, "gemini_api_key", None) or os.getenv("GEMINI_API_KEY")
    return (key or "").strip() or None


def gemini_available() -> bool:
    return bool(resolve_gemini_api_key())


def _extract_json(text: str) -> dict[str, Any]:
    raw = (text or "").strip()
    if not raw:
        raise ValueError("Resposta vazia do Gemini")
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)

    candidates = [raw]
    match = re.search(r"\{[\s\S]*\}", raw)
    if match:
        candidates.append(match.group(0))

    last_err: Exception | None = None
    for candidate in candidates:
        for attempt in (candidate, _repair_truncated_json(candidate)):
            try:
                data = json.loads(attempt)
                if isinstance(data, dict):
                    return data
            except json.JSONDecodeError as exc:
                last_err = exc
                continue

    preview = raw[:400].replace("\n", " ")
    raise ValueError(f"JSON inválido do Gemini ({last_err}). Prévia: {preview}…")


def _repair_truncated_json(raw: str) -> str:
    """Fecha chaves/colchetes e remove vírgula pendente em JSON truncado."""
    text = raw.strip()
    if not text:
        return text
    text = re.sub(r",\s*$", "", text)
    if text.count('"') % 2 == 1:
        text += '"'
    opens = text.count("{") - text.count("}")
    opens_arr = text.count("[") - text.count("]")
    text = re.sub(r",\s*$", "", text)
    text += "]" * max(0, opens_arr)
    text += "}" * max(0, opens)
    return text


def _mime_for(path: Path) -> str:
    suffix = path.suffix.lower()
    return {
        ".png": "image/png",
        ".webp": "image/webp",
        ".gif": "image/gif",
        ".bmp": "image/bmp",
        ".tif": "image/tiff",
        ".tiff": "image/tiff",
    }.get(suffix, "image/jpeg")


def _prepare_image_bytes(path: Path) -> tuple[bytes, str]:
    """Redimensiona imagens grandes para análise multimodal estável."""
    mime = _mime_for(path)
    raw = path.read_bytes()
    try:
        from PIL import Image

        img = Image.open(io.BytesIO(raw))
        img.load()
        if img.mode not in ("RGB", "L"):
            img = img.convert("RGB")
            mime = "image/jpeg"
        w, h = img.size
        max_side = max(w, h)
        if max_side > _IMAGE_MAX_SIDE:
            scale = _IMAGE_MAX_SIDE / max_side
            img = img.resize((max(1, int(w * scale)), max(1, int(h * scale))), Image.Resampling.LANCZOS)
        buf = io.BytesIO()
        if mime == "image/png":
            img.save(buf, format="PNG", optimize=True)
        else:
            mime = "image/jpeg"
            img.save(buf, format="JPEG", quality=85, optimize=True)
        return buf.getvalue(), mime
    except Exception as exc:
        logger.debug("Sem redimensionamento para %s: %s", path.name, exc)
        return raw, mime


def _sample_indices(n: int, limit: int) -> list[int]:
    if n <= limit:
        return list(range(n))
    # Amostra uniforme incluindo primeira e última
    step = (n - 1) / (limit - 1)
    idxs = sorted({min(n - 1, int(round(i * step))) for i in range(limit)})
    return idxs


def _call_gemini_json(
    *,
    client: Any,
    types: Any,
    model: str,
    instruction: str,
    image_paths: list[Path],
    temperature: float = 0.2,
    max_output_tokens: int = 24576,
) -> dict[str, Any]:
    parts: list[Any] = [instruction]
    for path in image_paths:
        try:
            data, mime = _prepare_image_bytes(path)
            parts.append(types.Part.from_bytes(data=data, mime_type=mime))
        except Exception as exc:
            logger.warning("Falha ao anexar imagem %s: %s", path, exc)

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


def _photo_caption_prompt(
    *,
    company_source: str,
    objeto: str,
    photo_meta_batch: list[dict[str, Any]],
) -> str:
    photos_block = "\n".join(
        f"- Foto {p.get('photo_number'):02d}: arquivo={p.get('filename')} "
        f"orientação={p.get('orientation') or 'n/d'} legenda_usuario={p.get('caption') or '—'}"
        for p in photo_meta_batch
    )
    return f"""Você é engenheiro civil elaborando o RELATÓRIO FOTOGRÁFICO de um laudo técnico
(estilo SEMINF / NBR 9452). Analise CADA imagem anexada com atenção.

Objeto da vistoria: {objeto or 'obra vistoriada'}
Fonte padrão: {company_source}

FOTOS DESTE LOTE (produza entrada para TODAS):
{photos_block}

Para cada foto, descreva o que REALMENTE aparece na imagem (elementos, danos, entorno).
Proibido descrição genérica ("Registro fotográfico da vistoria").

Responda APENAS JSON:
{{
  "photographic_report": [
    {{
      "photo_number": 1,
      "filename": "...",
      "title": "título específico da anomalia/vista",
      "description": "3 a 6 frases técnicas detalhadas",
      "legend": "{objeto or 'Objeto'} – Elemento | Patologia: … | Gravidade: CRÍTICA|ALTA|MÉDIA|BAIXA | Score: n/5 (pct%)",
      "severity": "crítica|alta|média|baixa",
      "score": 5,
      "source": "{company_source}",
      "pathology_refs": []
    }}
  ]
}}
"""


def generate_laudo_content(
    *,
    system_prompt: str,
    user_prompt: str,
    document_excerpts: list[str],
    knowledge_context: str,
    image_paths: list[Path],
    photo_meta: list[dict[str, Any]],
    company_source: str,
    chapters: list[dict],
    progress_cb: ProgressCb | None = None,
    georef_path: Path | None = None,
    georef_meta: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], str]:
    """
    Gera conteúdo estruturado do laudo via Gemini multimodal.
    Passagem 1: laudo + amostra de imagens (+ georref se houver).
    Passagem 2: legendas detalhadas em lotes para todas as fotos.
    Retorna (content_dict, model_used).
    """
    api_key = resolve_gemini_api_key()
    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY não configurada. Defina a chave no ambiente ou em Settings."
        )

    model = resolve_gemini_model()
    try:
        from google import genai
        from google.genai import types
    except ImportError as exc:
        raise RuntimeError(
            "Pacote google-genai não instalado. Execute: pip install google-genai"
        ) from exc

    client = genai.Client(api_key=api_key)

    def _progress(phase: str, percent: int, message: str) -> None:
        if progress_cb:
            progress_cb(phase, percent, message)

    chapter_list = "\n".join(
        f"- {c.get('id')}: {c.get('title')}" for c in (chapters or [])
    )
    all_photos_block = "\n".join(
        f"- Foto {p.get('photo_number'):02d}: arquivo={p.get('filename')} "
        f"orientação={p.get('orientation') or 'n/d'} legenda_usuario={p.get('caption') or '—'}"
        for p in photo_meta
    ) or "(nenhuma foto)"

    docs_block = (
        "\n\n---\n\n".join(document_excerpts[:12]) if document_excerpts else "(sem textos anexos)"
    )
    kb_block = knowledge_context.strip() or "(base de conhecimento não consultada)"

    n_images = len(image_paths)
    diag_idxs = _sample_indices(n_images, _DIAG_IMAGE_LIMIT) if n_images else []
    diag_paths = [image_paths[i] for i in diag_idxs]
    diag_meta = []
    if photo_meta and diag_idxs:
        for i in diag_idxs:
            if i < len(photo_meta):
                diag_meta.append(photo_meta[i])
    elif photo_meta:
        diag_meta = photo_meta[:_DIAG_IMAGE_LIMIT]

    # L4 — georref na passagem 1 (localização), fora do inventário fotográfico
    georef_block = "(sem imagem georreferenciada)"
    if georef_path and georef_path.exists():
        meta = georef_meta or {}
        lat = meta.get("latitude")
        lon = meta.get("longitude")
        label = meta.get("label") or meta.get("caption") or georef_path.name
        coords = (
            f"lat={lat}, lon={lon}"
            if lat is not None and lon is not None
            else "coordenadas não disponíveis no EXIF"
        )
        georef_block = (
            f"Arquivo={meta.get('filename') or georef_path.name}; "
            f"rótulo={label}; {coords}. "
            "Use esta imagem para situar o objeto no terreno e preencher local/coordenadas "
            "na ficha. NÃO inclua esta imagem no photographic_report."
        )
        diag_paths = [georef_path] + diag_paths

    diag_photos_block = "\n".join(
        f"- Foto {p.get('photo_number'):02d}: arquivo={p.get('filename')} "
        f"orientação={p.get('orientation') or 'n/d'} legenda_usuario={p.get('caption') or '—'}"
        for p in diag_meta
    ) or "(nenhuma foto nesta passagem)"

    instruction = f"""{system_prompt}

CAPÍTULOS OBRIGATÓRIOS DO TEMPLATE:
{chapter_list}

INSTRUÇÕES DO PROFISSIONAL:
{user_prompt or '(não informado)'}

FONTE PADRÃO DAS FOTOS (empresa):
{company_source}

INVENTÁRIO COMPLETO DE FOTOS DO LAUDO ({len(photo_meta)}):
{all_photos_block}

IMAGEM DE LOCALIZAÇÃO / GEORREFERENCIADA:
{georef_block}

IMAGENS ANEXADAS NESTA PASSAGEM (analise com atenção — base do diagnóstico):
{diag_photos_block}

Nesta passagem, preencha photographic_report apenas para as imagens fotográficas
do inventário (não a georref). O diagnóstico textual e as patologias devem
considerar o conjunto observado nestas imagens e a localização.

TRECHOS DE DOCUMENTOS/NORMAS ANEXADOS:
{docs_block}

CONTEXTO DA BASE DE CONHECIMENTO (RAG):
{kb_block}
"""

    _progress(
        "gemini",
        55,
        f"Passagem 1/2 — diagnóstico com {len(diag_paths)} imagem(ns) amostrada(s)…",
    )
    content = _call_gemini_json(
        client=client,
        types=types,
        model=model,
        instruction=instruction,
        image_paths=diag_paths,
        max_output_tokens=24576,
    )

    # Passagem 2: legendas detalhadas para todas as fotos
    photo_by_num: dict[int, dict[str, Any]] = {}
    for entry in content.get("photographic_report") or []:
        try:
            photo_by_num[int(entry.get("photo_number") or 0)] = entry
        except (TypeError, ValueError):
            continue

    if image_paths and photo_meta:
        total_batches = max(1, (len(photo_meta) + _PHOTO_BATCH_SIZE - 1) // _PHOTO_BATCH_SIZE)
        objeto = str(content.get("objeto") or content.get("titulo") or "Objeto vistoriado")
        for batch_i in range(0, len(photo_meta), _PHOTO_BATCH_SIZE):
            batch_meta = photo_meta[batch_i : batch_i + _PHOTO_BATCH_SIZE]
            batch_paths: list[Path] = []
            for offset, meta in enumerate(batch_meta):
                global_idx = batch_i + offset
                if global_idx < len(image_paths):
                    batch_paths.append(image_paths[global_idx])
                else:
                    fname = str(meta.get("filename") or "").lower()
                    for p in image_paths:
                        if p.name.lower() == fname:
                            batch_paths.append(p)
                            break

            batch_no = batch_i // _PHOTO_BATCH_SIZE + 1
            pct = 58 + int(22 * batch_no / total_batches)
            _progress(
                "gemini",
                min(80, pct),
                f"Passagem 2/2 — legendas detalhadas lote {batch_no}/{total_batches} "
                f"({len(batch_meta)} foto(s))…",
            )
            try:
                batch_json = _call_gemini_json(
                    client=client,
                    types=types,
                    model=model,
                    instruction=_photo_caption_prompt(
                        company_source=company_source,
                        objeto=objeto,
                        photo_meta_batch=batch_meta,
                    ),
                    image_paths=batch_paths,
                    temperature=0.15,
                    max_output_tokens=12288,
                )
                for entry in batch_json.get("photographic_report") or []:
                    try:
                        num = int(entry.get("photo_number") or 0)
                    except (TypeError, ValueError):
                        continue
                    if num:
                        photo_by_num[num] = entry
            except Exception as exc:
                logger.warning("Falha no lote de legendas %s: %s", batch_no, exc)

    # Garante entrada para cada foto do inventário
    ensured: list[dict[str, Any]] = []
    for meta in photo_meta:
        num = int(meta.get("photo_number") or 0)
        entry = dict(photo_by_num.get(num) or {})
        title = entry.get("title") or meta.get("caption") or f"Registro fotográfico {num:02d}"
        description = entry.get("description") or meta.get("caption") or ""
        if not description or description.lower().startswith("registro fotográfico"):
            description = (
                f"Registro da diligência in loco referente a {meta.get('filename')}. "
                "Recomenda-se revisão humana da legenda técnica com base na imagem original."
            )
        legend = entry.get("legend") or (
            f"{content.get('objeto') or 'Objeto'} – Elemento vistoriado | "
            f"Patologia: a classificar | Gravidade: MÉDIA | Score: 3/5 (60%)"
        )
        ensured.append(
            {
                "photo_number": num,
                "filename": meta.get("filename") or entry.get("filename"),
                "title": title,
                "description": description,
                "legend": legend,
                "severity": entry.get("severity") or "média",
                "score": entry.get("score") or 3,
                "source": entry.get("source") or company_source,
                "pathology_refs": entry.get("pathology_refs") or [],
                "orientation": meta.get("orientation"),
            }
        )
    content["photographic_report"] = ensured

    _progress("gemini", 81, "Análise multimodal concluída — consolidando JSON…")
    return content, model
