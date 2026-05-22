from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from fluentloop.db.models import LearningItem, User


@dataclass(frozen=True)
class EvaluationProbe:
    title: str
    prompt: str
    held_out_item_ids: list[int]
    generated_at: datetime


def select_held_out_items(
    session: Session, user: User, *, percent: int = 10, limit: int = 30
) -> list[LearningItem]:
    items = list(
        session.scalars(
            select(LearningItem)
            .where(
                LearningItem.user_id == user.id,
                LearningItem.status == "active",
                LearningItem.is_template.is_(False),
            )
            .order_by(LearningItem.id.asc())
            .limit(limit * 10)
        )
    )
    if not items:
        return []
    stride = max(2, round(100 / max(1, percent)))
    selected = [
        item for index, item in enumerate(items, start=1) if index % stride == 0
    ]
    return (selected or items[:1])[:limit]


def build_monthly_probe(session: Session, user: User) -> EvaluationProbe:
    held_out = select_held_out_items(session, user)
    prompt = (
        "Monthly CAE-style probe:\n"
        "1. 8 sentence transformations.\n"
        "2. 10 vocabulary-in-context questions.\n"
        "3. 12 cloze items.\n"
        "4. Short writing: describe your team's biggest engineering challenge "
        "this quarter."
    )
    return EvaluationProbe(
        title="EPIC-22 monthly learning probe",
        prompt=prompt,
        held_out_item_ids=[item.id for item in held_out],
        generated_at=datetime.now(UTC),
    )


def writing_metrics(text: str) -> dict[str, float]:
    words = [word.strip(".,;:!?()[]{}\"'").lower() for word in text.split()]
    words = [word for word in words if word]
    unique = len(set(words))
    hedges = {
        "may",
        "might",
        "could",
        "seem",
        "seems",
        "tend",
        "appears",
        "arguably",
        "roughly",
    }
    hedge_count = sum(1 for word in words if word in hedges)
    sentence_count = max(1, sum(text.count(mark) for mark in ".!?"))
    return {
        "word_count": float(len(words)),
        "lexical_diversity": unique / max(1, len(words)),
        "hedging_density": hedge_count / max(1, len(words)),
        "mean_sentence_length": len(words) / sentence_count,
    }
