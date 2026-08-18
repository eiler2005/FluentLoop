"""Backfill translations, glosses and examples on existing items.

Bank entries ship with an English gloss and an example but no Russian, so a
learner who seeded a starter list has hundreds of half-cards. This walks them,
asks the model once per item, and writes back only what was missing.

Dry run by default. One LLM call per item, so mind --limit on a large base.
"""

from __future__ import annotations

import argparse

from sqlalchemy import select

from fluentloop.config import get_settings
from fluentloop.db.models import LearningItem, User
from fluentloop.db.session import make_engine, make_session_factory, session_scope
from fluentloop.vocab_loop import CARD_ITEM_TYPES
from fluentloop.word_cards import enrich_item, needs_enrichment, stored_russian


def main() -> None:
    parser = argparse.ArgumentParser(description="Fill in missing card fields.")
    parser.add_argument("--limit", type=int, default=25, help="Items per run.")
    parser.add_argument("--apply", action="store_true", help="Write the changes.")
    args = parser.parse_args()

    settings = get_settings()
    if settings.telegram_allowed_user_id is None:
        raise SystemExit("TELEGRAM_ALLOWED_USER_ID is required.")

    factory = make_session_factory(make_engine(settings.db_url))
    with session_scope(factory) as session:
        user = session.scalar(
            select(User).where(
                User.telegram_user_id == settings.telegram_allowed_user_id
            )
        )
        if user is None:
            raise SystemExit("Owner profile not found.")

        items = [
            item
            for item in session.scalars(
                select(LearningItem)
                .where(
                    LearningItem.user_id == user.id,
                    LearningItem.status == "active",
                    LearningItem.type.in_(CARD_ITEM_TYPES),
                )
                .order_by(LearningItem.id)
            )
            if needs_enrichment(item)
        ]
        print(f"Incomplete cards: {len(items)}")
        batch = items[: max(0, args.limit)]
        print(f"This run        : {len(batch)}")
        if not batch:
            return

        changed = 0
        for item in batch:
            if enrich_item(session, item, settings=settings):
                changed += 1
                russian = stored_russian(item) or "-"
                example = (item.examples or ["-"])[0]
                print(f"  {item.text:<28} {russian:<28} {example[:44]}")

        print(f"\nEnriched: {changed}/{len(batch)}")
        if not args.apply:
            session.rollback()
            print("Dry run. Re-run with --apply to write.")
        else:
            print("Applied.")


if __name__ == "__main__":
    main()
