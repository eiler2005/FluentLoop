#!/usr/bin/env python3
"""Pre-flight check: minimal OpenAI API call to confirm the key works.

Sends a 1-token completion via gpt-4o-mini. Cost: well under $0.0001.
Does NOT echo the key. Exit codes:

    0 — call succeeded
    1 — call failed (auth, quota, network)
    2 — required env vars missing
"""
from __future__ import annotations

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


def main() -> int:
    load_env()

    api_key = os.environ.get("OPENAI_API_KEY", "")
    model = os.environ.get("OPENAI_MODEL_LIGHT", "gpt-4o-mini")
    provider = os.environ.get("AI_PROVIDER", "openai").lower()
    if not api_key:
        print("FAIL: OPENAI_API_KEY must be set", file=sys.stderr)
        return 2

    # Overnight stub mode: skip the real call. Bot will use a stub provider.
    if provider == "stub" or api_key == "STUB_OVERNIGHT_BUILD":
        print(
            "OK: stub mode (AI_PROVIDER=stub or sentinel key) — no real call made"
        )
        return 0

    try:
        from openai import OpenAI  # type: ignore[import-not-found]
    except ImportError:
        print("FAIL: openai not installed (pip install openai)", file=sys.stderr)
        return 1

    client = OpenAI(api_key=api_key)
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": "ping"}],
            max_tokens=1,
        )
        finish = response.choices[0].finish_reason
        usage = response.usage
        print(
            f"OK: model={model} finish={finish} "
            f"prompt_tokens={usage.prompt_tokens if usage else '?'} "
            f"completion_tokens={usage.completion_tokens if usage else '?'}"
        )
        return 0
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL: openai call error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
