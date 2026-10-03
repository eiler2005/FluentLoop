"""Per-user learning entrance; existing daily-loop preferences stay intact."""

from __future__ import annotations

from sqlalchemy.orm import Session

from fluentloop.db.models import User, utc_now

LEARNING_MODES = {"simple", "advanced"}


def get_learning_mode(user: User) -> str:
    raw = (user.preferences_json or {}).get("learning") or {}
    mode = raw.get("mode") if isinstance(raw, dict) else None
    return mode if isinstance(mode, str) and mode in LEARNING_MODES else "advanced"


def is_simple_mode(user: User) -> bool:
    return get_learning_mode(user) == "simple"


def set_learning_mode(session: Session, user: User, mode: str) -> User:
    if mode not in LEARNING_MODES:
        raise ValueError("Learning mode must be simple or advanced")
    preferences = dict(user.preferences_json or {})
    raw = preferences.get("learning") or {}
    preferences["learning"] = {
        **(raw if isinstance(raw, dict) else {}),
        "mode": mode,
    }
    user.preferences_json = preferences
    user.updated_at = utc_now()
    session.add(user)
    session.flush()
    return user
