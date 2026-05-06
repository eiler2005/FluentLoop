from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fluentloop.exercises import EXERCISE_TYPES, render_for_item
from fluentloop.learning import create_learning_item
from fluentloop.practice import next_exercise, record_attempt, start_or_resume_session
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
