#!/usr/bin/env python3
"""Validate the public lexical bank and regenerate its readable catalog."""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bank", type=Path, help="validate an edited public bank")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--render", type=Path, help="write public Markdown/HTML views")
    mode.add_argument("--check-render", type=Path, help="verify generated views")
    args = parser.parse_args(argv)
    from fluentloop.lexical_export import public_views
    from fluentloop.lexical_learning import LEXICON_PATH, validate_lexicon
    from fluentloop.workplace_roadmap import read_json

    try:
        bank = validate_lexicon(
            read_json(args.bank or LEXICON_PATH, max_bytes=2 * 1024 * 1024)
        )
        destination = args.render or args.check_render
        if destination:
            views = public_views(bank)
            if args.render:
                destination.mkdir(parents=True, exist_ok=True)
                for filename, content in views.items():
                    (destination / filename).write_text(content, encoding="utf-8")
            else:
                stale = [
                    name
                    for name, text in views.items()
                    if not (destination / name).exists()
                    or (destination / name).read_text(encoding="utf-8") != text
                ]
                if stale:
                    parser.error("Stale lexical views: " + ", ".join(stale))
        counts = Counter(entry["strand"] for entry in bank["entries"])
        print(
            f"Validated {len(bank['entries'])} senses in "
            f"{len(bank['functions'])} functions; {dict(counts)}"
        )
    except (ValueError, OSError) as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
