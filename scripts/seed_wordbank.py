from __future__ import annotations

import argparse
from pathlib import Path

from fluentloop.config import get_settings
from fluentloop.db.session import make_engine, make_session_factory, session_scope
from fluentloop.users import ensure_user
from fluentloop.vocab_prefs import get_prefs
from fluentloop.wordbank import seed_starter_list


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Seed the EPIC-25 starter word bank for the owner account."
    )
    parser.add_argument(
        "--size",
        type=int,
        default=None,
        help="How many entries to import (defaults to the user's starter size).",
    )
    parser.add_argument(
        "--path",
        default=None,
        help="Override the word bank JSONL path.",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Ignore the user's topic/kind selections and import everything.",
    )
    args = parser.parse_args()

    settings = get_settings()
    if settings.telegram_allowed_user_id is None:
        raise SystemExit("TELEGRAM_ALLOWED_USER_ID is required for owner import.")

    engine = make_engine(settings.db_url)
    factory = make_session_factory(engine)
    with session_scope(factory) as session:
        user = ensure_user(session, settings.telegram_allowed_user_id, settings)
        prefs = get_prefs(user)
        created, skipped = seed_starter_list(
            session,
            user,
            topics=None if args.all else prefs.topics,
            kinds=None if args.all else prefs.kinds,
            sets=None if args.all else prefs.sets,
            size=args.size if args.size is not None else prefs.starter_size,
            path=Path(args.path) if args.path else None,
        )
        print(f"Word bank: created={created}, skipped={skipped}")


if __name__ == "__main__":
    main()
