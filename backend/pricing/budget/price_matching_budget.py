"""Monta sessão PPD preservando etapas, sub-etapas e composições do PDF."""

from __future__ import annotations

from typing import Any

from pricing.budget.budget_session import SESSION_STORE
from pricing.budget.budget_structure import add_etapa, add_service_to_group, add_subetapa
from pricing.budget.ppd_layout import ROW_TYPE_SERVICO
from pricing.budget.composition_codes import normalize_composition_code
from pricing.budget.price_matching_hierarchy import ImportRowKind, ImportedBudgetLine
from pricing.budget.ppd_template import create_empty_ppd_metadata
from pricing.models.budget_metadata import BdiConfig
from pricing.models.budget_item import BudgetItem
from pricing.models.price_item import PriceItem

_BASE_SOURCE = {
    "SEMINF": "seminf",
    "SINAPI": "sinapi",
    "SICRO": "sicro",
    "ORSE": "orse",
}


def _source_priority_from_job(job: dict[str, Any]) -> list[str]:
    enabled = [b for b in job.get("price_bases") or [] if b.get("enabled", True) and b.get("reference")]
    if enabled:
        return [str(b.get("source") or "sinapi").lower() for b in enabled]
    return ["seminf", "sinapi", "sicro", "orse"]


def merge_job_price_bases(
    job: dict[str, Any],
    session_dict: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Preenche price_bases do job a partir da sessão/orçamento salvo quando o job estiver vazio."""
    out = dict(job)
    bases = list(out.get("price_bases") or [])
    if not bases and session_dict:
        project = session_dict.get("project") or {}
        bases = list(project.get("price_bases") or [])
    out["price_bases"] = bases
    return out


def ensure_job_price_bases_persisted(
    db: Any,
    job_id: str,
    job: dict[str, Any],
    session_dict: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Garante price_bases no job; persiste no banco se recuperou da sessão."""
    merged = merge_job_price_bases(job, session_dict)
    if merged.get("price_bases") and not (job.get("price_bases") or []):
        from pricing.budget.price_matching_store import STORE

        STORE.update_job_meta(db, job_id, price_bases=merged["price_bases"])
    return merged


def sync_job_prices_into_session_dict(
    session_dict: dict[str, Any] | None,
    job: dict[str, Any],
) -> dict[str, Any] | None:
    """Aplica preços das linhas do job na sessão PPD (memória ou payload salvo)."""
    if not session_dict or not job.get("rows"):
        return session_dict
    sync_sid = str(session_dict.get("session_id") or job.get("session_id") or "").strip()
    if not sync_sid:
        return session_dict
    from app.services.budget_db_service import session_from_payload

    if SESSION_STORE.get(sync_sid) is None:
        payload = dict(session_dict)
        if payload.get("session_id") != sync_sid:
            payload = {**payload, "session_id": sync_sid}
        session_from_payload(payload)
    try:
        return sync_priced_rows_to_session(sync_sid, job)
    except KeyError:
        return session_dict


def resolve_price_matching_session(
    db: Any,
    job: dict[str, Any],
    *,
    user: Any = None,
    sync_prices: bool = False,
) -> dict[str, Any]:
    """Carrega sessão PPD do orçamento salvo, memória ou reconstrói a partir do job."""
    from app.services.budget_db_service import get_budget, session_from_payload

    budget_id = job.get("budget_document_id")
    session_dict: dict[str, Any] | None = None

    if budget_id and db is not None:
        saved = get_budget(db, str(budget_id), user=user)
        if saved:
            session_dict = saved
            session_from_payload(saved)

    session_id = job.get("session_id")
    if not session_dict and session_id:
        session = SESSION_STORE.get(str(session_id))
        if session:
            session_dict = session.to_dict()

    if session_dict and sync_prices:
        session_dict = sync_job_prices_into_session_dict(session_dict, job) or session_dict
    elif session_id and job.get("rows") and sync_prices:
        try:
            synced = sync_and_persist_job_budget(db, job, user=user)
            if synced:
                session_dict = synced
                session_from_payload(synced)
        except KeyError:
            pass

    if not session_dict and session_id:
        session = SESSION_STORE.get(str(session_id))
        if session:
            session_dict = session.to_dict()

    if not session_dict:
        session_dict = build_budget_session_from_job(job)
        session_from_payload(session_dict)

    job_bases = list(job.get("price_bases") or [])
    if session_dict and job_bases:
        project = dict(session_dict.get("project") or {})
        project["price_bases"] = job_bases
        session_dict = {**session_dict, "project": project}

    return session_dict


def _job_meta(job: dict[str, Any]) -> tuple[Any, float]:
    title = str(job.get("obra") or job.get("title") or "Orçamento importado")
    meta = create_empty_ppd_metadata(projeto=title, objeto=title)
    meta.orgao = str(job.get("cliente") or "")
    meta.empresa = str(job.get("cliente") or "")

    price_bases = list(job.get("price_bases") or [])
    if price_bases:
        meta.price_bases = price_bases

    bdi = float(job.get("bdi") or 0)
    if bdi > 0:
        meta.bdi = BdiConfig.from_dict(
            {
                "obra_type": meta.bdi.obra_type,
                "source": "custom",
                "rate_com_desoneracao": bdi,
                "rate_sem_desoneracao": bdi,
                "label": "BDI importado",
                "obra_label": "Customizado",
            }
        )
    return meta, float(job.get("increase_index") or 1.0)


def _parent_pdf_key(item: str) -> str:
    if "." not in item:
        return item
    return item.rsplit(".", 1)[0]


def _unit_cost_from_row(row: dict[str, Any], increase_index: float) -> float:
    base = row.get("valor_unitario_base")
    if base is not None:
        return float(base)
    unit = row.get("valor_unitario")
    if unit is None:
        return 0.0
    inc = increase_index if increase_index > 0 else 1.0
    return float(unit) / inc


def _unit_costs_comd_semd_from_row(
    priced: dict[str, Any],
    job: dict[str, Any],
    increase_index: float,
) -> tuple[float, float]:
    """Retorna custos unitários ComD e SemD a partir da base de preços."""
    inc = increase_index if increase_index > 0 else 1.0
    base = priced.get("valor_unitario_base")
    if base is not None:
        val = round(float(base) * inc, 4)
        return val, val
    unit = _unit_cost_from_row(priced, increase_index)
    if unit > 0:
        return unit, unit

    uf = str(job.get("uf") or "AM").upper()
    reference = str(priced.get("reference") or "").replace("/", "-")
    code = str(priced.get("codigo_base") or "").strip()
    if reference and code:
        try:
            from pricing.budget.price_bank_store import PriceBankStore

            store = PriceBankStore.for_reference(reference)
            for bank_row in store.load_closed():
                bank_code = str(bank_row.get("code") or "").strip()
                if bank_code != code and bank_code.split("/")[0] != code.split("/")[0]:
                    continue
                reg = (bank_row.get("regional") or {}).get(uf)
                if reg:
                    comd = float(reg.get("comd") or reg.get("com") or 0)
                    semd = float(reg.get("semd") or reg.get("sem") or comd)
                    if comd > 0:
                        return round(comd * inc, 4), round(semd * inc, 4)
                price = float(bank_row.get("price") or 0)
                if price > 0:
                    p = round(price * inc, 4)
                    return p, p
        except Exception:
            pass
    return 0.0, 0.0


def _apply_priced_row_to_service(
    item: BudgetItem,
    priced: dict[str, Any],
    job: dict[str, Any],
    *,
    increase_index: float,
    bdi_calc: Any,
) -> None:
    unit_comd, unit_semd = _unit_costs_comd_semd_from_row(priced, job, increase_index)
    if unit_comd <= 0 and not priced.get("codigo_base"):
        return
    item.unit_cost = unit_comd
    item.unit_cost_semd = unit_semd if unit_semd > 0 else unit_comd
    if priced.get("base"):
        item.source_base = str(priced.get("base") or item.source_base or "").upper()
    if priced.get("codigo_base"):
        normalized = normalize_composition_code(str(priced.get("codigo_base") or ""))
        if normalized:
            item.source_code = normalized
    if priced.get("descricao_base"):
        item.metadata["descricao_base"] = str(priced.get("descricao_base"))
    item.metadata["price_matching_row_id"] = priced.get("id")
    item.metadata["match_level"] = priced.get("match_level")
    item.metadata["confidence"] = priced.get("score_confianca")
    item.metadata["price_matching_status"] = priced.get("status")
    if priced.get("reference"):
        item.metadata["price_reference"] = str(priced.get("reference"))
    bdi_calc.apply_to_item(item)
    item.recompute_total()


def _resolve_container(
    roots: list[BudgetItem],
    pdf_map: dict[str, BudgetItem],
    parent_key: str,
    meta: Any,
) -> BudgetItem:
    if parent_key in pdf_map:
        return pdf_map[parent_key]

    if "." in parent_key:
        grand = parent_key.split(".")[0]
        if grand not in pdf_map:
            pdf_map[grand] = add_etapa(roots, f"Grupo {grand}", meta)
        parent = pdf_map[grand]
        sub = add_subetapa(roots, parent.code, f"Subgrupo {parent_key}", meta)
        pdf_map[parent_key] = sub
        return sub

    etapa = add_etapa(roots, f"Grupo {parent_key}", meta)
    pdf_map[parent_key] = etapa
    return etapa


def _add_service(
    container: BudgetItem,
    line: ImportedBudgetLine | dict[str, Any],
    meta: Any,
    *,
    increase_index: float = 1.0,
    priced_row: dict[str, Any] | None = None,
) -> BudgetItem:
    if isinstance(line, dict):
        row = line
        desc_original = str(row.get("descricao_original") or "")
        qty = float(row.get("quantidade") or 0)
        unit = str(row.get("unidade") or "")
        pdf_item = str(row.get("item") or "")
        base_label = str(row.get("base") or "SINAPI").upper()
        source = _BASE_SOURCE.get(base_label, "sinapi")
        unit_cost = _unit_cost_from_row(row, increase_index)
        desc_base = str(row.get("descricao_base") or desc_original)
        code = normalize_composition_code(str(row.get("codigo_base") or ""))
    else:
        desc_original = line.descricao
        qty = line.quantidade
        unit = line.unidade
        pdf_item = line.item
        source = "sinapi"
        unit_cost = 0.0
        desc_base = desc_original
        code = ""
        if priced_row:
            base_label = str(priced_row.get("base") or "SINAPI").upper()
            source = _BASE_SOURCE.get(base_label, source)
            unit_cost = _unit_cost_from_row(priced_row, increase_index)
            desc_base = str(priced_row.get("descricao_base") or desc_original)
            code = normalize_composition_code(str(priced_row.get("codigo_base") or ""))

    price = PriceItem(
        code=code,
        description=desc_base,
        unit=unit,
        price=unit_cost,
        source=source,
        metadata={"reference": (priced_row or {}).get("reference")},
    )
    svc = add_service_to_group(
        container,
        price,
        meta,
        quantity=qty,
        unit_hint=unit,
    )
    svc.pricing_query = desc_original
    svc.name = desc_original
    svc.metadata.update(
        {
            "import_item": pdf_item,
            "pdf_item": pdf_item,
            "price_matching_row_id": (priced_row or {}).get("id"),
            "confidence": (priced_row or {}).get("score_confianca"),
            "match_level": (priced_row or {}).get("match_level"),
            "incomplete_import": isinstance(line, ImportedBudgetLine) and line.incomplete,
        }
    )
    return svc


def build_budget_from_hierarchy(
    lines: list[ImportedBudgetLine],
    job: dict[str, Any],
    *,
    priced_rows: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Constrói árvore PPD na ordem do PDF."""
    meta, increase_index = _job_meta(job)
    roots: list[BudgetItem] = []
    pdf_map: dict[str, BudgetItem] = {}
    priced_rows = priced_rows or {}

    for line in lines:
        if line.row_type == ImportRowKind.ETAPA.value:
            etapa = add_etapa(roots, line.descricao, meta)
            pdf_map[line.item] = etapa
            etapa.metadata["pdf_item"] = line.item
        elif line.row_type == ImportRowKind.SUB_ETAPA.value:
            parent_key = _parent_pdf_key(line.item)
            if not parent_key:
                continue
            parent = _resolve_container(roots, pdf_map, parent_key, meta)
            sub = add_subetapa(roots, parent.code, line.descricao, meta)
            pdf_map[line.item] = sub
            sub.metadata["pdf_item"] = line.item
        elif line.row_type == ImportRowKind.SERVICO.value:
            parent_key = _parent_pdf_key(line.item) or line.item.split(".")[0]
            container = _resolve_container(roots, pdf_map, parent_key, meta)
            priced = priced_rows.get(line.item)
            _add_service(container, line, meta, increase_index=increase_index, priced_row=priced)

    for root in roots:
        root.recompute_total()

    session = SESSION_STORE.create(
        roots=roots,
        title=meta.projeto,
        intent={"source": "price_matching", "job_id": job.get("id"), "hierarchical": True},
        project=meta,
        source_priority=_source_priority_from_job(job),
        session_id=job.get("session_id"),
    )
    return session.to_dict()


def _is_service_item(item: BudgetItem) -> bool:
    if item.metadata.get("is_memory_row") or item.row_type == "MEMORIA":
        return False
    if item.row_type in (ROW_TYPE_SERVICO, "SERVICO", ImportRowKind.SERVICO.value):
        return True
    return item.item_type.value == "composition"


def sync_priced_rows_to_session(session_id: str, job: dict[str, Any]) -> dict[str, Any]:
    """Atualiza custos unitários na sessão a partir das linhas matched."""
    session = SESSION_STORE.get(session_id)
    if not session:
        raise KeyError(f"Sessão não encontrada: {session_id}")

    _, increase_index = _job_meta(job)
    from pricing.budget.budget_structure import BdiCalculator

    bdi_calc = BdiCalculator(session.project.bdi)
    by_pdf_item: dict[str, dict] = {}
    for row in job.get("rows") or []:
        item = str(row.get("item") or "")
        if item:
            by_pdf_item[item] = row

    applied = 0

    def walk(items: list[BudgetItem]) -> None:
        nonlocal applied
        for item in items:
            if _is_service_item(item):
                pdf_item = str(item.metadata.get("pdf_item") or item.metadata.get("import_item") or "")
                priced = by_pdf_item.get(pdf_item)
                if priced:
                    unit_cost = _unit_cost_from_row(priced, increase_index)
                    if unit_cost > 0 or priced.get("codigo_base"):
                        _apply_priced_row_to_service(
                            item,
                            priced,
                            job,
                            increase_index=increase_index,
                            bdi_calc=bdi_calc,
                        )
                        applied += 1
            walk(item.children)

    walk(session.roots)
    for root in session.roots:
        root.recompute_total()
    session.updated_at = __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat()
    SESSION_STORE._persist_snapshot(session)  # noqa: SLF001
    session.intent["price_matching_applied"] = applied
    return session.to_dict()


def sync_hierarchy_codes_from_rows(job: dict[str, Any]) -> dict[str, Any]:
    """Preenche coluna codigo da hierarquia importada com codigo_base localizado."""
    hierarchy = job.get("hierarchy")
    rows = job.get("rows") or []
    if not hierarchy:
        return job

    by_item: dict[str, str] = {}
    for row in rows:
        item = str(row.get("item") or "").strip()
        code = str(row.get("codigo_base") or "").strip()
        if item and code:
            by_item[item] = code
    if not by_item:
        return job

    updated: list[dict[str, Any]] = []
    changed = False
    for ln in hierarchy:
        entry = dict(ln)
        item = str(entry.get("item") or "").strip()
        if item in by_item:
            entry["codigo"] = by_item[item]
            changed = True
        updated.append(entry)
    if not changed:
        return job
    out = dict(job)
    out["hierarchy"] = updated
    return out


def sync_and_persist_job_budget(
    db: Any,
    job: dict[str, Any],
    *,
    user: Any = None,
) -> dict[str, Any] | None:
    """Sincroniza preços na sessão PPD e persiste o orçamento vinculado."""
    job = sync_hierarchy_codes_from_rows(job)
    session_id = job.get("session_id")
    budget_id = job.get("budget_document_id")
    if not session_id:
        return None

    session_dict = sync_priced_rows_to_session(session_id, job)

    if job.get("id") and job.get("hierarchy"):
        from pricing.budget.price_matching_store import STORE

        STORE.save_job_hierarchy(db, str(job["id"]), job.get("hierarchy"))

    if not budget_id or db is None:
        return session_dict

    from app.services.budget_db_service import save_budget, session_from_payload

    title = str(job.get("obra") or session_dict.get("title") or "Orçamento importado")
    saved = save_budget(
        db,
        session_dict,
        title=title,
        budget_id=str(budget_id),
        user=user,
        sync_composition_snapshots=False,
    )
    try:
        from pricing.budget.composition_snapshot_service import schedule_snapshot_sync

        schedule_snapshot_sync(budget_id, saved, force_all=True)
    except Exception:
        pass
    session_from_payload(saved)
    return saved


def build_budget_session_from_job(job: dict[str, Any]) -> dict[str, Any]:
    """Compat — reconstrói ou sincroniza sessão a partir do job."""
    session_id = job.get("session_id")
    if session_id and job.get("rows"):
        try:
            return sync_priced_rows_to_session(session_id, job)
        except KeyError:
            pass

    hierarchy = job.get("hierarchy")
    if hierarchy:
        lines = [
            ImportedBudgetLine(
                item=h["item"],
                descricao=h["descricao"],
                unidade=h.get("unidade") or "",
                quantidade=float(h.get("quantidade") or 0),
                codigo=str(h.get("codigo") or ""),
                row_type=h.get("row_type") or ImportRowKind.SERVICO.value,
                row_index=int(h.get("row_index") or 0),
                incomplete=bool(h.get("incomplete")),
            )
            for h in hierarchy
        ]
        priced = {str(r.get("item")): r for r in job.get("rows") or [] if r.get("item")}
        return build_budget_from_hierarchy(lines, job, priced_rows=priced)

    return build_budget_from_hierarchy([], job)
