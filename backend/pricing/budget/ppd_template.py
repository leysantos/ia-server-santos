from __future__ import annotations

"""Template de orçamento vazio — exportação nativa Excel/PDF."""

from pricing.models.budget_item import BudgetItem
from pricing.models.budget_metadata import BdiConfig, BudgetProjectMetadata

BUDGET_TEMPLATE_ID = "BUDGET_CUSTOM"


def create_empty_ppd_metadata(
    projeto: str = "",
    objeto: str = "",
    local: str = "",
    orcamento: str = "",
    obra_type: str = "RF",
) -> BudgetProjectMetadata:
    bdi = BdiConfig.from_obra_type(obra_type)
    return BudgetProjectMetadata(
        template=BUDGET_TEMPLATE_ID,
        orgao="",
        projeto=projeto or "NOVO PROJETO",
        objeto=objeto or projeto or "NOVO PROJETO",
        local=local,
        orcamento=orcamento,
        obra_type=obra_type,
        bdi=bdi,
        base_preco="SINAPI",
    )


def create_empty_ppd_tree(metadata: BudgetProjectMetadata | None = None) -> list[BudgetItem]:
    """Árvore vazia — etapas e serviços inseridos manualmente pelo usuário."""
    return []
