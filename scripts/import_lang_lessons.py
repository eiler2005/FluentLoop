#!/usr/bin/env python3
"""Dry-run or publish the reviewed lang-lessons question bank."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--apply", action="store_true", help="publish curated templates"
    )
    parser.add_argument(
        "--subscribe-pilot",
        action="store_true",
        help="subscribe the admitted pilot profile to all 19 topics",
    )
    parser.add_argument(
        "--enable-simple",
        action="store_true",
        help="set simple mode for the pilot profile",
    )
    parser.add_argument("--db-url", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if (args.subscribe_pilot or args.enable_simple) and not args.apply:
        parser.error("--subscribe-pilot and --enable-simple require --apply")
    if args.enable_simple and not args.subscribe_pilot:
        parser.error("--enable-simple requires --subscribe-pilot")

    from fluentloop.lang_lessons import load_lang_lessons

    pack = load_lang_lessons()
    topics = len(pack["topics"])
    items = sum(len(topic["records"]) for topic in pack["topics"])
    if not args.apply:
        print(
            "Dry run: "
            f"topics={topics} items={items} "
            f"source_sha256={pack['source']['sha256']}"
        )
        return 0

    from fluentloop.config import get_settings
    from fluentloop.db.session import make_engine, make_session_factory
    from fluentloop.lang_lessons import publish_lang_lessons, subscribe_lang_lessons
    from fluentloop.lesson_library import get_seed_library_user

    settings = get_settings()
    if args.db_url:
        settings = settings.__class__(**{**settings.__dict__, "db_url": args.db_url})
    if args.subscribe_pilot and settings.telegram_allowed_user_id is None:
        raise RuntimeError(
            "TELEGRAM_ALLOWED_USER_ID is required for pilot subscription"
        )

    engine = make_engine(settings.db_url)
    factory = make_session_factory(engine)
    with factory() as session, session.begin():
        owner = get_seed_library_user(session)
        published = publish_lang_lessons(session, owner, pack)
        created_plans = reused_plans = 0
        if args.subscribe_pilot:
            from fluentloop.learning_prefs import set_learning_mode
            from fluentloop.users import ensure_user

            pilot = ensure_user(session, settings.telegram_allowed_user_id, settings)
            subscribed = subscribe_lang_lessons(session, pilot)
            created_plans = subscribed.created_plans
            reused_plans = subscribed.reused_plans
            if args.enable_simple:
                set_learning_mode(session, pilot, "simple")

    print(
        "Published lang-lessons templates: "
        f"templates={published.templates} "
        f"reused_templates={published.reused_templates} "
        f"items={published.items} reused_items={published.reused_items} "
        f"pilot_plans={created_plans} reused_pilot_plans={reused_plans}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
