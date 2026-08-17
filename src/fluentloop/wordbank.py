"""In-repo starter word bank for the daily vocabulary loop (EPIC-25).

Structurally a sibling of ``curriculum_chunks``: a validated JSONL file plus an
idempotent importer. Bank entries ship with their quiz distractors already
filled in, which is what keeps the evening quiz off the LLM for normal use.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, ValidationError, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from fluentloop.db.models import LearningItem, User
from fluentloop.learning import ITEM_TYPES, create_learning_item

DEFAULT_BANK_PATH = Path(__file__).with_name("seeds") / "wordbank_v1.jsonl"

TOPICS = {
    "sports",
    "tech",
    "food",
    "travel",
    "business",
    "science",
    "gaming",
    "books",
    "fitness",
    "art",
}
KINDS = {
    "phrasal_verbs",
    "idioms",
    "business_english",
    "academic_ielts",
    "everyday_talk",
    "collocations",
    "news",
    "small_talk",
}
SETS = {
    "pulp_fiction",
    "film_noir",
    "fantasy_epic",
    "sci_fi",
    "internet_speak",
    "hiphop_slang",
    "posh_british",
    "horror_true_crime",
    "rom_com",
}
CEFR_LEVELS = ("B1", "B2", "B2+", "C1", "C1+")


class WordBankEntry(BaseModel):
    id: str
    text: str
    type: str
    meaning: str
    example: str = ""
    topics: list[str] = Field(default_factory=list)
    kinds: list[str] = Field(default_factory=list)
    sets: list[str] = Field(default_factory=list)
    cefr: str = "B2"
    synonyms: list[str] = Field(default_factory=list)
    collocations: list[str] = Field(default_factory=list)
    distractors: list[str] = Field(default_factory=list)

    @field_validator("type")
    @classmethod
    def _valid_type(cls, value: str) -> str:
        if value not in ITEM_TYPES:
            raise ValueError(f"Unsupported item type: {value}")
        return value

    @field_validator("topics")
    @classmethod
    def _valid_topics(cls, value: list[str]) -> list[str]:
        return _validate_all(value, TOPICS, "topic")

    @field_validator("kinds")
    @classmethod
    def _valid_kinds(cls, value: list[str]) -> list[str]:
        return _validate_all(value, KINDS, "kind")

    @field_validator("sets")
    @classmethod
    def _valid_sets(cls, value: list[str]) -> list[str]:
        return _validate_all(value, SETS, "set")

    @field_validator("cefr")
    @classmethod
    def _valid_cefr(cls, value: str) -> str:
        if value not in CEFR_LEVELS:
            raise ValueError(f"Unsupported CEFR level: {value}")
        return value

    def tags(self) -> list[str]:
        return [*self.topics, *self.kinds, *self.sets, "wordbank"]

    def metadata(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "wordbank_id": self.id,
            "source": "wordbank",
            "cefr": self.cefr,
        }
        if self.synonyms:
            payload["synonyms"] = list(self.synonyms)
        if self.collocations:
            payload["collocations"] = list(self.collocations)
        if len(self.distractors) >= 3:
            payload["mcq"] = {"distractors": list(self.distractors[:3])}
        return payload


def _validate_all(value: list[str], allowed: set[str], label: str) -> list[str]:
    for item in value:
        if item not in allowed:
            raise ValueError(f"Unsupported {label}: {item}")
    return value


def load_wordbank(path: Path | None = None) -> list[WordBankEntry]:
    source = path or DEFAULT_BANK_PATH
    if not source.exists():
        return []
    entries: list[WordBankEntry] = []
    for number, raw in enumerate(
        source.read_text(encoding="utf-8").splitlines(), start=1
    ):
        line = raw.strip()
        if not line or line.startswith("//"):
            continue
        try:
            entries.append(WordBankEntry.model_validate(json.loads(line)))
        except (json.JSONDecodeError, ValidationError) as exc:
            raise ValueError(f"{source}:{number}: {exc}") from exc
    return entries


def _cefr_distance(entry_level: str, user_level: str) -> int:
    normalized = user_level.split("/")[0].strip() or "B2"
    try:
        target = CEFR_LEVELS.index(normalized)
    except ValueError:
        target = CEFR_LEVELS.index("B2")
    try:
        actual = CEFR_LEVELS.index(entry_level)
    except ValueError:
        return len(CEFR_LEVELS)
    return abs(actual - target)


def select_starter_entries(
    entries: list[WordBankEntry],
    *,
    topics: list[str] | None = None,
    kinds: list[str] | None = None,
    sets: list[str] | None = None,
    size: int = 200,
    level: str = "B2+",
) -> list[WordBankEntry]:
    """Deterministically pick a starter list.

    With no selections the whole bank is eligible, which is what makes the
    wizard optional.
    """

    wanted_topics = set(topics or [])
    wanted_kinds = set(kinds or [])
    wanted_sets = set(sets or [])
    selective = bool(wanted_topics or wanted_kinds or wanted_sets)

    scored: list[tuple[tuple[int, int, str], WordBankEntry]] = []
    for entry in entries:
        matches = (
            len(wanted_topics & set(entry.topics))
            + len(wanted_kinds & set(entry.kinds))
            + len(wanted_sets & set(entry.sets))
        )
        if selective and matches == 0:
            continue
        key = (-matches, _cefr_distance(entry.cefr, level), entry.id)
        scored.append((key, entry))
    scored.sort(key=lambda row: row[0])
    return [entry for _, entry in scored[: max(0, size)]]


def seed_wordbank(
    session: Session,
    user: User,
    entries: list[WordBankEntry],
) -> tuple[int, int]:
    """Import entries for one user. Returns (created, skipped)."""

    existing = {
        text.casefold()
        for text in session.scalars(
            select(LearningItem.text).where(LearningItem.user_id == user.id)
        )
    }
    created = 0
    skipped = 0
    for entry in entries:
        if entry.text.casefold() in existing:
            skipped += 1
            continue
        create_learning_item(
            session,
            user,
            type_=entry.type,
            text=entry.text,
            meaning=entry.meaning,
            examples=[entry.example] if entry.example else [],
            tags=entry.tags(),
            metadata=entry.metadata(),
        )
        existing.add(entry.text.casefold())
        created += 1
    return created, skipped


def seed_starter_list(
    session: Session,
    user: User,
    *,
    topics: list[str] | None = None,
    kinds: list[str] | None = None,
    sets: list[str] | None = None,
    size: int = 200,
    path: Path | None = None,
) -> tuple[int, int]:
    entries = select_starter_entries(
        load_wordbank(path),
        topics=topics,
        kinds=kinds,
        sets=sets,
        size=size,
        level=user.level,
    )
    return seed_wordbank(session, user, entries)
