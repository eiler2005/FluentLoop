from __future__ import annotations

from sqlalchemy import select

from fluentloop.ai.provider import StubProvider
from fluentloop.bot.handlers import handle_today
from fluentloop.db.models import LessonPlan, LessonPlanItem, LessonStep, PracticeSession
from fluentloop.learning import create_learning_item
from fluentloop.lesson_plans import (
    available_lesson_plan,
    create_lesson_plan_from_source,
    lesson_items,
    lesson_steps,
)
from fluentloop.materials import approve_all, extract_candidates, store_material
from fluentloop.users import ensure_user


def test_create_lesson_plan_from_source_material(db_session, settings) -> None:
    user = ensure_user(db_session, 123456789, settings)
    material = store_material(
        db_session,
        user,
        "# [CODEX_TEST] Introverts and extroverts\nreported speech practice",
        type_="lesson_notes",
    )
    item = create_learning_item(
        db_session,
        user,
        type_="expression",
        text="[CODEX_TEST] suggested having",
        source_material_id=material.id,
        tags=["reported"],
    )

    plan = create_lesson_plan_from_source(db_session, user, material)

    assert plan.source_material_id == material.id
    assert plan.status == "active"
    assert "Reported speech" in plan.topic
    assert item.id in [linked.id for linked in lesson_items(db_session, plan)]


def test_lesson_step_ordering_and_item_links(db_session, settings) -> None:
    user = ensure_user(db_session, 123456789, settings)
    material = store_material(db_session, user, "[CODEX_TEST] architecture trade-offs")
    first = create_learning_item(
        db_session,
        user,
        type_="expression",
        text="[CODEX_TEST] I would lean towards",
        source_material_id=material.id,
    )
    second = create_learning_item(
        db_session,
        user,
        type_="grammar_rule",
        text="[CODEX_TEST] Hedging recommendations",
        source_material_id=material.id,
    )

    plan = create_lesson_plan_from_source(db_session, user, material)
    steps = lesson_steps(db_session, plan)
    links = list(
        db_session.scalars(
            select(LessonPlanItem)
            .where(LessonPlanItem.lesson_plan_id == plan.id)
            .order_by(LessonPlanItem.priority)
        )
    )

    assert [step.order_index for step in steps] == list(range(1, 8))
    assert [step.step_type for step in steps][:2] == ["warmup", "input"]
    assert [link.learning_item_id for link in links] == [first.id, second.id]
    assert links[0].role == "target"
    assert links[1].role == "grammar_focus"


def test_today_selects_available_lesson_plan(db_session, settings) -> None:
    user = ensure_user(db_session, 123456789, settings)
    material = store_material(
        db_session,
        user,
        "[CODEX_TEST] stakeholder communication and push back on timelines",
    )
    create_learning_item(
        db_session,
        user,
        type_="expression",
        text="[CODEX_TEST] push back on",
        source_material_id=material.id,
        tags=["stakeholders"],
    )
    plan = create_lesson_plan_from_source(db_session, user, material)

    reply = handle_today(db_session, user)
    practice = db_session.scalar(select(PracticeSession))

    assert available_lesson_plan(db_session, user).id == plan.id
    assert "Mode: lesson" in reply.text
    assert practice is not None
    assert practice.exercises[0]["lesson_plan_id"] == plan.id
    assert "Activate the topic" in reply.text


def test_today_falls_back_when_no_lesson_plan_exists(db_session, settings) -> None:
    user = ensure_user(db_session, 123456789, settings)
    create_learning_item(
        db_session, user, type_="expression", text="[CODEX_TEST] align on"
    )

    reply = handle_today(db_session, user)

    assert db_session.scalar(select(LessonPlan)) is None
    assert "Mode: mixed" in reply.text
    assert "Step 1/7 - Warm-up" in reply.text


def test_approval_creates_lesson_plan_from_material(
    db_session, settings, tmp_path
) -> None:
    user = ensure_user(db_session, 123456789, settings)
    material = store_material(
        db_session,
        user,
        "[CODEX_TEST] push back on and align on in reported speech",
        type_="lesson_notes",
    )
    extract_candidates(db_session, material, StubProvider(tmp_path / "usage.jsonl"))

    approved = approve_all(db_session, user, material)

    plan = db_session.scalar(select(LessonPlan))
    assert approved >= 1
    assert plan is not None
    assert plan.source_material_id == material.id
    assert db_session.scalar(select(LessonStep)) is not None
    assert db_session.scalar(select(LessonPlanItem)) is not None
