"""Agente IA para organizar cronograma via linguagem natural."""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from pricing.schedule.cpm_engine import run_cpm
from pricing.schedule.schedule_builder import add_link, remove_link, update_project_start, update_task_duration
from pricing.schedule.schedule_models import ProjectSchedule, ScheduleTask

logger = logging.getLogger(__name__)

_LINK_TYPES = {"FS", "SS", "FF", "SF"}

_REORG_KEYWORDS = (
    "reorganiz",
    "ajuste completo",
    "refazer",
    "do zero",
    "sequenciar tod",
    "sequenciar todas",
    "ordem de execu",
    "ordem correta",
    "reorganizar",
    "replanej",
    "cronograma completo",
    "todo o cronograma",
)

_ADMIN_KEYWORDS = (
    "administra",
    "engenheiro",
    "encarregado",
    "vigia",
    "almoxarife",
    "equipe técnic",
    "equipe tecnic",
)

_ADMIN_ETAPA_KEYWORDS = ("administra", "indiret", "canteiro")


@dataclass
class ScheduleActionLog:
    action: str
    status: str
    detail: str = ""

    def to_dict(self) -> dict[str, str]:
        return {"action": self.action, "status": self.status, "detail": self.detail}


@dataclass
class ScheduleComposeIntent:
    replace_links: bool = False
    admin_full_span: bool = False
    reorder_services: bool = False


@dataclass
class ScheduleAgentResult:
    schedule: ProjectSchedule
    summary: str = ""
    log: list[ScheduleActionLog] = field(default_factory=list)
    llm_model: str | None = None
    detected_intent: ScheduleComposeIntent | None = None

    def log_dicts(self) -> list[dict[str, str]]:
        return [x.to_dict() for x in self.log]


def _code_sort_key(code: str) -> list[int | str]:
    parts: list[int | str] = []
    for part in code.split("."):
        parts.append(int(part) if part.isdigit() else part)
    return parts


def _calendar_days(start_iso: str, end_iso: str) -> int:
    s = date.fromisoformat(start_iso[:10])
    e = date.fromisoformat(end_iso[:10])
    return max(1, (e - s).days + 1)


def _project_span_days(schedule: ProjectSchedule) -> int:
    if schedule.project_end and schedule.project_start:
        return _calendar_days(schedule.project_start, schedule.project_end)
    leaves = schedule.leaf_tasks()
    return max((t.duration_days for t in leaves), default=1)


def _row_lookup(rows: list[dict[str, Any]] | None) -> dict[str, dict[str, Any]]:
    if not rows:
        return {}
    return {str(r.get("code") or ""): r for r in rows if r.get("code")}


def detect_compose_intent(prompt: str) -> ScheduleComposeIntent:
    lower = (prompt or "").lower()
    replace_links = any(k in lower for k in _REORG_KEYWORDS)
    admin_full_span = any(
        k in lower
        for k in (
            "todo o per",
            "toda a obra",
            "durante toda",
            "monitorar",
            "acompanhar a obra",
            "período da obra",
            "periodo da obra",
            "período do projeto",
            "periodo do projeto",
        )
    ) and any(k in lower for k in _ADMIN_KEYWORDS + ("administra",))
    reorder_services = replace_links or any(
        k in lower for k in ("sequenc", "ordem", "organiz", "corrigir a ordem")
    )
    return ScheduleComposeIntent(
        replace_links=replace_links,
        admin_full_span=admin_full_span,
        reorder_services=reorder_services,
    )


def _etapa_groups(schedule: ProjectSchedule) -> list[tuple[ScheduleTask, list[ScheduleTask]]]:
    etapas = [t for t in schedule.tasks if t.is_summary and t.row_type == "ETAPA"]
    leaves = schedule.leaf_tasks()
    groups: list[tuple[ScheduleTask, list[ScheduleTask]]] = []
    for etapa in etapas:
        prefix = f"{etapa.budget_code}."
        children = sorted(
            [
                t
                for t in leaves
                if t.budget_code.startswith(prefix) or t.parent_code == etapa.budget_code
            ],
            key=lambda t: _code_sort_key(t.budget_code),
        )
        groups.append((etapa, children))
    return groups


def _is_admin_etapa(name: str) -> bool:
    lower = name.lower()
    return any(k in lower for k in _ADMIN_ETAPA_KEYWORDS)


