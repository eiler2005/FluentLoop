from __future__ import annotations

from collections import Counter

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from fluentloop.db.models import (
    ExtractedCandidate,
    LearningItem,
    ReviewState,
    User,
    utc_now,
)

ITEM_TYPES = {"word", "expression", "grammar_rule", "mistake_pattern", "chunk"}
ITEM_STATUSES = {"active", "archived", "suspended", "graduated"}
USER_ADDED_PRIORITY = 10


def create_learning_item(
    session: Session,
    user: User,
    *,
    type_: str,
    text: str,
    meaning: str = "",
    explanation: str = "",
    examples: list[str] | None = None,
    tags: list[str] | None = None,
    source_material_id: int | None = None,
    is_favorite: bool = False,
    metadata: dict | None = None,
    priority: int = 0,
) -> LearningItem:
    if type_ not in ITEM_TYPES:
        raise ValueError(f"Unsupported item type: {type_}")
    normalized = text.strip()
    if not normalized:
        raise ValueError("Text is required")
    existing = session.scalar(
        select(LearningItem).where(
            LearningItem.user_id == user.id,
            LearningItem.type == type_,
            LearningItem.text == normalized,
        )
    )
    if existing is not None:
        return existing
    item = LearningItem(
        user_id=user.id,
        type=type_,
        text=normalized,
        meaning=meaning.strip(),
        explanation=explanation.strip(),
        examples=examples or [],
        tags=tags or [],
        metadata_json=metadata or {},
        level=user.level,
        source_material_id=source_material_id,
        is_favorite=is_favorite,
        status="active",
        priority=priority,
    )
    session.add(item)
    session.flush()
    session.add(ReviewState(learning_item_id=item.id, due_at=utc_now()))
    session.flush()
    return item


def promote_candidate(
    session: Session, user: User, candidate: ExtractedCandidate
) -> LearningItem:
    item = create_learning_item(
        session,
        user,
        type_=candidate.type,
        text=candidate.text,
        meaning=candidate.meaning,
        explanation=candidate.explanation,
        examples=candidate.examples,
        tags=candidate.tags,
        source_material_id=candidate.source_material_id,
    )
    candidate.status = "approved"
    candidate.terminal_at = utc_now()
    session.add(candidate)
    return item


def set_item_status(session: Session, item: LearningItem, status: str) -> LearningItem:
    if status not in ITEM_STATUSES:
        raise ValueError(f"Unsupported status: {status}")
    item.status = status
    session.add(item)
    session.flush()
    return item


def toggle_favorite(session: Session, item: LearningItem) -> LearningItem:
    item.is_favorite = not item.is_favorite
    session.add(item)
    session.flush()
    return item


def active_items(session: Session, user_id: int) -> list[LearningItem]:
    return list(
        session.scalars(
            select(LearningItem)
            .where(LearningItem.user_id == user_id, LearningItem.status == "active")
            .order_by(LearningItem.created_at)
        )
    )


def list_items(
    session: Session,
    user_id: int,
    *,
    status: str = "active",
    limit: int = 20,
) -> list[LearningItem]:
    if status not in ITEM_STATUSES:
        raise ValueError(f"Unsupported status: {status}")
    return list(
        session.scalars(
            select(LearningItem)
            .where(LearningItem.user_id == user_id, LearningItem.status == status)
            .order_by(LearningItem.created_at.desc())
            .limit(limit)
        )
    )


def favorite_items(
    session: Session, user_id: int, *, limit: int = 20
) -> list[LearningItem]:
    return list(
        session.scalars(
            select(LearningItem)
            .where(
                LearningItem.user_id == user_id,
                LearningItem.status == "active",
                LearningItem.is_favorite.is_(True),
            )
            .order_by(LearningItem.created_at)
            .limit(limit)
        )
    )


def item_counts(session: Session, user_id: int) -> Counter[str]:
    rows = session.execute(
        select(LearningItem.type, func.count())
        .where(LearningItem.user_id == user_id)
        .group_by(LearningItem.type)
    )
    return Counter({type_: count for type_, count in rows})
