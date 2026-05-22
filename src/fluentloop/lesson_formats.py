from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from fluentloop.db.models import LearningItem, MistakePattern
from fluentloop.format_analysis import critical_reading_card, vocabulary_lab_card
from fluentloop.operational_drills import (
    article_lab_modules,
    debate_card,
    fluency432_card,
    pre_meeting_brief_card,
    translation_lab_pack,
)


@dataclass(frozen=True)
class LessonFormat:
    mode: str
    title: str
    focus: str
    command: str


LESSON_FORMATS: tuple[LessonFormat, ...] = (
    LessonFormat("vocab", "Vocabulary Lab", "lexical chunks", "/practice vocab"),
    LessonFormat("grammar", "Grammar Lab", "grammar repair", "/practice grammar"),
    LessonFormat(
        "mistakes", "Mistake Drill 2.0", "recurring errors", "/practice mistakes"
    ),
    LessonFormat("writing", "Mini Writing", "short production", "/practice writing"),
    LessonFormat("review", "SRS Review", "due items", "/practice review"),
    LessonFormat("mixed", "Mixed Practice", "balanced micro-drills", "/practice mixed"),
    LessonFormat(
        "diplomatic",
        "Diplomatic Rewrite Drill",
        "pragmatic competence",
        "/practice diplomatic",
    ),
    LessonFormat("notebook", "Notebook", "free write + diff", "/practice notebook"),
    LessonFormat(
        "discourse", "Discourse Builder", "paragraph structure", "/practice discourse"
    ),
    LessonFormat(
        "reading", "Critical Reading Club", "argument analysis", "/practice reading"
    ),
    LessonFormat(
        "genre", "Genre Curriculum", "work artifact schemas", "/practice genre"
    ),
    LessonFormat(
        "writing_workshop",
        "Writing Workshop",
        "outline-draft-revision",
        "/practice writing_workshop",
    ),
)

PRACTICE_MODE_ALIASES: dict[str, str] = {
    "mistake_focus": "mistakes",
    "translation_lab": "diplomatic",
    "translate_lab": "diplomatic",
}


GENRE_SPECS: tuple[dict[str, str], ...] = (
    {
        "name": "incident_post_mortem",
        "schema": "Timeline -> Impact -> Root cause -> Remediation -> Prevention",
        "target": "passive voice, past perfect, hedged conclusions",
    },
    {
        "name": "rfc_decision_memo",
        "schema": "Problem -> Constraints -> Options -> Trade-offs -> Recommendation",
        "target": "comparatives, probability modals, signposting",
    },
    {
        "name": "standup_update",
        "schema": "Done -> Doing -> Blockers",
        "target": "present simple, present continuous, concise blockers",
    },
    {
        "name": "architecture_proposal",
        "schema": "Context -> Proposal -> Alternatives -> Risks -> Migration plan",
        "target": "hedging, future perfect, conditionals",
    },
    {
        "name": "performance_review_give",
        "schema": "Strengths -> Growth areas -> Examples -> Goals",
        "target": "indirect feedback and mitigated negatives",
    },
    {
        "name": "performance_review_receive",
        "schema": "Acknowledge -> Clarify -> Reflect -> Commit",
        "target": "active listening markers and hedged response",
    },
    {
        "name": "customer_escalation_response",
        "schema": "Acknowledge -> Investigate -> Action -> Prevent",
        "target": "empathy markers and future-perfect commitments",
    },
    {
        "name": "cold_outreach_email",
        "schema": "Context -> Reason -> Ask -> Soft close",
        "target": "softened modal questions",
    },
    {
        "name": "technical_blog_post",
        "schema": "Hook -> Problem -> Solution -> Trade-offs -> Conclusion",
        "target": "formal connectives and hedged claims",
    },
    {
        "name": "conference_talk_qa",
        "schema": "Acknowledge -> Rephrase -> Answer -> Bridge",
        "target": "thinking-time fillers and concise bridging",
    },
)

_SCENARIO_TITLES = (
    "Design review - defend choice A vs B",
    "Code review feedback - receive criticism gracefully",
    "Code review feedback - give criticism diplomatically",
    "RFC discussion in Slack threading",
    "Incident post-mortem facilitation",
    "Architecture migration proposal",
    "Tech-debt prioritization debate",
    "Scope renegotiation with PM",
    "Estimation pushback",
    "Cross-team dependency negotiation",
    "Customer demo opening and Q&A",
    "Customer escalation absorb and de-escalate",
    "Vendor pricing pushback",
    "Vendor SLA negotiation",
    "Discovery call",
    "Bad news to customer",
    "Sales hand-off conversation",
    "Reference call",
    "1:1 mentoring conversation",
    "Performance review - giving",
    "Performance review - receiving",
    "Salary negotiation",
    "Promotion case presentation",
    "Resignation conversation",
    "Hiring interview - interviewer",
    "Hiring interview - candidate",
    "Standup update",
    "Quarterly all-hands speech",
    "Board update on engineering velocity",
    "Tech blog post draft",
    "Investor demo",
    "Conference talk Q&A handling",
    "Disagree with senior architect publicly",
    "Tell teammate they are underperforming",
    "Push back on micromanagement gently",
    "Decline scope creep",
    "Apologize for production outage",
    "Diplomatic refusal of impossible deadline",
    "Ask for help when you should know",
    "Admit I do not know without losing face",
)


