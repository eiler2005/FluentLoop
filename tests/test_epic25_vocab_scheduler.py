from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from sqlalchemy import select

from fluentloop.db.models import PracticeSession, VocabDelivery
from fluentloop.db.session import make_engine, make_session_factory
from fluentloop.learning import create_learning_item
from fluentloop.scheduler import (
    build_scheduler,
    claim_slot,
    run_vocab_tick,
    send_reminders,
)
from fluentloop.users import ensure_user
from fluentloop.vocab_prefs import update_pref

# 05:00 UTC is 08:00 in Moscow and 01:00 in New York.
MORNING_UTC = datetime(2026, 8, 17, 5, 0, tzinfo=UTC)


@dataclass
class SentMessage:
    chat_id: Any
    text: str
    id: int = 1


class FakeClient:
    """Records outbound messages instead of talking to Telegram."""

    def __init__(self) -> None:
        self.sent: list[SentMessage] = []

    async def send_message(self, chat_id, text, buttons=None, parse_mode=None):
        message = SentMessage(chat_id=chat_id, text=text, id=len(self.sent) + 1)
        self.sent.append(message)
        return message


@pytest.fixture
def factory(tmp_path):
    engine = make_engine(f"sqlite:///{tmp_path / 'tick.sqlite'}")
    return make_session_factory(engine)


def _seed_user(factory, settings, telegram_id: int, timezone: str) -> int:
    with factory() as session:
        user = ensure_user(session, telegram_id, settings)
        user.timezone = timezone
        for index in range(4):
            create_learning_item(
                session,
                user,
                type_="word",
                text=f"word-{telegram_id}-{index}",
                meaning="a meaning",
                examples=["An example sentence."],
            )
        session.commit()
        return user.id


# --- the tick --------------------------------------------------------------


@pytest.mark.asyncio
async def test_tick_delivers_morning_slot_in_user_timezone(factory, settings) -> None:
    _seed_user(factory, settings, 123456789, "Europe/Moscow")
    client = FakeClient()

    sent = await run_vocab_tick(client, factory, settings, now=MORNING_UTC)

    assert sent == 1
    assert "Morning phrases" in client.sent[0].text


@pytest.mark.asyncio
async def test_tick_is_idempotent_across_restarts(factory, settings) -> None:
    _seed_user(factory, settings, 123456789, "Europe/Moscow")
    client = FakeClient()

    first = await run_vocab_tick(client, factory, settings, now=MORNING_UTC)
    # A minute later - or after a restart - the claim row blocks a resend.
    second = await run_vocab_tick(
        client, factory, settings, now=MORNING_UTC + timedelta(minutes=1)
    )

    assert (first, second) == (1, 0)
    assert len(client.sent) == 1


@pytest.mark.asyncio
async def test_tick_skips_users_in_other_timezones(factory, settings) -> None:
    _seed_user(factory, settings, 987654321, "America/New_York")
    client = FakeClient()

    sent = await run_vocab_tick(client, factory, settings, now=MORNING_UTC)

    assert sent == 0
    assert client.sent == []


@pytest.mark.asyncio
async def test_tick_respects_pause(factory, settings) -> None:
    _seed_user(factory, settings, 123456789, "Europe/Moscow")
    with factory() as session:
        user = ensure_user(session, 123456789, settings)
        update_pref(session, user, "paused", True)
        session.commit()
    client = FakeClient()

    assert await run_vocab_tick(client, factory, settings, now=MORNING_UTC) == 0


@pytest.mark.asyncio
async def test_tick_records_delivery_row(factory, settings) -> None:
    _seed_user(factory, settings, 123456789, "Europe/Moscow")
    client = FakeClient()

    await run_vocab_tick(client, factory, settings, now=MORNING_UTC)

    with factory() as session:
        delivery = session.scalar(select(VocabDelivery))
        assert delivery is not None
        assert delivery.slot == "morning"
        assert delivery.status == "sent"
        assert delivery.local_date == datetime(2026, 8, 17).date()
        assert delivery.learning_item_ids


@pytest.mark.asyncio
async def test_tick_skips_slot_without_items(factory, settings) -> None:
    with factory() as session:
        ensure_user(session, 123456789, settings)
        session.commit()
    client = FakeClient()

    sent = await run_vocab_tick(client, factory, settings, now=MORNING_UTC)

    assert sent == 0
    with factory() as session:
        delivery = session.scalar(select(VocabDelivery))
        assert delivery is not None
        assert delivery.status == "skipped"


@pytest.mark.asyncio
async def test_tick_delivers_evening_quiz_with_options(factory, settings) -> None:
    _seed_user(factory, settings, 123456789, "Europe/Moscow")
    client = FakeClient()
    # 16:00 UTC is 19:00 in Moscow.
    evening = datetime(2026, 8, 17, 16, 0, tzinfo=UTC)

    sent = await run_vocab_tick(client, factory, settings, now=evening)

    assert sent == 1
    assert "Evening quiz" in client.sent[0].text
    with factory() as session:
        delivery = session.scalar(
            select(VocabDelivery).where(VocabDelivery.slot == "evening")
        )
        assert len(delivery.payload_json["options"]) == 4


