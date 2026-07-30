"""Pipeline OrçaFacil: ingest → index_base → vision → plan → resolve → mount → save DB."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Callable

from pricing.budget.orca_facil import job_store
from pricing.budget.orca_facil.base_index import ModelPriceBaseIndex, build_base_index_from_model
from pricing.budget.orca_facil.gemini_orca import run_p1_project_info, run_p2_plan
from pricing.budget.orca_facil.example_tree import extract_example_tree, map_example_codes_to_model_base
from pricing.budget.orca_facil.session_builder import build_session_from_plan
from pricing.budget.orca_facil.model_writer import write_plan_to_model_copy

logger = logging.getLogger(__name__)

ProgressCb = Callable[[str, int, str], None]


def _path(val: Any) -> Path | None:
    if not val:
        return None
    p = Path(str(val))
    return p if p.is_file() else None


def _paths(vals: list[Any] | None) -> list[Path]:
    out: list[Path] = []
    for v in vals or []:
        p = _path(v)
        if p:
            out.append(p)
    return out


def _item_qty(item: dict[str, Any]) -> float:
    raw = item.get("qty")
    try:
        return float(raw if raw is not None else 0)
    except (TypeError, ValueError):
        return 0.0


def _trunc2(value: float) -> float:
    """Paridade Excel TRUNC(x, 2) — truncamento em direção a zero."""
    import math

    return math.trunc(float(value) * 100) / 100.0


def _line_total_with_bdi(qty: float, unit_price: float, bdi_rate: float) -> float:
    """Paridade PLANILHA: PU_c/BDI = TRUNC(PU*(1+BDI),2); total = TRUNC(qtd*PU_c/BDI,2)."""
    pu_bdi = _trunc2(unit_price * (1.0 + bdi_rate))
    return _trunc2(qty * pu_bdi)


def _resolve_bdi_rates(obra_type: str | None) -> tuple[str, float, float]:
    from pricing.budget.bdi_types import get_obra_bdi

    rates = get_obra_bdi(obra_type)
    return rates.code, float(rates.rate_com_desoneracao), float(rates.rate_sem_desoneracao)


def _items_totals(
    items: list[dict[str, Any]],
    *,
    bdi_comd: float = 0.0,
    bdi_semd: float = 0.0,
    with_bdi: bool = True,
) -> tuple[float, float]:
    """Totais ComD/SemD. Com with_bdi=True (default) espelha a planilha modelo."""
    comd = 0.0
    semd = 0.0
    for it in items:
        qty = _item_qty(it)
        pc = it.get("price_comd")
        ps = it.get("price_semd")
        if pc is not None:
            try:
                pu = float(pc)
                comd += _line_total_with_bdi(qty, pu, bdi_comd) if with_bdi else qty * pu
            except (TypeError, ValueError):
                pass
        if ps is not None:
            try:
                pu = float(ps)
                semd += _line_total_with_bdi(qty, pu, bdi_semd) if with_bdi else qty * pu
            except (TypeError, ValueError):
                pass
    return comd, semd


def enrich_plan_prices(plan: dict[str, Any], base_index: ModelPriceBaseIndex) -> dict[str, Any]:
    """Preenche price_comd/price_semd nos itens a partir da base do modelo."""
    for stage in plan.get("stages") or []:
        for item in stage.get("items") or []:
            code = str(item.get("code") or "").strip()
            if not code:
                continue
            row = base_index.get_by_code(code)
            if row:
                item["price_comd"] = row.price_comd
                item["price_semd"] = row.price_semd
        for sub in stage.get("subetapas") or []:
            for item in sub.get("items") or []:
                code = str(item.get("code") or "").strip()
                if not code:
                    continue
                row = base_index.get_by_code(code)
                if row:
                    item["price_comd"] = row.price_comd
                    item["price_semd"] = row.price_semd
    return plan


def _build_preview(
    plan: dict[str, Any],
    session_dict: dict[str, Any] | None,
    *,
    obra_type: str | None = None,
) -> dict[str, Any]:
    bdi_code, bdi_comd, bdi_semd = _resolve_bdi_rates(obra_type)
    stages = []
    total_comd = 0.0
    total_semd = 0.0
    cost_comd = 0.0
    cost_semd = 0.0
    for st in plan.get("stages") or []:
        items = list(st.get("items") or [])
        for sub in st.get("subetapas") or []:
            items.extend(list(sub.get("items") or []))
        stage_comd, stage_semd = _items_totals(items, bdi_comd=bdi_comd, bdi_semd=bdi_semd, with_bdi=True)
        stage_cost_c, stage_cost_s = _items_totals(items, with_bdi=False)
        total_comd += stage_comd
        total_semd += stage_semd
        cost_comd += stage_cost_c
        cost_semd += stage_cost_s
        stages.append(
            {
                "name": st.get("name"),
                "n_services": len(items),
                "codes": [str(i.get("code") or "") for i in items if i.get("code")][:12],
                "sample_memory": (items[0].get("memory") if items else "") or "",
                "total_comd": round(stage_comd, 2),
                "total_semd": round(stage_semd, 2),
                "cost_comd": round(stage_cost_c, 2),
                "cost_semd": round(stage_cost_s, 2),
            }
        )
    return {
        "stages": stages,
        "n_etapas": len(stages),
        "n_services": sum(int(s.get("n_services") or 0) for s in stages),
        "total_comd": round(total_comd, 2),
        "total_semd": round(total_semd, 2),
        "cost_comd": round(cost_comd, 2),
        "cost_semd": round(cost_semd, 2),
        "bdi_obra_type": bdi_code,
        "bdi_rate_comd": bdi_comd,
        "bdi_rate_semd": bdi_semd,
        "grand_total": (session_dict or {}).get("grand_total") or round(total_comd, 2),
        "title": (session_dict or {}).get("title"),
    }


def _persist_budget(
    session_dict: dict[str, Any],
    *,
    title: str,
    user_id: Any = None,
    budget_id: str | None = None,
) -> dict[str, Any] | None:
    """Salva orçamento no PostgreSQL (mesmo fluxo do Lançar Preços)."""
    try:
        from core.database.connection import SessionLocal, is_db_enabled
        from core.database.models import User
        from app.services.budget_db_service import save_budget, session_from_payload
    except Exception as exc:
        logger.warning("Persistência OrçaFacil indisponível: %s", exc)
        return None

    if not is_db_enabled():
        logger.warning("DB desabilitado — OrçaFacil não persistiu orçamento")
        return None

    db = SessionLocal()
    try:
        user = db.get(User, user_id) if user_id else None
        saved = save_budget(
            db,
            session_dict,
            title=title,
            budget_id=budget_id,
            user=user,
            sync_composition_snapshots=False,
        )
        session_from_payload(saved)
        return saved
    except Exception as exc:
        logger.exception("Falha ao salvar orçamento OrçaFacil: %s", exc)
        return None
    finally:
        db.close()


def rewrite_workbook_from_plan(job_id: str) -> dict[str, Any]:
    """Regrava a cópia do modelo a partir do plan atual (após edição no editor MCQ)."""
    job = job_store.get_job(job_id)
    if not job:
        raise KeyError(job_id)
    modelo = _path((job.get("files") or {}).get("modelo"))
    if not modelo:
        raise ValueError("Planilha modelo ausente")
    plan = job.get("plan")
    if not isinstance(plan, dict) or not plan.get("stages"):
        raise ValueError("Plano vazio — nada para gravar")

    project_info = dict(job.get("project_info") or {})
    premissas = dict(job.get("premissas") or {})
    obra_type = str(project_info.get("obra_type") or premissas.get("obra_type") or "ED")
    plan = dict(plan)
    base_index = None
    try:
        base_index = build_base_index_from_model(modelo)
        enrich_plan_prices(plan, base_index)
    except Exception as exc:
        logger.warning("Não foi possível enriquecer preços no rewrite: %s", exc)
    dest = job_store._job_dir(job_id) / "output" / f"ORCAFACIL_{job_id}.xlsm"
    dest.parent.mkdir(parents=True, exist_ok=True)
    wb_stats = write_plan_to_model_copy(
        modelo_path=modelo,
        dest_path=dest,
        plan=plan,
        project_info=project_info,
        premissas=premissas,
        base_index=base_index,
    )
    preview = _build_preview(plan, None, obra_type=obra_type)
    preview["workbook_n_servicos"] = wb_stats.get("n_servicos")
    preview["workbook_n_etapas"] = wb_stats.get("n_etapas")
    return job_store.update_job(
        job_id,
        plan=plan,
        workbook_path=str(dest),
        workbook_stats=wb_stats,
        preview=preview,
    )


def run_orca_facil_job(job_id: str, *, progress: ProgressCb | None = None) -> dict[str, Any]:
    def emit(phase: str, pct: int, msg: str) -> None:
        try:
            job_store.append_event(job_id, phase, pct, msg)
        except Exception:
            pass
        if progress:
            progress(phase, pct, msg)

    job = job_store.get_job(job_id)
    if not job:
        raise KeyError(job_id)

    job_store.update_job(job_id, status="running", error=None)
    emit("ingest", 5, "Validando arquivos…")

    files = job.get("files") or {}
    modelo = _path(files.get("modelo"))
    if not modelo:
        job_store.update_job(job_id, status="error", error="Planilha modelo obrigatória")
        emit("error", 0, "Planilha modelo obrigatória")
        raise ValueError("Planilha modelo obrigatória")

    exemplo = _path(files.get("exemplo"))
    pranchas = _paths(files.get("pranchas"))
    fotos = _paths(files.get("fotos"))
    premissas = dict(job.get("premissas") or {})
    user_prompt = str(job.get("user_prompt") or "").strip()
    etapas_seed = list(job.get("etapas_seed") or [])
    if not etapas_seed:
        etapas_seed = [
            {"name": "ADMINISTRAÇÃO DA OBRA"},
            {"name": "SERVIÇOS PRELIMINARES"},
            {"name": "TRABALHOS EM TERRA"},
            {"name": "DRENAGEM"},
            {"name": "CONTENÇÕES DE ATERRO"},
            {"name": "PAISAGISMO"},
            {"name": "SERVIÇOS FINAIS"},
        ]
        job_store.update_job(job_id, etapas_seed=etapas_seed)

    emit("index_base", 15, "Indexando base de preços do modelo…")
    base_index: ModelPriceBaseIndex = build_base_index_from_model(modelo)
    if base_index.size == 0:
        raise ValueError("Base de preços não encontrada na planilha modelo (aba Base_*)")
    job_store.update_job(job_id, base_summary=base_index.to_summary())

    emit("vision_project_info", 30, "Extraindo dados da obra nas pranchas…")
    p1 = run_p1_project_info(
        prancha_paths=pranchas,
        foto_paths=fotos,
        premissas=premissas,
        user_prompt=user_prompt,
        progress=emit,
    )
    project_info = dict(p1.get("project_info") or {})
    quantities = list(p1.get("quantities") or [])
    if not project_info.get("obra_type"):
        project_info["obra_type"] = premissas.get("obra_type") or "ED"
    job_store.update_job(job_id, project_info=project_info, quantities=quantities)

    emit("example", 40, "Extraindo árvore da planilha exemplo…")
    example_tree = extract_example_tree(exemplo)

    def _ex_search(query: str, top_k: int = 3) -> list:
        return base_index.search_base(query, top_k=top_k)

    example_mapped = map_example_codes_to_model_base(
        example_tree,
        get_by_code=base_index.get_by_code,
        search_base=_ex_search,
    )
    job_store.update_job(
        job_id,
        example_summary={
            "source": example_tree.get("source"),
            "n_etapas": example_tree.get("n_etapas"),
            "n_servicos": example_tree.get("n_servicos"),
            "mapped_n_servicos": example_mapped.get("n_servicos"),
        },
    )
    if example_tree.get("n_servicos"):
        emit(
            "example",
            42,
            f"Exemplo: {example_tree.get('n_etapas')} etapas · "
            f"{example_tree.get('n_servicos')} serviços "
            f"(mapeados: {example_mapped.get('n_servicos')})",
        )

    def search_fn(query: str, top_k: int = 6) -> list[dict[str, Any]]:
        return [
            {
                "code": row.code,
                "description": row.description[:160],
                "unit": row.unit,
                "score": score,
            }
            for row, score in base_index.search_base(query, top_k=top_k)
        ]

    emit("plan", 50, "Gerando composições e memórias de cálculo (Gemini 3.6)…")
    plan = run_p2_plan(
        etapas_seed=etapas_seed,
        project_info=project_info,
        quantities=quantities,
        premissas=premissas,
        base_sample=base_index.sample_for_prompt(limit=50),
        example_tree=example_tree,
        example_mapped=example_mapped,
        user_prompt=user_prompt,
        prancha_paths=pranchas,
        search_fn=search_fn,
        progress=emit,
    )
    emit("resolve_prices", 68, "Resolvendo preços na base do modelo…")
    enrich_plan_prices(plan, base_index)
    job_store.update_job(job_id, plan=plan)
    emit("mount", 78, "Montando sessão auxiliar de orçamento…")
    title = str(
        job.get("title")
        or project_info.get("orcamento")
        or project_info.get("objeto")
        or "OrçaFacil"
    )
    built = build_session_from_plan(
        plan=plan,
        project_info=project_info,
        base_index=base_index,
        obra_type=str(premissas.get("obra_type") or project_info.get("obra_type") or "ED"),
        title=title,
    )

    warnings = list(built.get("warnings") or [])
    if p1.get("fallback"):
        warnings.append("Gemini P1 indisponível — cabeçalho/qtds parciais (premissas)")
    if plan.get("fallback"):
        warnings.append("Gemini P2 indisponível — plano a partir do exemplo/heurística; revise")
    if not exemplo:
        warnings.append("Sem planilha exemplo — densidade de serviços pode ficar abaixo do ouro")
    if not user_prompt:
        warnings.append("Sem prompt do engenheiro — considere descrever a obra antes de regenerar")

    session_dict = built.get("session") or {}
    session_id = built.get("session_id") or session_dict.get("session_id")

    emit("write_model", 85, "Escrevendo MCQ + CURVA_ABC + CRONOGRAMA no modelo…")
    dest = job_store._job_dir(job_id) / "output" / f"ORCAFACIL_{job_id}.xlsm"
    try:
        wb_stats = write_plan_to_model_copy(
            modelo_path=modelo,
            dest_path=dest,
            plan=plan,
            project_info=project_info,
            premissas=premissas,
            base_index=base_index,
        )
        workbook_path = str(dest)
        if wb_stats.get("n_servicos", 0) < 15:
            warnings.append(
                f"Poucos serviços na planilha modelo ({wb_stats.get('n_servicos')}) — "
                "revise etapas/exemplo/prompt; ouro CONT_DREN tem 39."
            )
        abc = (wb_stats.get("abc_cronograma") or {}).get("curva_abc") or {}
        crono = (wb_stats.get("abc_cronograma") or {}).get("cronograma") or {}
        if abc.get("n_itens"):
            emit(
                "write_model",
                88,
                f"CURVA_ABC: {abc.get('n_itens')} itens · CRONOGRAMA: "
                f"{crono.get('n_etapas')} etapas / {crono.get('n_meses')} meses",
            )
        if (wb_stats.get("abc_cronograma") or {}).get("error"):
            warnings.append(f"ABC/CRONO parcial: {wb_stats['abc_cronograma']['error']}")
    except Exception as exc:
        logger.exception("Falha ao escrever modelo: %s", exc)
        workbook_path = None
        wb_stats = None
        warnings.append(f"Falha ao gravar cópia do modelo: {exc}")

    emit("save", 92, "Salvando sessão auxiliar no banco…")
    saved = _persist_budget(
        session_dict,
        title=title,
        user_id=job.get("user_id"),
        budget_id=str(job.get("budget_document_id")) if job.get("budget_document_id") else None,
    )
    budget_document_id = None
    if saved:
        budget_document_id = str(saved.get("db_id") or "")
        session_id = saved.get("session_id") or session_id
        session_dict = saved
    else:
        warnings.append(
            "Sessão auxiliar não persistiu — use o editor MCQ do OrçaFacil e baixe o .xlsm."
        )

    preview = _build_preview(
        plan,
        session_dict,
        obra_type=str(premissas.get("obra_type") or project_info.get("obra_type") or "ED"),
    )
    if wb_stats:
        preview["workbook_n_servicos"] = wb_stats.get("n_servicos")
        preview["workbook_n_etapas"] = wb_stats.get("n_etapas")

    job_store.update_job(
        job_id,
        status="ready",
        session_id=session_id,
        budget_document_id=budget_document_id,
        workbook_path=workbook_path,
        workbook_stats=wb_stats,
        warnings=warnings,
        stats=built.get("stats"),
        preview=preview,
        gemini_model=plan.get("gemini_model") or p1.get("gemini_model"),
    )
    emit(
        "ready",
        100,
        "Planilha modelo pronta"
        + (f" · {wb_stats.get('n_servicos')} serviços" if wb_stats else "")
        + (f" · modelo {plan.get('gemini_model')}" if plan.get("gemini_model") else ""),
    )
    return job_store.get_job(job_id) or {}
