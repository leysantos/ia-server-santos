from __future__ import annotations

"""Template PPD MC/OR vazio — estrutura municipal padrão SEMINF."""

from pricing.budget.ppd_layout import PPD_TEMPLATE_ID
from pricing.models.budget_item import BudgetItem
from pricing.models.budget_metadata import BdiConfig, BudgetProjectMetadata


def create_empty_ppd_metadata(
    projeto: str = "",
    objeto: str = "",
    local: str = "",
    orcamento: str = "",
    obra_type: str = "RF",
) -> BudgetProjectMetadata:
    bdi = BdiConfig.from_obra_type(obra_type)
    return BudgetProjectMetadata(
        template=PPD_TEMPLATE_ID,
        orgao="SEMINF",
        projeto=projeto or "NOVO PROJETO",
        objeto=objeto or projeto or "NOVO PROJETO",
        local=local,
        orcamento=orcamento,
        obra_type=obra_type,
        bdi=bdi,
        base_preco=(
            "SINAPI/SEMINF (COM DESONERAÇÃO) - "
            "[Horista: 98,35%] - [Mensalista: 58,20%] - "
            "[Mês de Referência: 03/2026]"
        ),
    )


def create_empty_ppd_tree(metadata: BudgetProjectMetadata | None = None) -> list[BudgetItem]:
    """Árvore vazia — etapas e serviços inseridos manualmente pelo usuário."""
    return []
