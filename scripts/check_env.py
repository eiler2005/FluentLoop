#!/usr/bin/env python3
"""Pre-flight check: verify .env has every required key set to a non-empty
value. Does not echo values. Exit codes:

    0 — all keys present and non-empty
    1 — at least one key missing or empty
    2 — .env file unreadable or absent
"""
from __future__ import annotations

import sys
from pathlib import Path

REQUIRED = (
    "TELEGRAM_BOT_TOKEN",
    "TELEGRAM_API_ID",
    "TELEGRAM_API_HASH",
    "TELEGRAM_ALLOWED_USER_ID",
    "OPENAI_API_KEY",
    "AI_PROVIDER",
    "OPENAI_MODEL_LIGHT",
    "OPENAI_MODEL_HEAVY",
    "DB_URL",
    "TIMEZONE",
    "REMINDER_TIME_DEFAULT",
    "PRACTICE_DURATION_MINUTES",
    "PRE_GEN_HOUR",
    "PRE_GEN_MINUTE",
    "BACKUP_HOUR",
    "BACKUP_MINUTE",
    "BACKUP_RETENTION_DAYS",
    "LOG_LEVEL",
)

PLACEHOLDER_MARKERS = ("<", "TODO", "FILL_ME", "REPLACE_ME")

# Sentinel values that are intentionally non-real (overnight build mode).
# Recognized as "set" so check_env passes; downstream scripts dispatch
# stubs when they see these.
SENTINELS = {
    "OPENAI_API_KEY": ("STUB_OVERNIGHT_BUILD",),
    "AI_PROVIDER": ("stub",),
}


def parse_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, _, val = line.partition("=")
        values[key.strip()] = val.strip()
    return values


def main() -> int:
    env_path = Path(__file__).resolve().parent.parent / ".env"
    if not env_path.exists():
        print(f"FAIL: .env not found at {env_path}", file=sys.stderr)
        return 2
    try:
        values = parse_env(env_path)
    except OSError as exc:
        print(f"FAIL: .env unreadable: {exc}", file=sys.stderr)
        return 2

    missing: list[str] = []
    placeholder: list[str] = []
    for key in REQUIRED:
        val = values.get(key, "")
        sentinel_ok = val in SENTINELS.get(key, ())
        if not val:
            missing.append(key)
        elif sentinel_ok:
            continue
        elif any(marker in val for marker in PLACEHOLDER_MARKERS):
            placeholder.append(key)

    if missing or placeholder:
        if missing:
            print(f"FAIL: missing or empty: {', '.join(missing)}", file=sys.stderr)
        if placeholder:
            print(
                f"FAIL: still has placeholder value: {', '.join(placeholder)}",
                file=sys.stderr,
            )
        return 1

    print(f"OK: {len(REQUIRED)} required keys set in {env_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
