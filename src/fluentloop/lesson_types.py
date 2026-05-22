from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass

from fluentloop.db.models import LearningItem, LessonPlan
from fluentloop.exercises import EXERCISE_TYPES
from fluentloop.lesson_formats import LESSON_FORMATS, normalize_practice_mode


@dataclass(frozen=True)
class LessonType:
    key: str
    title: str
    goal: str
    when_to_use: str
    commands: tuple[str, ...]
    expected_item_types: tuple[str, ...]
    typical_exercise_types: tuple[str, ...]
    metrics: tuple[str, ...]
    recommended_next_modes: tuple[str, ...]
    practice_modes: tuple[str, ...] = ()
    plan_formats: tuple[str, ...] = ()


LESSON_TYPES: tuple[LessonType, ...] = (
    LessonType(
        "vocabulary",
        "Vocabulary",
        "Learn useful terms and convert them into recallable language.",
        "Use when you meet new standalone words or tech terms.",
        ("/practice vocab", "/review"),
        ("word", "expression"),
        ("guess", "translate", "word_family", "noticing"),
        ("active vocabulary", "review accuracy"),
        ("/practice vocab", "/today"),
        ("vocab",),
    ),
    LessonType(
        "chunks",
        "Chunks and Collocations",
        (
            "Turn phrases, collocations, and reusable workplace language into "
            "active production."
        ),
        "Use when you want to sound less translated and reuse ready-made English.",
        ("/practice vocab", "/practice notebook", "/today"),
        ("chunk", "expression", "word"),
        ("cloze", "collocation_drill", "chunk_builder", "mini_writing"),
        ("productive chunks", "reuse count"),
        ("/practice notebook", "/practice vocab"),
        ("vocab", "notebook"),
    ),
    LessonType(
        "grammar",
        "Grammar",
        "Repair grammar patterns that block clear business/IT communication.",
        "Use when the issue is form, tense, articles, prepositions, or sentence shape.",
        ("/practice grammar", "/practice mistakes"),
        ("grammar_rule", "mistake_pattern"),
        (
            "grammar_rewrite",
            "error_correction",
            "sentence_transform",
            "register_choice",
        ),
        ("grammar accuracy", "repeat errors"),
        ("/practice grammar", "/review"),
        ("grammar",),
    ),
    LessonType(
        "mistakes",
        "Mistake Repair",
        "Extinguish recurring mistakes and Russian-transfer traps.",
        "Use when the same error keeps coming back or confidence is low.",
        ("/practice mistakes", "/review"),
        ("mistake_pattern", "grammar_rule"),
        ("error_correction", "collocation_drill", "grammar_rewrite"),
        ("mistake extinction", "L1 density"),
        ("/practice mistakes", "/translate_lab"),
        ("mistakes", "mistake_focus"),
    ),
    LessonType(
        "diplomatic",
        "Diplomatic Workplace English",
        "Make pushback, disagreement, feedback, and risk language firm but natural.",
        "Use for stakeholder communication, negotiation, feedback, and workplace tone.",
        ("/practice diplomatic", "/translate_lab", "/scene"),
        ("expression", "grammar_rule", "mistake_pattern", "chunk"),
        ("register_choice", "grammar_rewrite", "mini_writing"),
        ("hedging density", "L1 density"),
        ("/practice diplomatic", "/scene"),
        ("diplomatic", "translate_lab", "translation_lab"),
    ),
    LessonType(
        "notebook",
        "Notebook",
        "Generate real free writing for native-diff, chunk mining, and L1 checks.",
        "Use when the system needs fresh production data from you.",
        ("/practice notebook", "/reflect"),
        ("chunk", "expression", "grammar_rule"),
        ("mini_writing", "follow_up", "noticing"),
        ("word count", "lexical diversity", "mined chunks"),
        ("/practice notebook", "/outcomes full"),
        ("notebook",),
    ),
    LessonType(
        "reading",
        "Critical Reading",
        (
            "Read articles or arguments and produce claim, assumption, and "
            "summary outputs."
        ),
        "Use for articles, blog posts, product docs, and executive summaries.",
        ("/article <text>", "/practice reading"),
        ("expression", "chunk", "grammar_rule"),
        ("noticing", "mini_writing", "follow_up"),
        ("reading events", "summary quality"),
        ("/article <text>", "/practice reading"),
        ("reading",),
    ),
    LessonType(
        "writing",
        "Writing",
        "Draft workplace artifacts with clear structure, tone, and reusable chunks.",
        "Use for updates, emails, reports, reviews, resumes, and written answers.",
        (
            "/practice writing",
            "/practice discourse",
            "/practice writing_workshop",
            "/baseline",
        ),
        ("chunk", "expression", "grammar_rule"),
        ("mini_writing", "follow_up", "sentence_transform"),
        ("writing metrics", "hedging density"),
        ("/practice writing", "/practice notebook"),
        ("writing", "discourse", "writing_workshop", "sprint"),
    ),
    LessonType(
        "genre",
        "Genre Curriculum",
        "Practice the structure of recurring work artifacts.",
        "Use when the hard part is not one phrase, but the whole document shape.",
        ("/practice genre",),
        ("chunk", "expression", "grammar_rule"),
        ("noticing", "chunk_builder", "mini_writing"),
        ("genre coverage", "artifact completion"),
        ("/practice genre", "/practice writing_workshop"),
        ("genre",),
        ("genre",),
    ),
    LessonType(
        "scenario",
        "Scenario / Roleplay",
        (
            "Rehearse a realistic business/IT situation with tasks, roles, "
            "and target chunks."
        ),
        "Use before meetings, interviews, negotiation, or difficult conversations.",
        ("/scene <topic or number>", "/brief <agenda>"),
        ("chunk", "expression", "mistake_pattern"),
        ("register_choice", "mini_writing", "follow_up"),
        ("scenario coverage", "tone/L1 repair"),
        ("/scene", "/practice diplomatic"),
        ("scene",),
    ),
    LessonType(
        "review",
        "Review / SRS",
        "Bring due and weak items back until they are easy to recall.",
        "Use when retention is low or `/outcomes` says sample size is thin.",
        ("/review", "/today", "/practice review"),
        ("word", "expression", "chunk", "grammar_rule", "mistake_pattern"),
        ("active_recall", "cloze", "guess", "error_correction"),
        ("held-out retention", "review accuracy"),
        ("/today", "/review"),
        ("review",),
    ),
    LessonType(
        "mixed",
        "Mixed Lesson",
        "Combine vocabulary, chunks, grammar, writing, and recall in one lesson.",
        "Use for textbook lessons, seed lessons, and broad workplace topics.",
        ("/today", "/lesson <id>", "/practice mixed"),
        ("word", "expression", "chunk", "grammar_rule", "mistake_pattern"),
        ("noticing", "cloze", "grammar_rewrite", "mini_writing", "active_recall"),
        ("attempts", "retention", "productive chunks"),
        ("/today", "/outcomes full"),
        ("mixed", "lesson"),
        ("lesson", "tech_textbook"),
    ),
    LessonType(
        "outcomes",
        "Outcomes",
        "Measure learning quality and choose the next training loop.",
        "Use weekly or monthly to decide what to train next.",
        ("/baseline", "/outcomes", "/outcomes full", "/mentor"),
        (),
        (),
        ("retention", "productive chunks", "L1 density", "mistake extinction"),
        ("/today", "/practice notebook", "/practice diplomatic"),
    ),
)

