from __future__ import annotations

from sqlalchemy import select

from fluentloop.db.models import MaterialChunk
from fluentloop.learning import create_learning_item
from fluentloop.learning_engine import compose_learning_session
from fluentloop.lesson_plans import create_lesson_plan_from_source
from fluentloop.material_context import (
    build_material_context,
    index_source_material,
    search_material_chunks,
    split_material_into_chunks,
)
from fluentloop.materials import store_material
from fluentloop.users import ensure_user


def test_split_material_into_chunks_bounds_text() -> None:
    text = "\n\n".join(
        f"Paragraph {index} about stakeholder communication." for index in range(20)
    )

    chunks = split_material_into_chunks(text, max_chars=180)

    assert len(chunks) > 1
    assert all(len(chunk) <= 180 for chunk in chunks)


def test_store_material_indexes_chunks(db_session, settings) -> None:
    user = ensure_user(db_session, 123456789, settings)
    material = store_material(
        db_session,
        user,
        "[CODEX_TEST] Architecture trade-offs.\n\nStakeholder communication.",
    )

    chunks = list(
        db_session.scalars(
            select(MaterialChunk).where(MaterialChunk.source_material_id == material.id)
        )
    )

    assert chunks
    assert index_source_material(db_session, material) == chunks


def test_search_material_chunks_returns_relevant_chunks(db_session, settings) -> None:
    user = ensure_user(db_session, 123456789, settings)
    store_material(
        db_session,
        user,
        (
            "[CODEX_TEST] Architecture trade-offs require stakeholder "
            "communication, hedging, and risk mitigation."
        ),
    )

    results = search_material_chunks(
        db_session,
        user,
        "stakeholder communication hedging trade-off architecture",
    )

    assert results
    assert "stakeholder" in results[0].text.lower()


def test_build_material_context_empty_fallback(db_session, settings) -> None:
    user = ensure_user(db_session, 123456789, settings)

    assert build_material_context(db_session, user, "missing topic") == []


def test_learning_engine_uses_lesson_material_context(db_session, settings) -> None:
    user = ensure_user(db_session, 123456789, settings)
    material = store_material(
        db_session,
        user,
        (
            "[CODEX_TEST] Topic: architecture trade-offs. "
            "The safest next step is to delay a risky release and align on "
            "stakeholder priorities."
        ),
        type_="lesson_notes",
    )
    create_learning_item(
        db_session,
        user,
        type_="expression",
        text="the safest next step is",
        source_material_id=material.id,
        tags=["architecture"],
    )
    create_lesson_plan_from_source(db_session, user, material)

    exercises = compose_learning_session(db_session, user)
    input_step = next(
        exercise for exercise in exercises if exercise["stage"] == "input"
    )

    assert "Material context:" in input_step["prompt"]
    assert input_step["metadata"]["material_context_chunk_ids"]
