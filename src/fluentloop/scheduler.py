from __future__ import annotations

import logging
from datetime import timedelta
from pathlib import Path
from typing import Any

import pytz
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from fluentloop.config import Settings
from fluentloop.db.models import PracticeSession, User, VocabDelivery
from fluentloop.db.session import session_scope
from fluentloop.practice import backup_sqlite, cache_session
from fluentloop.stats import weekly_summary
from fluentloop.vocab_loop import local_date

LOG = logging.getLogger(__name__)


def sqlite_path_from_url(db_url: str) -> Path:
    if db_url.startswith("sqlite:///"):
        return Path(db_url.removeprefix("sqlite:///"))
    raise ValueError("Only SQLite DB_URL is supported for local backups")


def run_backup(settings: Settings) -> Path:
    db_path = sqlite_path_from_url(settings.db_url)
    backup_dir = db_path.parent / "backups"
    target = backup_sqlite(
        db_path,
        backup_dir,
        retention_days=settings.backup_retention_days,
    )
    LOG.info("SQLite backup completed: %s", target)
    return target


def run_pre_generation(settings: Settings, session_factory: sessionmaker) -> int:
    count = 0
    with session_scope(session_factory) as session:
        users = session.scalars(select(User)).all()
        for user in users:
            # "Tomorrow" is relative to the learner's own day, not UTC.
            tomorrow = local_date(user) + timedelta(days=1)
            cache_session(session, user, target_date=tomorrow)
            count += 1
    LOG.info("Pre-generated practice sessions for %s user(s)", count)
    return count


async def send_reminders(client: Any, session_factory: sessionmaker) -> int:
    from telethon import Button

    sent = 0
    with session_scope(session_factory) as session:
        users = session.scalars(select(User)).all()
        for user in users:
            # PracticeSession.target_date_local is written in the user's
            # timezone, so the lookup has to use the same calendar.
            today = local_date(user)
            active = session.scalar(
                select(PracticeSession).where(
                    PracticeSession.user_id == user.id,
                    PracticeSession.target_date_local == today,
                    PracticeSession.status == "in_progress",
                )
            )
            if active is not None:
                continue
            await client.send_message(
                user.telegram_user_id,
                "Ready for today's English practice? Send /today.",
                buttons=[[Button.inline("Start", b"start_today")]],
            )
            sent += 1
    LOG.info("Sent %s reminder(s)", sent)
    return sent


def split_telegram_message(text: str, *, limit: int = 4096) -> list[str]:
    if len(text) <= limit:
        return [text]
    parts: list[str] = []
    current: list[str] = []
    current_len = 0
    for line in text.splitlines():
        line_len = len(line) + 1
        if current and current_len + line_len > limit:
            parts.append("\n".join(current))
            current = []
            current_len = 0
        current.append(line)
        current_len += line_len
    if current:
        parts.append("\n".join(current))
    return parts


async def send_weekly_summaries(client: Any, session_factory: sessionmaker) -> int:
    sent = 0
    with session_scope(session_factory) as session:
        users = session.scalars(select(User)).all()
        for user in users:
            for part in split_telegram_message(weekly_summary(session, user)):
                await client.send_message(user.telegram_user_id, part)
                sent += 1
    LOG.info("Sent %s weekly summary message(s)", sent)
    return sent


def claim_slot(
    session: Any,
    user: User,
    slot: str,
    day: Any,
) -> VocabDelivery | None:
    """Reserve a slot for one local day.

    The unique constraint on (user, local_date, slot, seq) is the lock: if
    another tick already claimed it the insert fails and we skip. This is what
    makes the dispatcher safe across restarts and overlapping ticks.
    """

    delivery = VocabDelivery(
        user_id=user.id,
        local_date=day,
        slot=slot,
        seq=0,
        status="claimed",
    )
    session.add(delivery)
    try:
        session.flush()
    except IntegrityError:
        session.rollback()
        return None
    return delivery


