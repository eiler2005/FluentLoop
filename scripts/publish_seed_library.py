#!/usr/bin/env python3
from __future__ import annotations

import argparse

from fluentloop.config import get_settings
from fluentloop.db.session import make_engine, make_session_factory
from fluentloop.lesson_library import seed_and_publish_catalog_templates


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db-url", help="override DB_URL for local/test runs")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="commit changes; without this flag the script rolls back",
    )
    args = parser.parse_args()
    settings = get_settings()
    if args.db_url:
        settings = settings.__class__(**{**settings.__dict__, "db_url": args.db_url})
    engine = make_engine(settings.db_url)
    factory = make_session_factory(engine)
    with factory() as session:
        result = seed_and_publish_catalog_templates(session)
        if args.apply:
            session.commit()
            mode = "applied"
        else:
            session.rollback()
            mode = "dry-run"
    print(
        f"OK: seed library {mode} "
        f"seeded_lessons={result['seeded_lessons']} "
        f"seeded_items={result['seeded_items']} "
        f"templates_marked={result['templates']} "
        f"sources_marked={result['sources']} "
        f"items_marked={result['items']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
