"""
Design Generator — gera múltiplas soluções técnicas por disciplina (mín. 2).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from core.aed.project_understanding import ProjectUnderstanding

MIN_OPTIONS_PER_DISCIPLINE = 2

DESIGN_TEMPLATES: dict[str, list[dict[str, str]]] = {
    "ESTRUTURAL": [
        {
            "variant": "conservative",
            "name": "Solução conservadora",
            "approach": "Dimensionamento com margens de segurança elevadas, concreto armado convencional",
            "materials": "Concreto C30, aço CA-50",
        },
        {
            "variant": "optimized",
            "name": "Solução otimizada",
            "approach": "Dimensionamento otimizado com pré-dimensionamento e verificação NBR 6118",
            "materials": "Concreto C35, aço CA-60, protensão parcial se aplicável",
        },
    ],
    "HIDROSSANITÁRIO": [
        {
            "variant": "conventional",
            "name": "Rede convencional",
            "approach": "Dimensionamento NBR 5626/8160 com reservatórios e recalque padrão",
            "materials": "PVC esgoto, CPVC água fria",
        },
        {
            "variant": "optimized",
            "name": "Rede otimizada",
            "approach": "Pressurização direta com dimensionamento de diâmetros por trechos críticos",
            "materials": "PEAD/PPR, válvulas de controle",
        },
    ],
    "ELÉTRICA": [
        {
            "variant": "basic",
            "name": "Instalação básica",
            "approach": "Quadro de distribuição NBR 5410, circuitos dedicados",
            "materials": "Cabos 2,5/4/6 mm², DR e DPS",
        },
        {
            "variant": "enhanced",
            "name": "Instalação reforçada",
            "approach": "Seletividade, dimensionamento de demanda com fator de demanda otimizado",
            "materials": "Cabos dimensionados por queda de tensão, SPDA se exigido",
        },
    ],
    "ORÇAMENTO": [
        {
            "variant": "reference",
            "name": "Orçamento referência SINAPI",
            "approach": "Composições SINAPI regional, BDI padrão",
            "materials": "Referência SINAPI",
        },
        {
            "variant": "value_engineering",
            "name": "Orçamento value engineering",
            "approach": "Alternativas de materiais e métodos construtivos com análise de custo-benefício",
            "materials": "Mix otimizado de composições",
        },
    ],
    "ARQUITETURA": [
        {
            "variant": "standard",
            "name": "Layout padrão NBR 9050",
            "approach": "Plantas com acessibilidade e ventilação/iluminação natural",
            "materials": "Programa de necessidades padrão",
        },
        {
            "variant": "flexible",
            "name": "Layout flexível",
            "approach": "Espaços modulares com adaptabilidade de uso",
            "materials": "Divisórias leves, pé-direito otimizado",
        },
    ],
    "INCÊNDIO": [
        {
            "variant": "minimum",
            "name": "PCI mínimo normativo",
            "approach": "Atendimento NBR 17240 com rotas de fuga e extintores",
            "materials": "Extintores, sinalização",
        },
        {
            "variant": "enhanced",
            "name": "PCI reforçado",
            "approach": "Sprinklers + detecção + compartimentação",
            "materials": "Sistema sprinkler, detectores, reservatório incêndio",
        },
    ],
}

DEFAULT_TEMPLATES = [
    {
        "variant": "standard",
        "name": "Solução padrão",
        "approach": "Abordagem técnica convencional conforme normas ABNT",
        "materials": "Materiais padrão de mercado",
    },
    {
        "variant": "alternative",
        "name": "Solução alternativa",
        "approach": "Abordagem alternativa com otimização de recursos",
        "materials": "Materiais alternativos certificados",
    },
]


@dataclass
class DesignOption:
    option_id: str
    discipline: str
    variant: str
    name: str
    approach: str
    materials: str
    description: str
    premissas: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "option_id": self.option_id,
            "discipline": self.discipline,
            "variant": self.variant,
            "name": self.name,
            "approach": self.approach,
            "materials": self.materials,
            "description": self.description,
            "premissas": self.premissas,
        }


def generate_designs(understanding: ProjectUnderstanding) -> list[DesignOption]:
    """Gera no mínimo 2 opções técnicas por disciplina identificada."""
    designs: list[DesignOption] = []

    for disc in understanding.disciplines:
        templates = DESIGN_TEMPLATES.get(disc, DEFAULT_TEMPLATES)
        if len(templates) < MIN_OPTIONS_PER_DISCIPLINE:
            templates = templates + DEFAULT_TEMPLATES[: MIN_OPTIONS_PER_DISCIPLINE - len(templates)]

        for idx, tmpl in enumerate(templates[: max(MIN_OPTIONS_PER_DISCIPLINE, len(templates))], 1):
            option_id = f"{disc.lower()}_{tmpl['variant']}"
            premissas = [
                f"Projeto tipo: {understanding.project_type}",
                f"Intent: {understanding.intent}",
            ]
            if understanding.constraints:
                premissas.append(f"Restrições: {', '.join(understanding.constraints)}")

            normas = understanding.normas.get(disc, [])
            description = (
                f"{tmpl['approach']}. "
                f"Materiais: {tmpl['materials']}. "
                f"Normas: {', '.join(normas) if normas else 'ABNT aplicáveis'}."
            )

            designs.append(DesignOption(
                option_id=option_id,
                discipline=disc,
                variant=tmpl["variant"],
                name=tmpl["name"],
                approach=tmpl["approach"],
                materials=tmpl["materials"],
                description=description,
                premissas=premissas,
            ))

    return designs