def _is_admin_task(task: ScheduleTask, etapa_name: str = "") -> bool:
    name = f"{etapa_name} {task.name}".lower()
    return _is_admin_etapa(etapa_name) or any(k in name for k in _ADMIN_KEYWORDS)


def _build_catalog(
    schedule: ProjectSchedule,
    budget_rows: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    rows_by_code = _row_lookup(budget_rows)
    etapas_json: list[dict[str, Any]] = []
    valid_codes: list[str] = []

    for etapa, children in _etapa_groups(schedule):
        svc_list: list[dict[str, Any]] = []
        for task in children:
            valid_codes.append(task.budget_code)
            row = rows_by_code.get(task.budget_code, {})
            svc_list.append(
                {
                    "budget_code": task.budget_code,
                    "name": task.name,
                    "duration_days": task.duration_days,
                    "quantity": row.get("quantity"),
                    "unit": row.get("unit"),
                    "is_administration": _is_admin_task(task, etapa.name),
                }
            )
        etapas_json.append(
            {
                "etapa_code": etapa.budget_code,
                "etapa_name": etapa.name,
                "is_administration": _is_admin_etapa(etapa.name),
                "services": svc_list,
            }
        )

    code_by_id = {t.task_id: t.budget_code for t in schedule.tasks}
    links = [
        {
            "predecessor_code": code_by_id.get(l.predecessor_id, "?"),
            "successor_code": code_by_id.get(l.successor_id, "?"),
            "link_type": l.link_type,
            "lag_days": l.lag_days,
        }
        for l in schedule.links
    ]

    return {
        "project_start": schedule.project_start,
        "project_end": schedule.project_end or "",
        "project_span_days": _project_span_days(schedule),
        "valid_service_codes": valid_codes,
        "etapas": etapas_json,
        "links": links,
    }


def _suggested_sequence_lines(schedule: ProjectSchedule) -> list[str]:
    lines: list[str] = []
    for etapa, children in _etapa_groups(schedule):
        if not children:
            continue
        if _is_admin_etapa(etapa.name):
            codes = ", ".join(c.budget_code for c in children)
            lines.append(
                f"- Etapa {etapa.budget_code} ({etapa.name}): serviços {codes} "
                "→ paralelos desde o início, duração = período total da obra"
            )
            continue
        chain = " → ".join(c.budget_code for c in children)
        lines.append(
            f"- Etapa {etapa.budget_code} ({etapa.name}): sequência FS sugerida: {chain}"
        )
    return lines


def _tasks_context(
    schedule: ProjectSchedule,
    budget_rows: list[dict[str, Any]] | None = None,
) -> str:
    catalog = _build_catalog(schedule, budget_rows)
    suggestions = _suggested_sequence_lines(schedule)
    catalog_json = json.dumps(catalog, ensure_ascii=False, indent=2)
    return (
        f"project_start={schedule.project_start}\n"
        f"project_end={schedule.project_end or '?'}\n"
        f"project_span_days={catalog['project_span_days']}\n\n"
        f"Códigos válidos (somente estes em budget_code / predecessor_code / successor_code):\n"
        f"{', '.join(catalog['valid_service_codes'])}\n\n"
        f"Catálogo estruturado (JSON):\n{catalog_json}\n\n"
        f"Sequência lógica sugerida:\n"
        + ("\n".join(suggestions) if suggestions else "(sem serviços)")
    )


def _build_prompt(
    user_prompt: str,
    schedule: ProjectSchedule,
    budget_rows: list[dict[str, Any]] | None = None,
    intent: ScheduleComposeIntent | None = None,
) -> str:
    intent = intent or detect_compose_intent(user_prompt)
    reorg_note = (
        "O usuário pediu REORGANIZAÇÃO COMPLETA: inclua remove_link para vínculos antigos "
        "e recrie a cadeia FS correta por etapa (exceto administração, que fica paralela)."
        if intent.replace_links
        else "Preserve vínculos existentes salvo pedido explícito de mudança."
    )
    admin_note = (
        "Serviços de ADMINISTRAÇÃO/INDIRETOS devem ter duration_days = project_span_days "
        "e NÃO devem ser encadeados em FS entre si — rodam em paralelo durante toda a obra."
        if intent.admin_full_span
        else "Administração: preferir paralelo e duração compatível com o prazo global quando mencionado."
    )

    return f"""Você é engenheiro planejador civil (CPM/PDM). Organize o cronograma conforme o comando.

IMPORTANTE:
- Use EXCLUSIVamente budget_code da lista valid_service_codes.
- NUNCA invente códigos nem use nomes no lugar de códigos.
- duration_days e lag_days são inteiros >= 1 (lag pode ser 0).
- {reorg_note}
- {admin_note}
- Serviços de construção na mesma etapa: encadeie FS na ordem numérica (1.1→1.2→1.3).
- Etapas diferentes: encadeie FS entre último serviço de uma etapa e primeiro da próxima quando fizer sentido.

Estado atual:
{_tasks_context(schedule, budget_rows)}

Comando do usuário:
{user_prompt.strip()}

Responda APENAS JSON válido (sem markdown, sem texto extra):
{{
  "summary": "explicação curta em português",
  "actions": [
    {{"type": "set_duration", "budget_code": "2.3", "duration_days": 45}},
    {{"type": "add_link", "predecessor_code": "2.1", "successor_code": "2.2", "link_type": "FS", "lag_days": 0}},
    {{"type": "remove_link", "predecessor_code": "1.1", "successor_code": "1.2"}},
    {{"type": "set_project_start", "date": "2026-06-01"}}
  ]
}}

Tipos permitidos: set_duration, add_link, remove_link, set_project_start.
link_type: FS, SS, FF ou SF.

Exemplo — administração durante toda a obra + sequência na etapa 2:
{{
  "summary": "Administração estendida ao prazo total; serviços preliminares sequenciados.",
  "actions": [
    {{"type": "set_duration", "budget_code": "1.1", "duration_days": {max(30, _project_span_days(schedule))}}},
    {{"type": "add_link", "predecessor_code": "2.1", "successor_code": "2.2", "link_type": "FS", "lag_days": 0}}
  ]
}}
"""


def _parse_json_response(raw: str) -> dict[str, Any]:
    text = raw.strip()
    if "```" in text:
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.MULTILINE)
        text = re.sub(r"\s*```$", "", text, flags=re.MULTILINE)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            return json.loads(text[start : end + 1])
        raise


