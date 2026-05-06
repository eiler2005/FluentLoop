#!/usr/bin/env python3
"""Seed an idempotent demo dataset for audit and smoke testing.

The seed uses the stub AI provider even when real OpenAI credentials are
present, so it is safe for the overnight budget. It writes only product data
into the configured FluentLoop SQLite database.
"""
from __future__ import annotations

import argparse
from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from fluentloop.ai.provider import StubProvider
from fluentloop.config import get_settings
from fluentloop.db.models import MistakeEvent, PracticeAttempt, PracticeSession, User
from fluentloop.db.session import make_engine, make_session_factory
from fluentloop.grammar import seed_concepts
from fluentloop.learning import create_learning_item, toggle_favorite
from fluentloop.materials import approve_all, extract_candidates, store_material
from fluentloop.mistakes import ingest_mistake_event, promote_pattern
from fluentloop.practice import cache_session, compose_session
from fluentloop.users import ensure_user

DEMO_RAW_TEXT = (
    "Lesson demo: push back on an idea politely; align on delivery risks; "
    "hedging recommendations with might need to; articles before the sprint."
)

DEMO_ITEMS = [
    {
        "type_": "expression",
        "text": "push back on",
        "meaning": "мягко возражать",
        "explanation": "A natural way to challenge an idea politely.",
        "examples": ["I'd like to push back on this timeline a bit."],
        "tags": ["demo", "meetings", "stakeholders"],
        "is_favorite": True,
    },
    {
        "type_": "expression",
        "text": "align on",
        "meaning": "согласовать позицию по",
        "explanation": "Use align on + topic.",
        "examples": ["We need to align on priorities before the sprint starts."],
        "tags": ["demo", "planning"],
    },
    {
        "type_": "word",
        "text": "trade-off",
        "meaning": "компромисс",
        "explanation": "A balance between two competing engineering choices.",
        "examples": ["The main trade-off is latency versus reliability."],
        "tags": ["demo", "architecture"],
    },
    {
        "type_": "word",
        "text": "mitigate",
        "meaning": "снизить риск",
        "explanation": "To reduce the impact or probability of a risk.",
        "examples": ["We can mitigate this risk with a smaller release."],
        "tags": ["demo", "risk"],
    },
    {
        "type_": "grammar_rule",
        "text": "Hedging recommendations",
        "meaning": "смягчение рекомендаций",
        "explanation": "Use might need to / could / it may be worth.",
        "examples": ["We might need to reconsider the architecture soon."],
        "tags": ["demo", "hedging"],
    },
    {
        "type_": "grammar_rule",
        "text": "Articles with specific project events",
        "meaning": "артикли для конкретных событий проекта",
        "explanation": "Use the when referring to a specific sprint or incident.",
        "examples": ["We should review it before the sprint starts."],
        "tags": ["demo", "articles"],
    },
    {
        "type_": "mistake_pattern",
        "text": "Missing preposition after align",
        "meaning": "align on, not align priorities",
        "explanation": "Use align on + noun phrase.",
        "examples": ["We need to align on priorities."],
        "tags": ["demo", "collocation"],
    },
]


def _get_or_store_material(session: Session, user_id: int):
    from fluentloop.db.models import SourceMaterial

    existing = session.scalar(
        select(SourceMaterial).where(
            SourceMaterial.user_id == user_id,
            SourceMaterial.type == "lesson_notes",
            SourceMaterial.raw_text == DEMO_RAW_TEXT,
        )
    )
    if existing is not None:
        return existing
    user = session.get(User, user_id)
    assert user is not None
    return store_material(session, user, DEMO_RAW_TEXT, type_="lesson_notes")


def _seed_items(session: Session, user) -> list[int]:
    item_ids: list[int] = []
    for payload in DEMO_ITEMS:
        item = create_learning_item(session, user, **payload)
        if payload.get("is_favorite") and not item.is_favorite:
            toggle_favorite(session, item)
        item_ids.append(item.id)
    return item_ids


