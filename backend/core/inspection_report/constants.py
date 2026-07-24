"""Módulo de Laudos de Vistoria — geração com Gemini + templates + export Word/PDF.

Layout e estrutura alinhados ao modelo institucional
`laudos/LAUDO TECNICO N05 - PONTE DO BARIRI - ESTRUTURADO.docx`.
"""

from __future__ import annotations

DEFAULT_CHAPTERS: list[dict] = [
    {"id": "capa", "title": "Capa / Identificação", "required": True},
    {"id": "sumario", "title": "Sumário", "required": True},
    {"id": "solicitacao", "title": "1. Solicitação", "required": True},
    {"id": "assunto", "title": "2. Assunto", "required": True},
    {"id": "local_data", "title": "3. Local e Data", "required": True},
    {"id": "objetivo", "title": "4. Objetivo", "required": True},
    {"id": "responsabilidade", "title": "5. Responsabilidade Técnica", "required": True},
    {"id": "identificacao", "title": "6. Identificação e Histórico", "required": True},
    {"id": "ficha_tecnica", "title": "7. Ficha Técnica e Concepção Estrutural", "required": True},
    {"id": "patologias", "title": "8. Descrição e Classificação das Patologias", "required": True},
    {"id": "indicadores", "title": "9. Cards-Resumo, Indicadores e Gráficos", "required": True},
    {"id": "gravidade", "title": "10. Tabela de Gravidade e Ranking de Criticidade", "required": True},
    {"id": "parecer", "title": "11. Parecer Técnico (Notas DNIT / normas aplicáveis)", "required": True},
    {"id": "plano_correcao", "title": "12. Plano de Correção Estrutural", "required": True},
    {"id": "cronograma", "title": "13. Cronograma de Reparo por Prioridade", "required": True},
    {"id": "conclusao", "title": "14. Conclusão", "required": True},
    {"id": "referencias", "title": "15. Referências", "required": True},
    {"id": "fotografico", "title": "16. Relatório Fotográfico", "required": True},
]

TEMPLATE_DEFS: list[dict] = [
    {
        "slug": "pontes",
        "name": "Pontes",
        "description": "Vistoria estrutural e de conservação de pontes (modelo SEMINF / Bariri)",
        "discipline_hint": "INFRAESTRUTURA",
    },
    {
        "slug": "viadutos",
        "name": "Viadutos",
        "description": "Vistoria de viadutos e obras de arte especiais",
        "discipline_hint": "INFRAESTRUTURA",
    },
    {
        "slug": "edificacao",
        "name": "Edificação",
        "description": "Vistoria predial / patologias em edificações",
        "discipline_hint": "ESTRUTURAL",
    },
    {
        "slug": "erosao",
        "name": "Erosão",
        "description": "Vistoria de processos erosivos e estabilização",
        "discipline_hint": "GEOTECNIA",
    },
    {
        "slug": "barragem",
        "name": "Barragem",
        "description": "Vistoria de barragens e estruturas de contenção hídrica",
        "discipline_hint": "GEOTECNIA",
    },
    {
        "slug": "drenagem",
        "name": "Drenagem",
        "description": "Vistoria de sistemas de drenagem urbana/rodoviária",
        "discipline_hint": "DRENAGEM",
    },
    {
        "slug": "pavimentacao",
        "name": "Pavimentação",
        "description": "Vistoria de pavimentos flexíveis/rígidos",
        "discipline_hint": "TRANSPORTES",
    },
    {
        "slug": "muro_contencao",
        "name": "Muro de contenção / arrimo",
        "description": "Vistoria de muros de contenção e arrimo",
        "discipline_hint": "GEOTECNIA",
    },
    {
        "slug": "geral",
        "name": "Vistoria geral",
        "description": "Template genérico de laudo técnico de vistoria",
        "discipline_hint": "GERAL",
    },
]


