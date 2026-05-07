from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from fluentloop.ai.provider import StubProvider
from fluentloop.bot.handlers import (
    handle_answer,
    handle_attempt_ack,
    handle_dispute,
    handle_today,
)
from fluentloop.db.models import (
    MistakeEvent,
    MistakePattern,
    PracticeAttempt,
    PracticeSession,
)
from fluentloop.exercises import EXERCISE_TYPES, render_for_item
from fluentloop.learning import create_learning_item
from fluentloop.practice import (
    compose_session,
    next_exercise,
    record_attempt,
    start_or_resume_session,
    summarize_session,
)
from fluentloop.srs import get_due_items, record_result
from fluentloop.users import ensure_user


def test_srs_intervals_and_due_order(db_session, settings) -> None:
    user = ensure_user(db_session, 123456789, settings)
    item = create_learning_item(db_session, user, type_="expression", text="align on")
    now = datetime.now(UTC)
    state = record_result(db_session, item.id, "Good", now=now)
    assert timedelta(days=1, hours=23) < state.due_at - now < timedelta(days=3)
    state = record_result(db_session, item.id, "Again", now=now)
    assert state.due_at == now
    assert get_due_items(db_session, user.id, now=now)[0].id == item.id
    for _ in range(3):
        state = record_result(db_session, item.id, "Good", now=now)
    assert state.due_at - now >= timedelta(days=7)


def test_exercise_registry_and_session_resume(db_session, settings) -> None:
    user = ensure_user(db_session, 123456789, settings)
    item = create_learning_item(
        db_session,
        user,
        type_="expression",
        text="push back on",
        meaning="мягко возражать",
        examples=["I'd like to push back on this proposal."],
    )
    assert len(EXERCISE_TYPES) == 6
    rendered = render_for_item(item, "cloze")
    assert "____" in rendered.prompt
    practice = start_or_resume_session(db_session, user)
    first = next_exercise(db_session, practice)
    assert first is not None
    index, exercise = first
    record_attempt(
        db_session,
        practice,
        index,
        exercise,
        "push back on",
        {"status": "correct"},
    )
    resumed = start_or_resume_session(db_session, user)
    second = next_exercise(db_session, resumed)
    assert second is not None
    assert second[0] == 1


def test_compose_session_avoids_item_duplicates_and_uses_seed_fillers(
    db_session, settings
) -> None:
    user = ensure_user(db_session, 123456789, settings)
    item = create_learning_item(
        db_session,
        user,
        type_="expression",
        text="align on",
        meaning="согласовать",
    )
    exercises = compose_session(db_session, user)
    targeted = [
        target_id
        for exercise in exercises
        for target_id in exercise["target_learning_item_ids"]
    ]
    assert targeted.count(item.id) == 1
    assert len(exercises) == 7
    assert any(not exercise["target_learning_item_ids"] for exercise in exercises)


def test_session_summary_counts_attempt_statuses(db_session, settings) -> None:
    user = ensure_user(db_session, 123456789, settings)
    practice = start_or_resume_session(db_session, user)
    first = next_exercise(db_session, practice)
    assert first is not None
    index, exercise = first
    record_attempt(
        db_session,
        practice,
        index,
        exercise,
        "answer",
        {"status": "correct"},
    )
    summary = summarize_session(db_session, practice)
    assert "Correct: 1" in summary
    assert "Answered: 1/7" in summary


def test_session_completion_marks_completed_after_all_attempts(
    db_session, settings
) -> None:
    user = ensure_user(db_session, 123456789, settings)
    practice = start_or_resume_session(db_session, user)
    for _ in range(7):
        current = next_exercise(db_session, practice)
        assert current is not None
        index, exercise = current
        record_attempt(
            db_session,
            practice,
            index,
            exercise,
            "answer",
            {"status": "correct"},
        )
    assert next_exercise(db_session, practice) is None
    assert practice.status == "completed"
    assert practice.completed_at is not None


def test_high_confidence_mistake_pattern_adds_refresher(
    db_session, settings
) -> None:
    user = ensure_user(db_session, 123456789, settings)
    db_session.add(
        MistakePattern(
            user_id=user.id,
            description="Recurring article issue",
            mistake_type="articles",
            confidence="high",
            status="active",
            wrong_examples=["We start before sprint."],
            correct_examples=["We start before the sprint."],
            event_count=3,
        )
    )
    db_session.flush()
    exercises = compose_session(db_session, user)
    assert any("recurring articles" in exercise["prompt"] for exercise in exercises)


def test_feedback_dispute_logs_and_removes_mistake_event(
    tmp_path, db_session, settings
) -> None:
    user = ensure_user(db_session, 123456789, settings)
    create_learning_item(db_session, user, type_="expression", text="align on")
    start_or_resume_session(db_session, user)
    handle_answer(db_session, user, StubProvider(tmp_path / "usage.jsonl"), "wrong")
    attempt = db_session.scalar(select(PracticeAttempt))
    assert attempt is not None
    assert db_session.scalar(select(MistakeEvent)) is not None

    reply = handle_dispute(
        db_session,
        user,
        attempt.id,
        "mine was equally valid",
        base_dir=tmp_path / "disputes",
    )
    assert "Dispute logged" in reply.text
    assert db_session.scalar(select(MistakeEvent)) is None
    assert attempt.status == "disputed"
    assert list((tmp_path / "disputes").glob("*.jsonl"))

    ack = handle_attempt_ack(db_session, user, attempt.id)
    assert f"attempt #{attempt.id}" in ack.text


def test_answer_targets_channel_when_channel_mode_enabled(db_session, settings) -> None:
    user = ensure_user(db_session, 123456789, settings)
    create_learning_item(db_session, user, type_="expression", text="align on")
    start_or_resume_session(db_session, user)
    reply = handle_answer(
        db_session,
        user,
        StubProvider(),
        "align on",
        channel_id="-100123",
    )
    assert reply.target_chat_id == "-100123"
    assert reply.text.startswith("#feedback\nAttempt #")
    assert "#next_prompt\nExercise 2/7" in reply.text
    assert "Exercise 2/7" in reply.text
    assert reply.buttons is not None
    button_data = {button.data for row in reply.buttons for button in row}
    assert "attempt:ack:1" in button_data
    assert "dispute:1:equally_valid" in button_data


def test_today_targets_channel_with_logical_topic(db_session, settings) -> None:
    user = ensure_user(db_session, 123456789, settings)
    create_learning_item(db_session, user, type_="expression", text="align on")
    reply = handle_today(db_session, user, channel_id="-100123")
    assert reply.target_chat_id == "-100123"
    assert reply.text.startswith("#practice_flow\nToday's English practice")


def test_answer_without_session_does_not_create_practice(db_session, settings) -> None:
    user = ensure_user(db_session, 123456789, settings)
    reply = handle_answer(db_session, user, StubProvider(), "anything")
    assert "No active exercise" in reply.text
    assert "/upload" in reply.text
    assert db_session.scalar(select(PracticeSession)) is None