def normalize_practice_mode(mode: str) -> str:
    normalized = mode.strip().lower().replace("-", "_")
    return PRACTICE_MODE_ALIASES.get(normalized, normalized)


def format_for_mode(mode: str) -> LessonFormat | None:
    normalized = normalize_practice_mode(mode)
    return next((item for item in LESSON_FORMATS if item.mode == normalized), None)


def practice_modes_help() -> str:
    lines = ["Practice modes"]
    for item in LESSON_FORMATS:
        lines.append(f"{item.command} - {item.title}: {item.focus}")
    return "\n".join(lines)


def scenario_cards() -> list[dict[str, Any]]:
    cards: list[dict[str, Any]] = []
    for index, title in enumerate(_SCENARIO_TITLES, start=1):
        cards.append(
            {
                "id": f"scenario_{index:02d}",
                "setting": title,
                "my_role": "FluentLoop learner in a senior IT/business context",
                "partner_role": "realistic stakeholder",
                "tasks": [
                    "acknowledge the other side",
                    "state the constraint clearly",
                    "land on a concrete next step",
                ],
                "pdi": {"power": "mixed", "distance": "medium", "imposition": "medium"},
                "target_chunks": [
                    "I might be missing something, but...",
                    "One constraint we should account for is...",
                    "Could we align on the next step?",
                ],
                "common_l1_traps": ["over-direct pushback", "insufficient hedging"],
            }
        )
    return cards


def apply_lesson_format(
    mode: str,
    exercises: list[dict[str, Any]],
    items: list[LearningItem],
    patterns: list[MistakePattern],
) -> list[dict[str, Any]]:
    lesson_format = format_for_mode(mode)
    if lesson_format is None:
        return exercises
    for exercise in exercises:
        metadata = exercise.get("metadata")
        if not isinstance(metadata, dict):
            metadata = {}
            exercise["metadata"] = metadata
        metadata["lesson_format"] = lesson_format.mode
        metadata["format_title"] = lesson_format.title
        exercise["lesson_format"] = lesson_format.mode
        exercise["format_title"] = lesson_format.title

    if lesson_format.mode == "vocab":
        card = vocabulary_lab_card(items)
        _set_prompt(
            exercises,
            0,
            "Vocabulary Lab: field / register / function.",
            card["prompt"],
            "Use metadata groupings to turn passive chunks into productive language.",
        )
        if exercises:
            exercises[0]["metadata"]["vocabulary_lab"] = card
    elif lesson_format.mode == "diplomatic":
        _set_prompt(
            exercises,
            0,
            "Diplomatic rewrite: make a blunt message more professional.",
            'Rewrite: "Your plan is unrealistic and will break production."',
            "Use hedging and indirect disagreement.",
        )
    elif lesson_format.mode == "notebook":
        _set_prompt(
            exercises,
            0,
            "Notebook free write: describe a real technical conversation.",
            "Write 4-5 sentences. The feedback will separate errors from native style.",
            "Keep it concrete; mention one stakeholder and one constraint.",
        )
    elif lesson_format.mode == "discourse":
        _set_prompt(
            exercises,
            0,
            "Discourse Builder: create a four-sentence argument.",
            "Topic -> support -> counterpoint -> recommendation.",
            "Use at least one signpost such as however or therefore.",
        )
    elif lesson_format.mode == "reading":
        card = critical_reading_card("")
        _set_prompt(
            exercises,
            0,
            "Critical Reading Club: analyze the author's argument.",
            card["prompt"],
            "Focus on argumentation, not comprehension only.",
        )
        if exercises:
            exercises[0]["metadata"]["critical_reading"] = card
    elif lesson_format.mode == "genre":
        genre = GENRE_SPECS[0]
        _set_prompt(
            exercises,
            0,
            f"Genre practice: {genre['name']}.",
            f"Draft the stages: {genre['schema']}.",
            genre["target"],
        )
    elif lesson_format.mode == "writing_workshop":
        _set_prompt(
            exercises,
            0,
            "Writing Workshop: outline first, draft later.",
            "Write a 3-5 bullet outline for a proposal to stakeholders.",
            "Do not write the full text yet; plan the structure.",
        )
        _set_prompt(
            exercises,
            1,
            "Writing Workshop: draft.",
            "Turn the outline into 120-160 words. Keep one clear ask.",
            "Use the outline; do not add a new argument halfway through.",
        )
        _set_prompt(
            exercises,
            2,
            "Writing Workshop: revision.",
            "Revise for reader impact: shorter opening, clearer trade-off, softer ask.",
            "Cut one vague sentence and add one concrete owner/date.",
        )
    elif lesson_format.mode == "mistakes" and patterns:
        first = patterns[0]
        _set_prompt(
            exercises,
            0,
            "Mistake Drill 2.0: repair a recurring pattern.",
            first.description,
            "Explain the cause before writing the corrected version.",
        )
    return exercises