def _ch(*pairs: tuple[str, str], required: bool = True) -> list[dict]:
    return [{"id": i, "title": t, "required": required} for i, t in pairs]


_COMMON_HEAD = [
    ("capa", "Capa / Identificação"),
    ("sumario", "Sumário"),
    ("solicitacao", "1. Solicitação"),
    ("assunto", "2. Assunto"),
    ("local_data", "3. Local e Data"),
    ("objetivo", "4. Objetivo"),
    ("responsabilidade", "5. Responsabilidade Técnica"),
    ("identificacao", "6. Identificação e Histórico"),
]

_COMMON_TAIL = [
    ("parecer", "Parecer Técnico"),
    ("plano_correcao", "Plano de Correção"),
    ("cronograma", "Cronograma de Reparo por Prioridade"),
    ("conclusao", "Conclusão"),
    ("referencias", "Referências"),
    ("fotografico", "Relatório Fotográfico"),
]


def _numbered(mid: list[tuple[str, str]], start: int = 7) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    n = start
    for cid, title in mid + _COMMON_TAIL:
        if title[0].isdigit():
            out.append((cid, title))
        else:
            out.append((cid, f"{n}. {title}"))
            n += 1
    return out


CHAPTERS_BY_SLUG: dict[str, list[dict]] = {
    "pontes": list(DEFAULT_CHAPTERS),
    "viadutos": _ch(
        *_COMMON_HEAD,
        *_numbered(
            [
                ("ficha_tecnica", "Ficha Técnica e Concepção Estrutural (viaduto/OAE)"),
                ("patologias", "Descrição e Classificação das Patologias"),
                ("indicadores", "Cards-Resumo, Indicadores e Gráficos"),
                ("gravidade", "Tabela de Gravidade e Ranking de Criticidade"),
            ]
        ),
    ),
    "edificacao": _ch(
        *_COMMON_HEAD,
        *_numbered(
            [
                ("ficha_tecnica", "Ficha Técnica Predial (uso, pavimentos, sistema estrutural)"),
                ("patologias", "Patologias Prediais (fissuras, umidade, corrosão, revestimentos)"),
                ("indicadores", "Indicadores de Conservação Predial"),
                ("gravidade", "Ranking de Criticidade por Ambiente/Elemento"),
            ]
        ),
    ),
    "erosao": _ch(
        *_COMMON_HEAD,
        *_numbered(
            [
                ("ficha_tecnica", "Caracterização do Processo Erosivo e Terreno"),
                ("patologias", "Mecanismos de Erosão, Assoreamento e Instabilidade"),
                ("indicadores", "Indicadores de Evolução e Risco"),
                ("gravidade", "Priorização de Intervenções de Estabilização"),
            ]
        ),
    ),
    "barragem": _ch(
        *_COMMON_HEAD,
        *_numbered(
            [
                ("ficha_tecnica", "Ficha Técnica da Barragem / Estrutura Hídrica"),
                ("patologias", "Anomalias (infiltração, recalque, erosão interna, vertedouro)"),
                ("indicadores", "Indicadores de Segurança e Conservação"),
                ("gravidade", "Ranking de Criticidade e Monitoramento"),
            ]
        ),
    ),
    "drenagem": _ch(
        *_COMMON_HEAD,
        *_numbered(
            [
                ("ficha_tecnica", "Ficha do Sistema de Drenagem (bacias, dispositivos)"),
                ("patologias", "Obstruções, Colapsos, Assoreamento e Ineficiência Hidráulica"),
                ("indicadores", "Indicadores de Desempenho Hidráulico"),
                ("gravidade", "Priorização de Limpeza, Reparo e Ampliação"),
            ]
        ),
    ),
    "pavimentacao": _ch(
        *_COMMON_HEAD,
        *_numbered(
            [
                ("ficha_tecnica", "Ficha do Pavimento (tipo, camada, tráfego)"),
                ("patologias", "Defeitos de Superfície e Estruturais (IRI, trincas, panelas)"),
                ("indicadores", "Indicadores de Conservação do Pavimento"),
                ("gravidade", "Ranking de Trechos Críticos"),
            ]
        ),
    ),
    "muro_contencao": _ch(
        *_COMMON_HEAD,
        *_numbered(
            [
                ("ficha_tecnica", "Ficha Técnica do Muro / Sistema de Contenção"),
                ("patologias", "Deslocamentos, Drenagem, Fissuras e Instabilidade"),
                ("indicadores", "Indicadores Geotécnicos de Desempenho"),
                ("gravidade", "Ranking de Criticidade e Risco a Jusante"),
            ]
        ),
    ),
    "geral": _ch(
        *_COMMON_HEAD,
        *_numbered(
            [
                ("ficha_tecnica", "Ficha Técnica do Objeto"),
                ("patologias", "Descrição e Classificação das Anomalias"),
                ("indicadores", "Indicadores e Gráficos"),
                ("gravidade", "Tabela de Gravidade e Ranking"),
            ]
        ),
    ),
}

