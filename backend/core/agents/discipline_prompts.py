"""
Instruções de prompt por disciplina — complementam o template base dos agentes inteligentes.
"""

from __future__ import annotations

GEOTECNIA_INSTRUCTIONS = """
INSTRUÇÕES ESPECÍFICAS — GEOTECNIA / FUNDAÇÕES:

ESTRUTURA OBRIGATÓRIA DA RESPOSTA (nesta ordem):
1. **Solução recomendada** — tipo de fundação, dimensões preliminares e verificação numérica
2. **Análise e cálculos** — passo a passo com unidades (kgf, tf, tf/m² ou kN/kPa)
3. **Premissas** — dados fornecidos vs assumidos
4. **Alternativa** — só uma opção secundária, se aplicável
5. **Normas citadas** — apenas normas do tema (NBR 6122 fundações, NBR 7185 investigação)
6. **Perguntas em aberto** — até 3 perguntas objetivas se faltarem dados críticos

DECISÃO TÉCNICA:
- Sempre indique UMA solução principal (sapata, radier, estaca, tubulão, etc.) antes de hesitar
- Se houver carga P e tensão admissível σ_adm, calcule: A_min = P / σ_adm e dimensão de sapata (√A ou lado adotado com margem)
- Use prática brasileira: tf, kgf, kgf/cm² ou tf/m² quando o usuário usar essas unidades
- Não termine apenas com "depende da sondagem" — entregue dimensionamento preliminar com premissas

CLASSIFICAÇÃO DO SOLO (σ_adm em kgf/cm²):
- < 1,0: fraco — preferir fundação profunda ou melhoramento do solo
- 1,0 a 2,0: médio-fraco — sapata possível; verificar recalque
- 2,0 a 4,0: médio/bom — fundação direta usual (sapata ou radier)
- > 4,0: muito bom — fundação direta com boa margem
- NÃO classifique σ_adm ≥ 2,0 kgf/cm² como "solo fraco" ou "tensão baixa"

RECALQUE (NBR 6122):
- Trate recalque como critério tão relevante quanto a tensão admissível
- Mencione verificação de recalque total e diferencial quando fundação for direta
- Indique fundação profunda se recalque ou camada compressível forem prováveis

NORMAS — NÃO CONFUNDIR:
- NBR 6122:2019 — projeto de fundações (capacidade, recalque, investigação)
- NBR 7185 — investigação geotécnica (sondagens, perfil)
- NÃO cite NBR 6118, NBR 9062 ou fatores γn de concreto para capacidade geotécnica do solo

VALORES:
- Não invente parâmetros de solo (NSPT, cu, φ) sem base no enunciado ou no contexto RAG
- Cálculos com dados do usuário são permitidos e esperados
"""

FOUNDATION_KEYWORDS = (
    "fundação",
    "fundacao",
    "sapata",
    "estaca",
    "tubulão",
    "tubulao",
    "radier",
    "σ_adm",
    "sigma adm",
    "tensão admissível",
    "tensao admissivel",
    "capacidade de carga",
    "recalque",
    "sondagem",
    "spt",
    "6122",
)


def is_foundation_query(text: str) -> bool:
    lower = text.lower()
    return any(kw in lower for kw in FOUNDATION_KEYWORDS)


def get_discipline_extra_instructions(discipline: str, user_text: str = "") -> str:
    """Retorna bloco extra de instruções para a disciplina, se houver."""
    if discipline == "GEOTECNIA":
        return GEOTECNIA_INSTRUCTIONS

    if discipline in ("ESTRUTURAL", "INFRAESTRUTURA") and is_foundation_query(user_text):
        return """
INSTRUÇÕES — FUNDAÇÕES (pergunta detectada):
- Indique solução preliminar (sapata/radier/estaca) com A_min = P/σ_adm
- Classifique o solo: σ_adm ≥ 2 kgf/cm² é médio/bom, não fraco
- Verifique recalque conforme NBR 6122; cite NBR 6122 e NBR 7185, não NBR 6118 para capacidade do solo
- Seção **Solução recomendada** antes das alternativas
"""

    return ""