async def run_vocab_tick(
    client: Any,
    session_factory: sessionmaker,
    settings: Settings,
    *,
    now: Any | None = None,
) -> int:
    """Deliver any daily-loop slot that is due in each user's local time."""

    from fluentloop.bot.app import send_reply
    from fluentloop.bot.handlers import (
        render_daily_slot,
        set_drill_state,
    )
    from fluentloop.vocab_loop import due_slots, local_now
    from fluentloop.vocab_prefs import get_prefs

    sent = 0
    with session_scope(session_factory) as session:
        users = session.scalars(select(User)).all()
        for user in users:
            prefs = get_prefs(user)
            now_local = local_now(user, now=now)
            slots = due_slots(prefs, now_local)
            if not slots:
                continue
            for slot in slots:
                delivery = claim_slot(session, user, slot, now_local.date())
                if delivery is None:
                    continue
                try:
                    reply = render_daily_slot(
                        session, user, slot, delivery, now=now, settings=settings
                    )
                    if reply is None:
                        delivery.status = "skipped"
                        session.add(delivery)
                        continue
                    delivered = False
                    if slot == "evening" and settings.vocab_quiz_polls:
                        delivered = await _try_quiz_poll(client, user, delivery)
                    if not delivered:
                        message = await send_reply(
                            client, user.telegram_user_id, reply, settings
                        )
                        delivery.message_id = _message_id(message)
                    delivery.status = "sent"
                    if slot == "midday":
                        set_drill_state(session, user, delivery.id)
                    session.add(delivery)
                    sent += 1
                except Exception:
                    # Mark the row failed rather than leaving it claimed, so a
                    # broken slot is logged once instead of retried in a loop.
                    delivery.status = "failed"
                    session.add(delivery)
                    LOG.exception(
                        "Vocabulary %s slot failed for user %s", slot, user.id
                    )
    if sent:
        LOG.info("Delivered %s vocabulary slot message(s)", sent)
    return sent


async def _try_quiz_poll(client: Any, user: User, delivery: VocabDelivery) -> bool:
    """Send the evening quiz as a native poll, or report failure.

    A False return means the caller should fall back to the inline-button
    quiz, which is always prepared alongside.
    """

    from fluentloop.bot.polls import send_quiz_poll, spec_from_payload

    payload = delivery.payload_json or {}
    item_ids = delivery.learning_item_ids or []
    spec = spec_from_payload(payload, item_ids[0] if item_ids else 0)
    if spec is None:
        return False
    try:
        poll_id, message_id = await send_quiz_poll(
            client, user.telegram_user_id, spec
        )
    except Exception:
        LOG.exception("Native quiz poll failed; falling back to inline buttons")
        return False
    delivery.poll_id = poll_id
    delivery.message_id = message_id
    delivery.payload_json = {**payload, "mode": "poll"}
    return True


def _message_id(message: Any) -> int | None:
    for attribute in ("message_id", "id"):
        value = getattr(message, attribute, None)
        if isinstance(value, int):
            return value
    return None


def build_scheduler(
    settings: Settings,
    session_factory: sessionmaker,
    *,
    client: Any | None = None,
) -> AsyncIOScheduler:
    timezone = pytz.timezone(settings.timezone)
    scheduler = AsyncIOScheduler(timezone=timezone)
    scheduler.add_job(
        run_backup,
        "cron",
        hour=settings.backup_hour,
        minute=settings.backup_minute,
        args=[settings],
        id="daily_sqlite_backup",
        replace_existing=True,
        misfire_grace_time=3600,
    )
    scheduler.add_job(
        run_pre_generation,
        "cron",
        hour=settings.pre_gen_hour,
        minute=settings.pre_gen_minute,
        args=[settings, session_factory],
        id="overnight_pre_generation",
        replace_existing=True,
        misfire_grace_time=3600,
    )
    if client is not None:
        hour, minute = [int(part) for part in settings.reminder_time_default.split(":")]
        # APScheduler awaits coroutine functions directly. Wrapping them in
        # asyncio.create_task would drop the task reference and swallow errors.
        scheduler.add_job(
            send_reminders,
            "cron",
            hour=hour,
            minute=minute,
            args=[client, session_factory],
            id="daily_reminder",
            replace_existing=True,
            misfire_grace_time=1800,
        )
        scheduler.add_job(
            send_weekly_summaries,
            "cron",
            day_of_week="sun",
            hour=18,
            minute=0,
            args=[client, session_factory],
            id="weekly_summary",
            replace_existing=True,
            misfire_grace_time=3600,
        )
        scheduler.add_job(
            run_vocab_tick,
            "cron",
            minute="*",
            args=[client, session_factory, settings],
            id="vocab_loop_tick",
            replace_existing=True,
            misfire_grace_time=120,
            coalesce=True,
            max_instances=1,
        )
    return scheduler