PROMPT_EXTRAS_BY_SLUG: dict[str, str] = {
    "pontes": (
        "Foque em OAE/ponte: superestrutura, mesoestrutura, infraestrutura, aparelhos de apoio, "
        "juntas, drenagem da pista, erosão de margens. Use notas DNIT Anexo C quando aplicável. "
        "Normas: NBR 9452, DNIT 010/2004-PRO, NBR 7187, NBR 6118."
    ),
    "viadutos": (
        "Foque em viaduto/OAE urbana: vãos, pilares, encontros, interferências viárias. "
        "Classifique gravidade com lógica DNIT/NBR 9452. Normas: NBR 9452, NBR 7187, NBR 6118."
    ),
    "edificacao": (
        "Foque em edificação: estrutura, alvenaria, impermeabilização, revestimentos, instalações "
        "aparentes, segurança. NÃO force ficha de ponte/OAE. Normas: NBR 6118, NBR 15575, NBR 9575, "
        "NBR 13755 quando pertinente."
    ),
    "erosao": (
        "Foque em processos erosivos, voçorocas, assoreamento, proteção de taludes e drenagem "
        "superficial. Normas geotécnicas e de drenagem aplicáveis (NBR 11682, manuais DNIT)."
    ),
    "barragem": (
        "Foque em segurança de barragem: maciço, fundação, extravasor, tomada d'água, instrumentação. "
        "Cite premissas quando faltar dado de projeto. Normas/legislação de segurança de barragens."
    ),
    "drenagem": (
        "Foque em dispositivos de drenagem (meio-fio, bocas de lobo, galerias, dissipadores), "
        "capacidade hidráulica e manutenção. Normas/manuais de drenagem urbana e rodoviária."
    ),
    "pavimentacao": (
        "Foque em pavimento flexível/rígido: trincas, panelas, afundamento, exsudação, desgaste. "
        "Relacione a tráfego e drenagem. Normas/DNIT de pavimentação quando pertinentes."
    ),
    "muro_contencao": (
        "Foque em muro de arrimo/contenção: geometria, drenagem interna, empuxos, deslocamentos, "
        "fissuras. Normas geotécnicas (NBR 11682) e estruturais quando couber."
    ),
    "geral": (
        "Adapte a ficha técnica e as patologias ao objeto descrito pelo profissional. "
        "Evite jargão exclusivo de pontes se o objeto não for OAE."
    ),
}

