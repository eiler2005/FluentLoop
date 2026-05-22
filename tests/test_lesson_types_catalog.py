from __future__ import annotations

from fluentloop.bot.handlers import (
    handle_lesson,
    handle_library,
    handle_library_callback,
    handle_subscribe,
)
from fluentloop.catalog_export import build_public_catalog, render_catalog_files
from fluentloop.curriculum_b2 import CURRICULUM_TAG
from fluentloop.exercises import EXERCISE_TYPES
from fluentloop.learning import create_learning_item
from fluentloop.lesson_formats import LESSON_FORMATS
from fluentloop.lesson_library import (
    get_seed_library_user,
    library_templates,
    seed_and_publish_catalog_templates,
)
from fluentloop.lesson_plans import create_lesson_plan_from_source
from fluentloop.lesson_types import (
    lesson_type_for_exercise_type,
    lesson_type_for_format,
    lesson_type_for_plan,
    lesson_type_for_practice_mode,
    practice_modes_missing_type,
)
from fluentloop.materials import store_material
from fluentloop.users import ensure_user


def test_lesson_type_registry_covers_modes_formats_and_exercises() -> None:
    assert practice_modes_missing_type() == set()

    for lesson_format in LESSON_FORMATS:
        assert lesson_type_for_practice_mode(lesson_format.mode).key

    for exercise_type in EXERCISE_TYPES:
        assert lesson_type_for_exercise_type(exercise_type).key

    assert lesson_type_for_format("genre").key == "genre"
    assert lesson_type_for_format("tech_textbook").key == "mixed"
    assert lesson_type_for_format("legacy_unknown").key == "mixed"


def test_plan_type_inference_uses_format_text_and_target_mix(
    db_session, settings
) -> None:
    user = ensure_user(db_session, 555010001, settings)
    material = store_material(
        db_session,
        user,
        "Practice diplomatic pushback and scope negotiation.",
        type_="lesson_notes",
    )
    item = create_learning_item(
        db_session,
        user,
        type_="expression",
        text="I might be missing something, but...",
        source_material_id=material.id,
    )
    plan = create_lesson_plan_from_source(db_session, user, material, items=[item])
    plan.title = "Diplomatic pushback for scope negotiation"
    plan.format = "lesson"
    db_session.add(plan)
    db_session.flush()

    assert lesson_type_for_plan(plan, [item]).key == "diplomatic"


def test_public_catalog_export_excludes_private_and_raw_source_text(
    db_session, settings
) -> None:
    seed_and_publish_catalog_templates(db_session)
    owner = ensure_user(db_session, 555010002, settings)
    private_material = store_material(
        db_session,
        owner,
        "SECRET_PRIVATE_RAW_SOURCE",
        type_="lesson_notes",
    )
    private_item = create_learning_item(
        db_session,
        owner,
        type_="expression",
        text="SECRET_PRIVATE_ITEM",
        source_material_id=private_material.id,
    )
    create_lesson_plan_from_source(
        db_session, owner, private_material, items=[private_item]
    )

    library_user = get_seed_library_user(db_session)
    english_material = store_material(
        db_session,
        library_user,
        "RAW_PUBLIC_SOURCE_SHOULD_NOT_APPEAR",
        type_="lesson_notes",
    )
    english_item = create_learning_item(
        db_session,
        library_user,
        type_="chunk",
        text="ship a backwards-compatible migration",
        source_material_id=english_material.id,
    )
    english_plan = create_lesson_plan_from_source(
        db_session, library_user, english_material, items=[english_item]
    )
    english_plan.title = "English for Tech 01: Release Planning"
    english_plan.topic = "Engineering delivery"
    english_plan.goal = "Talk about release plans and migration risk."
    english_plan.format = "tech_textbook"
    english_plan.tags_json = ["series:english-for-tech"]
    english_plan.is_template = True
    english_material.is_template = True
    english_item.is_template = True
    db_session.add_all([english_plan, english_material, english_item])
    db_session.flush()

    catalog = build_public_catalog(db_session)
    files = render_catalog_files(catalog, html=True)
    joined = "\n".join(files.values())

    assert len([lesson for lesson in catalog if lesson.series_key == "scenarios"]) == 40
    assert any(CURRICULUM_TAG in lesson.tags for lesson in catalog)
    assert "English for Tech 01: Release Planning" in joined
    assert "/subscribe" in files["english-for-tech.html"]
    assert "SECRET_PRIVATE_RAW_SOURCE" not in joined
    assert "SECRET_PRIVATE_ITEM" not in joined
    assert "RAW_PUBLIC_SOURCE_SHOULD_NOT_APPEAR" not in joined


def test_public_catalog_groups_library_by_series_and_lesson_type(
    db_session, settings
) -> None:
    seed_and_publish_catalog_templates(db_session)
    user = ensure_user(db_session, 555010003, settings)
    library = handle_library(db_session, user, "risk")
    template = library_templates(db_session, query="risk")[0]
    template_details = handle_library_callback(
        db_session, user, "details", str(template.id)
    )
    subscribed = handle_subscribe(db_session, user, template.id)
    clone_id = int(subscribed.text.split("LessonPlan #", 1)[1].split(":", 1)[0])
    lesson_details = handle_lesson(db_session, user, str(clone_id))

    assert "Shared library matching risk" in library.text
    assert "Lesson type" in template_details.text
    assert "What you train" in template_details.text
    assert "Target mix" in lesson_details.text
