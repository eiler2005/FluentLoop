from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from fluentloop.db.models import LearningItem, User
from fluentloop.learning import create_learning_item

CHUNK_TYPES = {
    "collocation",
    "fixed_expression",
    "semi_fixed_expression",
    "discourse_marker",
    "phrasal_verb",
    "idiom",
    "signposting",
    "hedge",
}
CHUNK_FIELDS = {
    "UNCERTAINTY",
    "DISAGREEMENT",
    "DECISION",
    "INFLUENCE",
    "CRITIQUE",
    "SUPPORT",
    "TIME",
    "RESPONSIBILITY",
    "NEGOTIATION",
}
REGISTERS = {"very_formal", "professional", "collegial", "casual", "blunt_direct"}
FUNCTIONS = {"hedging", "signposting", "softening"}
CEFR_LEVELS = {"B2", "B2+", "C1", "C1+"}


class ChunkRecord(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    text: str
    type: str
    field: str
    register_name: str = Field(alias="register")
    function: str
    genres: list[str] = Field(default_factory=list)
    cefr_target: str
    russian_gloss: str = ""
    l1_trap: str | None = None
    example_sentences: list[str] = Field(default_factory=list)
    anti_examples: list[str] = Field(default_factory=list)
    etymology_or_why: str = ""

    @field_validator("type")
    @classmethod
    def _valid_type(cls, value: str) -> str:
        if value not in CHUNK_TYPES:
            raise ValueError(f"unsupported chunk type: {value}")
        return value

    @field_validator("field")
    @classmethod
    def _valid_field(cls, value: str) -> str:
        if value not in CHUNK_FIELDS:
            raise ValueError(f"unsupported field: {value}")
        return value

    @field_validator("register_name")
    @classmethod
    def _valid_register(cls, value: str) -> str:
        if value not in REGISTERS:
            raise ValueError(f"unsupported register: {value}")
        return value

    @field_validator("function")
    @classmethod
    def _valid_function(cls, value: str) -> str:
        if value not in FUNCTIONS:
            raise ValueError(f"unsupported function: {value}")
        return value

    @field_validator("cefr_target")
    @classmethod
    def _valid_cefr(cls, value: str) -> str:
        if value not in CEFR_LEVELS:
            raise ValueError(f"unsupported CEFR target: {value}")
        return value

    def metadata(self) -> dict[str, Any]:
        return {
            "chunk_id": self.id,
            "chunk_type": self.type,
            "field": self.field,
            "register": self.register_name,
            "function": self.function,
            "genres": self.genres,
            "cefr_target": self.cefr_target,
            "l1_trap": self.l1_trap,
            "anti_examples": self.anti_examples,
            "etymology_or_why": self.etymology_or_why,
        }


def load_chunk_records(path: Path) -> list[ChunkRecord]:
    records: list[ChunkRecord] = []
    errors: list[str] = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                records.append(ChunkRecord.model_validate(json.loads(stripped)))
            except (json.JSONDecodeError, ValidationError, ValueError) as exc:
                errors.append(f"line {line_number}: {exc}")
    if errors:
        joined = "\n".join(errors[:5])
        raise ValueError(f"Invalid chunk JSONL:\n{joined}")
    return records


def import_chunk_records(
    session: Session, user: User, records: list[ChunkRecord]
) -> tuple[int, int]:
    created = 0
    skipped = 0
    seen: set[tuple[str, str]] = set()
    for record in records:
        key = (record.text.strip().lower(), record.field)
        if key in seen:
            skipped += 1
            continue
        seen.add(key)
        existing = session.scalar(
            select(LearningItem).where(
                LearningItem.user_id == user.id,
                LearningItem.type == "chunk",
                LearningItem.text == record.text.strip(),
            )
        )
        if existing is not None:
            skipped += 1
            continue
        create_learning_item(
            session,
            user,
            type_="chunk",
            text=record.text,
            meaning=record.russian_gloss,
            explanation=record.etymology_or_why,
            examples=record.example_sentences,
            tags=[
                record.field.lower(),
                record.register_name,
                record.function,
                *record.genres,
            ],
            metadata=record.metadata(),
        )
        created += 1
    return created, skipped


def import_chunks_jsonl(session: Session, user: User, path: Path) -> tuple[int, int]:
    return import_chunk_records(session, user, load_chunk_records(path))
