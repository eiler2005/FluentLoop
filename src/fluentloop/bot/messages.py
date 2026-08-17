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
- /today asks whether you want words or a lesson.
- Feedback has layers: Errors, Native, Why.
- SRS, confidence, L1 traps, and mistake patterns decide what comes back.
- /stats shows activity; /outcomes shows learning evidence.

Your day - the bot writes to you three times, each under a minute:

  Morning 08:00   Your words for today. Each one shows an example sentence
                  and a short definition.
  Midday  13:00   One quick drill. Tap "Answer" and reply with a message.
                  Roughly every third day it asks you to write 2-3 sentences
                  of your own; otherwise it is a gap-fill or a translation.
  Evening 19:00   A four-option quiz. Tap an option. You then see whether it
                  was right, what the answer means, and what the other three
                  options meant, so the ones you rejected stick too.

Prompts are in English. Russian appears only after you answer.
Right answers push a word further out: 5 seconds, then minutes, hours, days.
Once a word survives a 120-day gap it graduates and leaves the rotation.

Adding your own words - just send them, no command needed:
  cut corners, push back on, roll out
Commas or new lines for several at once. Your own words always come first.

Not sure what to start? Send /today - it asks which of the two you want:

  Words   ~2 min   the vocabulary track, below
  Lesson  ~15 min  a structured session from your lesson plans

The cards and the vocabulary lessons train the SAME words - they differ only
in how hard they make you work:

  /cards            shows cards. Passive: you read, nothing is asked.
  /review           drills the words that are due right now - the ones this
                    morning's cards showed. Start here to practise them.
  /practice vocab   a full vocabulary lesson built around those words:
                    collocations, paraphrase, cloze, reverse translation.

Daily-loop commands:
  /cards 5          show 5 cards right now, without waiting for the morning
  /words            your list, what is coming up, how many graduated
  /more <word>      full card: meaning, synonyms, collocations, examples
  /learned <word>   mark as mastered (with an Undo button)
  /delete <word>    remove a word (also undoable)
  /pause /resume    stop and restart the three daily messages
  /setup            redo the wizard: topics, vocabulary kinds, pace
  /settings         change slot times and words per day

/today 5 still works as a shortcut for /cards 5.

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
/today - choose: word cards or the full lesson
/cards [n] - show word cards right now
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
        f"FluentLoop is ready.\n{where}\n\n"
        "Three short messages a day: words at 08:00, a drill at 13:00, "
        "a quiz at 19:00. /pause stops them.\n"
        "Send me any word or phrase to add it.\n\n"
        "To practise now: /review for the words that are due, "
        "/practice vocab for a vocabulary lesson, /today for the full "
        "15-minute session.\n"
        "/help explains everything."
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
