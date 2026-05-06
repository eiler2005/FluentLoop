from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

LIGHT_INPUT_PER_M = 0.150
LIGHT_OUTPUT_PER_M = 0.600
HEAVY_INPUT_PER_M = 2.50
HEAVY_OUTPUT_PER_M = 10.00


def estimate_cost(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    if model == "gpt-4o":
        return (prompt_tokens / 1_000_000 * HEAVY_INPUT_PER_M) + (
            completion_tokens / 1_000_000 * HEAVY_OUTPUT_PER_M
        )
    return (prompt_tokens / 1_000_000 * LIGHT_INPUT_PER_M) + (
        completion_tokens / 1_000_000 * LIGHT_OUTPUT_PER_M
    )


def append_usage(
    path: Path,
    *,
    provider: str,
    model: str,
    task: str,
    prompt_tokens: int,
    completion_tokens: int,
    cost_usd: float,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    row = {
        "ts": datetime.now(UTC).isoformat(),
        "provider": provider,
        "model": model,
        "task": task,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "cost_usd": cost_usd,
    }
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def total_usage(path: Path) -> float:
    if not path.exists():
        return 0.0
    total = 0.0
    for raw in path.read_text(encoding="utf-8").splitlines():
        if raw.strip():
            total += float(json.loads(raw).get("cost_usd", 0.0))
    return total
