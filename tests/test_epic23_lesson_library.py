from __future__ import annotations

from sqlalchemy import select

from fluentloop.bot.handlers import (
    handle_lesson,
    handle_lessons,
    handle_library,
    handle_library_callback,
    handle_publish,
    handle_subscribe,
    handle_today,
)
from fluentloop.curriculum_b2 import CURRICULUM_TAG
from fluentloop.db.models import LearningItem, LessonPlan, PracticeSession
from fluentloop.learning import create_learning_item
from fluentloop.lesson_library import (
    get_seed_library_user,
    library_templates,
    seed_and_publish_catalog_templates,
    subscribe_to_template,
)
from fluentloop.lesson_plans import create_lesson_plan_from_source, lesson_items
from fluentloop.materials import store_material
from fluentloop.users import ensure_user


def test_seed_library_publish_marks_only_b2_catalog_templates(
    db_session, settings
) -> None:
    owner = ensure_user(db_session, 123456789, settings)
    private_material = store_material(
        db_session,
        owner,
        "[CODEX_TEST] private owner lesson about board updates",
        type_="lesson_notes",
    )
    create_learning_item(
        db_session,
        owner,
        type_="expression",
        text="[CODEX_TEST] private board update",
        source_material_id=private_material.id,
    )
    private_plan = create_lesson_plan_from_source(db_session, owner, private_material)

    result = seed_and_publish_catalog_templates(db_session)
    templates = library_templates(db_session, limit=100)
    library_user = get_seed_library_user(db_session)

    assert result["seeded_lessons"] == 20
    assert len(templates) == 20
    assert all(CURRICULUM_TAG in (template.tags_json or []) for template in templates)
    assert all(template.user_id == library_user.id for template in templates)
    assert private_plan.is_template is False
    assert private_plan.id not in {template.id for template in templates}


def test_subscribe_clones_template_plan_and_reuses_items_on_repeat(
    db_session, settings
) -> None:
    seed_and_publish_catalog_templates(db_session)
    user = ensure_user(db_session, 555000111, settings)
    template = library_templates(db_session, query="risk")[0]
    template_item_ids = {item.id for item in lesson_items(db_session, template)}

    first = subscribe_to_template(db_session, user, template.id)
    second = subscribe_to_template(db_session, user, template.id)
    first_items = lesson_items(db_session, first.plan)
    second_items = lesson_items(db_session, second.plan)

    assert first.plan.user_id == user.id
    assert first.plan.template_of == template.id
    assert first.plan.is_template is False
    assert first.created_items == len(first_items)
    assert second.plan.id != first.plan.id
    assert second.created_items == 0
    assert second.reused_items == len(first_items)
    assert {item.id for item in first_items} == {item.id for item in second_items}
    assert not ({item.id for item in first_items} & template_item_ids)
    assert all(item.user_id == user.id and not item.is_template for item in first_items)
    assert all(item.template_of in template_item_ids for item in first_items)


def test_library_handlers_and_lesson_flow_after_subscribe(db_session, settings) -> None:
    seed_and_publish_catalog_templates(db_session)
    user = ensure_user(db_session, 555000222, settings)
    library = handle_library(db_session, user, "risk")
    template = library_templates(db_session, query="risk")[0]

    details = handle_library_callback(db_session, user, "details", str(template.id))
    subscribed = handle_subscribe(db_session, user, template.id)
    clone = db_session.scalar(
        select(LessonPlan)
        .where(LessonPlan.user_id == user.id, LessonPlan.template_of == template.id)
        .order_by(LessonPlan.id.desc())
    )
    assert clone is not None
    lessons = handle_lessons(db_session, user, "risk")
    started = handle_lesson(db_session, user, f"start {clone.id}")
    today = handle_today(db_session, user)
    practice = db_session.scalar(
        select(PracticeSession)
        .where(PracticeSession.status == "in_progress")
        .order_by(PracticeSession.id.desc())
    )

    assert "Shared library matching risk" in library.text
    assert f"library:subscribe:{template.id}" in {
        button.data for row in (library.buttons or []) for button in row
    }
    assert "Shared library lesson" in details.text
    assert "Subscribed to template" in subscribed.text
    assert str(clone.id) in lessons.text
    assert "Today's English practice" in started.text
    assert "Today's English practice" in today.text
    assert practice is not None
    assert practice.exercises[0]["lesson_plan_id"] == clone.id


def test_library_invalid_publish_and_private_visibility(db_session, settings) -> None:
    owner = ensure_user(db_session, 123456789, settings)
    other = ensure_user(db_session, 555000333, settings)
    private_material = store_material(
        db_session,
        owner,
        "[CODEX_TEST] private architecture review",
        type_="lesson_notes",
    )
    create_learning_item(
        db_session,
        owner,
        type_="expression",
        text="[CODEX_TEST] private architecture chunk",
        source_material_id=private_material.id,
    )
    private_plan = create_lesson_plan_from_source(db_session, owner, private_material)
    seed_and_publish_catalog_templates(db_session)

    before = handle_library(db_session, other, "private architecture")
    denied = handle_publish(
        db_session,
        other,
        private_plan.id,
        owner_telegram_user_id=settings.telegram_allowed_user_id,
    )
    published = handle_publish(
        db_session,
        owner,
        private_plan.id,
        owner_telegram_user_id=settings.telegram_allowed_user_id,
    )
    invalid_subscribe = handle_subscribe(db_session, other, 999999)

    assert "No shared seed lessons" in before.text
    assert "Owner-only" in denied.text
    assert "Published template" in published.text
    assert private_plan.is_template is True
    assert "Could not subscribe" in invalid_subscribe.text
    assert db_session.scalar(
        select(LearningItem).where(
            LearningItem.user_id == other.id,
            LearningItem.text == "[CODEX_TEST] private architecture chunk",
        )
    ) is None
