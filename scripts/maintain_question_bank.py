#!/usr/bin/env python3
"""Inspect eligible bank maintenance or execute the bounded daily work."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--apply", action="store_true", help="run approved-profile maintenance"
    )
    parser.add_argument(
        "--disable-pilot",
        action="store_true",
        help="disable owner bank maintenance without changing learning history",
    )
    args = parser.parse_args()
    if args.disable_pilot and not args.apply:
        parser.error("--disable-pilot requires --apply")
    from sqlalchemy import select

    from fluentloop.config import get_settings
    from fluentloop.db.models import User
    from fluentloop.db.session import make_engine, make_session_factory
    from fluentloop.learning_prefs import is_simple_mode
    from fluentloop.question_quality import run_question_maintenance

    settings = get_settings()
    factory = make_session_factory(make_engine(settings.db_url, create=False))
    if args.disable_pilot:
        from copy import deepcopy

        from sqlalchemy import update

        with factory.begin() as session:
            owner = session.scalar(
                select(User).where(
                    User.telegram_user_id == settings.telegram_allowed_user_id
                )
            )
            if owner is None:
                raise RuntimeError("Pilot profile unavailable")
            session.execute(
                update(User)
                .where(User.id == owner.id)
                .values(updated_at=User.updated_at)
            )
            session.refresh(owner)
            preferences = deepcopy(owner.preferences_json or {})
            preferences.setdefault("learning", {})["adaptive_auto_expand"] = False
            owner.preferences_json = preferences
        print(json.dumps({"pilot_maintenance_enabled": False}))
        return 0
    if not args.apply:
        with factory() as session:
            count = sum(
                is_simple_mode(user)
                and bool(
                    (user.preferences_json or {})
                    .get("learning", {})
                    .get("adaptive_auto_expand")
                )
                for user in session.scalars(select(User))
            )
        print(
            json.dumps(
                {
                    "dry_run": True,
                    "eligible_profiles": count,
                    "max_candidates_per_day": 2,
                }
            )
        )
        return 0
    print(json.dumps(asdict(run_question_maintenance(settings, factory))))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
