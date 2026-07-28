"""Catálogo de ensaios instrumentados por tipología e gravidade da patologia.

Quando o laudo marca `suggest_instrumented_tests`, a API sugere ensaios
compatíveis com o template (pontes, viadutos, erosão…) e com a severidade
observada (crítica → alta → média → baixa).
"""

from __future__ import annotations

from typing import Any

# Ordem de gravidade (maior = mais crítica)
_SEV_RANK = {"crítica": 4, "critica": 4, "alta": 3, "média": 2, "media": 2, "baixa": 1}

# Ensaios comuns (aplicáveis a várias tipologías estruturais)
_COMMON_ESTRUTURAL: dict[str, list[dict[str, str]]] = {
    "crítica": [
        {
            "codigo": "EI-01",
            "ensaio": "Prova de carga estática / dinâmica",
            "objetivo": "Verificar capacidade residual e comportamento sob carregamento real",
            "norma_ref": "NBR 6122 / NBR 7187 / manuais DNIT",
        },
        {
            "codigo": "EI-02",
            "ensaio": "Ensaio de ultrassom (velocidade de pulso)",
            "objetivo": "Avaliar homogeneidade e discontinuidades no concreto",
            "norma_ref": "NBR 8802",
        },
        {
            "codigo": "EI-03",
            "ensaio": "Esclerometria",
            "objetivo": "Estimativa da resistência superficial do concreto",
            "norma_ref": "NBR 7584",
        },
        {
            "codigo": "EI-04",
            "ensaio": "Pacometria (localização e cobrimento de armaduras)",
            "objetivo": "Mapear armaduras e cobrimento efetivo",
            "norma_ref": "NBR 6118 / práticas IPR-DNIT",
        },
        {
            "codigo": "EI-05",
            "ensaio": "Carbonatação (solução de fenolftaleína)",
            "objetivo": "Determinar profundidade de frente de carbonatação",
            "norma_ref": "RILEM CPC-18 / práticas laboratoriais",
        },
        {
            "codigo": "EI-06",
            "ensaio": "Extração de testemunhos (coring) + ensaio à compressão",
            "objetivo": "Resistência real do concreto in situ",
            "norma_ref": "NBR 7680 / NBR 5739",
        },
        {
            "codigo": "EI-07",
            "ensaio": "Monitoramento contínuo de fissuras (fissurômetros / LVDT)",
            "objetivo": "Verificar evolução e estabilidade de aberturas",
            "norma_ref": "Práticas de instrumentação estrutural",
        },
        {
            "codigo": "EI-08",
            "ensaio": "Potencial de corrosão / resistividade elétrica",
            "objetivo": "Diagnóstico de corrosão ativa em armaduras",
            "norma_ref": "ASTM C876 / práticas de diagnóstico",
        },
    ],
    "alta": [
        {
            "codigo": "EI-02",
            "ensaio": "Ensaio de ultrassom (velocidade de pulso)",
            "objetivo": "Avaliar homogeneidade e discontinuidades no concreto",
            "norma_ref": "NBR 8802",
        },
        {
            "codigo": "EI-03",
            "ensaio": "Esclerometria",
            "objetivo": "Estimativa da resistência superficial do concreto",
            "norma_ref": "NBR 7584",
        },
        {
            "codigo": "EI-04",
            "ensaio": "Pacometria (localização e cobrimento de armaduras)",
            "objetivo": "Mapear armaduras e cobrimento efetivo",
            "norma_ref": "NBR 6118 / práticas IPR-DNIT",
        },
        {
            "codigo": "EI-05",
            "ensaio": "Carbonatação (solução de fenolftaleína)",
            "objetivo": "Determinar profundidade de frente de carbonatação",
            "norma_ref": "RILEM CPC-18 / práticas laboratoriais",
        },
        {
            "codigo": "EI-07",
            "ensaio": "Monitoramento de fissuras (fissurômetros)",
            "objetivo": "Acompanhar evolução de aberturas críticas",
            "norma_ref": "Práticas de instrumentação estrutural",
        },
        {
            "codigo": "EI-08",
            "ensaio": "Potencial de corrosão / resistividade elétrica",
            "objetivo": "Diagnóstico de corrosão em armaduras",
            "norma_ref": "ASTM C876 / práticas de diagnóstico",
        },
    ],
    "média": [
        {
            "codigo": "EI-03",
            "ensaio": "Esclerometria",
            "objetivo": "Estimativa indicativa da resistência superficial",
            "norma_ref": "NBR 7584",
        },
        {
            "codigo": "EI-04",
            "ensaio": "Pacometria (amostral)",
            "objetivo": "Verificar cobrimento em pontos representativos",
            "norma_ref": "NBR 6118",
        },
        {
            "codigo": "EI-05",
            "ensaio": "Carbonatação (pontos representativos)",
            "objetivo": "Amostrar frente de carbonatação",
            "norma_ref": "RILEM CPC-18",
        },
    ],
    "baixa": [
        {
            "codigo": "EI-03",
            "ensaio": "Esclerometria (pontual)",
            "objetivo": "Conferir resistência superficial em áreas suspeitas",
            "norma_ref": "NBR 7584",
        },
        {
            "codigo": "EI-VIS",
            "ensaio": "Inspeção visual instrumentada (registro métrico / drone)",
            "objetivo": "Documentar anomalias leves para acompanhamento",
            "norma_ref": "NBR 9452 / DNIT 010/2004-PRO",
        },
    ],
}

