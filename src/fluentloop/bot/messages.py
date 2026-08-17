from __future__ import annotations

from collections.abc import Iterable

from fluentloop.db.models import ExtractedCandidate, MistakePattern
from fluentloop.lesson_overview import infer_lesson_overview

HELP = """How to use FluentLoop

FluentLoop helps you train B2+/C1 business/IT English from real material:
lesson notes, phrase lists, Slack/email drafts, articles, meeting notes, or
shared seed lessons.

Start here:
1. No material yet: /library -> /subscribe <template_id>
2. Have material: /upload -> /approve <material_id>
3. Measure start: /baseline <answer>
4. Train daily: /today
5. Check progress: /outcomes or /outcomes full

What happens in practice:
- Your lesson base lives in /topics, /lessons, and /lesson.
- /lesson shows lesson type, what you train, and target mix.
- /today chooses practice from your personal base.
- Feedback has layers: Errors, Native, Why.
- SRS, confidence, L1 traps, and mistake patterns decide what comes back.
- /stats shows activity; /outcomes shows learning evidence.

Your day:
- Morning: your words with example sentences.
- Midday: a quick drill; some days you write your own sentence.
- Evening: a short quiz.
Right answers push a word further out; it graduates once you have mastered it.
Send me any word or phrase any time to add it - commas or new lines for
several at once. Your own words always get top priority.

If you want focused practice:
- /practice notebook - free writing + native diff
- /practice diplomatic - softer workplace tone
- /translate_lab <topic> - RU->EN transfer repair
- /article <text> - critical reading and executive summary
- /scene <topic or number> - one of 40 business/IT scenario cards
- /practice mistakes - recurring mistakes
- /practice vocab - active chunks

If you upload material:
- Use #materials_upload / Materials Upload.
- Best paste: Context, Vocabulary/chunks, Grammar/patterns,
  Mistakes/teacher feedback, My examples.
- New learning items become active only after approval.

Seed library topics: B2/B2+ business/IT, English for Tech, pushback, incidents,
trade-offs, risks, tech debt, reports, reliability, postmortems, async updates,
exec summaries, alignment.

Useful commands:
/today - start daily practice; /today <n> shows n word cards
/words - your list and what is coming up
/more <word> - detailed card: meaning, synonyms, collocations
/learned <word> - mark as mastered
/delete <word> - remove a word
/pause and /resume - daily messages off and on
/baseline [answer] - show or save monthly baseline
/outcomes [full] - show 30-day learning outcomes
/library [query] - browse shared seed lessons
/subscribe <template_id> - copy a seed lesson into your base
/topics - browse knowledge areas
/lessons [query] - list your lessons
/lesson <id>|random|topic <query> - inspect or start lessons
/upload - upload lesson material
/approve <material_id> - approve extracted targets
/review - review due items
/feedback explain <attempt_id> - full teacher feedback
/reflect <text> - save a reflection note
/mentor - teacher question + Coach Journal
/brief <agenda> - meeting language
/scene <topic> - roleplay card
/stats - operational progress
/help or /howto - show this guide

Full docs:
- docs/user-guide.md: what the system can do and how lessons work
- docs/learning-methodology.md: learning loop and lesson types
- docs/lesson-catalog/index.md: public lesson catalog
- docs/learning-plans.md: first week, 30-day, and 12-week plans
- docs/material-upload-guide.md: simple upload examples"""


def start_message(channel_enabled: bool = False) -> str:
    where = (
        "Channel mode is enabled for practice posts."
        if channel_enabled
        else "Practice runs here."
    )
    return (
        f"FluentLoop is ready.\n{where}\n"
        "Send /library, /upload, /baseline, or /today."
    )


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