@pytest.mark.asyncio
async def test_tick_catches_up_inside_the_window(factory, settings) -> None:
    _seed_user(factory, settings, 123456789, "Europe/Moscow")
    client = FakeClient()
    late = MORNING_UTC + timedelta(minutes=45)

    assert await run_vocab_tick(client, factory, settings, now=late) == 1


@pytest.mark.asyncio
async def test_tick_gives_up_after_the_window(factory, settings) -> None:
    _seed_user(factory, settings, 123456789, "Europe/Moscow")
    client = FakeClient()
    too_late = MORNING_UTC + timedelta(minutes=95)

    assert await run_vocab_tick(client, factory, settings, now=too_late) == 0


def test_claim_slot_returns_none_on_second_claim(db_session, settings) -> None:
    user = ensure_user(db_session, 123456789, settings)
    day = datetime(2026, 8, 17).date()

    assert claim_slot(db_session, user, "morning", day) is not None
    assert claim_slot(db_session, user, "morning", day) is None


# --- scheduler registration and the fixed date bugs ------------------------


def test_scheduler_registers_the_tick_and_keeps_legacy_jobs(settings) -> None:
    engine = make_engine("sqlite:///:memory:")
    factory = make_session_factory(engine)

    scheduler = build_scheduler(settings, factory, client=FakeClient())

    job_ids = {job.id for job in scheduler.get_jobs()}
    assert "vocab_loop_tick" in job_ids
    assert {
        "daily_sqlite_backup",
        "overnight_pre_generation",
        "daily_reminder",
        "weekly_summary",
    } <= job_ids


def test_scheduler_jobs_are_coroutines_not_lambdas(settings) -> None:
    import inspect

    engine = make_engine("sqlite:///:memory:")
    factory = make_session_factory(engine)

    scheduler = build_scheduler(settings, factory, client=FakeClient())

    for job_id in ("daily_reminder", "weekly_summary", "vocab_loop_tick"):
        job = scheduler.get_job(job_id)
        assert inspect.iscoroutinefunction(job.func), job_id


@pytest.mark.asyncio
async def test_send_reminders_uses_the_user_local_date(factory, settings) -> None:
    """Regression: the active-session lookup used to compare against UTC."""

    with factory() as session:
        user = ensure_user(session, 123456789, settings)
        user.timezone = "Pacific/Kiritimati"  # UTC+14, so local date runs ahead
        session.flush()
        local_today = (datetime.now(UTC) + timedelta(hours=14)).date()
        session.add(
            PracticeSession(
                user_id=user.id,
                target_date_local=local_today,
                status="in_progress",
            )
        )
        session.commit()
    client = FakeClient()

    sent = await send_reminders(client, factory)

    assert sent == 0
    assert client.sent == []


@pytest.mark.asyncio
async def test_a_duplicate_claim_does_not_erase_earlier_deliveries(
    factory, settings
) -> None:
    """Regression: session.rollback() in claim_slot wiped the whole tick.

    Two users are due in the same tick. The first has no delivery row yet and
    is sent to; the second already has one, so its claim conflicts. That
    conflict must not discard the first user's row - otherwise the slot is
    re-delivered every minute for the whole catch-up window.
    """

    _seed_user(factory, settings, settings.telegram_allowed_user_id, "Europe/Moscow")
    _seed_user(factory, settings, 222222222, "Europe/Moscow")
    with factory() as session:
        # Pre-claim the morning slot for the SECOND user only.
        second = ensure_user(session, 222222222, settings)
        session.add(
            VocabDelivery(
                user_id=second.id,
                local_date=MORNING_UTC.astimezone(
                    __import__("zoneinfo").ZoneInfo("Europe/Moscow")
                ).date(),
                slot="morning",
                seq=0,
                status="sent",
            )
        )
        session.commit()

    client = FakeClient()
    sent = await run_vocab_tick(client, factory, settings, now=MORNING_UTC)

    assert sent == 1
    with factory() as session:
        rows = session.scalars(select(VocabDelivery)).all()
        # One pre-existing row plus one newly persisted row.
        assert len(rows) == 2
        assert {row.status for row in rows} == {"sent"}

    # The next tick must be a no-op, which is only true if the row survived.
    again = await run_vocab_tick(
        client, factory, settings, now=MORNING_UTC + timedelta(minutes=1)
    )
    assert again == 0
    assert len(client.sent) == 1


@pytest.mark.asyncio
async def test_tick_skips_accounts_the_bot_would_reject(factory, settings) -> None:
    """Seed/demo rows must not generate a Telegram call per slot per day."""

    _seed_user(factory, settings, settings.telegram_allowed_user_id, "Europe/Moscow")
    _seed_user(factory, settings, 900000501, "Europe/Moscow")
    client = FakeClient()

    sent = await run_vocab_tick(client, factory, settings, now=MORNING_UTC)

    assert sent == 1
    assert client.sent[0].chat_id == settings.telegram_allowed_user_id
    with factory() as session:
        rows = session.scalars(select(VocabDelivery)).all()
        assert len(rows) == 1