_OAE_EXTRA: dict[str, list[dict[str, str]]] = {
    "crítica": [
        {
            "codigo": "EI-ACO-01",
            "ensaio": "Medição de espessura residual por ultrassom (UT) em perfis e chapas metálicas",
            "objetivo": (
                "Quantificar a espessura remanescente de alma, mesa e chapas "
                "após corrosão, para avaliar a redução da área da seção transversal"
            ),
            "norma_ref": "ASTM E797 / práticas de UT em estruturas metálicas / NBR 8800",
        },
        {
            "codigo": "EI-ACO-02",
            "ensaio": "Avaliação da perda de seção transversal / área residual de elementos metálicos",
            "objetivo": (
                "Calcular a área efetiva remanescente de perfis e chapas corroídos "
                "e comparar com a seção de projeto/norma"
            ),
            "norma_ref": "NBR 8800 / AISC / manuais DNIT de OAE metálicas",
        },
        {
            "codigo": "EI-ACO-03",
            "ensaio": "Mapeamento de corrosão e perda de massa em estrutura metálica",
            "objetivo": "Delimitar extensões e graus de corrosão em longarinas, transversinas e ligações",
            "norma_ref": "NBR 9452 / práticas de inspeção de OAE metálicas",
        },
        {
            "codigo": "EI-ACO-04",
            "ensaio": "Ensaios de soldas (líquido penetrante / partículas magnéticas)",
            "objetivo": "Detectar descontinuidades em soldas e ligações sob corrosão/fadiga",
            "norma_ref": "ASTM E165 / ASTM E709 / práticas de END",
        },
        {
            "codigo": "EI-OAE-01",
            "ensaio": "Inspeção submersa / batimetria junto a fundações",
            "objetivo": "Avaliar erosão, solapamento e integridade de pilares/fundações",
            "norma_ref": "Manuais IPR/DNIT de inspeção de OAE",
        },
        {
            "codigo": "EI-OAE-02",
            "ensaio": "Ensaio de vibração / identificação modal",
            "objetivo": "Caracterizar resposta dinâmica e anomalias de rigidez",
            "norma_ref": "Práticas de dinâmica estrutural / DNIT",
        },
        {
            "codigo": "EI-OAE-03",
            "ensaio": "Medição de recalques e deslocamentos (nível / estações totais)",
            "objetivo": "Quantificar movimentos de meso/infraestrutura",
            "norma_ref": "Práticas de monitoração geotécnica-estrutural",
        },
        {
            "codigo": "EI-OAE-04",
            "ensaio": "Ensaios em aparelhos de apoio e juntas de dilatação",
            "objetivo": "Verificar desempenho e degradação de apoios/juntas",
            "norma_ref": "NBR 9452 / manuais DNIT",
        },
    ],
    "alta": [
        {
            "codigo": "EI-ACO-01",
            "ensaio": "Medição de espessura residual por ultrassom (UT) em pontos críticos",
            "objetivo": "Verificar redução de espessura em perfis/chapas com corrosão avançada",
            "norma_ref": "ASTM E797 / NBR 8800",
        },
        {
            "codigo": "EI-ACO-02",
            "ensaio": "Avaliação amostral da perda de seção transversal metálica",
            "objetivo": "Estimar área residual e capacidade remanescente dos elementos corroídos",
            "norma_ref": "NBR 8800 / manuais DNIT",
        },
        {
            "codigo": "EI-ACO-03",
            "ensaio": "Mapeamento de corrosão em elementos metálicos principais",
            "objetivo": "Registrar extensão e severidade da corrosão",
            "norma_ref": "NBR 9452",
        },
        {
            "codigo": "EI-OAE-01",
            "ensaio": "Inspeção submersa / batimetria (pontos críticos)",
            "objetivo": "Checar erosão e solapamento em fundações sensíveis",
            "norma_ref": "Manuais IPR/DNIT de inspeção de OAE",
        },
        {
            "codigo": "EI-OAE-03",
            "ensaio": "Medição de recalques / prumo de pilares",
            "objetivo": "Detectar deslocamentos anômalos",
            "norma_ref": "Práticas de monitoração",
        },
        {
            "codigo": "EI-OAE-04",
            "ensaio": "Inspeção detalhada de aparelhos de apoio e juntas",
            "objetivo": "Avaliar desgaste e travamento",
            "norma_ref": "NBR 9452 / manuais DNIT",
        },
    ],
    "média": [
        {
            "codigo": "EI-ACO-01",
            "ensaio": "Medição pontual de espessura residual (UT) em chapas/perfis suspeitos",
            "objetivo": "Conferir perda localizada de espessura",
            "norma_ref": "ASTM E797",
        },
        {
            "codigo": "EI-OAE-04",
            "ensaio": "Inspeção de aparelhos de apoio e juntas (amostral)",
            "objetivo": "Conferir estado de conservação",
            "norma_ref": "NBR 9452",
        },
    ],
    "baixa": [
        {
            "codigo": "EI-ACO-03",
            "ensaio": "Inspeção visual detalhada de corrosão em elementos metálicos",
            "objetivo": "Registrar pontos de oxidação para acompanhamento",
            "norma_ref": "NBR 9452",
        },
    ],
}

_EROSAO_GEO: dict[str, list[dict[str, str]]] = {
    "crítica": [
        {
            "codigo": "EI-GEO-01",
            "ensaio": "Sondagem SPT / CPT nas margens e taludes",
            "objetivo": "Caracterizar estratigrafia e resistência do maciço",
            "norma_ref": "NBR 6484 / NBR 12069",
        },
        {
            "codigo": "EI-GEO-02",
            "ensaio": "Piezometria / monitoramento de nível d'água",
            "objetivo": "Avaliar pressões intersticiais e saturação",
            "norma_ref": "Práticas geotécnicas de monitoramento",
        },
        {
            "codigo": "EI-GEO-03",
            "ensaio": "Inclinometria / marcas de deslocamento de talude",
            "objetivo": "Detectar movimentos de massa",
            "norma_ref": "NBR 11682 / práticas de instrumentação",
        },
        {
            "codigo": "EI-GEO-04",
            "ensaio": "Levantamento topográfico / drone (MDT antes-depois)",
            "objetivo": "Quantificar avanço erosivo e volumes",
            "norma_ref": "Práticas de topografia e fotogrametria",
        },
        {
            "codigo": "EI-GEO-05",
            "ensaio": "Ensaios de cisalhamento / caracterização laboratorial",
            "objetivo": "Parâmetros de resistência para estabilização",
            "norma_ref": "NBR 6459 / NBR 7181 / NBR 12069",
        },
    ],
    "alta": [
        {
            "codigo": "EI-GEO-01",
            "ensaio": "Sondagem SPT (pontos representativos)",
            "objetivo": "Caracterizar solo nas zonas de erosão",
            "norma_ref": "NBR 6484",
        },
        {
            "codigo": "EI-GEO-03",
            "ensaio": "Marcas de deslocamento / monitoramento de talude",
            "objetivo": "Acompanhar evolução de movimentos",
            "norma_ref": "NBR 11682",
        },
        {
            "codigo": "EI-GEO-04",
            "ensaio": "Levantamento topográfico / drone",
            "objetivo": "Mapear avanço erosivo",
            "norma_ref": "Práticas de topografia",
        },
    ],
    "média": [
        {
            "codigo": "EI-GEO-04",
            "ensaio": "Levantamento topográfico simplificado",
            "objetivo": "Registrar geometria atual do processo erosivo",
            "norma_ref": "Práticas de topografia",
        },
        {
            "codigo": "EI-GEO-06",
            "ensaio": "Ensaios de granulometria / limites de Atterberg (amostras)",
            "objetivo": "Classificar materiais erodíveis",
            "norma_ref": "NBR 7181 / NBR 6459",
        },
    ],
    "baixa": [
        {
            "codigo": "EI-GEO-04",
            "ensaio": "Registro fotogramétrico / drone de acompanhamento",
            "objetivo": "Baseline para monitoramento periódico",
            "norma_ref": "Práticas de inspeção",
        },
    ],
}

_BARRAGEM: dict[str, list[dict[str, str]]] = {
    "crítica": [
        {
            "codigo": "EI-BAR-01",
            "ensaio": "Auscultação (piezômetros, marcos superficiais, vazões de drenos)",
            "objetivo": "Avaliar performance e anomalias de percolação",
            "norma_ref": "Legislação de segurança de barragens / manuais",
        },
        {
            "codigo": "EI-BAR-02",
            "ensaio": "Inspeção de extravasor / tomada d'água (mergulho / ROV)",
            "objetivo": "Verificar erosão, obstrução e integridade hidráulica",
            "norma_ref": "Práticas de segurança de barragens",
        },
        {
            "codigo": "EI-BAR-03",
            "ensaio": "Ensaios de permeabilidade / vazamentos",
            "objetivo": "Quantificar percolações anômalas",
            "norma_ref": "Práticas geotécnicas de barragens",
        },
        *_EROSAO_GEO["crítica"][:3],
    ],
    "alta": [
        {
            "codigo": "EI-BAR-01",
            "ensaio": "Auscultação (leitura de instrumentação existente)",
            "objetivo": "Conferir tendência de piezômetros e marcos",
            "norma_ref": "Manuais de segurança de barragens",
        },
        {
            "codigo": "EI-BAR-02",
            "ensaio": "Inspeção de extravasor / dispositivos hidráulicos",
            "objetivo": "Detectar erosão e obstruções",
            "norma_ref": "Práticas de segurança de barragens",
        },
        *_EROSAO_GEO["alta"][:2],
    ],
    "média": list(_EROSAO_GEO["média"]),
    "baixa": list(_EROSAO_GEO["baixa"]),
}

