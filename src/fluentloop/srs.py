from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from fluentloop.db.models import LearningItem, ReviewState

RESULTS = {"Again", "Hard", "Good", "Easy"}


def next_interval_days(result: str, last_interval_days: float) -> float:
    if result == "Again":
        return 0.0
    if result == "Hard":
        return 1.0
    if result == "Good":
        return min(7.0, max(2.0, last_interval_days * 2.0))
    if result == "Easy":
        return max(7.0, last_interval_days * 3.0)
    raise ValueError(f"Unsupported review result: {result}")


def record_result(
    session: Session,
    item_id: int,
    result: str,
    *,
    now: datetime | None = None,
) -> ReviewState:
    if result not in RESULTS:
        raise ValueError(f"Unsupported review result: {result}")
    current = now or datetime.now(UTC)
    state = session.scalar(
        select(ReviewState).where(ReviewState.learning_item_id == item_id)
    )
    if state is None:
        state = ReviewState(learning_item_id=item_id, due_at=current)
        session.add(state)
        session.flush()
    interval = next_interval_days(result, state.last_interval_days)
    state.last_result = result
    state.last_reviewed_at = current
    state.review_count += 1
    state.last_interval_days = interval
    if result in {"Again", "Hard"}:
        state.fail_count += 1
        state.difficulty += 1.0 if result == "Again" else 0.5
    else:
        state.success_count += 1
        state.stability = max(state.stability, interval)
    state.due_at = current + timedelta(days=interval)
    session.add(state)
    session.flush()
    return state


def get_due_items(
    session: Session,
    user_id: int,
    *,
    limit: int = 20,
    now: datetime | None = None,
) -> list[LearningItem]:
    current = now or datetime.now(UTC)
    due_soon = current + timedelta(days=1)
    stmt = (
        select(LearningItem)
        .join(ReviewState)
        .where(
            LearningItem.user_id == user_id,
            LearningItem.status == "active",
            ReviewState.due_at <= due_soon,
        )
        .order_by(
            ReviewState.due_at.asc(),
            (ReviewState.fail_count - ReviewState.success_count).desc(),
            LearningItem.is_favorite.desc(),
        )
        .limit(limit)
    )
    return list(session.scalars(stmt))
