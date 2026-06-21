"""Prompts e modos de análise visual — obras, laudos e relatórios fotográficos."""

from __future__ import annotations

from enum import StrEnum


class VisionAnalysisMode(StrEnum):
    """Modos de análise multimodal."""

    PLANTA = "planta"
    OBRA = "obra"
    LAUDO = "laudo"
    RELATORIO_FOTOGRAFICO = "relatorio_fotografico"
    PCI = "pci"
    ESTRUTURAL = "estrutural"


MODE_LABELS: dict[str, str] = {
    VisionAnalysisMode.PLANTA: "Planta / prancha técnica",
    VisionAnalysisMode.OBRA: "Foto de obra (acompanhamento)",
    VisionAnalysisMode.LAUDO: "Laudo / vistoria técnica",
    VisionAnalysisMode.RELATORIO_FOTOGRAFICO: "Relatório fotográfico",
    VisionAnalysisMode.PCI: "Projeto PCI (incêndio)",
    VisionAnalysisMode.ESTRUTURAL: "Projeto estrutural",
}


def prompt_for_mode(mode: str) -> str:
    key = (mode or VisionAnalysisMode.PLANTA).strip().lower()
    builder = _PROMPTS.get(key, _PROMPT_PLANTA)
    return builder()


def supported_modes() -> list[dict[str, str]]:
    return [{"value": m.value, "label": MODE_LABELS[m.value]} for m in VisionAnalysisMode]


def _json_only_footer() -> str:
    return (
        "\nResponda APENAS com JSON válido (sem markdown, sem texto antes ou depois). "
        "Se não identificar um campo, use string vazia ou lista vazia."
    )


def _PROMPT_PLANTA() -> str:
    return f"""Você é engenheiro civil especialista em revisão de projetos.
Analise a planta/prancha/imagem técnica e produza JSON com esta estrutura:
{{
  "disciplina": "arquitetura|estrutura|hidraulica|eletrica|pci|desconhecida",
  "pavimento": "",
  "escala": "",
  "area_construida": "",
  "elementos_detectados": [{{"tipo": "", "descricao": "", "quantidade": null}}],
  "carimbos": [],
  "legendas": [],
  "cotas": [],
  "tabelas_detectadas": [],
  "inconsistencias": [],
  "nao_conformidades": [],
  "normas_aplicaveis": [],
  "recomendacoes": [],
  "resumo_tecnico": ""
}}
Seja técnico e objetivo.{_json_only_footer()}"""


def _PROMPT_OBRA() -> str:
    return f"""Você é engenheiro civil fiscal de obras públicas/privadas.
Analise a foto de canteiro de obras e produza JSON com esta estrutura:
{{
  "disciplina": "estrutura|arquitetura|hidraulica|eletrica|pci|infraestrutura|desconhecida",
  "fase_obra": "fundacao|estrutura|alvenaria|instalacoes|acabamento|desconhecida",
  "local_aproximado": "",
  "atividades_visiveis": [],
  "materiais_identificados": [],
  "equipamentos_presentes": [],
  "epis_observados": [],
  "epis_ausentes_ou_irregulares": [],
  "condicoes_seguranca": [],
  "qualidade_execucao": "adequada|parcial|inadequada|indeterminada",
  "percentual_estimado_conclusao": "",
  "inconsistencias": [],
  "nao_conformidades": [],
  "riscos": [],
  "normas_aplicaveis": [],
  "recomendacoes": [],
  "legenda_sugerida": "",
  "resumo_tecnico": ""
}}
Descreva o que é visível; não invente elementos ocultos.{_json_only_footer()}"""


def _PROMPT_LAUDO() -> str:
    return f"""Você é perito/engenheiro em laudos técnicos de engenharia civil.
Analise a imagem para embasar um laudo de vistoria e produza JSON:
{{
  "tipo_vistoria": "estrutural|instalacoes|pci|acabamento|patologia|geral",
  "objeto_analisado": "",
  "data_referencia_visivel": "",
  "condicoes_observadas": [],
  "patologias": [{{"tipo": "", "localizacao": "", "severidade": "baixa|media|alta|critica", "descricao": ""}}],
  "medidas_aparentes": [],
  "causa_provavel": "",
  "impacto_tecnico": "",
  "urgencia": "baixa|media|alta|critica",
  "nao_conformidades": [],
  "normas_aplicaveis": [],
  "recomendacoes": [],
  "conclusao_parcial": "",
  "legenda_laudo": "",
  "resumo_tecnico": ""
}}
Linguagem técnica, imparcial, adequada a laudo pericial.{_json_only_footer()}"""


