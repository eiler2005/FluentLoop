from __future__ import annotations

import argparse
import asyncio

from fluentloop.bot.app import run_bot
from fluentloop.config import get_settings
from fluentloop.db.session import make_engine, make_session_factory
from fluentloop.grammar import seed_concepts
from fluentloop.logging import configure_logging


def main() -> int:
    parser = argparse.ArgumentParser(prog="fluentloop")
    parser.add_argument("--check", action="store_true", help="construct app and exit")
    args = parser.parse_args()

    settings = get_settings()
    configure_logging(settings.log_level)
    engine = make_engine(settings.db_url)
    session_factory = make_session_factory(engine)
    with session_factory() as session:
        seed_concepts(session)
        session.commit()
    if args.check:
        print("OK: FluentLoop app constructs")
        return 0
    asyncio.run(run_bot(settings, session_factory))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
