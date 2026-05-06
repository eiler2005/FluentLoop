#!/usr/bin/env python3
"""Pre-flight check: Telethon bot-mode handshake.

Connects to Telegram, calls get_me(), prints the bot username, disconnects.
Does NOT echo the token. Exit codes:

    0 — connection succeeded
    1 — handshake failed (auth, network, or telethon error)
    2 — required env vars missing
"""
from __future__ import annotations

import asyncio
import os
import sys
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


async def run() -> int:
    try:
        from telethon import TelegramClient  # type: ignore[import-not-found]
    except ImportError:
        print("FAIL: telethon not installed (pip install telethon)", file=sys.stderr)
        return 1

    api_id_raw = os.environ.get("TELEGRAM_API_ID", "")
    api_hash = os.environ.get("TELEGRAM_API_HASH", "")
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    if not api_id_raw or not api_hash or not bot_token:
        print(
            "FAIL: TELEGRAM_API_ID / TELEGRAM_API_HASH / "
            "TELEGRAM_BOT_TOKEN must be set",
            file=sys.stderr,
        )
        return 2
    try:
        api_id = int(api_id_raw)
    except ValueError:
        print("FAIL: TELEGRAM_API_ID must be an integer", file=sys.stderr)
        return 2

    sessions_dir = Path(__file__).resolve().parent.parent / "data" / "sessions"
    sessions_dir.mkdir(parents=True, exist_ok=True)
    session_path = sessions_dir / "fluentloop-preflight"

    client = TelegramClient(str(session_path), api_id, api_hash)
    try:
        await client.start(bot_token=bot_token)
        me = await client.get_me()
        username = getattr(me, "username", None) or "<no-username>"
        print(f"OK: connected as @{username} (id={me.id})")
        return 0
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL: telethon handshake error: {exc}", file=sys.stderr)
        return 1
    finally:
        await client.disconnect()


def main() -> int:
    load_env()
    return asyncio.run(run())


if __name__ == "__main__":
    sys.exit(main())