def _task_by_code(schedule: ProjectSchedule, code: str) -> ScheduleTask | None:
    code = code.strip()
    for t in schedule.tasks:
        if not t.is_summary and t.budget_code == code:
            return t
    return None


def _normalize_code(code: str) -> str:
    parts = [p for p in code.strip().split(".") if p]
    normalized: list[str] = []
    for part in parts:
        normalized.append(str(int(part)) if part.isdigit() else part)
    return ".".join(normalized)


def resolve_task_ref(schedule: ProjectSchedule, ref: str) -> ScheduleTask | None:
    """Resolve tarefa por budget_code exato, normalizado ou trecho único do nome."""
    ref = (ref or "").strip()
    if not ref:
        return None

    task = _task_by_code(schedule, ref)
    if task:
        return task

    norm_ref = _normalize_code(ref)
    if norm_ref != ref:
        task = _task_by_code(schedule, norm_ref)
        if task:
            return task

    ref_lower = ref.lower()
    by_norm: dict[str, ScheduleTask] = {}
    for leaf in schedule.leaf_tasks():
        by_norm[_normalize_code(leaf.budget_code)] = leaf
    if norm_ref in by_norm:
        return by_norm[norm_ref]

    name_matches = [
        t for t in schedule.leaf_tasks() if ref_lower in t.name.lower()
    ]
    if len(name_matches) == 1:
        return name_matches[0]

    code_suffix_matches = [
        t
        for t in schedule.leaf_tasks()
        if t.budget_code.endswith(f".{norm_ref}") or t.budget_code == norm_ref
    ]
    if len(code_suffix_matches) == 1:
        return code_suffix_matches[0]

    return None


def _find_link(schedule: ProjectSchedule, pred_id: str, succ_id: str):
    for link in schedule.links:
        if link.predecessor_id == pred_id and link.successor_id == succ_id:
            return link
    return None