def _set_prompt(
    exercises: list[dict[str, Any]],
    index: int,
    title: str,
    prompt: str,
    hint: str,
) -> None:
    if len(exercises) <= index:
        return
    exercise = exercises[index]
    exercise["prompt"] = f"{title}\n{prompt}"
    exercise["hint"] = hint
    metadata = exercise.get("metadata")
    if isinstance(metadata, dict):
        metadata["target_skill"] = title.split(":", 1)[0].lower().replace(" ", "_")


def pre_meeting_brief(agenda: str) -> str:
    card = pre_meeting_brief_card(agenda)
    chunks = "; ".join(card["chunks"])
    moves = "; ".join(card["moves"])
    traps = "; ".join(card["l1_traps"])
    return (
        f"Pre-meeting brief: {card['topic']}\n"
        f"Chunks: {chunks}\n"
        f"Moves: {moves}\n"
        f"L1 traps: {traps}\n"
        "Hedging: I might be missing something; my read is; one concern is."
    )


def mentor_question() -> str:
    return (
        "Mentor's Question\n"
        "What was the hardest English moment at work this week, and what did you "
        "simplify because you did not have the language yet?"
    )


def scene_builder(payload: str) -> str:
    cards = scenario_cards()
    selected = cards[0]
    query = payload.strip()
    if query:
        normalized = query.lower().replace("#", "").replace("scenario_", "")
        if normalized.isdigit():
            index = int(normalized) - 1
            if 0 <= index < len(cards):
                selected = cards[index]
        elif any(card["id"] == query for card in cards):
            selected = next(card for card in cards if card["id"] == query)
        else:
            selected = {
                **selected,
                "setting": payload,
            }
    if query and selected is cards[0] and query not in {"1", "01", "scenario_01"}:
        selected = {
            **selected,
            "setting": payload,
        }
    tasks = "; ".join(selected["tasks"])
    chunks = "; ".join(selected["target_chunks"])
    return (
        f"Scene Builder: {selected['setting']}\n"
        f"Your role: {selected['my_role']}\n"
        f"Partner: {selected['partner_role']}\n"
        f"Tasks: {tasks}\n"
        f"Target chunks: {chunks}"
    )


def article_lab_prompt(text: str) -> str:
    source = text.strip() or "paste an article after /article"
    reading = critical_reading_card(source)
    tasks = "\n".join(f"- {task}" for task in reading["tasks"])
    modules = "\n".join(
        f"- {module['name']}: {module['task']}"
        for module in article_lab_modules(source)
    )
    return (
        "Article Lab v1\n"
        "Modules:\n"
        f"{modules}\n"
        "Critical reading tasks:\n"
        f"{tasks}\n"
        f"Source: {source[:500]}"
    )


def debate_prompt(topic: str) -> str:
    card = debate_card(topic)
    axes = "; ".join(card["score_axes"])
    return (
        f"Debate Mode: {card['topic']}\n"
        f"Your task: {card['learner_task']}\n"
        f"Bot role: {card['bot_role']}.\n"
        f"Score axes: {axes}."
    )


def translation_lab_prompt(topic: str) -> str:
    pack = translation_lab_pack(topic)
    sentences = "\n".join(f"- {sentence}" for sentence in pack["sentences_ru"])
    focus = "; ".join(pack["l1_focus"])
    return (
        f"Translation Lab: {pack['topic']}\n"
        f"{sentences}\n"
        f"L1 focus: {focus}."
    )


def fluency432_prompt(topic: str) -> str:
    card = fluency432_card(topic)
    rounds = "\n".join(
        f"- {round_['minutes']} min: {round_['goal']}"
        for round_ in card["rounds"]
    )
    return (
        f"4-3-2 Fluency: {card['topic']}\n"
        f"{rounds}\n"
        f"Success: {card['success']}."
    )
