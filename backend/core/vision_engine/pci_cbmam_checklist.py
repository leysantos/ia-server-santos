"""Checklist IT-11 / NT-03 / PSCIP simplificado — cruzamento multi-arquivo."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Iterable


@dataclass
class ChecklistItemResult:
    id: str
    norma: str
    titulo: str
    descricao: str
    status: str  # conforme | parcial | pendente | nao_aplicavel
    evidencias: list[str] = field(default_factory=list)
    observacao: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "norma": self.norma,
            "titulo": self.titulo,
            "descricao": self.descricao,
            "status": self.status,
            "evidencias": self.evidencias,
            "observacao": self.observacao,
        }


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").lower()).strip()


def _blob(row: dict[str, Any]) -> str:
    parts: list[str] = [row.get("filename") or ""]
    ocr = row.get("ocr") or {}
    if isinstance(ocr, dict):
        parts.append(str(ocr.get("texto") or ""))
    analysis = row.get("analysis") or {}
    if isinstance(analysis, dict):
        parts.append(str(analysis))
        parts.append(str(analysis.get("resumo_tecnico") or ""))
        for key in (
            "inconsistencias",
            "nao_conformidades",
            "recomendacoes",
            "rotas_fuga",
            "saidas_emergencia",
            "sinalizacao",
        ):
            val = analysis.get(key)
            if val:
                parts.append(str(val))
    tech = row.get("technical_report") or {}
    if isinstance(tech, dict):
        parts.append(str(tech))
    return _norm(" ".join(parts))


def _match_name(filename: str, patterns: Iterable[str]) -> bool:
    name = _norm(filename)
    return any(p in name for p in patterns)


def _find_rows(rows: list[dict[str, Any]], patterns: Iterable[str]) -> list[dict[str, Any]]:
    return [r for r in rows if _match_name(r.get("filename") or "", patterns)]


def _has_any(text: str, keywords: Iterable[str]) -> bool:
    return any(k in text for k in keywords)


def _status_from_flags(found: bool, partial: bool = False) -> str:
    if found:
        return "conforme"
    if partial:
        return "parcial"
    return "pendente"


def run_pci_cbmam_checklist(analyses: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Avalia conformidade PSCIP simplificado cruzando todos os arquivos analisados.
    `analyses`: lista com filename, analysis, ocr, technical_report (como vision_json).
    """
    rows = [a for a in analyses if not a.get("skipped")]
    corpus = " ".join(_blob(r) for r in rows)

    ppci_rows = _find_rows(rows, ("ppci", "ppc i"))
    mem_calc_rows = _find_rows(
        rows,
        ("memória de cálculo", "memoria de calculo", "item-03", "população", "populacao"),
    )
    termo_nt03_rows = _find_rows(
        rows,
        ("termo de responsabilidade", "item-04", "porta de correr", "portão de correr"),
    )
    memorial_rows = _find_rows(
        rows,
        ("memorial descritivo", "item-02-md", "item-02", "md_ppci"),
    )
    carta_rows = _find_rows(rows, ("obs-02", "carta resposta", "parecer técnico", "parecer tecnico"))

    items: list[ChecklistItemResult] = []

    # --- IT-11 ---
    mem_text = " ".join(_blob(r) for r in mem_calc_rows)
    has_pop = _has_any(
        mem_text or corpus,
        ("população", "populacao", "94 pessoa", "94 pessoas", "carga de incêndio", "carga de incendio"),
    )
    has_up = _has_any(mem_text or corpus, ("2 up", "duas up", "2 unidades", "unidade de passagem"))
    items.append(
        ChecklistItemResult(
            id="it11_memoria_populacao",
            norma="IT-11",
            titulo="Memória de população e carga de incêndio",
            descricao="Documento com cálculo de população/ocupação e carga conforme IT-11 CBMAM.",
            status=_status_from_flags(bool(mem_calc_rows) and has_pop),
            evidencias=[r["filename"] for r in mem_calc_rows],
            observacao="Arquivo ITEM-03 ou equivalente com população declarada."
            if not has_pop
            else "População/carga identificada na memória.",
        )
    )

    items.append(
        ChecklistItemResult(
            id="it11_dimensionamento_saidas",
            norma="IT-11",
            titulo="Dimensionamento de saídas de emergência (UP)",
            descricao="Quantidade/largura de UP dimensionada (ex.: 2 UP para 94 pessoas).",
            status=_status_from_flags(has_up, partial=has_pop and not has_up),
            evidencias=[r["filename"] for r in mem_calc_rows or ppci_rows],
            observacao="Verificar memória IT-11 com número de UP e larguras mínimas.",
        )
    )

    e5_found = _has_any(corpus, ("e-5", "e5", "educacional", "escola", "creche", "ensino"))
    items.append(
        ChecklistItemResult(
            id="it11_tipo_ocupacao_e5",
            norma="IT-11",
            titulo="Tipo de ocupação E-5 (educacional) declarado",
            descricao="Projeto identifica ocupação CBMAM E-5 ou equivalente educacional.",
            status=_status_from_flags(
                _has_any(corpus, ("e-5", " e5", "ocupação e-5", "ocupacao e-5")),
                partial=e5_found,
            ),
            evidencias=[
                r["filename"]
                for r in rows
                if _has_any(_blob(r), ("e-5", "e5", "educacional", "escola"))
            ],
            observacao="Campo tipo_edificacao deve conter código E-5 explícito.",
        )
    )

    rotas_ok = False
    rotas_partial = False
    rotas_evidencias: list[str] = []
    for r in ppci_rows:
        analysis = r.get("analysis") or {}
        rotas = analysis.get("rotas_fuga") or []
        text = _blob(r)
        if rotas and len(rotas) > 0:
            rotas_ok = True
            rotas_evidencias.append(r["filename"])
        elif _has_any(text, ("rota de fuga", "rotas de fuga", "tracejada", "tracejado", "fluxo de saída")):
            rotas_partial = True
            rotas_evidencias.append(r["filename"])
    items.append(
        ChecklistItemResult(
            id="it11_rotas_fuga_demarcadas",
            norma="IT-11 / NBR 9077",
            titulo="Rotas de fuga demarcadas na planta PPCI",
            descricao="Planta com rotas tracejadas/setas de fluxo até saídas de emergência.",
            status=_status_from_flags(rotas_ok, partial=rotas_partial),
            evidencias=rotas_evidencias or [r["filename"] for r in ppci_rows],
            observacao="Campo rotas_fuga vazio na análise visual — exige overlay gráfico na prancha.",
        )
    )

    sinal_ok = False
    sinal_evid: list[str] = []
    for r in ppci_rows:
        analysis = r.get("analysis") or {}
        sinal = analysis.get("sinalizacao") or []
        if sinal:
            sinal_ok = True
            sinal_evid.append(r["filename"])
        elif _has_any(_blob(r), ("sinalização", "sinalizacao", "iluminação de emergência", "placa de saída")):
            sinal_ok = True
            sinal_evid.append(r["filename"])
    items.append(
        ChecklistItemResult(
            id="it11_sinalizacao_emergencia",
            norma="IT-11 / NBR 10898",
            titulo="Sinalização de emergência",
            descricao="Sinalização fotoluminescente/elétrica e placas de saída indicadas.",
            status=_status_from_flags(sinal_ok),
            evidencias=sinal_evid or [r["filename"] for r in ppci_rows],
        )
    )

    corrimao = _has_any(corpus, ("corrimão", "corrimao", "corrimãos", "corrimãos"))
    items.append(
        ChecklistItemResult(
            id="it11_corrimao_rampa",
            norma="IT-11",
            titulo="Corrimãos em rampas da rota de fuga",
            descricao="Detalhamento de corrimãos conforme exigência CBMAM em rampas de fuga.",
            status=_status_from_flags(corrimao),
            evidencias=[r["filename"] for r in carta_rows + memorial_rows if corrimao],
            observacao="Exigência comum em carta de resposta ao parecer (OBS-02).",
        )
    )

    largura = _has_any(
        corpus,
        ("largura do corredor", "corredor", "hall salas", "salas 4 e 5", "largura mínima"),
    )
    items.append(
        ChecklistItemResult(
            id="it11_largura_corredor",
            norma="IT-11",
            titulo="Largura de corredor/rota de fuga adequada",
            descricao="Corredores e rotas com largura mínima conforme IT-11/NBR 9077.",
            status=_status_from_flags(largura, partial=_has_any(corpus, ("corredor", "hall"))),
            evidencias=[r["filename"] for r in carta_rows + ppci_rows if largura],
        )
    )

    ext_ok = False
    for r in ppci_rows:
        analysis = r.get("analysis") or {}
        if analysis.get("hidrantes_mangotinhos") or analysis.get("sprinklers"):
            ext_ok = True
        if _has_any(_blob(r), ("extintor", "hidrante", "mangotinho")):
            ext_ok = True
    items.append(
        ChecklistItemResult(
            id="it11_extintores_hidrantes",
            norma="IT-11",
            titulo="Extintores / hidrantes na planta PPCI",
            descricao="Equipamentos de combate a incêndio indicados e dimensionados.",
            status=_status_from_flags(ext_ok),
            evidencias=[r["filename"] for r in ppci_rows],
        )
    )

    # --- NT-03 ---
    portao_fuga = False
    portao_files: list[str] = []
    for r in ppci_rows:
        if _has_any(_blob(r), ("portão", "portao", "metalon", "correr", "deslizante")):
            portao_fuga = True
            portao_files.append(r["filename"])
    termo_ok = bool(termo_nt03_rows)
    items.append(
        ChecklistItemResult(
            id="nt03_termo_porta_correr",
            norma="NT-03",
            titulo="Termo de responsabilidade — porta/portão de correr",
            descricao="NT-03 assinada quando há porta/portão de correr na rota de fuga.",
            status=_status_from_flags(termo_ok) if portao_fuga else "nao_aplicavel",
            evidencias=[r["filename"] for r in termo_nt03_rows],
            observacao="Obrigatório se portão de correr estiver na rota de fuga."
            if portao_fuga and not termo_ok
            else "",
        )
    )

    items.append(
        ChecklistItemResult(
            id="nt03_portao_rota_fuga",
            norma="NT-03",
            titulo="Portão/porta de correr identificado na rota de fuga",
            descricao="Planta indica portão de correr e vincula à NT-03.",
            status=_status_from_flags(portao_fuga and termo_ok, partial=portao_fuga),
            evidencias=portao_files,
        )
    )

    # --- PSCIP simplificado ---
    items.append(
        ChecklistItemResult(
            id="pscip_memorial_descritivo",
            norma="PSCIP",
            titulo="Memorial descritivo PCI assinado",
            descricao="Memorial descritivo do PPCI (ITEM-02 ou equivalente).",
            status=_status_from_flags(bool(memorial_rows)),
            evidencias=[r["filename"] for r in memorial_rows],
        )
    )

    items.append(
        ChecklistItemResult(
            id="pscip_planta_ppci",
            norma="PSCIP",
            titulo="Planta PPCI legível",
            descricao="Prancha PPCI com saídas, rotas, sinalização e equipamentos.",
            status=_status_from_flags(bool(ppci_rows)),
            evidencias=[r["filename"] for r in ppci_rows],
        )
    )

    items.append(
        ChecklistItemResult(
            id="pscip_carta_resposta",
            norma="PSCIP",
            titulo="Carta resposta ao parecer técnico CBMAM",
            descricao="Documento respondendo exigências do processo (OBS-02).",
            status=_status_from_flags(bool(carta_rows)),
            evidencias=[r["filename"] for r in carta_rows],
        )
    )

    assin_ok = _has_any(
        corpus,
        ("assinatura", "assinado", "credenciamento", "rt ", "responsável técnico", "responsavel tecnico"),
    )
    items.append(
        ChecklistItemResult(
            id="pscip_assinaturas_credenciamento",
            norma="PSCIP",
            titulo="Assinaturas / credenciamento RT",
            descricao="Pranchas e memoriais com assinatura e RT credenciado CBMAM.",
            status=_status_from_flags(assin_ok, partial=_has_any(corpus, ("rt", "crea"))),
            evidencias=[r["filename"] for r in rows if _has_any(_blob(r), ("assin", "crea", "rt"))],
        )
    )

    # RAG audit — verifica se análises usaram knowledge layer
    rag_used = sum(1 for r in rows if (r.get("rag_sources") or r.get("normative_context")))
    rag_hits = sum(int((r.get("normative_context") or {}).get("hits_count") or 0) for r in rows)

    counts = {"conforme": 0, "parcial": 0, "pendente": 0, "nao_aplicavel": 0}
    for it in items:
        counts[it.status] = counts.get(it.status, 0) + 1

    aplicaveis = [it for it in items if it.status != "nao_aplicavel"]
    score = 0.0
    if aplicaveis:
        score = round(
            sum(1.0 if it.status == "conforme" else 0.5 if it.status == "parcial" else 0.0 for it in aplicaveis)
            / len(aplicaveis)
            * 100,
            1,
        )

    by_id = {it.id: it for it in items}
    rotas_ok = by_id.get("it11_rotas_fuga_demarcadas", ChecklistItemResult("", "", "", "", "pendente")).status == "conforme"
    pronto = (
        score >= 90
        and counts["pendente"] == 0
        and rotas_ok
        and by_id.get("it11_memoria_populacao", ChecklistItemResult("", "", "", "", "pendente")).status == "conforme"
    )

    return {
        "total_itens": len(items),
        "conformes": counts["conforme"],
        "parciais": counts["parcial"],
        "pendentes": counts["pendente"],
        "nao_aplicaveis": counts["nao_aplicavel"],
        "score_percent": score,
        "pronto_cbmam": pronto,
        "arquivos_analisados": len(rows),
        "rag_audit": {
            "analises_com_rag": rag_used,
            "total_analises": len(rows),
            "hits_normativos_totais": rag_hits,
            "rag_ativo_no_pipeline": rag_used > 0,
            "observacao": (
                "Modelos consultaram a Knowledge Layer (trechos CBMAM/NBR injetados no prompt)."
                if rag_used
                else "Análises anteriores sem RAG — reexecute em modo PCI para injetar normas indexadas."
            ),
        },
        "itens": [it.to_dict() for it in items],
    }
