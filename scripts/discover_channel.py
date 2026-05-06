#!/usr/bin/env python3
"""Discover a Telegram channel id from recent bot updates without printing secrets."""

from __future__ import annotations

import json
import os
import sys
import urllib.request
from pathlib import Path


def load_env() -> None:
    env_path = Path(__file__).resolve().parent.parent / ".env"
    if not env_path.exists():
        return
    for raw in env_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        os.environ.setdefault(key.strip(), val.strip())


def main() -> int:
    load_env()
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    title = os.environ.get("TELEGRAM_CHANNEL_TITLE", "FluentLoop English")
    if not token:
        print("FAIL: TELEGRAM_BOT_TOKEN must be set", file=sys.stderr)
        return 2
    from fluentloop.channel import find_channel_from_updates

    url = f"https://api.telegram.org/bot{token}/getUpdates?limit=100"
    with urllib.request.urlopen(url, timeout=10) as resp:
        updates = json.loads(resp.read().decode("utf-8")).get("result", [])
    channel_id = find_channel_from_updates(updates, title)
    if channel_id is None:
        print(f"NOT_FOUND: no recent updates for channel title {title!r}")
        return 1
    print(f"OK: channel {title!r} discovered; set TELEGRAM_CHANNEL_ID=<channel-id>")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
