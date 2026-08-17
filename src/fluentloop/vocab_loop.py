"""Daily vocabulary loop: slot timing, item selection, and message rendering.

Pure by design. Nothing here imports Telethon or touches the network, so the
whole daily rhythm is testable by calling functions with an injected ``now``.
The sending half lives in ``fluentloop.scheduler``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy.orm import Session

from fluentloop.db.models import LearningItem, User
from fluentloop.exercises import Exercise, render_for_item
from fluentloop.learning_engine import score_learning_items
from fluentloop.srs import get_due_items
from fluentloop.vocab_prefs import SLOTS, VocabPrefs, parse_hhmm

# A slot stays deliverable for this long after its nominal time, so a bot that
# was restarted at 08:20 still sends the morning cards.
CATCHUP_MINUTES = 90

CARD_ITEM_TYPES = ("word", "expression", "chunk")
# Rotated by date so the learner is not drilled the same way every day. Every
# third day is a "write your own sentence" task.
MIDDAY_TYPES = ("cloze", "translate", "collocation_drill")

MAX_WORD_LIST_SEGMENTS = 20
MAX_WORD_LIST_CHARS = 300
MAX_SEGMENT_WORDS = 6
MAX_SEGMENT_CHARS = 64
_SEGMENT_SPLIT_RE = re.compile(r"[\n,;]+")
_LETTER_RE = re.compile(r"[^\W\d_]", re.UNICODE)
_CYRILLIC_RE = re.compile(r"[Ѐ-ӿ]")


def has_cyrillic(text: str) -> bool:
    return bool(_CYRILLIC_RE.search(text or ""))


def english_definition(item: LearningItem) -> str:
    """The English gloss for an item, preferred for anything the bot asks.

    Items arrive from several sources and some carry a Russian gloss in
    `meaning` while the English one sits in `explanation`, or the other way
    round. Prompts stay in English, so pick whichever field has no Cyrillic.
    """

    candidates = [(item.meaning or "").strip(), (item.explanation or "").strip()]
    for text in candidates:
        if text and not has_cyrillic(text):
            return text
    return ""


def russian_definition(item: LearningItem) -> str:
    """The Russian gloss, shown only after the learner has answered."""

    for text in ((item.meaning or "").strip(), (item.explanation or "").strip()):
        if text and has_cyrillic(text):
            return text
    return ""


def any_definition(item: LearningItem) -> str:
    return english_definition(item) or russian_definition(item)


@dataclass(frozen=True)
class QuizSpec:
    """A multiple-choice question, independent of how it gets delivered."""

    item_id: int
    question: str
    options: list[str]
    correct_index: int
    solution: str = ""


def local_now(user: User, *, now: datetime | None = None) -> datetime:
    current = now or datetime.now(UTC)
    try:
        zone = ZoneInfo(user.timezone)
    except (ZoneInfoNotFoundError, ValueError):
        zone = UTC
    return current.astimezone(zone)


def local_date(user: User, *, now: datetime | None = None) -> date:
    return local_now(user, now=now).date()


def due_slots(prefs: VocabPrefs, now_local: datetime) -> list[str]:
    """Slots whose delivery window contains ``now_local``."""

    if prefs.paused:
        return []
    minutes_now = now_local.hour * 60 + now_local.minute
    due: list[str] = []
    for slot in SLOTS:
        try:
            slot_minutes = parse_hhmm(prefs.slots[slot])
        except (KeyError, ValueError):
            continue
        if slot_minutes <= minutes_now < slot_minutes + CATCHUP_MINUTES:
            due.append(slot)
    return due


def select_cards(
    session: Session,
    user: User,
    *,
    count: int,
    now: datetime | None = None,
) -> list[LearningItem]:
    """Pick the items to show as cards, due ones first."""

    selected: list[LearningItem] = []
    seen: set[int] = set()
    for item in get_due_items(session, user.id, limit=max(count * 3, count), now=now):
        if item.type in CARD_ITEM_TYPES and item.id not in seen:
            selected.append(item)
            seen.add(item.id)
        if len(selected) >= count:
            return selected
    for scored in score_learning_items(session, user, now=now, limit=count * 3):
        item = scored.item
        if item.type in CARD_ITEM_TYPES and item.id not in seen:
            selected.append(item)
            seen.add(item.id)
        if len(selected) >= count:
            break
    return selected


def render_cards(items: list[LearningItem], *, title: str = "Morning phrases") -> str:
    from fluentloop.bot.formatting import bold, html_escape, italic

    lines = [f"🌅 {bold(title)}", ""]
    for index, item in enumerate(items, start=1):
        example = item.examples[0] if item.examples else ""
        headline = f"{index}. {bold(item.text)}"
        if example:
            headline += f" — {html_escape(example)}"
        lines.append(headline)
        meaning = any_definition(item)
        if meaning:
            lines.append(f"    {italic(meaning)}")
        lines.append("")
    return "\n".join(lines).rstrip()


def midday_exercise_type(day: date) -> str:
    if day.toordinal() % 3 == 0:
        return "mini_writing"
    return MIDDAY_TYPES[day.toordinal() % 3]


def select_drill_item(
    session: Session,
    user: User,
    *,
    now: datetime | None = None,
) -> LearningItem | None:
    items = select_cards(session, user, count=1, now=now)
    return items[0] if items else None


def build_drill(
    session: Session,
    user: User,
    *,
    now: datetime | None = None,
) -> tuple[LearningItem, Exercise] | None:
    item = select_drill_item(session, user, now=now)
    if item is None:
        return None
    day = local_date(user, now=now)
    exercise = render_for_item(item, midday_exercise_type(day))
    return item, exercise


def render_drill(exercise: Exercise) -> str:
    from fluentloop.bot.formatting import bold, html_escape, italic

    lines = [f"✍️ {bold('Quick drill')}", "", html_escape(exercise.prompt)]
    hint = (exercise.hint or "").strip()
    if hint:
        lines.append("")
        lines.append(italic(hint))
    lines.append("")
    lines.append(
        italic("Type your answer in English, or tap Skip to see it.")
    )
    return "\n".join(lines)


def looks_like_word_list(raw: str) -> bool:
    """True when a plain message reads as a list of words to add.

    Deliberately conservative: anything that looks like prose falls through to
    the existing "treat this as lesson material" path.
    """

    text = raw.strip()
    if not text or len(text) > MAX_WORD_LIST_CHARS:
        return False
    if text.startswith("/"):
        return False
    segments = [part.strip() for part in _SEGMENT_SPLIT_RE.split(text)]
    segments = [part for part in segments if part]
    if not segments or len(segments) > MAX_WORD_LIST_SEGMENTS:
        return False
    for segment in segments:
        if len(segment) > MAX_SEGMENT_CHARS:
            return False
        if len(segment.split()) > MAX_SEGMENT_WORDS:
            return False
        if segment[-1] in ".!?":
            return False
        if not _LETTER_RE.search(segment):
            return False
    return True


def split_word_list(raw: str) -> list[str]:
    """Split a plain message into candidate items, preserving order."""

    segments = [part.strip() for part in _SEGMENT_SPLIT_RE.split(raw)]
    seen: set[str] = set()
    result: list[str] = []
    for segment in segments:
        if not segment:
            continue
        key = segment.casefold()
        if key in seen:
            continue
        seen.add(key)
        result.append(segment)
    return result


def guess_item_type(text: str) -> str:
    return "expression" if " " in text.strip() else "word"