LESSON_TYPES_BY_KEY = {item.key: item for item in LESSON_TYPES}

_FORMAT_TO_TYPE = {
    plan_format: item.key for item in LESSON_TYPES for plan_format in item.plan_formats
}
_MODE_TO_TYPE = {
    mode: item.key for item in LESSON_TYPES for mode in (*item.practice_modes, item.key)
}


def lesson_type_by_key(key: str) -> LessonType:
    return LESSON_TYPES_BY_KEY.get(key, LESSON_TYPES_BY_KEY["mixed"])


def lesson_type_for_practice_mode(mode: str) -> LessonType:
    normalized = normalize_practice_mode(mode)
    return lesson_type_by_key(_MODE_TO_TYPE.get(normalized, normalized))


def lesson_type_for_format(format_value: str | None) -> LessonType:
    if not format_value:
        return LESSON_TYPES_BY_KEY["mixed"]
    normalized = format_value.strip().lower()
    return lesson_type_by_key(_FORMAT_TO_TYPE.get(normalized, normalized))


def lesson_type_for_exercise_type(exercise_type: str) -> LessonType:
    exercise = EXERCISE_TYPES.get(exercise_type)
    if exercise is None:
        return LESSON_TYPES_BY_KEY["mixed"]
    for mode in exercise.mode_tags:
        mapped = lesson_type_for_practice_mode(mode)
        if mapped.key != "mixed":
            return mapped
    return LESSON_TYPES_BY_KEY["mixed"]


