from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from fluentloop.db.models import PracticeAttempt, PracticeSession, User
from fluentloop.outcomes import latest_outcome_summary
from fluentloop.polish import rolling_native_comparison


def write_coach_journal(
    session: Session,
    user: User,
    *,
    base_dir: Path = Path("data/coach_journal"),
    limit: int = 12,
) -> Path:
    base_dir.mkdir(parents=True, exist_ok=True)
    attempts = list(
        session.scalars(
            select(PracticeAttempt)
            .join(
                PracticeSession,
                PracticeSession.id == PracticeAttempt.practice_session_id,
            )
            .where(PracticeSession.user_id == user.id)
            .order_by(PracticeAttempt.created_at.desc())
            .limit(limit)
        )
    )
    current = datetime.now(UTC)
    path = base_dir / f"{current.date().isoformat()}-{user.id}.md"
    path.write_text(
        _render_journal(user, attempts, current, latest_outcome_summary(session, user)),
        encoding="utf-8",
    )
    return path


def _render_journal(
    user: User,
    attempts: list[PracticeAttempt],
    current: datetime,
    outcome_summary: str | None = None,
) -> str:
    statuses = [str(attempt.status) for attempt in attempts]
    l1_hits = [
        hit.get("rule_id", "")
        for attempt in attempts
        for hit in (attempt.feedback.get("l1_hits") or [])
        if isinstance(hit, dict)
    ]
    format_notes = [
        key
        for attempt in attempts
        for key in (attempt.feedback.get("format_feedback") or {})
    ]
    native_comparisons = rolling_native_comparison(attempts)
    incorrect = len(statuses) - statuses.count("correct") - statuses.count("partial")
    lines = [
        f"# Coach Journal - {current.date().isoformat()}",
        "",
        f"- User: {user.telegram_user_id}",
        f"- Attempts reviewed: {len(attempts)}",
        f"- Correct: {statuses.count('correct')}",
        f"- Partial: {statuses.count('partial')}",
        f"- Incorrect/skipped: {incorrect}",
        "",
        "## Focus",
        f"- L1 hits: {', '.join(l1_hits[:5]) if l1_hits else 'none'}",
        f"- Format notes: {', '.join(format_notes[:5]) if format_notes else 'none'}",
        "",
        "## Latest Outcomes",
        *(
            outcome_summary.splitlines()
            if outcome_summary
            else ["- run /outcomes first"]
        ),
        "",
        "## Rolling Native Comparison",
        *(
            [f"- {item}" for item in native_comparisons]
            if native_comparisons
            else ["- none yet"]
        ),
        "",
        "## Next Teacher Move",
        "- Pick one review target and one stretch target; end with cold recall.",
        "",
    ]
    return "\n".join(lines)
