#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from fluentloop.config import get_settings
from fluentloop.curriculum_b2 import render_curriculum_markdown, seed_b2_curriculum
from fluentloop.db.session import make_engine, make_session_factory
from fluentloop.users import ensure_user


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db-url", help="override DB_URL for local/test runs")
    parser.add_argument(
        "--write-markdown",
        default="docs/curriculum/b2_b2plus_lesson_catalog.md",
        help="write curriculum catalog markdown to this path",
    )
    args = parser.parse_args()
    settings = get_settings()
    if args.db_url:
        settings = settings.__class__(**{**settings.__dict__, "db_url": args.db_url})
    if settings.telegram_allowed_user_id is None:
        raise RuntimeError("TELEGRAM_ALLOWED_USER_ID is required for curriculum seed")
    engine = make_engine(settings.db_url)
    factory = make_session_factory(engine)
    with factory() as session:
        user = ensure_user(session, settings.telegram_allowed_user_id, settings)
        result = seed_b2_curriculum(session, user)
        session.commit()
    if args.write_markdown:
        path = Path(args.write_markdown)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(render_curriculum_markdown(), encoding="utf-8")
    print(
        "OK: B2/B2+ curriculum seeded "
        f"lessons={result['lessons']} items={result['items']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
