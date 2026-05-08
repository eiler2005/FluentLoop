#!/usr/bin/env python3
"""Post-deploy smoke test for Telegram reachability.

The Bot HTTP API cannot impersonate the user, so it cannot truly send
``/start`` *to* a Telethon bot and wait for the bot to process it. This smoke
test verifies the deploy-facing Telegram path that is available without a user
session: token auth via ``getMe`` plus outbound delivery to the allowed chat.

Container health and Telethon long-polling are checked by deploy/VPS logs.

Exit codes:
    0 — Bot API auth and outbound delivery succeeded
    1 — Bot API returned ok=false
    2 — required env vars missing
    3 — HTTP error
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


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


def call_bot(token: str, method: str, payload: dict) -> dict:
    url = f"https://api.telegram.org/bot{token}/{method}"
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json"}, method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"HTTP {exc.code}: {body}") from exc


def git_value(args: list[str]) -> str | None:
    repo_root = Path(__file__).resolve().parent.parent
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=repo_root,
            check=True,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    value = result.stdout.strip()
    return value or None


def current_time_label() -> str:
    timezone_name = os.environ.get("TIMEZONE", "Europe/Moscow")
    try:
        tz = ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError:
        tz = None
    if tz is not None:
        now = datetime.now(tz).astimezone()
    else:
        now = datetime.now().astimezone()
    return now.strftime("%Y-%m-%d %H:%M:%S %Z")


def build_label(explicit_build_id: str | None = None) -> str:
    if explicit_build_id:
        return explicit_build_id
    env_build = os.environ.get("FLUENTLOOP_BUILD_ID") or os.environ.get("BUILD_ID")
    if env_build:
        return env_build
    build_number = git_value(["rev-list", "--count", "HEAD"])
    commit_sha = git_value(["rev-parse", "--short", "HEAD"])
    if build_number and commit_sha:
        return f"{build_number} ({commit_sha})"
    return commit_sha or build_number or "unknown"


def format_smoke_message(
    text: str,
    *,
    plans: list[str],
    build_id: str | None = None,
) -> str:
    if not plans:
        return text
    lines = [
        text,
        "",
        f"Build: {build_label(build_id)}",
        f"Time: {current_time_label()}",
        "",
        "Plan:",
    ]
    lines.extend(f"- {plan}" for plan in plans)
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--text",
        default="FluentLoop deploy smoke: Bot API outbound check passed.",
        help="message text to send to TELEGRAM_ALLOWED_USER_ID",
    )
    parser.add_argument(
        "--plan",
        action="append",
        default=[],
        help="one implementation/validation note to include in the smoke message",
    )
    parser.add_argument(
        "--build-id",
        default=None,
        help="explicit build identifier; defaults to git commit count and short SHA",
    )
    args = parser.parse_args()
    load_env()
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat_id_raw = os.environ.get("TELEGRAM_ALLOWED_USER_ID", "")
    if not token or not chat_id_raw:
        print(
            "FAIL: TELEGRAM_BOT_TOKEN and TELEGRAM_ALLOWED_USER_ID must be set",
            file=sys.stderr,
        )
        return 2
    try:
        chat_id = int(chat_id_raw)
    except ValueError:
        print("FAIL: TELEGRAM_ALLOWED_USER_ID must be an integer", file=sys.stderr)
        return 2

    try:
        me = call_bot(token, "getMe", {})
    except RuntimeError as exc:
        print(f"FAIL: getMe error: {exc}", file=sys.stderr)
        return 3
    if not me.get("ok"):
        print(f"FAIL: getMe returned ok=false: {me}", file=sys.stderr)
        return 1

    try:
        text = format_smoke_message(
            args.text,
            plans=args.plan,
            build_id=args.build_id,
        )
        sent = call_bot(
            token,
            "sendMessage",
            {
                "chat_id": chat_id,
                "text": text,
            },
        )
    except RuntimeError as exc:
        print(f"FAIL: sendMessage error: {exc}", file=sys.stderr)
        return 3
    if not sent.get("ok"):
        print(f"FAIL: sendMessage returned ok=false: {sent}", file=sys.stderr)
        return 1
    username = me.get("result", {}).get("username", "<unknown>")
    message_id = sent.get("result", {}).get("message_id", "?")
    print(f"OK: @{username} reachable; outbound message_id={message_id}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
