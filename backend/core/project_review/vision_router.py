"""VisionRouter — roteamento multimodal para plantas, fotos de obra e laudos."""

from __future__ import annotations

import base64
import io
import json
import logging
from pathlib import Path
from typing import Any

import requests

from config.settings import OLLAMA_BASE_URL, OLLAMA_CONNECT_TIMEOUT
from core.project_review.constants import (
    TECHNICAL_MODEL,
    TECHNICAL_MODEL_FALLBACK,
    VISION_MODEL_FALLBACKS,
    VISION_MODEL_PRIMARY,
)
from core.project_review.vision_prompts import VisionAnalysisMode, prompt_for_mode

logger = logging.getLogger(__name__)

_IMAGE_SUFFIXES = frozenset({".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff", ".heic", ".heif"})
_MAX_IMAGE_DIM = 1536
_MAX_PDF_PAGES = 3


def _model_installed(names: set[str], candidate: str) -> bool:
    if candidate in names:
        return True
    base = candidate.split(":")[0]
    return any(n == candidate or n.startswith(f"{base}:") for n in names)


def _resolve_vision_model_tags(names: set[str]) -> list[str]:
    """Retorna tags exatas instaladas no Ollama, na ordem de preferência."""
    resolved: list[str] = []
    for candidate in (VISION_MODEL_PRIMARY, *VISION_MODEL_FALLBACKS):
        if not _model_installed(names, candidate):
            continue
        exact = next((n for n in names if n == candidate), None)
        if exact:
            resolved.append(exact)
            continue
        base = candidate.split(":")[0]
        partial = sorted(n for n in names if n.startswith(f"{base}:"))
        for tag in partial:
            if tag not in resolved:
                resolved.append(tag)
    return resolved


