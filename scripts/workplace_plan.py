#!/usr/bin/env python3
"""Validate/export a Study plan; apply only to the configured admitted pilot."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


def _export(path: Path, plan: dict) -> None:
    # Personal notes can be confidential even when the underlying syllabus is public.
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        os.fchmod(handle.fileno(), 0o600)
        json.dump(plan, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", type=Path, help="public curriculum JSON")
    parser.add_argument("--profile", type=Path, help="portable personal plan JSON")
    parser.add_argument(
        "--export", type=Path, help="export default or validated profile"
    )
    parser.add_argument(
        "--export-pilot",
        type=Path,
        help="explicitly read/export the configured pilot's stored plan",
    )
    parser.add_argument("--apply", action="store_true", help="save validated profile")
    parser.add_argument(
        "--pilot", action="store_true", help="target admitted pilot only"
    )
    parser.add_argument("--db-url", help=argparse.SUPPRESS)
    parser.add_argument("--render", type=Path, help="write public Markdown/HTML views")
    parser.add_argument(
        "--check-render", type=Path, help="check that public views match the curriculum"
    )
    args = parser.parse_args(argv)
    if args.render and args.check_render:
        parser.error("Choose --render or --check-render")
    if (args.render or args.check_render) and (
        args.profile
        or args.export
        or args.export_pilot
        or args.apply
        or args.pilot
        or args.db_url
    ):
        parser.error("Public rendering cannot be combined with personal/DB operations")
    if args.apply and (not args.pilot or args.profile is None):
        parser.error("--apply requires --pilot and --profile")
    if args.pilot and not args.apply:
        parser.error("--pilot requires --apply")
    if args.export_pilot and (args.apply or args.profile or args.export):
        parser.error("--export-pilot cannot be combined with profile/export/apply")
    if args.db_url and not (args.apply or args.export_pilot):
        parser.error("--db-url requires explicit --apply or --export-pilot")

    from sqlalchemy.exc import SQLAlchemyError

    from fluentloop.workplace_roadmap import (
        default_plan,
        get_plan,
        load_curriculum,
        plan_outline,
        read_json,
        save_plan,
        validate_plan,
    )

    try:
        catalog = load_curriculum(args.catalog)
        if args.render or args.check_render:
            from fluentloop.roadmap_export import (
                render_roadmap_html,
                render_roadmap_markdown,
                write_roadmap_files,
            )

            if args.render:
                write_roadmap_files(args.render, catalog)
                print("Rendered public curriculum views")
            else:
                expected = {
                    "workplace-roadmap.md": render_roadmap_markdown(catalog),
                    "workplace-planner.html": render_roadmap_html(catalog),
                    "client-work-plan.json": json.dumps(
                        default_plan(catalog), ensure_ascii=False, indent=2
                    ) + "\n",
                }
                for name, content in expected.items():
                    path = args.check_render / name
                    if not path.exists() or path.read_text(encoding="utf-8") != content:
                        raise ValueError(f"Public render is missing or stale: {name}")
                print("Public curriculum views are current")
            return 0
        plan = (
            validate_plan(read_json(args.profile, max_bytes=256 * 1024), catalog)
            if args.profile is not None
            else default_plan(catalog)
        )
        if args.apply or args.export_pilot:
            from sqlalchemy import create_engine, select
            from sqlalchemy.orm import Session

            from fluentloop.config import get_settings
            from fluentloop.db.models import User

            settings = get_settings()
            pilot_id = settings.telegram_allowed_user_id
            if pilot_id is None:
                raise ValueError("Configure an admitted pilot before DB operations")
            # Do not initialise a database, admit users or activate curriculum items.
            engine = create_engine(args.db_url or settings.db_url)
            try:
                with Session(engine) as session, session.begin():
                    user = session.scalar(
                        select(User).where(User.telegram_user_id == pilot_id)
                    )
                    if user is None:
                        raise ValueError("Configured pilot profile does not exist")
                    plan = (
                        save_plan(session, user, plan, catalog)
                        if args.apply
                        else get_plan(user, catalog)
                    )
                    if args.export_pilot:
                        _export(args.export_pilot, plan)
            finally:
                engine.dispose()
        if args.export:
            _export(args.export, plan)
        outline = plan_outline(plan, catalog)
    except SQLAlchemyError:
        parser.error("Pilot database operation failed; verify its configured location")
    except (OSError, ValueError) as exc:
        parser.error(str(exc))

    action = "Applied to configured pilot" if args.apply else "Validated personal plan"
    print(
        f"{action}: modules={len(catalog['modules'])} track={plan['track']} "
        f"weekly_minutes={plan['weekly_minutes']} "
        f"general_minutes={outline['general_minutes']} "
        f"work_minutes={outline['work_minutes']} "
        f"lexical_minutes={outline['lexical_minutes']} paused={len(plan['paused'])}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
