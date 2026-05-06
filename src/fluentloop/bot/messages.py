from __future__ import annotations

from fluentloop.db.models import ExtractedCandidate, MistakePattern

HELP = """Commands
/start - create or load profile
/today - start today's practice
/review - review due items
/add - add a learning item
/add expression | push back on | мягко возражать | meetings,stakeholders
/approve <material_id> - approve all pending candidates for a material
/upload - upload lesson material
/mistakes - show mistake patterns
/rules - show grammar concepts
/stats - show progress
/favorites - show favorite items
/settings - change settings
/settings set reminder_time 20:30
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
    material_id = candidates[0].source_material_id if candidates else "?"
    return (
        f"Found {parts or '0 candidates'}.\n"
        f"Send /approve {material_id} to add all pending candidates."
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
