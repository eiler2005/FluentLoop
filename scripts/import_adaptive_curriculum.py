#!/usr/bin/env python3
"""Validate or publish the curated B2-to-C1 introductory topic curriculum."""

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
        help="subscribe the admitted owner pilot and enable adaptive pool expansion",
    )
    parser.add_argument(
        "--enable-simple",
        action="store_true",
        help="set simple mode for the subscribed pilot",
    )
    parser.add_argument("--db-url", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if (args.subscribe_pilot or args.enable_simple) and not args.apply:
        parser.error("--subscribe-pilot and --enable-simple require --apply")
    if args.enable_simple and not args.subscribe_pilot:
        parser.error("--enable-simple requires --subscribe-pilot")

    from fluentloop.adaptive_curriculum import load_adaptive_curriculum

    pack = load_adaptive_curriculum()
    records = [record for topic in pack["topics"] for record in topic["records"]]
    practice = sum(
        record["simple_question"]["adaptive"]["role"] == "practice"
        for record in records
    )
    transfer = len(records) - practice
    if not args.apply:
        print(
            f"Dry run: topics={len(pack['topics'])} stages=30 "
            f"items={len(records)} practice={practice} transfer={transfer} "
            f"content_sha256={pack['content_sha256']}"
        )
        return 0

    from fluentloop.adaptive_curriculum import (
        publish_adaptive_curriculum,
        subscribe_adaptive_curriculum,
    )
    from fluentloop.config import get_settings
    from fluentloop.db.session import make_engine, make_session_factory
    from fluentloop.lesson_library import get_seed_library_user

    settings = get_settings()
    database_url = args.db_url or settings.db_url
    if args.subscribe_pilot and settings.telegram_allowed_user_id is None:
        raise RuntimeError("An admitted owner pilot is required for subscription")
    factory = make_session_factory(make_engine(database_url))
    with factory() as session, session.begin():
        published = publish_adaptive_curriculum(
            session, get_seed_library_user(session), pack
        )
        created_plans = reused_plans = 0
        if args.subscribe_pilot:
            from fluentloop.learning_prefs import set_learning_mode
            from fluentloop.users import ensure_user

            pilot = ensure_user(session, settings.telegram_allowed_user_id, settings)
            subscribed = subscribe_adaptive_curriculum(session, pilot)
            created_plans = subscribed.created_plans
            reused_plans = subscribed.reused_plans
            preferences = dict(pilot.preferences_json or {})
            raw_learning = preferences.get("learning")
            learning = dict(raw_learning) if isinstance(raw_learning, dict) else {}
            preferences["learning"] = {**learning, "adaptive_auto_expand": True}
            pilot.preferences_json = preferences
            session.add(pilot)
            if args.enable_simple:
                set_learning_mode(session, pilot, "simple")
    print(
        "Published adaptive curriculum: "
        f"templates={published.templates} "
        f"reused_templates={published.reused_templates} "
        f"items={published.items} reused_items={published.reused_items} "
        f"pilot_plans={created_plans} reused_pilot_plans={reused_plans}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
