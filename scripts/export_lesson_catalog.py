from __future__ import annotations

import argparse
from pathlib import Path

from fluentloop.catalog_export import write_public_catalog
from fluentloop.config import get_settings
from fluentloop.db.session import make_engine, make_session_factory, session_scope


def main() -> None:
    parser = argparse.ArgumentParser(description="Export public FluentLoop catalog")
    parser.add_argument(
        "--public-only",
        action="store_true",
        help=(
            "Export shared templates and code scenario cards only. "
            "This is v1 default."
        ),
    )
    parser.add_argument("--html", action="store_true", help="Also render HTML files.")
    parser.add_argument(
        "--out",
        default="docs/lesson-catalog",
        help="Output directory for generated catalog files.",
    )
    parser.add_argument(
        "--db-url",
        default="",
        help="Override DB URL. Defaults to DB_URL from environment/settings.",
    )
    args = parser.parse_args()

    settings = get_settings()
    db_url = args.db_url or settings.db_url
    engine = make_engine(db_url)
    factory = make_session_factory(engine)
    with session_scope(factory) as session:
        written = write_public_catalog(session, Path(args.out), html=args.html)

    print(f"Exported {len(written)} catalog files to {args.out}")
    for relative_path in sorted(written):
        print(f"- {relative_path}")


if __name__ == "__main__":
    main()
