from __future__ import annotations

from sqlalchemy import select

from fluentloop.ai.provider import StubProvider
from fluentloop.ai.schemas import Validated
from fluentloop.bot.handlers import (
    handle_approve_all,
    handle_candidate_action,
    handle_candidates,
    handle_mistake_action,
    handle_upload,
)
from fluentloop.db.models import ExtractedCandidate, LearningItem, MistakeEvent
from fluentloop.feedback import apply_feedback, check_answer
from fluentloop.materials import approve_all, extract_candidates, store_material
from fluentloop.mistakes import ingest_mistake_event, promote_pattern
from fluentloop.users import ensure_user


class MalformedProvider(StubProvider):
    def heavy_call(self, task: str, payload: dict) -> Validated:
        raise RuntimeError("bad model output")


def test_upload_extract_approve_and_feedback(tmp_path, db_session, settings) -> None:
    user = ensure_user(db_session, 123456789, settings)
    provider = StubProvider(tmp_path / "usage.jsonl")
    material = store_material(db_session, user, "push back on; align on; articles")
    candidates = extract_candidates(db_session, material, provider)
    assert len(candidates) >= 3
    assert approve_all(db_session, user, material) == len(candidates)
    exercise = {
        "exercise_type": "translate",
        "prompt": "Translate",
        "expected_answer": "push back on",
        "target_learning_item_ids": [],
    }
    feedback = check_answer(provider, exercise, "push back")
    assert feedback.status in {"partial", "correct"}
    apply_feedback(db_session, user, exercise, "push back", feedback)
    assert (tmp_path / "usage.jsonl").exists()


def test_upload_handler_returns_approve_command(tmp_path, db_session, settings) -> None:
    user = ensure_user(db_session, 123456789, settings)
    provider = StubProvider(tmp_path / "usage.jsonl")
    reply = handle_upload(db_session, user, provider, "push back on and align on")
    assert "Send /approve" in reply.text
    material_id = int(reply.text.split("/approve ", 1)[1].split()[0])
    listed = handle_candidates(db_session, user, material_id)
    assert "Use /candidate add" in listed.text
    candidate = db_session.scalar(select(ExtractedCandidate))
    assert candidate is not None
    skipped = handle_candidate_action(db_session, user, "skip", candidate.id)
    assert "Skipped" in skipped.text
    added = handle_candidate_action(db_session, user, "add", candidate.id)
    assert "already handled" in added.text
    approved = handle_approve_all(db_session, user, material_id)
    assert "Added" in approved.text
    item = db_session.scalar(
        select(LearningItem).where(LearningItem.user_id == user.id)
    )
    assert item is not None


def test_upload_handler_returns_friendly_size_error(
    tmp_path, db_session, settings
) -> None:
    user = ensure_user(db_session, 123456789, settings)
    provider = StubProvider(tmp_path / "usage.jsonl")
    reply = handle_upload(db_session, user, provider, "x" * 10_001)
    assert "Could not store material" in reply.text


def test_upload_handler_returns_friendly_extraction_error(
    tmp_path, db_session, settings
) -> None:
    user = ensure_user(db_session, 123456789, settings)
    provider = MalformedProvider(tmp_path / "usage.jsonl")
    reply = handle_upload(db_session, user, provider, "push back on")
    assert "Could not extract material" in reply.text
    assert "try again or rephrase" in reply.text


def test_mistake_pattern_threshold(db_session, settings) -> None:
    user = ensure_user(db_session, 123456789, settings)
    pattern = None
    for index in range(3):
        event = MistakeEvent(
            user_id=user.id,
            wrong_answer=f"wrong {index}",
            corrected_answer="right",
            explanation="because",
            mistake_type="articles",
        )
        db_session.add(event)
        db_session.flush()
        pattern = ingest_mistake_event(db_session, event)
    assert pattern is not None
    assert pattern.confidence == "low"
    promote_pattern(db_session, pattern)
    assert pattern.confidence == "high"


def test_mistake_pattern_actions(db_session, settings) -> None:
    user = ensure_user(db_session, 123456789, settings)
    pattern = None
    for index in range(3):
        event = MistakeEvent(
            user_id=user.id,
            wrong_answer=f"wrong {index}",
            corrected_answer="right",
            explanation="because",
            mistake_type="articles",
        )
        db_session.add(event)
        db_session.flush()
        pattern = ingest_mistake_event(db_session, event)
    assert pattern is not None
    reply = handle_mistake_action(db_session, user, "focus", pattern.id)
    assert "Promoted" in reply.text
    assert pattern.confidence == "high"
    reply = handle_mistake_action(db_session, user, "ignore", pattern.id)
    assert "Archived" in reply.text
    assert pattern.status == "archived"
