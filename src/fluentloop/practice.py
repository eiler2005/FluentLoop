from __future__ import annotations

import shutil
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from fluentloop.db.models import (
    PracticeAttempt,
    PracticeSession,
    PracticeSessionCached,
    User,
    utc_now,
)
from fluentloop.exercises import EXERCISE_TYPES, Exercise, render_for_item
from fluentloop.learning import active_items
from fluentloop.srs import get_due_items


def compose_session(
    session: Session, user: User, *, target_date: date | None = None
) -> list[dict]:
    selected = get_due_items(session, user.id, limit=7)
    if len(selected) < 7:
        seen = {item.id for item in selected}
        selected.extend(
            item for item in active_items(session, user.id) if item.id not in seen
        )
    exercises: list[Exercise] = []
    type_cycle = list(EXERCISE_TYPES)
    for index, item in enumerate(selected[:7]):
        exercises.append(render_for_item(item, type_cycle[index % len(type_cycle)]))
    if not exercises:
        exercises.append(
            Exercise(
                "follow_up",
                "Reply in 2-3 sentences: what delivery risk should we discuss first?",
                "We should discuss the highest-impact delivery risk first.",
                "Use concise stakeholder language.",
                "Seed exercise until learning items exist.",
                [],
            )
        )
    while len(exercises) < 7:
        exercises.append(exercises[len(exercises) % len(exercises)])
    return [exercise.as_dict() for exercise in exercises[:7]]


def cache_session(
    session: Session, user: User, *, target_date: date
) -> PracticeSessionCached:
    cached = session.scalar(
        select(PracticeSessionCached).where(
            PracticeSessionCached.user_id == user.id,
            PracticeSessionCached.target_date_local == target_date,
        )
    )
    if cached is not None:
        return cached
    cached = PracticeSessionCached(
        user_id=user.id,
        target_date_local=target_date,
        exercises=compose_session(session, user, target_date=target_date),
        status="ready",
    )
    session.add(cached)
    session.flush()
    return cached


def start_or_resume_session(
    session: Session,
    user: User,
    *,
    target_date: date | None = None,
) -> PracticeSession:
    local_date = target_date or datetime.now(UTC).date()
    current = session.scalar(
        select(PracticeSession).where(
            PracticeSession.user_id == user.id,
            PracticeSession.target_date_local == local_date,
            PracticeSession.status == "in_progress",
        )
    )
    if current is not None:
        return current
    cached = cache_session(session, user, target_date=local_date)
    current = PracticeSession(
        user_id=user.id,
        target_date_local=local_date,
        exercises=cached.exercises,
        status="in_progress",
    )
    session.add(current)
    session.flush()
    return current


def get_in_progress_session(
    session: Session,
    user: User,
    *,
    target_date: date | None = None,
) -> PracticeSession | None:
    local_date = target_date or datetime.now(UTC).date()
    return session.scalar(
        select(PracticeSession).where(
            PracticeSession.user_id == user.id,
            PracticeSession.target_date_local == local_date,
            PracticeSession.status == "in_progress",
        )
    )


def next_exercise(
    session: Session, practice_session: PracticeSession
) -> tuple[int, dict] | None:
    answered = {
        row.exercise_index
        for row in session.scalars(
            select(PracticeAttempt).where(
                PracticeAttempt.practice_session_id == practice_session.id
            )
        )
    }
    for index, exercise in enumerate(practice_session.exercises):
        if index not in answered:
            return index, exercise
    practice_session.status = "completed"
    practice_session.completed_at = utc_now()
    session.add(practice_session)
    session.flush()
    return None


def record_attempt(
    session: Session,
    practice_session: PracticeSession,
    exercise_index: int,
    exercise: dict,
    answer: str,
    feedback: dict,
) -> PracticeAttempt:
    attempt = PracticeAttempt(
        practice_session_id=practice_session.id,
        exercise_index=exercise_index,
        exercise_type=exercise["exercise_type"],
        target_learning_item_ids=exercise.get("target_learning_item_ids", []),
        prompt=exercise["prompt"],
        user_answer=answer,
        status=feedback.get("status", "unchecked"),
        feedback=feedback,
    )
    session.add(attempt)
    session.flush()
    return attempt


def backup_sqlite(db_path: Path, backup_dir: Path, *, retention_days: int = 14) -> Path:
    backup_dir.mkdir(parents=True, exist_ok=True)
    target = backup_dir / f"db-{datetime.now(UTC).date().isoformat()}.sqlite"
    if db_path.exists():
        shutil.copy2(db_path, target)
    cutoff = datetime.now(UTC) - timedelta(days=retention_days)
    for path in backup_dir.glob("db-*.sqlite"):
        if datetime.fromtimestamp(path.stat().st_mtime, UTC) < cutoff:
            path.unlink()
    return target
