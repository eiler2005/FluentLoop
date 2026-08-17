from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from fluentloop.db.models import LearningItem, ReviewState

RESULTS = {"Again", "Hard", "Good", "Easy"}
SECOND = 1.0 / 86_400.0
# An item graduates once it reaches the 120-day rung of the ladder below, which
# takes about five clean successes spread over a month or more (EPIC-25).
GRADUATION_INTERVAL_DAYS = 120.0
GRADUATION_MIN_SUCCESSES = 4
GIR_INTERVAL_DAYS = (
    5 * SECOND,
    25 * SECOND,
    2 / 1_440,
    10 / 1_440,
    1 / 24,
    5 / 24,
    1.0,
    5.0,
    25.0,
    120.0,
    730.0,
)


def _next_gir_interval(last_interval_days: float, *, skip: int = 0) -> float:
    if last_interval_days <= 0:
        return GIR_INTERVAL_DAYS[min(skip, len(GIR_INTERVAL_DAYS) - 1)]
    for index, interval in enumerate(GIR_INTERVAL_DAYS):
        if interval > last_interval_days + SECOND:
            return GIR_INTERVAL_DAYS[min(index + skip, len(GIR_INTERVAL_DAYS) - 1)]
    return min(730.0, last_interval_days * (3.0 if skip else 2.0))


def next_interval_days(result: str, last_interval_days: float) -> float:
    if result == "Again":
        return GIR_INTERVAL_DAYS[0]
    if result == "Hard":
        if last_interval_days < 1.0:
            return _next_gir_interval(last_interval_days)
        return max(1.0, min(25.0, last_interval_days * 1.2))
    if result == "Good":
        return _next_gir_interval(last_interval_days)
    if result == "Easy":
        return _next_gir_interval(last_interval_days, skip=1)
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


def is_graduation_ready(state: ReviewState) -> bool:
    return (
        state.last_interval_days >= GRADUATION_INTERVAL_DAYS
        and state.last_result in {"Good", "Easy"}
        and state.success_count >= GRADUATION_MIN_SUCCESSES
    )


def apply_review(
    session: Session,
    item: LearningItem,
    result: str,
    *,
    now: datetime | None = None,
) -> tuple[ReviewState, bool]:
    """Record a review result and graduate the item once it is mastered.

    Returns the review state and whether this call graduated the item. Callers
    that only need the interval update can keep using ``record_result``.
    """

    state = record_result(session, item.id, result, now=now)
    graduated = False
    if item.status == "active" and is_graduation_ready(state):
        item.status = "graduated"
        session.add(item)
        session.flush()
        graduated = True
    return state, graduated


def convert_last_good_to_hard(session: Session, item_id: int) -> ReviewState:
    state = session.scalar(
        select(ReviewState).where(ReviewState.learning_item_id == item_id)
    )
    if state is None:
        raise ValueError("Review state not found")
    if state.last_result != "Good":
        return state
    reviewed_at = state.last_reviewed_at or datetime.now(UTC)
    state.success_count = max(0, state.success_count - 1)
    state.fail_count += 1
    state.difficulty += 0.5
    state.last_result = "Hard"
    state.last_interval_days = next_interval_days("Hard", 0.0)
    state.due_at = reviewed_at + timedelta(days=state.last_interval_days)
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
            LearningItem.priority.desc(),
            ReviewState.due_at.asc(),
            (ReviewState.fail_count - ReviewState.success_count).desc(),
            LearningItem.is_favorite.desc(),
        )
        .limit(limit)
    )
    return list(session.scalars(stmt))
