"""Testes do agente de cronograma."""

from pricing.schedule.cpm_engine import run_cpm
from pricing.schedule.schedule_agent import (
    apply_schedule_actions,
    compose_schedule_from_prompt,
    detect_compose_intent,
    enrich_schedule_plan,
    normalize_schedule_action,
    resolve_task_ref,
)
from pricing.schedule.schedule_builder import sync_schedule_from_budget


def _rows():
    return [
        {"row_id": "e1", "code": "1", "name": "ADMINISTRAÇÃO DA OBRA", "row_type": "ETAPA"},
        {
            "row_id": "s1",
            "code": "1.1",
            "name": "ENGENHEIRO CIVIL",
            "row_type": "S",
            "parent_code": "1",
            "quantity": 6,
            "unit": "MES",
        },
        {
            "row_id": "s2",
            "code": "1.2",
            "name": "ENCARREGADO GERAL",
            "row_type": "S",
            "parent_code": "1",
            "quantity": 6,
            "unit": "MES",
        },
        {"row_id": "e2", "code": "2", "name": "SERVIÇOS PRELIMINARES", "row_type": "ETAPA"},
        {
            "row_id": "s3",
            "code": "2.1",
            "name": "Cerca de obra",
            "row_type": "S",
            "parent_code": "2",
            "quantity": 1,
            "unit": "UN",
        },
        {
            "row_id": "s4",
            "code": "2.2",
            "name": "Container",
            "row_type": "S",
            "parent_code": "2",
            "quantity": 1,
            "unit": "UN",
        },
    ]


def test_apply_schedule_actions_duration_and_link():
    schedule = sync_schedule_from_budget(_rows(), project_start="2026-01-01")
    a, b = schedule.leaf_tasks()[:2]
    actions = [
        {"type": "set_duration", "budget_code": a.budget_code, "duration_days": 10},
        {
            "type": "add_link",
            "predecessor_code": a.budget_code,
            "successor_code": b.budget_code,
            "link_type": "FS",
            "lag_days": 2,
        },
    ]
    updated, log = apply_schedule_actions(schedule, actions)
    assert any(x.status == "ok" and x.action == "set_duration" for x in log)
    assert any(x.status == "ok" and x.action == "add_link" for x in log)
    run_cpm(updated)


def test_compose_schedule_rule_fallback():
    schedule = sync_schedule_from_budget(_rows(), project_start="2026-06-01")
    result = compose_schedule_from_prompt(
        schedule,
        "1.1 duração 15 dias e sequenciar tarefas",
        use_llm=False,
        budget_rows=_rows(),
    )
    assert result.schedule is not None
    assert result.summary
    assert isinstance(result.log, list)


def test_detect_compose_intent_reorganize():
    intent = detect_compose_intent(
        "ajuste completo do cronograma corrigindo ordem de execução dos serviços"
    )
    assert intent.replace_links is True
    assert intent.reorder_services is True


def test_resolve_task_ref_by_name():
    schedule = sync_schedule_from_budget(_rows(), project_start="2026-06-01")
    task = resolve_task_ref(schedule, "engenheiro civil")
    assert task is not None
    assert task.budget_code == "1.1"


def test_normalize_action_aliases():
    schedule = sync_schedule_from_budget(_rows(), project_start="2026-06-01")
    normalized = normalize_schedule_action(
        {"type": "add_link", "from": "2.1", "to": "2.2", "link_type": "fs"},
        schedule,
    )
    assert normalized == {
        "type": "add_link",
        "predecessor_code": "2.1",
        "successor_code": "2.2",
        "link_type": "FS",
        "lag_days": 0,
    }


def test_enrich_plan_admin_full_span():
    schedule = sync_schedule_from_budget(_rows(), project_start="2026-01-01")
    intent = detect_compose_intent(
        "reorganizar cronograma completo: administração monitora todo o período e sequenciar preliminares"
    )
    assert intent.replace_links is True
    assert intent.admin_full_span is True
    plan = enrich_schedule_plan(
        {"summary": "teste", "actions": []},
        schedule,
        "reorganizar cronograma completo",
        intent,
    )
    assert any(a["type"] == "add_link" for a in plan["actions"])
