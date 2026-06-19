"""
Discipline profiles — persistência de metadados de otimização por disciplina.

Estrutura:
{
  "discipline": "ESTRUTURAL",
  "prompt_version": 2,
  "prompt_key": "prompt_estrutural_v2",
  "agent_name": "estruturas_agent",
  "common_errors": [],
  "improvements": [],
  "frequent_themes": [],
  "updated_at": "...",
  "feedback_sample_size": 0,
  "low_quality_count": 0
}
"""

from __future__ import annotations

import json
import logging
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from config.settings import LEARNING_V2_PROFILES_DIR, LEARNING_V2_PROMPTS_DIR

logger = logging.getLogger(__name__)


def discipline_slug(discipline: str) -> str:
    """ESTRUTURAL → estrutural, HIDROSSANITÁRIO → hidrossanitario."""
    normalized = unicodedata.normalize("NFKD", discipline)
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-z0-9]+", "_", ascii_text.lower()).strip("_")
    return slug or "geral"


def prompt_key_for(discipline: str, version: int) -> str:
    return f"prompt_{discipline_slug(discipline)}_v{version}"


def prompt_dir_for(discipline: str) -> Path:
    return LEARNING_V2_PROMPTS_DIR / discipline_slug(discipline)


def prompt_path_for(discipline: str, version: int) -> Path:
    return prompt_dir_for(discipline) / f"{prompt_key_for(discipline, version)}.txt"


def profile_path_for(discipline: str) -> Path:
    return LEARNING_V2_PROFILES_DIR / f"{discipline.upper()}.json"


def ensure_dirs() -> None:
    LEARNING_V2_PROFILES_DIR.mkdir(parents=True, exist_ok=True)
    LEARNING_V2_PROMPTS_DIR.mkdir(parents=True, exist_ok=True)


def get_latest_prompt_version(discipline: str) -> int:
    """Retorna a maior versão existente (0 se nenhuma)."""
    prompt_dir = prompt_dir_for(discipline)
    if not prompt_dir.exists():
        return 0

    versions: list[int] = []
    prefix = f"prompt_{discipline_slug(discipline)}_v"
    for path in prompt_dir.glob(f"{prefix}*.txt"):
        match = re.search(r"_v(\d+)\.txt$", path.name)
        if match:
            versions.append(int(match.group(1)))
    return max(versions) if versions else 0


def load_profile(discipline: str) -> Optional[dict[str, Any]]:
    path = profile_path_for(discipline)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Falha ao ler profile %s: %s", discipline, exc)
        return None


def save_profile(profile: dict[str, Any]) -> dict[str, Any]:
    """Persiste profile (sobrescreve apenas o JSON de metadados, não prompts)."""
    ensure_dirs()
    discipline = profile["discipline"]
    profile["updated_at"] = datetime.now(timezone.utc).isoformat()
    path = profile_path_for(discipline)
    path.write_text(json.dumps(profile, ensure_ascii=False, indent=2), encoding="utf-8")
    return profile


def list_profiles() -> list[dict[str, Any]]:
    ensure_dirs()
    profiles: list[dict[str, Any]] = []
    for path in sorted(LEARNING_V2_PROFILES_DIR.glob("*.json")):
        try:
            profiles.append(json.loads(path.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, OSError):
            continue
    return profiles


def build_empty_profile(
    discipline: str,
    agent_name: str = "",
    prompt_version: int = 0,
) -> dict[str, Any]:
    version = prompt_version or get_latest_prompt_version(discipline)
    return {
        "discipline": discipline.upper(),
        "prompt_version": version,
        "prompt_key": prompt_key_for(discipline, version) if version > 0 else None,
        "agent_name": agent_name,
        "common_errors": [],
        "improvements": [],
        "frequent_themes": [],
        "feedback_sample_size": 0,
        "low_quality_count": 0,
        "updated_at": None,
    }
