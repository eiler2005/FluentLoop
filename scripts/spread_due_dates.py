"""Spread a backlog of already-due items over the coming weeks.

Seeding creates every item with ``due_at = now``, so a starter list of a few
hundred words lands as one wall of overdue reviews. The daily loop shows a
handful a day, so the queue never drains and "due now" stops meaning anything.

This deals the backlog out over N days, oldest-created first, so the learner
meets the words gradually. Items the learner added themselves keep their date:
they are the ones worth seeing first.
"""

from __future__ import annotations

import argparse
from datetime import timedelta

from sqlalchemy import select

from fluentloop.config import get_settings
from fluentloop.db.models import LearningItem, ReviewState, User, utc_now
from fluentloop.db.session import make_engine, make_session_factory, session_scope


def main() -> None:
    parser = argparse.ArgumentParser(description="Spread overdue reviews forward.")
    parser.add_argument("--days", type=int, default=21, help="Spread window.")
    parser.add_argument(
        "--per-day",
        type=int,
        default=None,
        help="Cap per day. Default: backlog / days, rounded up.",
    )
    parser.add_argument(
        "--keep-due",
        type=int,
        default=10,
        help="How many stay due right now.",
    )
    parser.add_argument(
        "--include-own",
        action="store_true",
        help="Also move words the learner added themselves (default: keep).",
    )
    parser.add_argument("--apply", action="store_true", help="Write the changes.")
    args = parser.parse_args()

    settings = get_settings()
    if settings.telegram_allowed_user_id is None:
        raise SystemExit("TELEGRAM_ALLOWED_USER_ID is required.")

    engine = make_engine(settings.db_url)
    factory = make_session_factory(engine)
    with session_scope(factory) as session:
        user = session.scalar(
            select(User).where(
                User.telegram_user_id == settings.telegram_allowed_user_id
            )
        )
        if user is None:
            raise SystemExit("Owner profile not found.")

        now = utc_now()
        stmt = (
            select(ReviewState, LearningItem)
            .join(LearningItem, LearningItem.id == ReviewState.learning_item_id)
            .where(
                LearningItem.user_id == user.id,
                LearningItem.status == "active",
                ReviewState.due_at <= now,
                ReviewState.review_count == 0,
            )
            .order_by(LearningItem.created_at, LearningItem.id)
        )
        rows = list(session.execute(stmt))
        if not args.include_own:
            rows = [row for row in rows if row[1].priority == 0]

        backlog = rows[args.keep_due :]
        if not backlog:
            print(f"Nothing to spread: {len(rows)} untouched due item(s).")
            return

        per_day = args.per_day or -(-len(backlog) // max(1, args.days))
        moved = 0
        for index, (state, _item) in enumerate(backlog):
            day = index // per_day + 1
            state.due_at = now + timedelta(days=day)
            session.add(state)
            moved += 1

        print(f"Due now, never reviewed : {len(rows)}")
        print(f"Staying due             : {min(args.keep_due, len(rows))}")
        print(f"Spread over {args.days:>3} days     : {moved} ({per_day}/day)")
        if not args.apply:
            session.rollback()
            print("\nDry run. Re-run with --apply to write.")
        else:
            print("\nApplied.")


if __name__ == "__main__":
    main()
