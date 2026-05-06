from __future__ import annotations

from fluentloop.db.models import ExtractedCandidate, MistakePattern

HELP = """Commands
/start - create or load profile
/today - start today's practice
/review - review due items
/add - add a learning item
/upload - upload lesson material
/mistakes - show mistake patterns
/rules - show grammar concepts
/stats - show progress
/settings - change settings
/help - show help"""


def start_message(channel_enabled: bool = False) -> str:
    where = (
        "Channel mode is enabled for practice posts."
        if channel_enabled
        else "Practice runs here."
    )
    return f"FluentLoop is ready.\n{where}\nSend /upload, /add, or /today."


def candidate_summary(candidates: list[ExtractedCandidate]) -> str:
    counts: dict[str, int] = {}
    for candidate in candidates:
        counts[candidate.type] = counts.get(candidate.type, 0) + 1
    parts = ", ".join(f"{value} {key}" for key, value in sorted(counts.items()))
    return (
        f"Found {parts or '0 candidates'}. Use approval buttons in the full bot flow."
    )


def mistake_patterns(patterns: list[MistakePattern]) -> str:
    if not patterns:
        return "No active mistake patterns yet."
    lines = ["Mistake patterns"]
    for pattern in patterns:
        lines.append(
            f"- {pattern.description} ({pattern.confidence}, {pattern.event_count})"
        )
    return "\n".join(lines)