_DRENAGEM: dict[str, list[dict[str, str]]] = {
    "crítica": [
        {
            "codigo": "EI-DR-01",
            "ensaio": "Inspeção CCTV / vídeoendoscopia de galerias",
            "objetivo": "Mapear colapsos, rachaduras e obstruções internas",
            "norma_ref": "Práticas de inspeção de drenagem",
        },
        {
            "codigo": "EI-DR-02",
            "ensaio": "Ensaio de vazão / capacidade hidráulica",
            "objetivo": "Verificar desempenho sob chuva de projeto",
            "norma_ref": "Manuais de drenagem urbana/rodoviária",
        },
        {
            "codigo": "EI-DR-03",
            "ensaio": "Levantamento altimétrico de dispositivos",
            "objetivo": "Checar declividades e pontos de estagnação",
            "norma_ref": "Práticas de topografia",
        },
    ],
    "alta": [
        {
            "codigo": "EI-DR-01",
            "ensaio": "Inspeção CCTV (trechos críticos)",
            "objetivo": "Identificar obstruções e danos internos",
            "norma_ref": "Práticas de inspeção de drenagem",
        },
        {
            "codigo": "EI-DR-03",
            "ensaio": "Levantamento altimétrico amostral",
            "objetivo": "Verificar declividades",
            "norma_ref": "Práticas de topografia",
        },
    ],
    "média": [
        {
            "codigo": "EI-DR-03",
            "ensaio": "Nivelamento simplificado de bocas de lobo / meio-fio",
            "objetivo": "Detectar pontos de empoçamento",
            "norma_ref": "Práticas de drenagem",
        },
    ],
    "baixa": [
        {
            "codigo": "EI-VIS",
            "ensaio": "Inspeção visual com registro fotográfico métrico",
            "objetivo": "Acompanhar sedimentação e vegetação",
            "norma_ref": "Práticas de manutenção",
        },
    ],
}

_PAVIMENTO: dict[str, list[dict[str, str]]] = {
    "crítica": [
        {
            "codigo": "EI-PAV-01",
            "ensaio": "FWD / Deflectometria",
            "objetivo": "Avaliar capacidade estrutural do pavimento",
            "norma_ref": "DNIT / práticas de avaliação de pavimentos",
        },
        {
            "codigo": "EI-PAV-02",
            "ensaio": "Extração de testemunhos de pavimento",
            "objetivo": "Espessuras e estado das camadas",
            "norma_ref": "Normas DNIT de pavimentação",
        },
        {
            "codigo": "EI-PAV-03",
            "ensaio": "IRI / irregularidade longitudinal",
            "objetivo": "Quantificar conforto e degradação superficial",
            "norma_ref": "Práticas DNIT",
        },
    ],
    "alta": [
        {
            "codigo": "EI-PAV-01",
            "ensaio": "FWD / Deflectometria (trechos críticos)",
            "objetivo": "Avaliar capacidade residual",
            "norma_ref": "DNIT",
        },
        {
            "codigo": "EI-PAV-02",
            "ensaio": "Testemunhos amostrais",
            "objetivo": "Conferir espessuras",
            "norma_ref": "Normas DNIT",
        },
    ],
    "média": [
        {
            "codigo": "EI-PAV-03",
            "ensaio": "Levantamento de irregularidade / inventário de falhas",
            "objetivo": "Classificar gravidade superficial",
            "norma_ref": "DNIT",
        },
    ],
    "baixa": [
        {
            "codigo": "EI-VIS",
            "ensaio": "Inventário visual de falhas (trincas, panelas)",
            "objetivo": "Baseline de conservação",
            "norma_ref": "DNIT",
        },
    ],
}

_EDIFICACAO: dict[str, list[dict[str, str]]] = {
    "crítica": list(_COMMON_ESTRUTURAL["crítica"])
    + [
        {
            "codigo": "EI-ED-01",
            "ensaio": "Termografia infravermelha",
            "objetivo": "Detectar umidade, descolamentos e anomalias térmicas",
            "norma_ref": "Práticas de inspeção predial",
        },
        {
            "codigo": "EI-ED-02",
            "ensaio": "Ensaio de permeabilidade / estanqueidade de fachadas",
            "objetivo": "Avaliar infiltrações",
            "norma_ref": "NBR 15575 / NBR 13755",
        },
    ],
    "alta": list(_COMMON_ESTRUTURAL["alta"])
    + [
        {
            "codigo": "EI-ED-01",
            "ensaio": "Termografia (áreas úmidas)",
            "objetivo": "Mapear umidade oculta",
            "norma_ref": "Práticas de inspeção predial",
        },
    ],
    "média": list(_COMMON_ESTRUTURAL["média"]),
    "baixa": list(_COMMON_ESTRUTURAL["baixa"]),
}

_MURO: dict[str, list[dict[str, str]]] = {
    "crítica": list(_COMMON_ESTRUTURAL["crítica"][:6])
    + [
        {
            "codigo": "EI-MU-01",
            "ensaio": "Inclinometria / prumo do muro",
            "objetivo": "Quantificar deslocamentos e inclinações",
            "norma_ref": "NBR 11682",
        },
        {
            "codigo": "EI-MU-02",
            "ensaio": "Verificação de drenagem interna (barbachãs / geotêxtil)",
            "objetivo": "Avaliar alívio de empuxos hidrostáticos",
            "norma_ref": "Práticas geotécnicas",
        },
        *_EROSAO_GEO["crítica"][:2],
    ],
    "alta": list(_COMMON_ESTRUTURAL["alta"][:4])
    + [
        {
            "codigo": "EI-MU-01",
            "ensaio": "Medição de prumo / deslocamento",
            "objetivo": "Detectar movimentos anômalos",
            "norma_ref": "NBR 11682",
        },
    ],
    "média": list(_COMMON_ESTRUTURAL["média"]),
    "baixa": list(_COMMON_ESTRUTURAL["baixa"]),
}


def _merge_sev(
    base: dict[str, list[dict[str, str]]],
    extra: dict[str, list[dict[str, str]]] | None = None,
) -> dict[str, list[dict[str, str]]]:
    out: dict[str, list[dict[str, str]]] = {}
    for sev in ("crítica", "alta", "média", "baixa"):
        items = list(base.get(sev) or [])
        if extra:
            items.extend(extra.get(sev) or [])
        # dedupe por codigo
        seen: set[str] = set()
        deduped: list[dict[str, str]] = []
        for it in items:
            code = it.get("codigo") or it.get("ensaio") or ""
            if code in seen:
                continue
            seen.add(code)
            deduped.append(it)
        out[sev] = deduped
    return out