SYSTEM_PROMPT_BASE = """Você é um engenheiro civil sênior especializado em laudos técnicos de vistoria
(estilo institucional SEMINF / NBR 9452 / DNIT 010/2004-PRO).

Elabore um laudo PROFISSIONAL, COMPLETO e DETALHADO em português (pt-BR).

════════════════════════════════════════
ANÁLISE OBRIGATÓRIA DAS IMAGENS
════════════════════════════════════════
Para CADA fotografia fornecida você DEVE:
1. Observar o conteúdo visual real (elementos estruturais, materiais, danos, entorno).
2. Identificar patologias visíveis (corrosão, fissura, erosão, desplacamento, obstrução etc.).
3. Redigir título específico (não genérico como "Foto 12").
4. Redigir descrição técnica de 3 a 6 frases: o que se vê, onde está, gravidade aparente, risco.
5. Redigir legenda no formato:
   "{Objeto} – {Elemento} | Patologia: {nome} | Gravidade: {CRÍTICA|ALTA|MÉDIA|BAIXA} | Score: {n}/5 ({pct}%)"
6. Nunca usar descrições vazias do tipo "Registro fotográfico da vistoria".

════════════════════════════════════════
QUALIDADE DO TEXTO DOS CAPÍTULOS
════════════════════════════════════════
- Capítulos técnicos (histórico, ficha, patologias, parecer, plano) devem ter
  vários parágrafos substantivos (mínimo 2–4 por capítulo relevante).
- Classifique gravidade: CRÍTICA / ALTA / MÉDIA / BAIXA e correlacione a notas
  DNIT Anexo C (5=boa … 1=crítica) quando for OAE/ponte/viaduto.
- Inclua tabelas (ficha técnica, ranking de criticidade, cronograma).
- Inclua indicadores: índice de comprometimento %, índice de conservação %,
  distribuição por gravidade (charts com labels/values).
- Cite normas reais (NBR 9452, DNIT 010/2004-PRO, NBR 6118, NBR 8800, NBR 7187…)
  — não invente códigos.
- Se faltar dado factual, declare premissa explicitamente.

════════════════════════════════════════
REGRAS DE SAÍDA
════════════════════════════════════════
1. Responda APENAS com JSON válido (sem markdown fora do JSON).
2. Respeite os capítulos do template.
3. Inclua TODAS as fotos enviadas nesta chamada no photographic_report.
4. Linguagem técnica, objetiva, sem sensacionalismo.
5. Inclua o capítulo "sumario" com a lista ordenada dos títulos dos demais
   capítulos do laudo (sem capa/fotográfico). O export institucional também
   monta o Sumário automaticamente a partir das seções geradas.

FORMATO JSON:
{
  "titulo": "LAUDO TÉCNICO DE VISTORIA",
  "subtitulo": "Vistoria Rotineira – NBR 9452 / DNIT 010/2004-PRO",
  "numero_laudo": "…",
  "objeto": "…",
  "local": "…",
  "data_vistoria": "…",
  "tipo_vistoria": "rotineira|especial|extraordinária",
  "compliance_note": "Documento elaborado em conformidade com …",
  "chapters": [
    {
      "id": "objetivo",
      "title": "4. Objetivo",
      "paragraphs": ["…"],
      "tables": [{"caption":"…","headers":["…"],"rows":[["…"]]}],
      "charts": [{"caption":"…","chart_type":"bar","labels":["…"],"values":[1]}]
    }
  ],
  "pathologies": [
    {
      "code": "P01",
      "name":"…",
      "location":"…",
      "element":"…",
      "severity":"crítica|alta|média|baixa",
      "dnit_note": 1,
      "score": 5,
      "description":"…",
      "cause":"…",
      "solution":"…",
      "urgency":"…"
    }
  ],
  "indicators": {
    "compromise_index_pct": 70.0,
    "conservation_index_pct": 30.0,
    "severity_distribution": {"crítica": 5, "alta": 4, "média": 2, "baixa": 1}
  },
  "schedule": [{"phase":"…","activities":"…","duration":"…","order":1}],
  "references": ["…"],
  "photographic_report": [
    {
      "photo_number": 1,
      "filename": "…",
      "title": "…",
      "description": "…",
      "legend": "…",
      "severity": "crítica",
      "score": 5,
      "source": "…",
      "pathology_refs": ["P01"]
    }
  ],
  "conclusions": ["…"]
}
"""
