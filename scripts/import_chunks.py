from __future__ import annotations

import argparse
from pathlib import Path

from fluentloop.config import get_settings
from fluentloop.curriculum_chunks import import_chunks_jsonl
from fluentloop.db.session import make_engine, make_session_factory, session_scope
from fluentloop.users import ensure_user


def main() -> None:
    parser = argparse.ArgumentParser(description="Import EPIC-22 chunks JSONL.")
    parser.add_argument(
        "path",
        nargs="?",
        default="data/curriculum/chunks_v1.jsonl",
        help="Path to chunks JSONL generated from the EPIC-22 spec.",
    )
    args = parser.parse_args()

    settings = get_settings()
    if settings.telegram_allowed_user_id is None:
        raise SystemExit("TELEGRAM_ALLOWED_USER_ID is required for owner import.")

    engine = make_engine(settings.db_url)
    factory = make_session_factory(engine)
    with session_scope(factory) as session:
        user = ensure_user(session, settings.telegram_allowed_user_id, settings)
        created, skipped = import_chunks_jsonl(session, user, Path(args.path))
        print(f"Imported chunks: created={created}, skipped={skipped}")


if __name__ == "__main__":
    main()