TESTS_BY_SLUG: dict[str, dict[str, list[dict[str, str]]]] = {
    "pontes": _merge_sev(_COMMON_ESTRUTURAL, _OAE_EXTRA),
    "viadutos": _merge_sev(_COMMON_ESTRUTURAL, _OAE_EXTRA),
    "edificacao": _EDIFICACAO,
    "erosao": _EROSAO_GEO,
    "barragem": _BARRAGEM,
    "drenagem": _DRENAGEM,
    "pavimentacao": _PAVIMENTO,
    "muro_contencao": _MURO,
    "geral": _merge_sev(_COMMON_ESTRUTURAL),
}


def normalize_severity(raw: Any) -> str:
    s = str(raw or "").strip().lower()
    if s in ("crítica", "critica"):
        return "crítica"
    if s == "alta":
        return "alta"
    if s in ("média", "media"):
        return "média"
    if s == "baixa":
        return "baixa"
    return "média"


def severity_rank(raw: Any) -> int:
    return _SEV_RANK.get(normalize_severity(raw), 2)


def catalog_for_slug(slug: str | None) -> dict[str, list[dict[str, str]]]:
    key = (slug or "geral").strip().lower()
    return TESTS_BY_SLUG.get(key) or TESTS_BY_SLUG["geral"]


def build_ensaios_prompt_block(slug: str | None, user_prompt: str = "") -> str:
    """
    Bloco CRÍTICO injetado no prompt do Gemini.
    Exige sugestão completa de ensaios por gravidade das patologias + tipo de obra.
    """
    catalog = catalog_for_slug(slug)
    tipo = (slug or "geral").strip().lower()
    tipo_nome = {
        "pontes": "PONTE / OAE",
        "viadutos": "VIADUTO / OAE",
        "edificacao": "EDIFICAÇÃO",
        "erosao": "EROSÃO / TALUDES",
        "barragem": "BARRAGEM",
        "drenagem": "DRENAGEM",
        "pavimentacao": "PAVIMENTAÇÃO",
        "muro_contencao": "MURO DE CONTENÇÃO",
        "geral": "VISTORIA GERAL",
    }.get(tipo, tipo.upper())

    lines = [
        "╔══════════════════════════════════════════════════════════════╗",
        "║  ETAPA CRÍTICA — ENSAIOS INSTRUMENTADOS (SEM OMISSÕES)     ║",
        "╚══════════════════════════════════════════════════════════════╝",
        "ATENÇÃO: esta etapa é OBRIGATÓRIA e de ALTA RESPONSABILIDADE TÉCNICA.",
        "Erros ou omissões de ensaios comprometem a segurança do laudo.",
        "O profissional ATIVOU a sugestão de ensaios instrumentados.",
        "",
        f"TIPO DE OBRA / TEMPLATE: {tipo_nome} (slug={tipo})",
        "",
        "MISSÃO (cumpra integralmente):",
        "1) Analise CADA patologia identificada (nome, local, elemento, gravidade).",
        "2) Para CADA patologia, indique os ensaios necessários àquela gravidade.",
        "3) Consolide a lista completa sem duplicar, ordenada do MAIS CRÍTICO",
        "   ao MENOS CRÍTICO.",
        "4) NÃO deixe de sugerir ensaios quando houver patologia crítica ou alta.",
        "5) NÃO invente ensaios irrelevantes ao tipo de obra; use o catálogo abaixo",
        "   como base mínima e complemente com justificativa técnica quando preciso.",
        "",
        "MATRIZ OBRIGATÓRIA POR GRAVIDADE:",
        "• CRÍTICA → incluir TODOS os ensaios do nível [CRÍTICA] do catálogo do",
        "  template + ensaios de ALTA pertinentes à patologia; necessidade 90–100%.",
        "• ALTA → incluir ensaios [ALTA] (+ MÉDIA pertinentes); necessidade 70–89%.",
        "• MÉDIA → incluir ensaios [MÉDIA] (+ BAIXA se útil); necessidade 45–69%.",
        "• BAIXA → incluir ensaios [BAIXA] / acompanhamento; necessidade 20–44%.",
        "",
        "REGRAS ANTI-ERRO (obrigatórias):",
        "- O campo JSON `instrumented_tests` NÃO pode ficar vazio nem ausente.",
        "- O capítulo `ensaios_instrumentados` é OBRIGATÓRIO, com tabela completa:",
        "  Item | Ensaio | Descrição do ensaio | Criticidade | Necessidade (%) |",
        "  Prazo recomendado | Norma/ref.",
        "- Cada ensaio DEVE citar `pathology_refs` (ex.: [\"P01\",\"P03\"]) quando",
        "  houver patologias correspondentes.",
        "- Em parecer, plano de correção e conclusão, MENCIONE a campanha de",
        "  ensaios e a urgência (interdição, prazo).",
        "- Se o profissional pediu ensaios específicos no texto, INCLUA-OS no topo.",
        "- Ponte/viaduto MISTO (concreto+aço) ou corrosão em perfis/chapas:",
        "  PRIORIZE EI-ACO-01 (espessura residual UT) e EI-ACO-02 (perda de seção).",
        "- Ultrasonografia de concreto (NBR 8802) ≠ UT de espessura de aço (E797):",
        "  NÃO confunda; use o ensaio certo para cada material.",
        "",
        "FORMATO de cada item em instrumented_tests:",
        '{'
        '"codigo":"EI-…","ensaio":"…","descricao":"…","norma_ref":"…",'
        '"gravidade_alvo":"crítica|alta|média|baixa","necessidade_pct":95,'
        '"prazo":"Imediato (até 7 dias)","pathology_refs":["P01"]'
        "}",
    ]
    up = (user_prompt or "").strip()
    if up:
        lines.extend(
            [
                "",
                "PEDIDOS EXPLÍCITOS DO PROFISSIONAL (cumprir SEM OMITIR):",
                "-----",
                up[:3000],
                "-----",
            ]
        )
    lines.extend(
        [
            "",
            f"CATÁLOGO MÍNIMO OBRIGATÓRIO — {tipo_nome}",
            "(Inclua os itens cabíveis à gravidade observada; não omita o nível crítico",
            " se houver patologia crítica.)",
        ]
    )
    for sev in ("crítica", "alta", "média", "baixa"):
        items = catalog.get(sev) or []
        lines.append(f"\n[{sev.upper()}] — {len(items)} ensaio(s) de referência:")
        for t in items:
            lines.append(
                f"  • {t.get('codigo')}: {t.get('ensaio')} — {t.get('objetivo')} "
                f"({t.get('norma_ref')})"
            )
    lines.extend(
        [
            "",
            "CHECKLIST FINAL ANTES DE RESPONDER O JSON:",
            "[ ] instrumented_tests preenchido com TODOS os ensaios necessários?",
            "[ ] Ordenado do mais crítico ao menos crítico?",
            "[ ] Capítulo ensaios_instrumentados com tabela?",
            "[ ] Pedidos do profissional atendidos?",
            "[ ] Ensaios coerentes com o tipo de obra e com cada patologia?",
            "Se algum item do checklist falhar, CORRIJA antes de enviar a resposta.",
        ]
    )
    return "\n".join(lines)


