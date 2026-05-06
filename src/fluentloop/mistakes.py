from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from fluentloop.db.models import MistakeEvent, MistakePattern


def ingest_mistake_event(
    session: Session, event: MistakeEvent
) -> MistakePattern | None:
    since = datetime.now(UTC) - timedelta(days=14)
    stmt = select(MistakeEvent).where(
        MistakeEvent.user_id == event.user_id,
        MistakeEvent.mistake_type == event.mistake_type,
        MistakeEvent.created_at >= since,
    )
    if event.linked_grammar_concept_id is not None:
        stmt = stmt.where(
            MistakeEvent.linked_grammar_concept_id == event.linked_grammar_concept_id
        )
    elif event.linked_learning_item_id is not None:
        stmt = stmt.where(
            MistakeEvent.linked_learning_item_id == event.linked_learning_item_id
        )
    else:
        stmt = stmt.where(MistakeEvent.linked_learning_item_id.is_(None))
    events = list(session.scalars(stmt))
    if len(events) < 3:
        return None
    existing = session.scalar(
        select(MistakePattern).where(
            MistakePattern.user_id == event.user_id,
            MistakePattern.mistake_type == event.mistake_type,
            MistakePattern.linked_learning_item_id == event.linked_learning_item_id,
            MistakePattern.linked_grammar_concept_id == event.linked_grammar_concept_id,
        )
    )
    wrong_examples = [row.wrong_answer for row in events][-5:]
    correct_examples = [row.corrected_answer for row in events if row.corrected_answer][
        -5:
    ]
    if existing is not None:
        existing.event_count = len(events)
        existing.wrong_examples = wrong_examples
        existing.correct_examples = correct_examples
        session.add(existing)
        session.flush()
        return existing
    pattern = MistakePattern(
        user_id=event.user_id,
        description=f"Recurring {event.mistake_type} issue",
        mistake_type=event.mistake_type,
        linked_learning_item_id=event.linked_learning_item_id,
        linked_grammar_concept_id=event.linked_grammar_concept_id,
        confidence="low",
        status="active",
        wrong_examples=wrong_examples,
        correct_examples=correct_examples,
        event_count=len(events),
    )
    session.add(pattern)
    session.flush()
    return pattern


def promote_pattern(session: Session, pattern: MistakePattern) -> MistakePattern:
    pattern.confidence = "high"
    pattern.status = "active"
    session.add(pattern)
    session.flush()
    return pattern


def archive_pattern(session: Session, pattern: MistakePattern) -> MistakePattern:
    pattern.status = "archived"
    session.add(pattern)
    session.flush()
    return pattern


def active_patterns(session: Session, user_id: int) -> list[MistakePattern]:
    return list(
        session.scalars(
            select(MistakePattern)
            .where(MistakePattern.user_id == user_id, MistakePattern.status == "active")
            .order_by(
                MistakePattern.confidence.desc(), MistakePattern.event_count.desc()
            )
        )
    )
