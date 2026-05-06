from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytz
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from fluentloop.config import Settings
from fluentloop.db.models import PracticeSession, User
from fluentloop.db.session import session_scope
from fluentloop.practice import backup_sqlite, cache_session

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
    tomorrow = datetime.now(UTC).date() + timedelta(days=1)
    count = 0
    with session_scope(session_factory) as session:
        users = session.scalars(select(User)).all()
        for user in users:
            cache_session(session, user, target_date=tomorrow)
            count += 1
    LOG.info("Pre-generated practice sessions for %s user(s)", count)
    return count


async def send_reminders(client: Any, session_factory: sessionmaker) -> int:
    sent = 0
    with session_scope(session_factory) as session:
        users = session.scalars(select(User)).all()
        for user in users:
            today = datetime.now(UTC).date()
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
            )
            sent += 1
    LOG.info("Sent %s reminder(s)", sent)
    return sent


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
        scheduler.add_job(
            lambda: asyncio.create_task(send_reminders(client, session_factory)),
            "cron",
            hour=hour,
            minute=minute,
            id="daily_reminder",
            replace_existing=True,
            misfire_grace_time=1800,
        )
    return scheduler