def lesson_type_for_plan(
    plan: LessonPlan, items: Iterable[LearningItem] | None = None
) -> LessonType:
    format_type = lesson_type_for_format(getattr(plan, "format", None))
    if format_type.key != "mixed":
        return format_type

    text = " ".join(
        [
            plan.title or "",
            plan.topic or "",
            plan.goal or "",
            " ".join(plan.language_focus_json or []),
            " ".join(plan.tags_json or []),
        ]
    ).casefold()
    if any(token in text for token in ("pushback", "disagree", "negotiat", "feedback")):
        return LESSON_TYPES_BY_KEY["diplomatic"]
    if any(token in text for token in ("reading", "article", "summary", "claim")):
        return LESSON_TYPES_BY_KEY["reading"]
    if any(token in text for token in ("resume", "interview", "email", "writing")):
        return LESSON_TYPES_BY_KEY["writing"]
    if any(token in text for token in ("grammar", "articles", "conditionals", "tense")):
        return LESSON_TYPES_BY_KEY["grammar"]

    counts = target_mix(items or [])
    if counts["mistake_pattern"]:
        return LESSON_TYPES_BY_KEY["mistakes"]
    if counts["grammar_rule"] > counts["word"] + counts["expression"] + counts["chunk"]:
        return LESSON_TYPES_BY_KEY["grammar"]
    if counts["chunk"] > 0:
        return LESSON_TYPES_BY_KEY["chunks"]
    if counts["word"] or counts["expression"]:
        return LESSON_TYPES_BY_KEY["vocabulary"]
    return LESSON_TYPES_BY_KEY["mixed"]


def target_mix(items: Iterable[LearningItem]) -> Counter[str]:
    counter: Counter[str] = Counter()
    for item in items:
        counter[item.type] += 1
    return counter


def format_target_mix(items: Iterable[LearningItem]) -> str:
    counts = target_mix(items)
    labels = [
        ("word", "words"),
        ("expression", "expressions"),
        ("chunk", "chunks"),
        ("grammar_rule", "grammar"),
        ("mistake_pattern", "mistakes"),
    ]
    parts = [f"{counts[key]} {label}" for key, label in labels if counts[key]]
    return ", ".join(parts) if parts else "no active targets"


def lesson_type_markdown_table() -> str:
    lines = [
        "| Type | What it trains | Commands | Evidence |",
        "|---|---|---|---|",
    ]
    for item in LESSON_TYPES:
        lines.append(
            "| "
            f"`{item.key}` | {item.goal} | {', '.join(item.commands)} | "
            f"{', '.join(item.metrics) or '-'} |"
        )
    return "\n".join(lines)


def practice_modes_missing_type() -> set[str]:
    known = {normalize_practice_mode(item.mode) for item in LESSON_FORMATS}
    mapped = set(_MODE_TO_TYPE)
    return {
        mode
        for mode in known
        if mode not in mapped and mode not in LESSON_TYPES_BY_KEY
    }
