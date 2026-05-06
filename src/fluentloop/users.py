from __future__ import annotations

import re

import pytz
from sqlalchemy import select
from sqlalchemy.orm import Session

from fluentloop.config import Settings
from fluentloop.db.models import User, utc_now

DEFAULT_FOCUS = ["business", "IT", "conversational", "grammar"]
LEVELS = {"B2", "B2+", "C1-", "C1", "B2+/C1-"}
LANGUAGES = {"ru", "en", "mixed"}
TIME_RE = re.compile(r"^\d{2}:\d{2}$")


def ensure_user(session: Session, telegram_user_id: int, settings: Settings) -> User:
    user = session.scalar(select(User).where(User.telegram_user_id == telegram_user_id))
    if user is not None:
        return user
    user = User(
        telegram_user_id=telegram_user_id,
        level="B2+/C1-",
        focus_areas=list(DEFAULT_FOCUS),
        timezone=settings.timezone,
        reminder_time=settings.reminder_time_default,
        practice_duration_minutes=settings.practice_duration_minutes,
        explanation_language="mixed",
    )
    session.add(user)
    session.flush()
    return user


def format_settings(user: User) -> str:
    focus = ", ".join(user.focus_areas)
    return (
        "Settings\n"
        f"Level: {user.level}\n"
        f"Focus: {focus}\n"
        f"Timezone: {user.timezone}\n"
        f"Reminder: {user.reminder_time}\n"
        f"Practice: {user.practice_duration_minutes} min\n"
        f"Explanations: {user.explanation_language}"
    )


def update_setting(session: Session, user: User, field: str, value: str) -> User:
    if field == "level":
        if value not in LEVELS:
            raise ValueError("Unsupported level")
        user.level = value
    elif field == "focus_areas":
        items = [item.strip() for item in value.split(",") if item.strip()]
        if not items:
            raise ValueError("At least one focus area is required")
        user.focus_areas = items
    elif field == "timezone":
        if value not in pytz.all_timezones:
            raise ValueError("Unknown timezone")
        user.timezone = value
    elif field == "reminder_time":
        if not TIME_RE.match(value):
            raise ValueError("Use HH:MM")
        hour, minute = [int(part) for part in value.split(":")]
        if hour > 23 or minute > 59:
            raise ValueError("Use HH:MM")
        user.reminder_time = value
    elif field == "explanation_language":
        if value not in LANGUAGES:
            raise ValueError("Use ru, en, or mixed")
        user.explanation_language = value
    elif field == "practice_duration_minutes":
        minutes = int(value)
        if minutes < 5 or minutes > 60:
            raise ValueError("Practice duration must be 5-60 minutes")
        user.practice_duration_minutes = minutes
    else:
        raise ValueError("Unknown setting")
    user.updated_at = utc_now()
    session.add(user)
    session.flush()
    return user