class VisionRouter:
    """Roteia documentos visuais para modelos multimodais Ollama."""

    def __init__(
        self,
        base_url: str = OLLAMA_BASE_URL,
        connect_timeout: int = OLLAMA_CONNECT_TIMEOUT,
        read_timeout: int = 180,
    ):
        self.base_url = base_url.rstrip("/")
        self.timeouts = (connect_timeout, read_timeout)

    def route_model(self, path: Path, *, task: str = "vision") -> str:
        if task == "technical":
            return TECHNICAL_MODEL
        return VISION_MODEL_PRIMARY

    def should_use_vision(self, path: Path) -> bool:
        ext = path.suffix.lower()
        return ext in _IMAGE_SUFFIXES or ext == ".pdf"

    def check_availability(self) -> dict[str, Any]:
        """Verifica Ollama e modelos VL instalados."""
        try:
            resp = requests.get(f"{self.base_url}/api/tags", timeout=self.timeouts)
            resp.raise_for_status()
            names = {m.get("name", "") for m in resp.json().get("models", [])}
            installed = _resolve_vision_model_tags(names)
            return {
                "available": bool(installed),
                "ollama_reachable": True,
                "models_installed": sorted(names),
                "vision_models_ready": installed,
                "primary": VISION_MODEL_PRIMARY,
                "technical_model": TECHNICAL_MODEL,
            }
        except Exception as exc:
            return {
                "available": False,
                "ollama_reachable": False,
                "error": str(exc),
                "vision_models_ready": [],
                "primary": VISION_MODEL_PRIMARY,
                "technical_model": TECHNICAL_MODEL,
            }

    def analyze_file(
        self,
        path: Path,
        *,
        mode: str = VisionAnalysisMode.PLANTA,
        extra_context: str = "",
    ) -> dict[str, Any]:
        """Analisa arquivo visual e retorna JSON estruturado padronizado."""
        path = Path(path).resolve()
        if not path.is_file():
            raise FileNotFoundError(str(path))

        images = self._prepare_images(path)
        if not images:
            return {"skipped": True, "reason": "no_visual_content", "analysis_mode": mode}

        prompt = prompt_for_mode(mode)
        if extra_context:
            prompt += f"\n\nContexto adicional:\n{extra_context[:2000]}"

        model_used = self.route_model(path)
        raw = self._chat_vision(prompt, images, model=model_used)
        parsed = self._parse_vision_json(raw)
        parsed["analysis_mode"] = mode
        parsed["_model_used"] = model_used
        return parsed

    def analyze_technical(self, context: str) -> tuple[str, str]:
        """Análise textual pós-visão via modelo técnico."""
        from models.ollama_client import OllamaClient

        client = OllamaClient(timeout=90)
        prompt = (
            "Com base no contexto técnico abaixo, produza análise de revisão "
            "com inconsistências, omissões e recomendações.\n\n"
            f"{context[:12000]}"
        )
        return client.generate(
            prompt,
            model=TECHNICAL_MODEL,
            fallback_models=[TECHNICAL_MODEL_FALLBACK],
        )

    def _prepare_images(self, path: Path) -> list[str]:
        ext = path.suffix.lower()
        if ext in _IMAGE_SUFFIXES:
            return [self._encode_image(path)]

        if ext == ".pdf":
            return self._pdf_first_pages(path, max_pages=_MAX_PDF_PAGES)

        return []

    def _encode_image(self, path: Path) -> str:
        raw = path.read_bytes()
        optimized = self._optimize_image_bytes(raw)
        return base64.b64encode(optimized).decode("ascii")

    def _optimize_image_bytes(self, raw: bytes) -> bytes:
        try:
            from PIL import Image
        except ImportError:
            return raw

        try:
            img = Image.open(io.BytesIO(raw))
            if img.mode not in ("RGB", "L"):
                img = img.convert("RGB")
            w, h = img.size
            longest = max(w, h)
            if longest > _MAX_IMAGE_DIM:
                scale = _MAX_IMAGE_DIM / longest
                img = img.resize((int(w * scale), int(h * scale)), Image.Resampling.LANCZOS)
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=88, optimize=True)
            return buf.getvalue()
        except Exception as exc:
            logger.debug("Otimização de imagem ignorada: %s", exc)
            return raw

    def _pdf_first_pages(self, path: Path, max_pages: int = 3) -> list[str]:
        try:
            import fitz  # PyMuPDF
        except ImportError:
            logger.warning("PyMuPDF não instalado — vision PDF limitado")
            return []

        images: list[str] = []
        doc = fitz.open(path)
        try:
            for i in range(min(len(doc), max_pages)):
                page = doc.load_page(i)
                pix = page.get_pixmap(matrix=fitz.Matrix(2.0, 2.0))
                png_bytes = pix.tobytes("png")
                optimized = self._optimize_image_bytes(png_bytes)
                images.append(base64.b64encode(optimized).decode("ascii"))
        finally:
            doc.close()
        return images

    def _chat_vision(self, prompt: str, images_b64: list[str], model: str) -> str:
        try:
            resp = requests.get(f"{self.base_url}/api/tags", timeout=self.timeouts)
            resp.raise_for_status()
            names = {m.get("name", "") for m in resp.json().get("models", [])}
            models = _resolve_vision_model_tags(names) or [model, *VISION_MODEL_FALLBACKS]
        except Exception:
            models = [model, *VISION_MODEL_FALLBACKS]

        last_error: Exception | None = None

        for current in models:
            try:
                body = {
                    "model": current,
                    "messages": [{"role": "user", "content": prompt, "images": images_b64}],
                    "stream": False,
                    "format": "json",
                }
                resp = requests.post(
                    f"{self.base_url}/api/chat",
                    json=body,
                    timeout=self.timeouts,
                )
                resp.raise_for_status()
                data = resp.json()
                message = data.get("message") or {}
                content = message.get("content") or data.get("response") or ""
                if content:
                    return content.strip()
            except Exception as exc:
                last_error = exc
                logger.warning("VisionRouter model=%s falhou: %s", current, exc)

        raise RuntimeError(
            f"VisionRouter indisponível. Instale um modelo VL no Ollama "
            f"(ex.: {VISION_MODEL_PRIMARY}). Detalhe: {last_error}"
        )

    @staticmethod
    def _parse_vision_json(raw: str) -> dict[str, Any]:
        text = raw.strip()
        if text.startswith("```"):
            parts = text.split("```")
            text = parts[1] if len(parts) > 1 else text
            if text.startswith("json"):
                text = text[4:]
        text = text.strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            start = text.find("{")
            end = text.rfind("}")
            if start >= 0 and end > start:
                try:
                    return json.loads(text[start : end + 1])
                except json.JSONDecodeError:
                    pass
            return {
                "disciplina": "desconhecida",
                "elementos_detectados": [],
                "inconsistencias": [],
                "nao_conformidades": [],
                "normas_aplicaveis": [],
                "recomendacoes": [],
                "resumo_tecnico": raw[:2000],
                "parse_error": True,
            }
