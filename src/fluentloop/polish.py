from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from fluentloop.db.models import PracticeAttempt


def article_lab_30_day_plan(text: str) -> list[dict[str, str]]:
    source_hint = (text.strip() or "article")[:80]
    return [
        {"day": "1", "task": "pre-read, chunk pick, first 1T cloze"},
        {"day": "2", "task": "comprehension and paraphrased cloze"},
        {"day": "3", "task": "reverse translation with 3 mined chunks"},
        {"day": "7", "task": "transfer test in a new work context"},
        {"day": "14", "task": "executive summary using active chunks"},
        {"day": "30", "task": f"cross-source recall against: {source_hint}"},
    ]


def sprint_mode_plan(goal: str = "") -> dict[str, Any]:
    focus = goal.strip() or "one English bottleneck"
    return {
        "focus": focus,
        "duration_days": 14,
        "daily_contract": [
            "one review block",
            "one stretch production",
            "one reflection line",
        ],
        "success_metric": "10 green sessions out of 14 and one cold final recall",
    }


def rolling_native_comparison(attempts: Sequence[PracticeAttempt]) -> list[str]:
    comparisons: list[str] = []
    for attempt in attempts:
        native = str(attempt.feedback.get("native_rewrite") or "").strip()
        answer = attempt.user_answer.strip()
        if native and answer and native.lower() != answer.lower():
            comparisons.append(f"{answer[:80]} -> {native[:80]}")
        if len(comparisons) >= 5:
            break
    return comparisons


def enrich_why_layer(
    base: str,
    *,
    rule: str = "",
    l1_hits: Sequence[dict[str, str]] | None = None,
    exercise_type: str = "",
) -> str:
    parts = [base.strip()] if base.strip() else []
    if rule:
        parts.append(f"Rule pressure: {rule}")
    if l1_hits:
        first = l1_hits[0]
        parts.append(
            "L1 mechanism: "
            f"{first.get('matched_text', '')} maps to {first.get('suggestion', '')}."
        )
    if exercise_type:
        parts.append(f"Practice transfer: watch this in {exercise_type} tasks.")
    return " ".join(part for part in parts if part).strip()
