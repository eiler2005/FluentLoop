from __future__ import annotations

from fluentloop.db.models import ExtractedCandidate, MistakePattern

HELP = """How FluentLoop works

Telegram workspace:
- FluentLoop English Forum is the main place to study.
- Practice Flow starts or resumes practice.
- #materials_upload / Materials Upload is for lesson notes, word lists,
  homework, exercises, and teacher feedback.
- Feedback, Next Prompts, Mistakes, Summaries, and Stats keep the work tidy.
- FluentLoop English is the announcement/digest channel.

Bot DM:
- Write free-text answers here if you started from the announcement channel.
- Upload material text here after tapping Upload material, or send /upload
  in the forum Materials Upload topic.
- Use commands here when buttons are inconvenient.

Commands:
/start - create or load profile and post workspace hubs
/today - start today's practice
/review - review due items
/upload - upload lesson material
/add expression | push back on | мягко возражать | meetings,stakeholders
/candidates <material_id> - review extracted candidates
/candidate add <candidate_id> - add one candidate
/candidate edit <candidate_id> - edit one candidate
/candidate skip <candidate_id> - skip one candidate
/approve <material_id> - approve all pending candidates for a material
/dispute <attempt_id> <reason> - dispute feedback
/mistakes - show mistake patterns
/mistakes focus|ignore|examples <pattern_id>
/rules - show grammar concepts
/stats - show progress
/favorites - show favorite items
/items [active|archived|suspended]
/item archive|suspend|restore <item_id>
/settings - change settings
/settings set reminder_time 20:30
/help - show this help"""


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
            f"- #{pattern.id} {pattern.description} "
            f"({pattern.confidence}, {pattern.event_count})"
        )
    return "\n".join(lines)
