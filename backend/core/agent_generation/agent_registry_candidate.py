"""
Agent Registry Candidate — registro versionado de agentes candidatos (não ativos).
Nunca modifica o dispatcher AGENTS automaticamente.
"""

from __future__ import annotations

import json
import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from config.settings import AGENT_GENERATION_DATA_DIR
from core.agent_generation.constants import (
    CANDIDATE_STATUS_DRAFT,
    CANDIDATE_STATUS_PROMOTED,
    CANDIDATE_STATUS_REJECTED,
    CANDIDATE_STATUS_SANDBOX,
    MAX_AGENTS_TOTAL,
    MAX_NEW_AGENTS_PER_WEEK,
    is_allowed_domain,
    resolve_discipline,
)

logger = logging.getLogger(__name__)

_DISCIPLINE_NORMAS: dict[str, list[str]] = {
    "ARQUITETURA": ["NBR 9050", "NBR 15575"],
    "ESTRUTURAL": ["NBR 6118", "NBR 8681"],
    "HIDROSSANITÁRIO": ["NBR 5626", "NBR 8160"],
    "DRENAGEM": ["NBR 10844", "NBR 9575"],
    "ELÉTRICA": ["NBR 5410", "NBR 14039"],
    "INCÊNDIO": ["NBR 17240", "NBR 10898"],
    "GEOTECNIA": ["NBR 6122", "NBR 7185"],
    "TRANSPORTES": ["NBR 7188", "NBR 7200"],
    "INFRAESTRUTURA": ["NBR 6118", "NBR 7188"],
    "ORÇAMENTO": ["SINAPI", "NBR ISO 12006"],
}

_registry: Optional["CandidateRegistry"] = None
_lock = threading.Lock()


@dataclass
class CandidateAgent:
    name: str
    discipline: str
    version: int
    purpose: str
    specialization: str
    system_instructions: str
    normas: list[str] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)
    status: str = CANDIDATE_STATUS_DRAFT
    proposal_id: Optional[str] = None
    risk_score: float = 0.35
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    promoted_at: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "discipline": self.discipline,
            "version": self.version,
            "purpose": self.purpose,
            "specialization": self.specialization,
            "system_instructions": self.system_instructions,
            "normas": self.normas,
            "dependencies": self.dependencies,
            "status": self.status,
            "proposal_id": self.proposal_id,
            "risk_score": self.risk_score,
            "created_at": self.created_at,
            "promoted_at": self.promoted_at,
        }


