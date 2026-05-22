from __future__ import annotations

from sqlalchemy import select

from fluentloop.ai.provider import StubProvider
from fluentloop.bot.handlers import (
    handle_answer,
    handle_confidence_rating,
    handle_feedback_layer,
    handle_practice,
)
from fluentloop.curriculum_chunks import ChunkRecord, import_chunk_records
from fluentloop.db.models import LearningItem, MistakeEvent, PracticeAttempt
from fluentloop.evaluation import build_monthly_probe, writing_metrics
from fluentloop.learning import create_learning_item
from fluentloop.lesson_formats import GENRE_SPECS, scenario_cards
from fluentloop.practice import start_or_resume_session
from fluentloop.reflections import record_reflection
from fluentloop.russian_l1_filter import detect_l1_interference
from fluentloop.users import ensure_user


def test_layered_feedback_l1_hit_and_confidence_callbacks(db_session, settings) -> None:
    user = ensure_user(db_session, 123456789, settings)
    create_learning_item(db_session, user, type_="expression", text="depend on")
    start_or_resume_session(db_session, user)

    confidence = handle_confidence_rating(db_session, user, 0, 5)
    reply = handle_answer(db_session, user, StubProvider(), "It depends from release.")
    attempt = db_session.scalar(select(PracticeAttempt))

    assert "Confidence recorded" in confidence.text
    assert attempt is not None
    assert attempt.feedback["confidence_rating"] == 5
    assert attempt.feedback["l1_hits"][0]["rule_id"] == "l1_depend_from"
    assert "L1 trap" in reply.text
    assert "feedback:layer:1:errors" in {
        button.data for row in (reply.buttons or []) for button in row
    }
    assert db_session.scalar(select(MistakeEvent)) is not None

    layer = handle_feedback_layer(db_session, user, attempt.id, "native")
    assert "Native rewrite" in layer.text


def test_epic22_practice_mode_registry_drives_session(db_session, settings) -> None:
    user = ensure_user(db_session, 123456789, settings)
    create_learning_item(
        db_session,
        user,
        type_="expression",
        text="push back on",
        tags=["stakeholder"],
    )

    reply = handle_practice(db_session, user, "diplomatic")

    assert "Diplomatic Rewrite Drill" in reply.text
    assert "practice:confidence:0:5" in {
        button.data for row in (reply.buttons or []) for button in row
    }
    assert len(scenario_cards()) == 40
    assert len(GENRE_SPECS) == 10


def test_reflection_evaluation_and_chunk_import(tmp_path, db_session, settings) -> None:
    user = ensure_user(db_session, 123456789, settings)
    for index in range(12):
        create_learning_item(
            db_session,
            user,
            type_="expression",
            text=f"chunk {index}",
        )

    reflection_path = record_reflection(
        user, "Hardest part: hedging.", base_dir=tmp_path
    )
    probe = build_monthly_probe(db_session, user)
    metrics = writing_metrics("We might need to adjust scope. It could reduce risk.")
    created, skipped = import_chunk_records(
        db_session,
        user,
        [
            ChunkRecord(
                id="chunk_0001",
                text="the underlying assumption is that",
                type="collocation",
                field="UNCERTAINTY",
                register="professional",
                function="hedging",
                genres=["rfc"],
                cefr_target="C1",
                russian_gloss="лежащее в основе предположение",
                example_sentences=[
                    "The underlying assumption is that demand grows linearly."
                ],
            )
        ],
    )
    item = db_session.scalar(
        select(LearningItem).where(
            LearningItem.text == "the underlying assumption is that"
        )
    )

    assert reflection_path.exists()
    assert probe.held_out_item_ids
    assert metrics["hedging_density"] > 0
    assert (created, skipped) == (1, 0)
    assert item is not None
    assert item.type == "chunk"
    assert item.metadata_json["field"] == "UNCERTAINTY"


def test_russian_l1_hit_list_is_deterministic() -> None:
    hits = detect_l1_interference(
        "We must discuss about this, it depends from the API."
    )

    assert [hit.rule_id for hit in hits[:2]] == [
        "l1_depend_from",
        "l1_discuss_about",
    ]