def _seed_mistakes(session: Session, user, linked_item_id: int | None) -> int | None:
    examples = [
        (
            "We need align priorities before sprint.",
            "We need to align on priorities before the sprint.",
        ),
        (
            "Let's align priorities with team.",
            "Let's align on priorities with the team.",
        ),
        (
            "Can we align risks before planning?",
            "Can we align on the risks before planning?",
        ),
    ]
    pattern = None
    for wrong, corrected in examples:
        existing = session.scalar(
            select(MistakeEvent).where(
                MistakeEvent.user_id == user.id,
                MistakeEvent.wrong_answer == wrong,
                MistakeEvent.mistake_type == "collocation",
            )
        )
        event = existing
        if event is None:
            event = MistakeEvent(
                user_id=user.id,
                wrong_answer=wrong,
                corrected_answer=corrected,
                explanation="Use align on + topic.",
                mistake_type="collocation",
                linked_learning_item_id=linked_item_id,
            )
            session.add(event)
            session.flush()
        pattern = ingest_mistake_event(session, event)
    if pattern is not None:
        promote_pattern(session, pattern)
        return pattern.id
    return None


def _seed_completed_session(session: Session, user) -> int:
    target_date = datetime.now(UTC).date() - timedelta(days=1)
    existing = session.scalar(
        select(PracticeSession).where(
            PracticeSession.user_id == user.id,
            PracticeSession.target_date_local == target_date,
            PracticeSession.status == "completed",
        )
    )
    if existing is not None:
        return existing.id
    exercises = compose_session(session, user, target_date=target_date)
    practice = PracticeSession(
        user_id=user.id,
        target_date_local=target_date,
        exercises=exercises,
        status="completed",
        completed_at=datetime.now(UTC),
    )
    session.add(practice)
    session.flush()
    for index, exercise in enumerate(exercises[:3]):
        session.add(
            PracticeAttempt(
                practice_session_id=practice.id,
                exercise_index=index,
                exercise_type=exercise["exercise_type"],
                target_learning_item_ids=exercise["target_learning_item_ids"],
                prompt=exercise["prompt"],
                user_answer=exercise["expected_answer"],
                status=["correct", "partial", "incorrect"][index],
                feedback={"status": ["correct", "partial", "incorrect"][index]},
            )
        )
    session.flush()
    return practice.id


def seed_demo_data(db_url: str | None = None) -> dict[str, int | str | None]:
    settings = get_settings()
    if db_url is not None:
        settings = settings.__class__(**{**settings.__dict__, "db_url": db_url})
    if settings.telegram_allowed_user_id is None:
        raise RuntimeError("TELEGRAM_ALLOWED_USER_ID is required for demo seeding")
    engine = make_engine(settings.db_url)
    factory = make_session_factory(engine)
    with factory() as session:
        seed_concepts(session)
        user = ensure_user(session, settings.telegram_allowed_user_id, settings)
        item_ids = _seed_items(session, user)
        material = _get_or_store_material(session, user.id)
        provider = StubProvider(Path("data") / "usage_log.jsonl")
        candidates = extract_candidates(session, material, provider)
        approved = approve_all(session, user, material)
        pattern_id = _seed_mistakes(session, user, item_ids[1] if item_ids else None)
        cache = cache_session(session, user, target_date=datetime.now(UTC).date())
        completed_session_id = _seed_completed_session(session, user)
        session.commit()
        return {
            "items": len(item_ids),
            "material_id": material.id,
            "candidates": len(candidates),
            "approved_now": approved,
            "pattern_id": pattern_id,
            "cached_session_id": cache.id,
            "completed_session_id": completed_session_id,
        }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db-url", help="override DB_URL for tests/audit runs")
    args = parser.parse_args()
    result = seed_demo_data(args.db_url)
    print(
        "OK: demo data seeded "
        f"items={result['items']} "
        f"material_id={result['material_id']} "
        f"candidates={result['candidates']} "
        f"approved_now={result['approved_now']} "
        f"pattern_id={result['pattern_id']} "
        f"cached_session_id={result['cached_session_id']} "
        f"completed_session_id={result['completed_session_id']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
