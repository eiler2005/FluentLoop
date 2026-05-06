from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from fluentloop.db.models import (
    LearningItem,
    MistakePattern,
    PracticeSession,
    ReviewState,
    User,
)
from fluentloop.learning import item_counts


def collect_stats(session: Session, user: User) -> dict:
    counts = item_counts(session, user.id)
    now = datetime.now(UTC)
    due_count = session.scalar(
        select(func.count())
        .select_from(ReviewState)
        .join(LearningItem)
        .where(LearningItem.user_id == user.id, ReviewState.due_at <= now)
    )
    weak_count = session.scalar(
        select(func.count())
        .select_from(ReviewState)
        .join(LearningItem)
        .where(
            LearningItem.user_id == user.id,
            ReviewState.fail_count > ReviewState.success_count,
        )
    )
    favorite_count = session.scalar(
        select(func.count())
        .select_from(LearningItem)
        .where(
            LearningItem.user_id == user.id,
            LearningItem.status == "active",
            LearningItem.is_favorite.is_(True),
        )
    )
    sessions_7 = session.scalar(
        select(func.count())
        .select_from(PracticeSession)
        .where(
            PracticeSession.user_id == user.id,
            PracticeSession.created_at >= now - timedelta(days=7),
        )
    )
    return {
        "counts": Counter(counts),
        "due_count": due_count or 0,
        "weak_count": weak_count or 0,
        "favorite_count": favorite_count or 0,
        "sessions_7": sessions_7 or 0,
    }


def render_stats(stats: dict) -> str:
    counts = stats["counts"]
    return (
        "Progress\n"
        f"Words: {counts.get('word', 0)}\n"
        f"Expressions: {counts.get('expression', 0)}\n"
        f"Grammar rules: {counts.get('grammar_rule', 0)}\n"
        f"Mistake patterns: {counts.get('mistake_pattern', 0)}\n"
        f"Due now: {stats['due_count']}\n"
        f"Weak items: {stats['weak_count']}\n"
        f"Favorites: {stats['favorite_count']}\n"
        f"Sessions last 7 days: {stats['sessions_7']}"
    )


def weekly_summary(session: Session, user: User) -> str:
    stats = collect_stats(session, user)
    top_pattern = session.scalar(
        select(MistakePattern)
        .where(MistakePattern.user_id == user.id, MistakePattern.status == "active")
        .order_by(MistakePattern.event_count.desc())
    )
    focus = top_pattern.description if top_pattern else "keep practicing recent items"
    return render_stats(stats) + f"\n\nRecommended focus next week: {focus}"
