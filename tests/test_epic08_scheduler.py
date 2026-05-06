from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from fluentloop.db.session import make_engine, make_session_factory
from fluentloop.scheduler import (
    build_scheduler,
    run_backup,
    run_pre_generation,
    send_reminders,
    send_weekly_summaries,
    split_telegram_message,
)
from fluentloop.users import ensure_user


class FakeClient:
    def __init__(self) -> None:
        self.messages: list[tuple[int, str, dict]] = []

    async def send_message(self, chat_id: int, text: str, **kwargs) -> None:
        self.messages.append((chat_id, text, kwargs))


def test_scheduler_registers_core_jobs(db_session, settings) -> None:
    engine = make_engine("sqlite:///:memory:")
    factory = make_session_factory(engine)
    scheduler = build_scheduler(settings, factory, client=FakeClient())
    job_ids = {job.id for job in scheduler.get_jobs()}
    assert {
        "daily_sqlite_backup",
        "overnight_pre_generation",
        "daily_reminder",
        "weekly_summary",
    } <= job_ids


def test_backup_and_pre_generation_jobs(tmp_path, settings) -> None:
    db_path = tmp_path / "fluentloop.sqlite"
    local_settings = settings.__class__(
        **{**settings.__dict__, "db_url": f"sqlite:///{db_path}"}
    )
    engine = make_engine(local_settings.db_url)
    factory = make_session_factory(engine)
    with factory() as session:
        ensure_user(session, 123456789, local_settings)
        session.commit()
    assert run_pre_generation(local_settings, factory) == 1
    target = run_backup(local_settings)
    expected = Path(
        tmp_path / "backups" / f"db-{datetime.now(UTC).date()}.sqlite"
    )
    assert target == expected
    assert target.exists()

@pytest.mark.asyncio
async def test_reminder_sends_start_button(settings) -> None:
    engine = make_engine("sqlite:///:memory:")
    factory = make_session_factory(engine)
    with factory() as session:
        ensure_user(session, 123456789, settings)
        session.commit()
    client = FakeClient()
    assert await send_reminders(client, factory) == 1
    assert client.messages
    assert "Ready for today's English practice" in client.messages[0][1]
    assert client.messages[0][2]["buttons"]


@pytest.mark.asyncio
async def test_weekly_summary_sends_and_message_splitter(settings) -> None:
    engine = make_engine("sqlite:///:memory:")
    factory = make_session_factory(engine)
    with factory() as session:
        ensure_user(session, 123456789, settings)
        session.commit()
    client = FakeClient()
    assert await send_weekly_summaries(client, factory) == 1
    assert "Recommended focus next week" in client.messages[0][1]
    assert len(split_telegram_message("a\n" * 5000)) > 1