# Padrões no prompt do profissional → ensaios obrigatórios
_PROMPT_ENSAIO_RULES: list[tuple[tuple[str, ...], list[dict[str, Any]]]] = [
    (
        (
            "seção transversal",
            "secao transversal",
            "sessão transversal",
            "sessao transversal",
            "área residual",
            "area residual",
            "perda de seção",
            "perda de secao",
            "espessura residual",
            "perfis e chapas",
            "chapas metálicas",
            "chapas metalicas",
            "perfis metálicos",
            "perfis metalicos",
            "corrosão avançado",
            "corrosao avancado",
            "estrutura metálica",
            "estrutura metalica",
            "ponte mista",
            "concreto e aço",
            "concreto e aco",
            "aço",
            "aco",
        ),
        [
            {
                "codigo": "EI-ACO-01",
                "ensaio": (
                    "Medição de espessura residual por ultrassom (UT) em perfis e chapas metálicas"
                ),
                "objetivo": (
                    "Quantificar a espessura remanescente de alma, mesa e chapas após corrosão, "
                    "para avaliar a redução da área da seção transversal — solicitado "
                    "explicitamente na vistoria"
                ),
                "norma_ref": "ASTM E797 / NBR 8800",
                "gravidade_alvo": "crítica",
                "necessidade_pct": 99,
                "prazo": "Imediato (até 7 dias)",
                "solicitado_pelo_profissional": True,
            },
            {
                "codigo": "EI-ACO-02",
                "ensaio": (
                    "Avaliação da perda de seção transversal / área residual de elementos metálicos"
                ),
                "objetivo": (
                    "Calcular a área efetiva remanescente de perfis e chapas corroídos e "
                    "comparar com a seção de projeto — solicitado explicitamente na vistoria"
                ),
                "norma_ref": "NBR 8800 / manuais DNIT de OAE metálicas",
                "gravidade_alvo": "crítica",
                "necessidade_pct": 98,
                "prazo": "Imediato (até 7 dias)",
                "solicitado_pelo_profissional": True,
            },
            {
                "codigo": "EI-ACO-03",
                "ensaio": "Mapeamento de corrosão e perda de massa em estrutura metálica",
                "objetivo": (
                    "Delimitar extensões e graus de corrosão nos elementos metálicos "
                    "vistoriados (perfis, chapas e ligações)"
                ),
                "norma_ref": "NBR 9452 / práticas de inspeção de OAE metálicas",
                "gravidade_alvo": "crítica",
                "necessidade_pct": 96,
                "prazo": "Imediato (até 7 dias)",
                "solicitado_pelo_profissional": True,
            },
        ],
    ),
]


def extract_requested_tests_from_prompt(user_prompt: str | None) -> list[dict[str, Any]]:
    """Extrai ensaios obrigatórios a partir do texto do profissional."""
    text = (user_prompt or "").lower()
    if not text:
        return []
    # normaliza acentos simples para match
    for a, b in (("ç", "c"), ("ã", "a"), ("á", "a"), ("é", "e"), ("í", "i"), ("ó", "o"), ("ú", "u")):
        text = text.replace(a, b)
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for keywords, tests in _PROMPT_ENSAIO_RULES:
        norm_keys = []
        for k in keywords:
            nk = k
            for a, b in (("ç", "c"), ("ã", "a"), ("á", "a"), ("é", "e"), ("í", "i"), ("ó", "o"), ("ú", "u")):
                nk = nk.replace(a, b)
            norm_keys.append(nk)
        if any(k in text for k in norm_keys):
            for t in tests:
                code = str(t.get("codigo") or "")
                if code in seen:
                    continue
                seen.add(code)
                out.append(dict(t))
    return out


def collect_severities(content: dict[str, Any]) -> list[str]:
    sevs: list[str] = []
    for p in content.get("pathologies") or []:
        if isinstance(p, dict):
            sevs.append(normalize_severity(p.get("severity")))
    for ph in content.get("photographic_report") or []:
        if isinstance(ph, dict) and ph.get("severity"):
            sevs.append(normalize_severity(ph.get("severity")))
    return sevs or ["média"]


# Necessidade base (%) por gravidade-alvo do ensaio
_NECESSIDADE_BASE = {
    "crítica": 95,
    "alta": 80,
    "média": 55,
    "baixa": 30,
}

_PRAZO_POR_SEV = {
    "crítica": "Imediato (até 7 dias)",
    "alta": "Curto prazo (até 30 dias)",
    "média": "Médio prazo (30–90 dias)",
    "baixa": "Programado (próxima campanha)",
}

_CRITICIDADE_LABEL = {
    "crítica": "Crítica",
    "alta": "Alta",
    "média": "Média",
    "baixa": "Baixa",
}


def _necessidade_pct(sev: str, *, max_rank: int, index_in_sev: int = 0) -> int:
    """
    Percentual de necessidade: base da gravidade + leve ajuste pela
    gravidade máxima do laudo e posição dentro do grupo.
    """
    base = _NECESSIDADE_BASE.get(normalize_severity(sev), 55)
    # Se o laudo tem patologia crítica, sobe um pouco os ensaios de alta/média
    boost = 0
    if max_rank >= 4 and normalize_severity(sev) in ("alta", "média"):
        boost = 5
    # Dentro do mesmo nível, os primeiros itens (mais estruturais) ficam um pouco acima
    fine = max(0, 4 - index_in_sev)
    pct = min(100, max(15, base + boost + fine - 2))
    return int(pct)


def enrich_test_row(
    raw: dict[str, Any],
    *,
    max_rank: int,
    index_in_sev: int = 0,
) -> dict[str, Any]:
    sev = normalize_severity(
        raw.get("gravidade_alvo") or raw.get("severity") or raw.get("criticidade")
    )
    pct = raw.get("necessidade_pct")
    try:
        pct_i = int(pct) if pct is not None else _necessidade_pct(sev, max_rank=max_rank, index_in_sev=index_in_sev)
    except (TypeError, ValueError):
        pct_i = _necessidade_pct(sev, max_rank=max_rank, index_in_sev=index_in_sev)
    pct_i = min(100, max(5, pct_i))
    descricao = str(
        raw.get("descricao")
        or raw.get("objetivo")
        or raw.get("description")
        or ""
    ).strip()
    return {
        "codigo": str(raw.get("codigo") or ""),
        "ensaio": str(raw.get("ensaio") or raw.get("name") or "").strip(),
        "descricao": descricao,
        "objetivo": descricao,
        "norma_ref": str(raw.get("norma_ref") or raw.get("norma") or "").strip(),
        "gravidade_alvo": sev,
        "criticidade": _CRITICIDADE_LABEL.get(sev, sev.title()),
        "necessidade_pct": pct_i,
        "prazo": str(raw.get("prazo") or _PRAZO_POR_SEV.get(sev, "A definir")),
        "pathology_refs": raw.get("pathology_refs") or [],
        "solicitado_pelo_profissional": bool(raw.get("solicitado_pelo_profissional")),
    }


