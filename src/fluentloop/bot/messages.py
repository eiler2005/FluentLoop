from __future__ import annotations

from collections.abc import Iterable

from fluentloop.db.models import ExtractedCandidate, MistakePattern
from fluentloop.lesson_overview import infer_lesson_overview

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
/practice vocab|grammar|mistakes|writing|review|mixed - start a mode
/topics - browse lesson topics and knowledge areas
/lessons [query] - list active lesson plans
/lesson <id>|random|topic <query> - inspect or start lessons
/skip - skip current exercise and show the answer
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


MAX_TELEGRAM_MESSAGE_CHARS = 3900


def candidate_summary(
    candidates: list[ExtractedCandidate],
    *,
    raw_text: str = "",
    material_type: str = "",
) -> str:
    counts: dict[str, int] = {}
    for candidate in candidates:
        counts[candidate.type] = counts.get(candidate.type, 0) + 1
    parts = ", ".join(f"{value} {key}" for key, value in sorted(counts.items()))
    material_id = candidates[0].source_material_id if candidates else "?"
    overview = infer_lesson_overview(
        raw_text,
        item_texts=[candidate.text for candidate in candidates],
        tags=[tag for candidate in candidates for tag in (candidate.tags or [])],
    )
    lines = [
        f"Lesson: {overview.title}",
        f"Theme: {overview.theme}",
        f"Focus: {overview.focus}",
        "Knowledge areas:",
        *_format_list("Topics", overview.knowledge_areas),
        *_format_list("Grammar", overview.grammar_rules),
        *_format_list("Skills", overview.communication_skills),
        *_format_list("Mistake risks", overview.mistake_risks),
        "",
        f"Found {len(candidates)} candidate(s): {parts or '0 candidates'}.",
    ]
    if candidates:
        lines.append("Candidates:")
        _append_bounded(
            lines,
            (_candidate_line(candidate) for candidate in candidates),
            overflow=(
                "List shortened only because Telegram has a message limit. "
                f"Use /candidates {material_id} to review the full list."
            ),
        )
    lines.append(
        "After approval, I'll create a lesson pool and rotate it into /today."
    )
    lines.append(f"Send /approve {material_id} to add all pending candidates.")
    return "\n".join(lines)


def _format_list(label: str, values: Iterable[str]) -> list[str]:
    compact = [value for value in values if value]
    if not compact:
        return []
    return [f"- {label}: {', '.join(compact)}"]


def _candidate_line(candidate: ExtractedCandidate) -> str:
    meaning = candidate.meaning or candidate.explanation
    suffix = f" - {meaning[:80]}" if meaning else ""
    return f"- {candidate.type}: {candidate.text}{suffix}"


def _append_bounded(
    lines: list[str], extra_lines: Iterable[str], *, overflow: str
) -> None:
    current_length = len("\n".join(lines))
    for line in extra_lines:
        projected = current_length + len(line) + 1
        if projected > MAX_TELEGRAM_MESSAGE_CHARS:
            lines.append(overflow)
            return
        lines.append(line)
        current_length = projected


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