def _pick(raw: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in raw and raw[key] not in (None, ""):
            return raw[key]
    return None


def normalize_schedule_action(
    raw: dict[str, Any],
    schedule: ProjectSchedule,
) -> dict[str, Any] | None:
    action_type = str(_pick(raw, "type", "action") or "").strip()
    if not action_type:
        return None

    if action_type == "set_duration":
        code_ref = str(
            _pick(raw, "budget_code", "code", "task_code", "service_code", "name") or ""
        )
        task = resolve_task_ref(schedule, code_ref)
        if not task:
            return None
        days_raw = _pick(raw, "duration_days", "days", "duration", "dias")
        try:
            days = max(1, int(float(days_raw)))
        except (TypeError, ValueError):
            return None
        return {"type": "set_duration", "budget_code": task.budget_code, "duration_days": days}

    if action_type == "add_link":
        pred_ref = str(
            _pick(raw, "predecessor_code", "predecessor", "pred_code", "from_code", "from") or ""
        )
        succ_ref = str(
            _pick(raw, "successor_code", "successor", "succ_code", "to_code", "to") or ""
        )
        pred = resolve_task_ref(schedule, pred_ref)
        succ = resolve_task_ref(schedule, succ_ref)
        if not pred or not succ:
            return None
        link_type = str(_pick(raw, "link_type", "type_link") or "FS").upper()
        if link_type not in _LINK_TYPES:
            link_type = "FS"
        try:
            lag = max(0, int(float(_pick(raw, "lag_days", "lag") or 0)))
        except (TypeError, ValueError):
            lag = 0
        return {
            "type": "add_link",
            "predecessor_code": pred.budget_code,
            "successor_code": succ.budget_code,
            "link_type": link_type,
            "lag_days": lag,
        }

    if action_type == "remove_link":
        pred_ref = str(_pick(raw, "predecessor_code", "predecessor", "from") or "")
        succ_ref = str(_pick(raw, "successor_code", "successor", "to") or "")
        pred = resolve_task_ref(schedule, pred_ref)
        succ = resolve_task_ref(schedule, succ_ref)
        if not pred or not succ:
            return None
        return {
            "type": "remove_link",
            "predecessor_code": pred.budget_code,
            "successor_code": succ.budget_code,
        }

    if action_type == "set_project_start":
        date_val = str(_pick(raw, "date", "project_start", "start") or "")[:10]
        if len(date_val) < 10:
            return None
        return {"type": "set_project_start", "date": date_val}

    return None


def normalize_schedule_actions(
    actions: list[Any],
    schedule: ProjectSchedule,
) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw in actions:
        if not isinstance(raw, dict):
            continue
        item = normalize_schedule_action(raw, schedule)
        if not item:
            continue
        key = json.dumps(item, sort_keys=True)
        if key in seen:
            continue
        seen.add(key)
        normalized.append(item)
    return normalized


def _sequential_link_actions(
    schedule: ProjectSchedule,
    *,
    skip_admin: bool = True,
) -> list[dict[str, Any]]:
    actions: list[dict[str, Any]] = []
    groups = _etapa_groups(schedule)
    ordered_etapas = [g for g in groups if g[1]]

    for etapa, children in ordered_etapas:
        if skip_admin and _is_admin_etapa(etapa.name):
            continue
        for i in range(len(children) - 1):
            actions.append(
                {
                    "type": "add_link",
                    "predecessor_code": children[i].budget_code,
                    "successor_code": children[i + 1].budget_code,
                    "link_type": "FS",
                    "lag_days": 0,
                }
            )

    for i in range(len(ordered_etapas) - 1):
        etapa_a, children_a = ordered_etapas[i]
        etapa_b, children_b = ordered_etapas[i + 1]
        if skip_admin and (_is_admin_etapa(etapa_a.name) or _is_admin_etapa(etapa_b.name)):
            continue
        if not children_a or not children_b:
            continue
        actions.append(
            {
                "type": "add_link",
                "predecessor_code": children_a[-1].budget_code,
                "successor_code": children_b[0].budget_code,
                "link_type": "FS",
                "lag_days": 0,
            }
        )
    return actions


def _admin_duration_actions(
    schedule: ProjectSchedule,
    span_days: int | None = None,
) -> list[dict[str, Any]]:
    days = span_days or _project_span_days(schedule)
    actions: list[dict[str, Any]] = []
    for etapa, children in _etapa_groups(schedule):
        if not _is_admin_etapa(etapa.name):
            continue
        for task in children:
            if task.duration_days != days:
                actions.append(
                    {
                        "type": "set_duration",
                        "budget_code": task.budget_code,
                        "duration_days": days,
                    }
                )
    return actions


def enrich_schedule_plan(
    plan: dict[str, Any],
    schedule: ProjectSchedule,
    prompt: str,
    intent: ScheduleComposeIntent,
) -> dict[str, Any]:
    raw_actions = plan.get("actions") if isinstance(plan.get("actions"), list) else []
    actions = normalize_schedule_actions(raw_actions, schedule)

    if intent.replace_links and intent.reorder_services:
        if not any(a["type"] == "add_link" for a in actions):
            actions = _sequential_link_actions(schedule) + actions

    if intent.admin_full_span:
        actions.extend(_admin_duration_actions(schedule))

    deduped = normalize_schedule_actions(actions, schedule)
    summary = str(plan.get("summary") or "").strip()
    if not summary:
        summary = "Cronograma atualizado conforme comando."
    return {"summary": summary, "actions": deduped}


def apply_schedule_actions(
    schedule: ProjectSchedule,
    actions: list[dict[str, Any]],
    *,
    replace_links: bool = False,
) -> tuple[ProjectSchedule, list[ScheduleActionLog]]:
    log: list[ScheduleActionLog] = []
    if replace_links:
        schedule.links = []
        log.append(ScheduleActionLog("clear_links", "ok", "Vínculos removidos"))

    for raw in actions:
        action_type = str(raw.get("type") or "").strip()
        try:
            if action_type == "set_project_start":
                date_val = str(raw.get("date") or "")[:10]
                if len(date_val) < 10:
                    raise ValueError("data inválida")
                schedule = update_project_start(schedule, date_val)
                log.append(ScheduleActionLog("set_project_start", "ok", date_val))

            elif action_type == "set_duration":
                code = str(raw.get("budget_code") or "")
                days = int(raw.get("duration_days") or 0)
                task = resolve_task_ref(schedule, code)
                if not task:
                    raise ValueError(f"tarefa {code} não encontrada")
                schedule = update_task_duration(schedule, task.task_id, days)
                log.append(ScheduleActionLog("set_duration", "ok", f"{task.budget_code}={days}d"))

            elif action_type == "add_link":
                pred_code = str(raw.get("predecessor_code") or "")
                succ_code = str(raw.get("successor_code") or "")
                link_type = str(raw.get("link_type") or "FS").upper()
                lag = int(raw.get("lag_days") or 0)
                if link_type not in _LINK_TYPES:
                    raise ValueError(f"link_type inválido: {link_type}")
                pred = resolve_task_ref(schedule, pred_code)
                succ = resolve_task_ref(schedule, succ_code)
                if not pred or not succ:
                    raise ValueError(f"tarefas {pred_code}->{succ_code} não encontradas")
                if pred.budget_code == succ.budget_code:
                    raise ValueError("predecessora e sucessora iguais")
                if _find_link(schedule, pred.task_id, succ.task_id):
                    log.append(
                        ScheduleActionLog(
                            "add_link", "skip", f"{pred.budget_code}->{succ.budget_code} já existe"
                        )
                    )
                else:
                    schedule = add_link(
                        schedule, pred.task_id, succ.task_id, link_type, lag
                    )
                    log.append(
                        ScheduleActionLog(
                            "add_link",
                            "ok",
                            f"{pred.budget_code}->{succ.budget_code} {link_type}",
                        )
                    )

            elif action_type == "remove_link":
                pred_code = str(raw.get("predecessor_code") or "")
                succ_code = str(raw.get("successor_code") or "")
                pred = resolve_task_ref(schedule, pred_code)
                succ = resolve_task_ref(schedule, succ_code)
                if not pred or not succ:
                    raise ValueError(f"tarefas {pred_code}->{succ_code} não encontradas")
                link = _find_link(schedule, pred.task_id, succ.task_id)
                if not link:
                    log.append(
                        ScheduleActionLog(
                            "remove_link",
                            "skip",
                            f"{pred.budget_code}->{succ.budget_code} não existe",
                        )
                    )
                else:
                    schedule = remove_link(schedule, link.link_id)
                    log.append(
                        ScheduleActionLog(
                            "remove_link", "ok", f"{pred.budget_code}->{succ.budget_code}"
                        )
                    )
            else:
                log.append(ScheduleActionLog(action_type or "unknown", "skip", "tipo desconhecido"))
        except Exception as exc:
            log.append(
                ScheduleActionLog(action_type or "error", "error", str(exc))
            )

    schedule = run_cpm(schedule)
    return schedule, log


def _post_apply_admin_span(
    schedule: ProjectSchedule,
    intent: ScheduleComposeIntent,
) -> tuple[ProjectSchedule, list[ScheduleActionLog]]:
    if not intent.admin_full_span:
        return schedule, []

    span = _project_span_days(schedule)
    log: list[ScheduleActionLog] = []
    for action in _admin_duration_actions(schedule, span):
        code = action["budget_code"]
        days = action["duration_days"]
        task = resolve_task_ref(schedule, code)
        if not task or task.duration_days == days:
            continue
        schedule = update_task_duration(schedule, task.task_id, days)
        log.append(ScheduleActionLog("set_duration", "ok", f"{code}={days}d (admin span)"))
    schedule = run_cpm(schedule)
    return schedule, log


def _rule_based_plan(
    prompt: str,
    schedule: ProjectSchedule,
    intent: ScheduleComposeIntent,
) -> dict[str, Any]:
    """Fallback heurístico quando LLM indisponível."""
    actions: list[dict[str, Any]] = []
    lower = prompt.lower()

    date_match = re.search(r"(\d{4}-\d{2}-\d{2})", prompt)
    if date_match or "início" in lower or "inicio" in lower:
        if date_match:
            actions.append({"type": "set_project_start", "date": date_match.group(1)})

    for match in re.finditer(
        r"(\d+(?:\.\d+)*)\s*(?:=|:)?\s*(\d+)\s*d(?:ias)?", prompt, re.I
    ):
        actions.append(
            {
                "type": "set_duration",
                "budget_code": match.group(1),
                "duration_days": int(match.group(2)),
            }
        )

    if intent.replace_links or ("sequenc" in lower or "ordem" in lower or "organiz" in lower):
        actions = _sequential_link_actions(schedule) + actions

    if intent.admin_full_span:
        actions.extend(_admin_duration_actions(schedule))

    plan = enrich_schedule_plan(
        {"summary": "Plano heurístico aplicado (Ollama offline ou resposta inválida).", "actions": actions},
        schedule,
        prompt,
        intent,
    )
    if not plan["actions"]:
        plan["summary"] = (
            "Nenhuma ação identificada — tente: 'reorganizar cronograma completo' "
            "ou '1.1 duração 60 dias'."
        )
    return plan


def compose_schedule_from_prompt(
    schedule: ProjectSchedule,
    prompt: str,
    *,
    use_llm: bool = True,
    replace_links: bool = False,
    llm_client: Any | None = None,
    budget_rows: list[dict[str, Any]] | None = None,
) -> ScheduleAgentResult:
    if not schedule.tasks:
        raise ValueError("Cronograma vazio — sincronize com o orçamento primeiro")

    intent = detect_compose_intent(prompt)
    if intent.replace_links:
        replace_links = True

    plan: dict[str, Any] | None = None
    model_used: str | None = None
    leaf_count = len(schedule.leaf_tasks())
    complexity = "HIGH" if replace_links or leaf_count >= 6 else "MEDIUM"

    if use_llm:
        try:
            from core.models.budget_model_routing import budget_generate
            from models.ollama_client import OllamaClient

            client = llm_client or OllamaClient()
            if getattr(client, "ping", lambda: True)():
                raw, model_used = budget_generate(
                    _build_prompt(prompt, schedule, budget_rows, intent),
                    user_text=prompt,
                    task="wbs",
                    client=client,
                    format_json=True,
                    complexity=complexity,
                )
                parsed = _parse_json_response(raw)
                plan = enrich_schedule_plan(parsed, schedule, prompt, intent)
        except Exception as exc:
            logger.warning("schedule_agent LLM failed: %s", exc)

    if not plan or not isinstance(plan.get("actions"), list):
        plan = _rule_based_plan(prompt, schedule, intent)

    actions = plan.get("actions") or []
    if not isinstance(actions, list):
        actions = []

    updated, log = apply_schedule_actions(
        schedule, actions, replace_links=replace_links
    )
    updated, post_log = _post_apply_admin_span(updated, intent)
    log.extend(post_log)

    return ScheduleAgentResult(
        schedule=updated,
        summary=str(plan.get("summary") or "Cronograma atualizado."),
        log=log,
        llm_model=model_used,
        detected_intent=intent,
    )
