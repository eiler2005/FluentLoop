from __future__ import annotations

from collections.abc import Iterable

from fluentloop.db.models import ExtractedCandidate, MistakePattern
from fluentloop.lesson_overview import infer_lesson_overview

HELP = """How to use FluentLoop

Daily loop:
1. Send /today for the automatic 15-minute lesson.
2. Answer each prompt in text.
3. Use Skip / show answer or /skip when you want the model answer first.
4. Read compact teacher feedback; use /feedback explain <attempt_id> for details.
5. Weak items, due reviews, and mistake patterns rotate back into future lessons.

Lessons and topics:
- /topics shows the knowledge areas in the active lesson base.
- /lessons [query] lists lesson pools by title, topic, focus, or tags.
- /lesson <id> shows one lesson card.
- /lesson random starts a random active lesson.
- /lesson topic <query> starts the best matching active lesson.
- /practice supports vocab, grammar, mistakes, writing, review, mixed,
  diplomatic, notebook, discourse, reading, genre, writing_workshop, and sprint.

Adding material:
- In #materials_upload / Materials Upload, send /upload, choose the material type,
  then paste text or attach a UTF-8 .md/.txt lesson file.
- FluentLoop extracts a lesson title, theme, knowledge areas, expressions, grammar
  rules, and mistake risks.
- New learning items become active only after approval with /approve <material_id>
  or the Approve all button.

Telegram workspace:
- Practice Flow: current lesson and answers.
- Materials Upload: lesson notes, word lists, homework, exercises, feedback.
- Feedback: answer checks and teacher explanations.
- Next Prompts: follow-up prompts when split from feedback.
- Mistakes, Summaries, and Stats: weak points and progress.
- Bot DM: private commands and text entry when Telegram needs a direct chat.

Commands:
/start - create or load profile and post workspace hubs
/today - start today's practice
/review - review due items
/practice <mode> - start a focused or EPIC-22 breakthrough mode
/topics - browse lesson topics and knowledge areas
/lessons [query] - list active lesson plans
/lesson <id>|random|topic <query> - inspect or start lessons
/skip - skip current exercise and show the answer
/feedback explain <attempt_id> - show detailed teacher feedback
/reflect <text> - save a short reflective practice note
/scene <topic> - build a business/IT roleplay card
/brief <agenda> - prepare just-in-time meeting language
/mentor - weekly Socratic prompt
/article <text> - text-first Article Lab v1
/debate <topic> - start Debate Mode
/translate_lab <topic> - RU->EN transfer practice
/fluency432 <topic> - 4-3-2 fluency practice
/upload - upload lesson material
/add expression | push back on | мягко возражать | meetings,stakeholders
/candidates <material_id> - review extracted candidates
/candidate add|edit|skip <candidate_id> - manage one candidate
/approve <material_id> - approve all pending candidates for a material
/dispute <attempt_id> <reason> - dispute feedback
/mistakes - show mistake patterns
/rules - show grammar concepts
/stats - show progress
/favorites - show favorite items
/items [active|archived|suspended]
/item archive|suspend|restore <item_id>
/settings - change settings
/help or /howto - show this guide"""


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
