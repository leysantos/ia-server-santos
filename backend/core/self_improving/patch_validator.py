"""
Patch Validator — valida propostas contra regras de segurança obrigatórias.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

FORBIDDEN_AUTO_APPLY = True
FORBIDDEN_DIRECT_AGENT_CODE = True
RAG_REQUIRES_VALIDATION = True

DEFAULT_RISK_THRESHOLD = 0.7


@dataclass
class ValidationResult:
    valid: bool
    patch_key: str
    patch_version: int
    status: str
    issues: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "valid": self.valid,
            "patch_key": self.patch_key,
            "patch_version": self.patch_version,
            "status": self.status,
            "issues": self.issues,
            "warnings": self.warnings,
        }


def validate_patch(
    patch: dict[str, Any],
    *,
    risk_threshold: float = DEFAULT_RISK_THRESHOLD,
) -> ValidationResult:
    """
    Regras obrigatórias:
    - não quebrar dispatcher (nunca auto_apply em dispatcher)
    - não alterar RAG sem validação
    - não alterar agents diretamente
    - risco <= threshold
    """
    patch_key = patch.get("patch_key", "unknown")
    version = int(patch.get("patch_version", 0))
    issues: list[str] = []
    warnings: list[str] = []

    risk = float(patch.get("risk_score", 1.0))
    if risk > risk_threshold:
        issues.append(f"risco {risk} excede threshold {risk_threshold}")

    changes = patch.get("changes") or {}
    if changes.get("auto_apply"):
        issues.append("auto_apply proibido — nenhuma auto-modificação permitida")

    module = str(changes.get("module", ""))
    if "dispatcher" in module.lower():
        issues.append("alteração direta do dispatcher proibida")

    patch_type = patch.get("patch_type", "")
    if patch_type == "agent_behavior":
        proposal = changes.get("proposal") or {}
        if proposal.get("auto_apply") or "modify_class" in str(proposal):
            issues.append("alteração direta de agentes proibida")

    if patch_type == "rag_boosting" or changes.get("type") == "rag_boosting":
        if not patch.get("requires_validation"):
            issues.append("alteração RAG requer requires_validation=true")
        if not (changes.get("proposal") or {}).get("requires_index_validation"):
            warnings.append("RAG boost deve incluir requires_index_validation")

    if patch_type == "router_weights":
        if changes.get("auto_apply"):
            issues.append("router weights não podem ser auto-aplicados")

    valid = len(issues) == 0
    status = "validated" if valid else "rejected"

    return ValidationResult(
        valid=valid,
        patch_key=patch_key,
        patch_version=version,
        status=status,
        issues=issues,
        warnings=warnings,
    )


def validate_patches(
    patches: list[dict[str, Any]],
    *,
    risk_threshold: float = DEFAULT_RISK_THRESHOLD,
) -> list[ValidationResult]:
    return [validate_patch(p, risk_threshold=risk_threshold) for p in patches]
