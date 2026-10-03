from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import select

from fluentloop.db.models import PracticeAttempt, PracticeSession, VocabDelivery
from fluentloop.db.session import make_engine, make_session_factory
from fluentloop.learning import create_learning_item
from fluentloop.learning_prefs import (
    get_learning_mode,
    is_simple_mode,
    set_learning_mode,
)
from fluentloop.outcomes import collect_outcome_metrics
from fluentloop.scheduler import (
    run_pre_generation,
    run_vocab_tick,
    send_reminders,
    send_weekly_summaries,
)
from fluentloop.users import ensure_user


class FakeClient:
    def __init__(self) -> None:
        self.messages: list[str] = []

    async def send_message(self, chat_id: int, text: str, **kwargs) -> None:
        self.messages.append(text)


def test_mode_roundtrip_preserves_existing_preferences(db_session, settings) -> None:
    user = ensure_user(db_session, 123456789, settings)
    legacy = {"vocab": {"paused": True, "slots": {"morning": "09:30"}}}
    user.preferences_json = legacy
    assert get_learning_mode(user) == "advanced"
    set_learning_mode(db_session, user, "simple")
    db_session.commit()
    db_session.expire_all()
    assert is_simple_mode(user)
    assert user.preferences_json["vocab"] == legacy["vocab"]
    set_learning_mode(db_session, user, "advanced")
    assert user.preferences_json["vocab"] == legacy["vocab"]
    with pytest.raises(ValueError):
        set_learning_mode(db_session, user, "unknown")
    user.preferences_json = {"learning": {"mode": []}}
    assert get_learning_mode(user) == "advanced"


@pytest.mark.asyncio
async def test_simple_profile_has_no_scheduled_learning_messages(settings) -> None:
    factory = make_session_factory(make_engine("sqlite:///:memory:"))
    with factory() as session:
        user = ensure_user(session, 123456789, settings)
        create_learning_item(
            session,
            user,
            type_="expression",
            text="align on scope",
            meaning="Agree on the boundaries of a project",
            examples=["We should align on scope before Friday."],
        )
        set_learning_mode(session, user, "simple")
        session.commit()
    client = FakeClient()
    assert run_pre_generation(settings, factory) == 0
    assert await send_reminders(client, factory) == 0
    assert await send_weekly_summaries(client, factory) == 0
    assert await run_vocab_tick(
        client, factory, settings, now=datetime(2026, 10, 3, 5, 0, tzinfo=UTC)
    ) == 0
    assert client.messages == []
    with factory() as session:
        assert session.scalar(select(VocabDelivery)) is None
        user = ensure_user(session, 123456789, settings)
        set_learning_mode(session, user, "advanced")
        session.commit()
    assert run_pre_generation(settings, factory) == 1
    assert await send_reminders(client, factory) == 1
    assert await send_weekly_summaries(client, factory) == 1


def test_choices_do_not_inflate_productive_outcomes(db_session, settings) -> None:
    user = ensure_user(db_session, 123456789, settings)
    item = create_learning_item(
        db_session, user, type_="chunk", text="align on scope"
    )
    now = datetime.now(UTC)
    run = PracticeSession(
        user_id=user.id, target_date_local=now.date(), status="completed", exercises=[]
    )
    db_session.add(run)
    db_session.flush()
    for index in range(3):
        db_session.add(
            PracticeAttempt(
                practice_session_id=run.id,
                exercise_index=index,
                exercise_type="simple_choice",
                target_learning_item_ids=[item.id],
                prompt="Choose the right phrase.",
                user_answer="align on scope",
                status="correct",
                feedback={"answer_modality": "recognition"},
            )
        )
    db_session.flush()
    metrics = collect_outcome_metrics(db_session, user, now=now)
    assert metrics["attempts"]["total"] == 3
    assert metrics["attempts"]["recognition"] == 3
    assert metrics["attempts"]["production"] == 0
    assert metrics["attempts"]["word_count"] == 0
    assert metrics["productive_chunks"]["productive_count"] == 0
    assert metrics["writing"]["status"].startswith("insufficient")
    db_session.add(
        PracticeAttempt(
            practice_session_id=run.id,
            exercise_index=3,
            exercise_type="simple_production",
            target_learning_item_ids=[item.id],
            prompt="Write one workplace sentence.",
            user_answer="We should align on scope before Friday.",
            status="correct",
            feedback={"answer_modality": "production"},
        )
    )
    db_session.flush()
    metrics = collect_outcome_metrics(db_session, user, now=now)
    assert metrics["attempts"]["production"] == 1
    assert metrics["attempts"]["recognition"] == 3
    assert metrics["productive_chunks"]["top_chunks"][0]["uses"] == 1