def _PROMPT_RELATORIO_FOTOGRAFICO() -> str:
    return f"""Você redige relatórios fotográficos de acompanhamento de obra.
Analise a foto e produza JSON para inclusão em relatório fotográfico:
{{
  "numero_foto_sugerido": "",
  "data_hora_aparente": "",
  "local": "",
  "frente_servico": "",
  "descricao_detalhada": "",
  "elementos_destaque": [],
  "situacao": "conforme|nao_conforme|em_andamento|pendente",
  "observacoes_fiscal": [],
  "acao_recomendada": "",
  "legenda_relatorio": "",
  "tags": [],
  "resumo_tecnico": ""
}}
A legenda_relatorio deve ser uma frase clara pronta para publicação no relatório.{_json_only_footer()}"""


def _PROMPT_PCI() -> str:
    return f"""Você é especialista em projetos de Prevenção e Combate a Incêndio (PCI) — CBMAM/AM.
Analise a planta/documento PCI cruzando com o CONTEXTO NORMATIVO fornecido (ITs CBMAM indexadas).
Produza JSON com esta estrutura EXATA:
{{
  "disciplina": "pci",
  "tipo_edificacao": "E-5 — Edificação educacional (ou código CBMAM correto)",
  "ocupacao_cbmam": "E-5",
  "projeto_simplificado": true,
  "pavimentos": [],
  "rotas_fuga": [
    {{
      "origem": "",
      "destino": "",
      "demarcacao": "tracejada|continua|nao_identificada",
      "conforme_it11": true,
      "observacao": ""
    }}
  ],
  "saidas_emergencia": [{{"tipo": "", "largura_m": null, "quantidade_up": null, "localizacao": ""}}],
  "sinalizacao": [{{"tipo": "", "local": "", "conforme_nbr10898": true}}],
  "hidrantes_mangotinhos": [],
  "extintores": [],
  "sprinklers": [],
  "compartimentacao": [],
  "resistencia_fogo": [],
  "distancias_criticas": [],
  "portas_portoes_rota_fuga": [{{"tipo": "correr|pivotante|etc", "exige_nt03": true, "local": ""}}],
  "inconsistencias": [],
  "nao_conformidades": [
    {{"codigo": "IT-11|NT-03|NBR9077", "item": "", "descricao": "", "severidade": "baixa|media|alta|critica"}}
  ],
  "normas_aplicaveis": ["IT-11 CBMAM", "NT-03 CBMAM", "NBR 9077", "NBR 10898"],
  "its_cbmam_citadas": ["IT-11", "NT-03"],
  "recomendacoes": [],
  "resumo_tecnico": ""
}}
REGRAS OBRIGATÓRIAS:
1. Preencha `tipo_edificacao` com código CBMAM (ex.: E-5 para escola/creche) — nunca deixe vazio se for edificação educacional.
2. Identifique rotas de fuga VISÍVEIS (linhas tracejadas, setas, fluxo) em `rotas_fuga`; se ausentes na prancha, registre NC referenciando IT-11/NBR 9077.
3. Se houver portão/porta de correr na rota de fuga, cite NT-03 e marque `exige_nt03: true`.
4. Cite ITs CBMAM por número (IT-11, NT-03, etc.) em NCs e recomendações — use trechos do contexto normativo quando disponível.
5. Para projeto simplificado térreo, verifique memorial, memória de população/saídas e sinalização mínima.{_json_only_footer()}"""


def _PROMPT_ESTRUTURAL() -> str:
    return f"""Você é engenheiro estrutural especialista em revisão de projetos.
Analise a prancha estrutural e produza JSON:
{{
  "disciplina": "estrutura",
  "sistema_estrutural": "",
  "elementos": [{{"tipo": "viga|pilar|laje|fundacao", "descricao": "", "secao": "", "armadura": ""}}],
  "cotas_estruturais": [],
  "detalhamentos": [],
  "quantitativos_aparentes": [],
  "inconsistencias": [],
  "nao_conformidades": [],
  "normas_aplicaveis": ["NBR 6118", "NBR 6120"],
  "recomendacoes": [],
  "resumo_tecnico": ""
}}
Seja rigoroso com detalhamentos e compatibilização.{_json_only_footer()}"""


_PROMPTS: dict[str, callable] = {
    VisionAnalysisMode.PLANTA: _PROMPT_PLANTA,
    VisionAnalysisMode.OBRA: _PROMPT_OBRA,
    VisionAnalysisMode.LAUDO: _PROMPT_LAUDO,
    VisionAnalysisMode.RELATORIO_FOTOGRAFICO: _PROMPT_RELATORIO_FOTOGRAFICO,
    VisionAnalysisMode.PCI: _PROMPT_PCI,
    VisionAnalysisMode.ESTRUTURAL: _PROMPT_ESTRUTURAL,
}
