"""Per-user settings for the daily vocabulary loop (EPIC-25).

Everything here lives in ``User.preferences_json["vocab"]`` rather than in
dedicated columns: the values are read together, written together, and never
queried individually.

``DEFAULTS`` is what lets users who never ran the onboarding wizard still get
working 08:00 / 13:00 / 19:00 pushes over their existing item base.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field, replace

from sqlalchemy.orm import Session

from fluentloop.db.models import User, utc_now

SLOTS: tuple[str, ...] = ("morning", "midday", "evening")
TIME_RE = re.compile(r"^\d{2}:\d{2}$")
MIN_WORDS_PER_DAY = 1
MAX_WORDS_PER_DAY = 20
STARTER_SIZES: tuple[int, ...] = (100, 200, 300, 500)
QUIZ_SIZES: tuple[int, ...] = (5, 10, 15, 20)

DEFAULT_SLOTS: dict[str, str] = {
    "morning": "08:00",
    "midday": "13:00",
    "evening": "19:00",
}


@dataclass(frozen=True)
class VocabPrefs:
    slots: dict[str, str] = field(default_factory=lambda: dict(DEFAULT_SLOTS))
    paused: bool = False
    words_per_day: int = 5
    topics: list[str] = field(default_factory=list)
    kinds: list[str] = field(default_factory=list)
    sets: list[str] = field(default_factory=list)
    starter_size: int = 200
    quiz_size: int = 10
    onboarded_at: str | None = None


DEFAULTS = VocabPrefs()


def parse_hhmm(value: str) -> int:
    """Return minutes since local midnight, raising ValueError on bad input."""

    text = value.strip()
    if not TIME_RE.match(text):
        raise ValueError("Use HH:MM")
    hour, minute = (int(part) for part in text.split(":"))
    if hour > 23 or minute > 59:
        raise ValueError("Use HH:MM")
    return hour * 60 + minute


def get_prefs(user: User) -> VocabPrefs:
    raw = (user.preferences_json or {}).get("vocab") or {}
    slots = dict(DEFAULT_SLOTS)
    for slot, value in (raw.get("slots") or {}).items():
        if slot in SLOTS and isinstance(value, str) and TIME_RE.match(value):
            slots[slot] = value
    return VocabPrefs(
        slots=slots,
        paused=bool(raw.get("paused", DEFAULTS.paused)),
        words_per_day=int(raw.get("words_per_day", DEFAULTS.words_per_day)),
        topics=list(raw.get("topics") or []),
        kinds=list(raw.get("kinds") or []),
        sets=list(raw.get("sets") or []),
        starter_size=int(raw.get("starter_size", DEFAULTS.starter_size)),
        quiz_size=int(raw.get("quiz_size", DEFAULTS.quiz_size)),
        onboarded_at=raw.get("onboarded_at"),
    )


def set_prefs(session: Session, user: User, prefs: VocabPrefs) -> User:
    # SQLAlchemy's JSON type is not mutation-tracked, so always reassign the
    # whole dict rather than mutating in place.
    user.preferences_json = {
        **(user.preferences_json or {}),
        "vocab": asdict(prefs),
    }
    user.updated_at = utc_now()
    session.add(user)
    session.flush()
    return user


def update_pref(session: Session, user: User, key: str, value: object) -> VocabPrefs:
    """Validate and persist a single preference.

    Mirrors ``users.update_setting``: unknown keys and bad values raise
    ``ValueError`` so the caller can surface the message to Telegram.
    """

    prefs = get_prefs(user)
    if key in SLOTS:
        parse_hhmm(str(value))
        prefs = replace(prefs, slots={**prefs.slots, key: str(value).strip()})
    elif key == "paused":
        prefs = replace(prefs, paused=_as_bool(value))
    elif key == "words_per_day":
        count = int(value)
        if count < MIN_WORDS_PER_DAY or count > MAX_WORDS_PER_DAY:
            raise ValueError(
                f"Words per day must be {MIN_WORDS_PER_DAY}-{MAX_WORDS_PER_DAY}"
            )
        prefs = replace(prefs, words_per_day=count)
    elif key == "starter_size":
        size = int(value)
        if size not in STARTER_SIZES:
            raise ValueError("Unsupported starter list size")
        prefs = replace(prefs, starter_size=size)
    elif key == "quiz_size":
        size = int(value)
        if size not in QUIZ_SIZES:
            raise ValueError("Quiz size must be one of 5, 10, 15, 20")
        prefs = replace(prefs, quiz_size=size)
    elif key in {"topics", "kinds", "sets"}:
        items = _as_list(value)
        prefs = replace(prefs, **{key: items})
    elif key == "onboarded_at":
        prefs = replace(prefs, onboarded_at=None if value is None else str(value))
    else:
        raise ValueError("Unknown vocabulary setting")
    set_prefs(session, user, prefs)
    return prefs


def mark_onboarded(session: Session, user: User) -> VocabPrefs:
    prefs = replace(get_prefs(user), onboarded_at=utc_now().isoformat())
    set_prefs(session, user, prefs)
    return prefs


def format_vocab_settings(prefs: VocabPrefs) -> str:
    slots = " / ".join(f"{slot} {prefs.slots[slot]}" for slot in SLOTS)
    state = "paused" if prefs.paused else "on"
    lines = [
        f"Daily loop: {state}",
        f"Slots: {slots}",
        f"Words per day: {prefs.words_per_day}",
        f"Quiz size: {prefs.quiz_size} questions",
    ]
    if prefs.topics:
        lines.append(f"Topics: {', '.join(prefs.topics)}")
    if prefs.kinds or prefs.sets:
        lines.append(f"Vocabulary: {', '.join([*prefs.kinds, *prefs.sets])}")
    return "\n".join(lines)


def _as_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _as_list(value: object) -> list[str]:
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    if isinstance(value, (list, tuple)):
        return [str(item).strip() for item in value if str(item).strip()]
    raise ValueError("Expected a list or comma-separated string")