class CandidateRegistry:
    """Persistência local + limites de segurança."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._data: dict[str, Any] = self._load()

    def _load(self) -> dict[str, Any]:
        if self.path.exists():
            try:
                return json.loads(self.path.read_text(encoding="utf-8"))
            except Exception:
                pass
        return {"candidates": [], "promotion_log": []}

    def _save(self) -> None:
        self.path.write_text(
            json.dumps(self._data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def list_all_names(self) -> list[str]:
        return [c["name"] for c in self._data.get("candidates", [])]

    def count_total(self) -> int:
        from core.agent_registry import DISCIPLINE_TO_AGENT

        active = len(DISCIPLINE_TO_AGENT) + 1  # + CHAT
        candidates = len(self._data.get("candidates", []))
        return active + candidates

    def count_promoted_this_week(self) -> int:
        from datetime import timedelta

        cutoff = datetime.now(timezone.utc) - timedelta(days=7)
        count = 0
        for entry in self._data.get("promotion_log", []):
            try:
                ts = datetime.fromisoformat(entry.get("promoted_at", ""))
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=timezone.utc)
                if ts >= cutoff:
                    count += 1
            except Exception:
                continue
        return count

    def can_register_new(self) -> tuple[bool, str]:
        if self.count_total() >= MAX_AGENTS_TOTAL:
            return False, f"MAX_AGENTS_TOTAL ({MAX_AGENTS_TOTAL}) atingido"
        if self.count_promoted_this_week() >= MAX_NEW_AGENTS_PER_WEEK:
            return False, f"MAX_NEW_AGENTS_PER_WEEK ({MAX_NEW_AGENTS_PER_WEEK}) atingido"
        return True, "ok"

    def register_candidate(self, candidate: CandidateAgent) -> CandidateAgent:
        if not is_allowed_domain(candidate.discipline):
            raise ValueError(f"Domínio não permitido: {candidate.discipline}")

        ok, reason = self.can_register_new()
        if not ok and candidate.status == CANDIDATE_STATUS_PROMOTED:
            raise ValueError(reason)

        candidate.discipline = resolve_discipline(candidate.discipline)
        records: list = self._data.setdefault("candidates", [])
        existing = next((c for c in records if c["name"] == candidate.name), None)
        if existing:
            candidate.version = int(existing.get("version", 1)) + 1

        payload = candidate.to_dict()
        if existing:
            records.remove(existing)
        records.append(payload)
        self._save()
        logger.info("Candidate registry: %s v%s status=%s", candidate.name, candidate.version, candidate.status)
        return candidate

    def promote_candidate(self, name: str, proposal_id: Optional[str] = None) -> Optional[CandidateAgent]:
        ok, reason = self.can_register_new()
        if not ok:
            raise ValueError(reason)

        records: list = self._data.get("candidates", [])
        record = next((c for c in records if c["name"] == name), None)
        if not record:
            return None

        record["status"] = CANDIDATE_STATUS_PROMOTED
        record["promoted_at"] = datetime.now(timezone.utc).isoformat()
        record["version"] = int(record.get("version", 1)) + 1
        if proposal_id:
            record["proposal_id"] = proposal_id

        self._data.setdefault("promotion_log", []).append(
            {
                "name": name,
                "version": record["version"],
                "promoted_at": record["promoted_at"],
                "proposal_id": proposal_id,
            }
        )
        self._save()
        return CandidateAgent(**record)

    def reject_candidate(self, name: str, reason: str = "") -> None:
        records: list = self._data.get("candidates", [])
        record = next((c for c in records if c["name"] == name), None)
        if record:
            record["status"] = CANDIDATE_STATUS_REJECTED
            record["reject_reason"] = reason
            self._save()

    def get(self, name: str) -> Optional[CandidateAgent]:
        records: list = self._data.get("candidates", [])
        record = next((c for c in records if c["name"] == name), None)
        return CandidateAgent(**record) if record else None

    def list_candidates(self, status: Optional[str] = None) -> list[CandidateAgent]:
        records: list = self._data.get("candidates", [])
        if status:
            records = [c for c in records if c.get("status") == status]
        return [CandidateAgent(**c) for c in records]

    @staticmethod
    def build_from_proposal(proposal: dict[str, Any]) -> CandidateAgent:
        discipline = resolve_discipline(proposal["discipline"])
        normas = _DISCIPLINE_NORMAS.get(discipline, [])
        specialization = proposal.get("specialization") or "specialist"
        instructions = (
            f"Você é um sub-especialista em {discipline} ({specialization}).\n"
            f"Propósito: {proposal.get('purpose', '')}\n"
            f"Baseline de referência: {proposal.get('baseline_agent', '')}\n"
            "Responda com análise técnica estruturada, cite NBRs e declare premissas."
        )
        return CandidateAgent(
            name=proposal["name"],
            discipline=discipline,
            version=int(proposal.get("version") or 1),
            purpose=proposal.get("purpose") or "",
            specialization=specialization,
            system_instructions=instructions,
            normas=normas,
            dependencies=list(proposal.get("dependencies") or []),
            status=CANDIDATE_STATUS_SANDBOX,
            proposal_id=proposal.get("id"),
            risk_score=float(proposal.get("risk_score") or 0.35),
        )


def get_candidate_registry() -> CandidateRegistry:
    global _registry
    with _lock:
        if _registry is None:
            _registry = CandidateRegistry(AGENT_GENERATION_DATA_DIR / "candidates.json")
        return _registry