def rank_and_number_tests(tests: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Ordena do mais crítico/necessário ao menos e numera Item 1..n."""
    ordered = sorted(
        tests,
        key=lambda t: (
            -int(t.get("necessidade_pct") or 0),
            -severity_rank(t.get("gravidade_alvo")),
            str(t.get("ensaio") or ""),
        ),
    )
    numbered: list[dict[str, Any]] = []
    for i, t in enumerate(ordered, start=1):
        row = dict(t)
        row["item"] = i
        numbered.append(row)
    return numbered


def suggest_tests_for_content(
    slug: str | None,
    content: dict[str, Any],
    *,
    user_prompt: str = "",
) -> list[dict[str, Any]]:
    """
    Une ensaios do catálogo + pedidos explícitos do profissional,
    com necessidade (%) e ordenação do mais crítico ao menos crítico.
    """
    catalog = catalog_for_slug(slug)
    sevs = collect_severities(content)
    max_rank = max(severity_rank(s) for s in sevs)
    if max_rank >= 4:
        needed_ranks = {4, 3, 2}
    elif max_rank == 3:
        needed_ranks = {3, 2}
    elif max_rank == 2:
        needed_ranks = {2, 1}
    else:
        needed_ranks = {1}

    # Sinais de estrutura metálica / corrosão em aço no conteúdo
    blob = " ".join(
        [
            user_prompt or "",
            str(content.get("objeto") or ""),
            str(content.get("subtitulo") or ""),
            " ".join(
                str(p.get("name") or "") + " " + str(p.get("description") or "")
                for p in (content.get("pathologies") or [])
                if isinstance(p, dict)
            ),
        ]
    ).lower()
    metal_signals = (
        "aço",
        "aco",
        "metálic",
        "metalic",
        "perfil",
        "chapa",
        "longarina",
        "ponte mista",
        "seção transversal",
        "secao transversal",
        "espessura residual",
    )
    if any(s in blob for s in metal_signals) and (slug or "") in (
        "pontes",
        "viadutos",
        "geral",
        "edificacao",
        "muro_contencao",
        "",
    ):
        # Garante pelo menos nível alta para trazer ensaios de aço
        needed_ranks.add(3)
        if max_rank >= 3 or any(
            k in blob for k in ("crítica", "critica", "precaria", "interdição", "interdicao")
        ):
            needed_ranks.add(4)

    rank_to_sev = {4: "crítica", 3: "alta", 2: "média", 1: "baixa"}
    seen: set[str] = set()
    out: list[dict[str, Any]] = []

    # 1) Pedidos explícitos do profissional — topo da lista
    for req in extract_requested_tests_from_prompt(user_prompt):
        code = str(req.get("codigo") or req.get("ensaio") or "")
        if not code or code in seen:
            continue
        seen.add(code)
        row = enrich_test_row(req, max_rank=max(max_rank, 4), index_in_sev=0)
        # Mantém % alto se veio do pedido
        if req.get("necessidade_pct"):
            try:
                row["necessidade_pct"] = int(req["necessidade_pct"])
            except (TypeError, ValueError):
                pass
        row["solicitado_pelo_profissional"] = True
        out.append(row)

    # 2) Catálogo por gravidade
    for rank in sorted(needed_ranks, reverse=True):
        sev = rank_to_sev[rank]
        for idx, t in enumerate(catalog.get(sev) or []):
            code = str(t.get("codigo") or t.get("ensaio") or "")
            if code in seen:
                continue
            seen.add(code)
            out.append(
                enrich_test_row(
                    {
                        **t,
                        "gravidade_alvo": sev,
                    },
                    max_rank=max_rank,
                    index_in_sev=idx,
                )
            )
    return rank_and_number_tests(out)


# Quantidade máxima de ensaios no corpo do laudo (protocolo); demais ficam no content JSON
ENSAIOS_EXPORT_TOP_N = 8


def ensaios_table(
    tests: list[dict[str, Any]],
    *,
    top_n: int | None = ENSAIOS_EXPORT_TOP_N,
) -> dict[str, Any]:
    """Tabela institucional: Item → Necessidade (%), do mais crítico ao menos."""
    ordered = rank_and_number_tests(list(tests))
    total = len(ordered)
    shown = ordered[: top_n] if top_n and top_n > 0 else ordered
    caption = (
        "Quadro de ensaios instrumentados prioritários — ordenados por criticidade "
        "(maior necessidade → menor necessidade)"
    )
    if top_n and total > len(shown):
        caption += (
            f" — exibindo top {len(shown)} de {total} "
            "(demais ensaios sugeridos constam no JSON técnico do laudo)"
        )
    return {
        "caption": caption,
        "headers": [
            "Item",
            "Ensaio",
            "Descrição do ensaio",
            "Criticidade",
            "Necessidade (%)",
            "Prazo recomendado",
            "Norma / ref.",
        ],
        "rows": [
            [
                str(t.get("item") or i),
                t.get("ensaio") or "—",
                t.get("descricao") or t.get("objetivo") or "—",
                t.get("criticidade") or _CRITICIDADE_LABEL.get(
                    normalize_severity(t.get("gravidade_alvo")), "—"
                ),
                f"{int(t.get('necessidade_pct') or 0)}%",
                t.get("prazo") or "—",
                t.get("norma_ref") or "—",
            ]
            for i, t in enumerate(shown, start=1)
        ],
    }


def _slug_context_label(slug: str | None) -> str:
    labels = {
        "pontes": "obras de arte especiais (pontes)",
        "viadutos": "obras de arte especiais (viadutos)",
        "edificacao": "edificações",
        "erosao": "processos erosivos e estabilização de taludes",
        "barragem": "barragens e estruturas hídricas",
        "drenagem": "sistemas de drenagem",
        "pavimentacao": "pavimentos",
        "muro_contencao": "muros de contenção / arrimo",
        "geral": "estruturas e obras civis",
    }
    return labels.get((slug or "geral").strip().lower(), "estruturas e obras civis")


def _pathology_summary(content: dict[str, Any], *, limit: int = 5) -> str:
    """Síntese curta das patologias mais graves para o texto introdutório."""
    paths = [p for p in (content.get("pathologies") or []) if isinstance(p, dict)]
    if not paths:
        # Fallback: legendas fotográficas com gravidade
        photos = [p for p in (content.get("photographic_report") or []) if isinstance(p, dict)]
        paths = [
            {
                "name": p.get("title") or p.get("legend") or f"Foto {p.get('photo_number')}",
                "severity": p.get("severity"),
                "location": "",
            }
            for p in photos
            if p.get("severity")
        ]
    if not paths:
        return ""

    ordered = sorted(paths, key=lambda p: -severity_rank(p.get("severity")))
    bits: list[str] = []
    for p in ordered[:limit]:
        name = str(p.get("name") or p.get("code") or "anomalia").strip()
        sev = _CRITICIDADE_LABEL.get(normalize_severity(p.get("severity")), "Média")
        loc = str(p.get("location") or p.get("element") or "").strip()
        if loc:
            bits.append(f"{name} ({sev}, {loc})")
        else:
            bits.append(f"{name} ({sev})")
    if len(ordered) > limit:
        bits.append(f"entre outras {len(ordered) - limit} ocorrência(s)")
    if len(bits) == 1:
        return bits[0]
    if len(bits) == 2:
        return f"{bits[0]} e {bits[1]}"
    return ", ".join(bits[:-1]) + f" e {bits[-1]}"


def build_ensaios_intro_paragraphs(
    content: dict[str, Any],
    *,
    slug: str | None,
    tests: list[dict[str, Any]],
    max_sev: str,
) -> list[str]:
    """
    Texto do capítulo de ensaios — redigido a partir do objeto e das patologias,
    sem jargão de sistema («template», «tipología»).
    """
    if not tests:
        return []

    objeto = str(content.get("objeto") or "").strip()
    local = str(content.get("local") or "").strip()
    contexto = _slug_context_label(slug)
    n_pat = len([p for p in (content.get("pathologies") or []) if isinstance(p, dict)])
    resumo = _pathology_summary(content)
    top = tests[0]
    n = len(tests)
    sev_label = _CRITICIDADE_LABEL.get(normalize_severity(max_sev), str(max_sev))

    where = ""
    if objeto and local:
        where = f" no objeto «{objeto}», situado em {local},"
    elif objeto:
        where = f" no objeto «{objeto}»,"
    elif local:
        where = f" na vistoria realizada em {local},"

    if resumo:
        diag = (
            f"A análise das anomalias{where} com destaque para {resumo}, "
            f"indica gravidade máxima {sev_label.lower()}"
        )
        if n_pat:
            diag += f" no conjunto de {n_pat} patologia(s) classificada(s)"
        diag += (
            f". Para {contexto}, recomenda-se a execução de {n} ensaio(s) "
            f"instrumentado(s), priorizados do mais crítico ao menos crítico, "
            f"a fim de confirmar o diagnóstico, dimensionar intervenções e "
            f"reduzir incertezas estruturais/geotécnicas."
        )
    else:
        diag = (
            f"Diante do quadro observado{where} e da criticidade {sev_label.lower()} "
            f"registrada na vistoria de {contexto}, recomenda-se a execução de "
            f"{n} ensaio(s) instrumentado(s), ordenados por prioridade técnica, "
            f"para aprofundar o diagnóstico e orientar o plano de correção."
        )

    prioridade = (
        f"O ensaio de maior prioridade é «{top.get('ensaio')}» "
        f"({top.get('necessidade_pct')}% de necessidade; prazo: {top.get('prazo')}). "
        f"A coluna Necessidade (%) da tabela expressa a urgência relativa de cada "
        f"ensaio frente às patologias identificadas — use o quadro para planejar "
        f"a campanha de instrumentação, o orçamento e o cronograma de intervenção."
    )
    if n > ENSAIOS_EXPORT_TOP_N:
        prioridade += (
            f" No corpo do laudo exibem-se os {ENSAIOS_EXPORT_TOP_N} ensaios de maior "
            f"necessidade (de {n} sugeridos); a lista completa permanece no registro "
            f"técnico do sistema."
        )

    legend = (
        "Critérios de necessidade: 90–100% imprescindível (ação imediata); "
        "70–89% alta prioridade; 45–69% recomendado; abaixo de 45% acompanhamento "
        "na próxima campanha. A criticidade segue a classificação das patologias "
        "(crítica, alta, média e baixa)."
    )
    return [diag, prioridade, legend]


def _attach_pathology_refs(tests: list[dict[str, Any]], content: dict[str, Any]) -> list[dict[str, Any]]:
    """Associa pathology_refs por gravidade quando o Gemini omitiu a ligação."""
    paths = [p for p in (content.get("pathologies") or []) if isinstance(p, dict)]
    if not paths:
        return tests
    by_sev: dict[str, list[str]] = {"crítica": [], "alta": [], "média": [], "baixa": []}
    for p in paths:
        code = str(p.get("code") or p.get("codigo") or "").strip()
        if not code:
            continue
        by_sev[normalize_severity(p.get("severity"))].append(code)
    out: list[dict[str, Any]] = []
    for t in tests:
        row = dict(t)
        refs = list(row.get("pathology_refs") or [])
        if not refs:
            sev = normalize_severity(row.get("gravidade_alvo"))
            # Ensaios do nível N aplicam-se a patologias com gravidade >= N
            rank = severity_rank(sev)
            linked: list[str] = []
            for s, codes in by_sev.items():
                if severity_rank(s) >= rank:
                    linked.extend(codes)
            row["pathology_refs"] = linked[:12]
        out.append(row)
    return out


def validate_ensaios_completeness(
    tests: list[dict[str, Any]],
    *,
    slug: str | None,
    content: dict[str, Any],
    user_prompt: str = "",
) -> list[str]:
    """
    Retorna lista de falhas de qualidade. Usado para log e garantia pós-Gemini.
    """
    issues: list[str] = []
    if not tests:
        issues.append("lista instrumented_tests vazia")
        return issues

    sevs = collect_severities(content)
    max_rank = max(severity_rank(s) for s in sevs)
    # Mínimos por gravidade máxima
    min_count = {4: 6, 3: 4, 2: 2, 1: 1}.get(max_rank, 2)
    if len(tests) < min_count:
        issues.append(f"poucos ensaios ({len(tests)} < mínimo {min_count} para gravidade máx.)")

    codes = {str(t.get("codigo") or "") for t in tests}
    catalog = catalog_for_slug(slug)
    if max_rank >= 4:
        crit_codes = {t.get("codigo") for t in (catalog.get("crítica") or []) if t.get("codigo")}
        missing = [c for c in list(crit_codes)[:4] if c not in codes]
        # Não exige 100% do catálogo (pode ser longo), mas sinaliza se faltou demais
        if len(missing) >= 3 and len(crit_codes) >= 3:
            issues.append("faltam vários ensaios do nível crítica do catálogo")

    req = extract_requested_tests_from_prompt(user_prompt)
    for r in req:
        code = str(r.get("codigo") or "")
        if code and code not in codes:
            issues.append(f"ensaio solicitado omitido: {code}")

    # Sem item/necessidade
    if any(not t.get("ensaio") for t in tests):
        issues.append("há ensaios sem nome")
    if any(int(t.get("necessidade_pct") or 0) < 5 for t in tests):
        issues.append("há ensaios com necessidade (%) inválida")

    return issues


def ensure_ensaios_chapter(
    content: dict[str, Any],
    *,
    slug: str | None,
    user_prompt: str = "",
) -> dict[str, Any]:
    """Garante `instrumented_tests` + capítulo dedicado no content do laudo."""
    import logging

    logger = logging.getLogger(__name__)

    out = dict(content or {})
    sevs = collect_severities(out)
    max_rank = max(severity_rank(s) for s in sevs)
    max_sev = max(sevs, key=severity_rank)

    prompt = user_prompt or str(out.get("_user_prompt") or "")
    catalog_tests = suggest_tests_for_content(slug, out, user_prompt=prompt)
    gemini_tests = out.get("instrumented_tests")
    gemini_count = len(gemini_tests) if isinstance(gemini_tests, list) else 0
    if gemini_count == 0:
        logger.warning(
            "Gemini omitiu instrumented_tests — aplicando catálogo completo "
            "(slug=%s, gravidade_max=%s)",
            slug,
            max_sev,
        )

    if isinstance(gemini_tests, list) and gemini_tests:
        # Preferir pedidos do profissional + catálogo; acrescentar extras do Gemini
        merged = list(catalog_tests)
        seen = {str(t.get("codigo") or t.get("ensaio") or "") for t in merged}
        for raw in gemini_tests:
            if not isinstance(raw, dict):
                continue
            code = str(raw.get("codigo") or raw.get("ensaio") or raw.get("name") or "")
            if not code or code in seen:
                continue
            seen.add(code)
            merged.append(enrich_test_row(raw, max_rank=max_rank))
        tests = rank_and_number_tests(merged)
    else:
        tests = catalog_tests

    # Reaplica item + % após merge (pedidos do profissional ficam no topo pelo %)
    tests = rank_and_number_tests([enrich_test_row(t, max_rank=max(max_rank, 4)) for t in tests])
    # Reaplica % dos solicitados explicitamente
    for t in tests:
        if t.get("solicitado_pelo_profissional") and t.get("codigo") in (
            "EI-ACO-01",
            "EI-ACO-02",
            "EI-ACO-03",
        ):
            if t["codigo"] == "EI-ACO-01":
                t["necessidade_pct"] = max(int(t.get("necessidade_pct") or 0), 99)
            elif t["codigo"] == "EI-ACO-02":
                t["necessidade_pct"] = max(int(t.get("necessidade_pct") or 0), 98)
            else:
                t["necessidade_pct"] = max(int(t.get("necessidade_pct") or 0), 96)
    tests = _attach_pathology_refs(tests, out)
    tests = rank_and_number_tests(tests)

    issues = validate_ensaios_completeness(
        tests, slug=slug, content=out, user_prompt=prompt
    )
    if issues:
        logger.warning(
            "Ensaios instrumentados — falhas de qualidade corrigidas/sinalizadas: %s",
            "; ".join(issues),
        )
        # Repara: se faltou pedido explícito, reinsere do extract
        if any("solicitado omitido" in i for i in issues):
            seen = {str(t.get("codigo") or "") for t in tests}
            for req in extract_requested_tests_from_prompt(prompt):
                code = str(req.get("codigo") or "")
                if code and code not in seen:
                    tests.insert(0, enrich_test_row(req, max_rank=4))
                    seen.add(code)
            tests = _attach_pathology_refs(tests, out)
            tests = rank_and_number_tests(tests)

    if not tests:
        # Última linha de defesa: catálogo médio do slug
        tests = suggest_tests_for_content(slug, out, user_prompt=prompt)
        tests = _attach_pathology_refs(tests, out)

    out["instrumented_tests"] = tests
    out["ensaios_quality"] = {
        "gemini_count": gemini_count,
        "final_count": len(tests),
        "issues": issues,
        "slug": slug,
        "max_severity": max_sev,
    }
    if not tests:
        return out

    table = ensaios_table(tests)
    top = tests[0]
    intro_paras = build_ensaios_intro_paragraphs(
        out, slug=slug, tests=tests, max_sev=max_sev
    )

    chapters = list(out.get("chapters") or [])
    found = False
    for ch in chapters:
        cid = str(ch.get("id") or "").lower()
        title_l = str(ch.get("title") or "").lower()
        if cid == "ensaios_instrumentados" or "ensaios instrumentados" in title_l:
            ch["id"] = "ensaios_instrumentados"
            ch["title"] = "Ensaios instrumentados prioritários"
            ch["paragraphs"] = list(intro_paras)
            tables = [
                t
                for t in (ch.get("tables") or [])
                if "ensaios instrumentados" not in str(t.get("caption") or "").lower()
                and "quadro de ensaios" not in str(t.get("caption") or "").lower()
            ]
            tables.insert(0, table)
            ch["tables"] = tables
            found = True
            break

    if not found:
        insert_at = len(chapters)
        for i, ch in enumerate(chapters):
            cid = str(ch.get("id") or "").lower()
            if cid in ("conclusao", "referencias", "fotografico", "cronograma", "interdicao"):
                insert_at = i
                break
        chapters.insert(
            insert_at,
            {
                "id": "ensaios_instrumentados",
                "title": "Ensaios instrumentados prioritários",
                "paragraphs": list(intro_paras),
                "tables": [table],
                "charts": [],
            },
        )
    out["chapters"] = chapters

    conclusions = list(out.get("conclusions") or [])
    objeto = str(out.get("objeto") or "o objeto vistoriado").strip()
    note = (
        f"Para {objeto}, recomenda-se {len(tests)} ensaio(s) instrumentado(s) "
        f"em função das patologias de gravidade até {max_sev} "
        f"(prioridade: {top.get('ensaio')} — {top.get('necessidade_pct')}%). "
        f"Detalhamento no capítulo de ensaios instrumentados."
    )
    # Atualiza nota de conclusão se já existir menção genérica antiga
    replaced = False
    for i, c in enumerate(conclusions):
        if "ensaio" in str(c).lower():
            conclusions[i] = note
            replaced = True
            break
    if not replaced:
        conclusions.append(note)
    out["conclusions"] = conclusions

    return out


def report_wants_ensaios(report: Any = None, content: dict[str, Any] | None = None) -> bool:
    """True se a flag do laudo ou do JSON pedir ensaios instrumentados."""
    if report is not None and bool(getattr(report, "suggest_instrumented_tests", False)):
        return True
    data = content if content is not None else (getattr(report, "content", None) if report is not None else None)
    if isinstance(data, dict) and data.get("suggest_instrumented_tests"):
        return True
    return False


def apply_instrumented_tests_to_content(
    content: dict[str, Any] | None,
    *,
    slug: str | None,
    enabled: bool,
    user_prompt: str = "",
) -> dict[str, Any]:
    """
    Aplica/atualiza capítulo e tabela de ensaios quando `enabled`.
    Sempre reordena o sumário depois, para o capítulo aparecer na lista.
    """
    from core.inspection_report.format_utils import ensure_sumario_chapter

    out = dict(content or {})
    out["suggest_instrumented_tests"] = bool(enabled)
    if enabled:
        out = ensure_ensaios_chapter(out, slug=slug, user_prompt=user_prompt)
        # Reforço em parecer / plano de correção (texto visível mesmo em leitura rápida)
        out = _inject_ensaios_mentions(out)
    out = ensure_sumario_chapter(out)
    return out


def _inject_ensaios_mentions(content: dict[str, Any]) -> dict[str, Any]:
    out = dict(content)
    tests = out.get("instrumented_tests") or []
    if not tests:
        return out
    n = len(tests)
    top = tests[0]
    mention = (
        f"Recomenda-se campanha de {n} ensaio(s) instrumentado(s), priorizados por "
        f"necessidade (Item 1: {top.get('ensaio')} — {top.get('necessidade_pct')}%, "
        f"prazo {top.get('prazo')}). Ver capítulo «Ensaios Instrumentados Sugeridos»."
    )
    chapters = list(out.get("chapters") or [])
    for ch in chapters:
        if not isinstance(ch, dict):
            continue
        cid = str(ch.get("id") or "").lower()
        title_l = str(ch.get("title") or "").lower()
        if cid in ("plano_correcao", "parecer", "conclusao") or "plano" in title_l or "parecer" in title_l or "conclus" in title_l:
            paras = [str(p) for p in (ch.get("paragraphs") or [])]
            if not any("ensaio" in p.lower() and "instrumentad" in p.lower() for p in paras):
                paras.append(mention)
                ch["paragraphs"] = paras
    out["chapters"] = chapters
    return out


def chapters_with_ensaios(chapters: list[dict] | None) -> list[dict]:
    """Garante o id de capítulo no template enviado ao Gemini."""
    chs = [dict(c) for c in (chapters or [])]
    for c in chs:
        if str(c.get("id") or "").lower() == "ensaios_instrumentados":
            return chs
    insert_at = len(chs)
    for i, c in enumerate(chs):
        if str(c.get("id") or "").lower() in ("conclusao", "referencias", "fotografico"):
            insert_at = i
            break
    chs.insert(
        insert_at,
        {
            "id": "ensaios_instrumentados",
            "title": "Ensaios Instrumentados Sugeridos",
            "required": True,
        },
    )
    return chs
