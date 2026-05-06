#!/usr/bin/env python3
"""Post-deploy smoke test: send /start to the bot via the Bot API and
verify a reply within 10 seconds.

Uses the raw Bot HTTP API (not Telethon) so it's a separate code path
from the bot itself — a true black-box smoke test.

Exit codes:
    0 — bot replied within timeout
    1 — bot did not reply within timeout
    2 — required env vars missing
    3 — HTTP error
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
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


def main() -> int:
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

    # Mark the cutoff so we ignore older updates.
    try:
        baseline = call_bot(token, "getUpdates", {"limit": 1, "offset": -1})
    except RuntimeError as exc:
        print(f"FAIL: getUpdates baseline error: {exc}", file=sys.stderr)
        return 3
    last_id = 0
    for upd in baseline.get("result", []):
        last_id = max(last_id, upd.get("update_id", 0))

    try:
        call_bot(token, "sendMessage", {"chat_id": chat_id, "text": "/start"})
    except RuntimeError as exc:
        print(f"FAIL: sendMessage error: {exc}", file=sys.stderr)
        return 3

    deadline = time.time() + 15.0
    while time.time() < deadline:
        try:
            polls = call_bot(
                token,
                "getUpdates",
                {"offset": last_id + 1, "timeout": 3, "limit": 10},
            )
        except RuntimeError as exc:
            print(f"FAIL: getUpdates poll error: {exc}", file=sys.stderr)
            return 3
        for upd in polls.get("result", []):
            last_id = max(last_id, upd.get("update_id", 0))
            msg = upd.get("message") or upd.get("edited_message") or {}
            from_bot = msg.get("from", {}).get("is_bot", False)
            if from_bot and msg.get("chat", {}).get("id") == chat_id:
                text = msg.get("text", "")[:80]
                print(f"OK: bot replied: {text!r}")
                return 0
        time.sleep(0.5)

    print("FAIL: bot did not reply within 15 seconds", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
