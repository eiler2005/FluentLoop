from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from fluentloop.ai_exercises import enhance_staged_exercises_with_ai
from fluentloop.db.models import (
    GrammarConcept,
    LearningItem,
    MistakePattern,
    ReviewState,
    User,
)
from fluentloop.exercises import Exercise, render_for_item
from fluentloop.grammar import select_focus_concept
from fluentloop.learning import active_items
from fluentloop.lesson_director import decide_lesson_format
from fluentloop.lesson_formats import apply_lesson_format, normalize_practice_mode
from fluentloop.lesson_plans import (
    available_lesson_plan,
    lesson_items,
    lesson_steps,
)
from fluentloop.material_context import build_material_context
from fluentloop.srs import get_due_items

DEFAULT_MICRO_DRILL_COUNT = 16
SESSION_STAGES = (
    "warmup",
    "input",
    "input",
    "controlled_practice",
    "controlled_practice",
    "controlled_practice",
    "controlled_practice",
    "controlled_practice",
    "controlled_practice",
    "controlled_practice",
    "grammar_or_mistake_focus",
    "grammar_or_mistake_focus",
    "grammar_or_mistake_focus",
    "free_production",
    "recap",
    "recap",
)

BUSINESS_TAGS = {
    "architecture",
    "business",
    "collocation",
    "incident",
    "it",
    "meeting",
    "meetings",
    "planning",
    "product",
    "pushback",
    "recommendations",
    "risk",
    "stakeholder",
    "stakeholders",
    "status-update",
    "tradeoffs",
}


@dataclass(frozen=True)
class ScoredLearningItem:
    item: LearningItem
    score: int
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class TopicGoal:
    topic: str
    lesson_goal: str


def _current(now: datetime | None = None) -> datetime:
    return now or datetime.now(UTC)


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _active_patterns(
    session: Session, user_id: int, *, limit: int = 5
) -> list[MistakePattern]:
    return list(
        session.scalars(
            select(MistakePattern)
            .where(MistakePattern.user_id == user_id, MistakePattern.status == "active")
            .order_by(
                MistakePattern.confidence.desc(),
                MistakePattern.event_count.desc(),
                MistakePattern.created_at.desc(),
            )
            .limit(limit)
        )
    )


def choose_session_mode(
    session: Session, user: User, *, now: datetime | None = None
) -> str:
    if available_lesson_plan(session, user) is not None:
        return "lesson"
    due_items = get_due_items(session, user.id, limit=20, now=_current(now))
    patterns = _active_patterns(session, user.id, limit=3)
    scored_items = [row.item for row in score_learning_items(session, user, now=now)]
    director = decide_lesson_format(
        due_items=due_items,
        scored_items=scored_items,
        patterns=patterns,
    )
    if director.mode == "mistakes":
        return "mistake_focus"
    if director.mode in {"review", "vocab", "genre"}:
        return director.mode

    clustered_source = session.execute(
        select(LearningItem.source_material_id, func.count())
        .where(
            LearningItem.user_id == user.id,
            LearningItem.status == "active",
            LearningItem.source_material_id.is_not(None),
        )
        .group_by(LearningItem.source_material_id)
        .order_by(func.count().desc())
        .limit(1)
    ).first()
    if clustered_source is not None and clustered_source[1] >= 3:
        return "lesson"
    return "mixed"


def _review_state(session: Session, item_id: int) -> ReviewState | None:
    return session.scalar(
        select(ReviewState).where(ReviewState.learning_item_id == item_id)
    )


def score_learning_items(
    session: Session,
    user: User,
    *,
    now: datetime | None = None,
    limit: int = 20,
) -> list[ScoredLearningItem]:
    current = _current(now)
    due_cutoff = current + timedelta(days=1)
    linked_pattern_item_ids = {
        pattern.linked_learning_item_id
        for pattern in _active_patterns(session, user.id, limit=20)
        if pattern.linked_learning_item_id is not None
    }
    scored: list[ScoredLearningItem] = []
    for item in active_items(session, user.id):
        state = _review_state(session, item.id)
        score = 0
        reasons: list[str] = []
        if state is not None and _as_utc(state.due_at) <= due_cutoff:
            score += 100
            reasons.append("due")
        if state is not None and (
            state.fail_count > state.success_count
            or state.last_result in {"Again", "Hard"}
        ):
            score += 50
            reasons.append("weak")
        if item.id in linked_pattern_item_ids:
            score += 40
            reasons.append("mistake_pattern")
        if item.is_favorite:
            score += 30
            reasons.append("favorite")
        if item.priority > 0:
            # Words the learner added themselves outrank seeded content.
            score += min(item.priority, 12) * 5
            reasons.append("user_added")
        recent_cutoff = current - timedelta(days=14)
        if (
            item.source_material_id is not None
            and _as_utc(item.created_at) >= recent_cutoff
        ):
            score += 25
            reasons.append("recent_material")
        tags = {tag.lower() for tag in item.tags or []}
        if tags & BUSINESS_TAGS:
            score += 15
            reasons.append("business_it")
        if item.type == "expression":
            score += 10
            reasons.append("expression")
        scored.append(
            ScoredLearningItem(item=item, score=score, reasons=tuple(reasons))
        )
    return sorted(
        scored,
        key=lambda row: (row.score, row.item.is_favorite, row.item.created_at),
        reverse=True,
    )[:limit]


def select_topic_and_goal(
    scored_items: list[ScoredLearningItem],
    patterns: list[MistakePattern] | None = None,
) -> TopicGoal:
    patterns = patterns or []
    all_text = " ".join(
        [
            *(item.item.text for item in scored_items[:5]),
            *(item.item.meaning or "" for item in scored_items[:5]),
            *(item.item.explanation or "" for item in scored_items[:5]),
            *(tag for item in scored_items[:5] for tag in (item.item.tags or [])),
            *(pattern.description for pattern in patterns[:2]),
            *(pattern.mistake_type for pattern in patterns[:2]),
        ]
    ).lower()
    if "introvert" in all_text or "extrovert" in all_text or "reported" in all_text:
        return TopicGoal(
            "Reported speech and workplace personality",
            "Report opinions and recommendations naturally in a workplace context.",
        )
    if "architecture" in all_text or "trade-off" in all_text or "tradeoff" in all_text:
        return TopicGoal(
            "Architecture trade-offs",
            "Compare options and explain risks diplomatically.",
        )
    if "incident" in all_text or "root cause" in all_text:
        return TopicGoal(
            "Incident and risk updates",
            "Explain status, impact, and next steps clearly.",
        )
    if "hedg" in all_text or "stakeholder" in all_text or "push back" in all_text:
        return TopicGoal(
            "Stakeholder communication",
            "Use diplomatic language to push back and recommend next steps.",
        )
    if scored_items:
        focus = scored_items[0].item.text
        return TopicGoal(
            "Business/IT communication",
            f"Use '{focus}' accurately in a short workplace exchange.",
        )
    return TopicGoal(
        "Business/IT communication",
        "Practice useful workplace language with active recall.",
    )


def compose_learning_session(
    session: Session,
    user: User,
    *,
    target_date: object | None = None,
    now: datetime | None = None,
    ai_gateway: object | None = None,
    mode_override: str | None = None,
    lesson_plan: object | None = None,
) -> list[dict[str, Any]]:
    plan = lesson_plan if lesson_plan is not None else None
    if plan is None and mode_override is None:
        plan = available_lesson_plan(session, user)
    mode = mode_override or (
        "lesson" if plan is not None else choose_session_mode(session, user, now=now)
    )
    mode = normalize_practice_mode(mode)
    scored_items = _scored_items_for_lesson_plan(session, plan)
    if not scored_items:
        scored_items = score_learning_items(session, user, now=now)
    scored_items = _filter_scored_items_for_mode(scored_items, mode)
    patterns = _active_patterns(session, user.id, limit=3)
    if plan is not None:
        topic_goal = TopicGoal(plan.topic, plan.goal)
    else:
        topic_goal = select_topic_and_goal(scored_items, patterns)
    material_context = []
    if plan is not None and plan.source_material_id is not None:
        material_context = build_material_context(
            session,
            user,
            f"{topic_goal.topic} {topic_goal.lesson_goal}",
            source_material_id=plan.source_material_id,
        )
    exercises = build_staged_exercises(
        session,
        user,
        mode=mode,
        topic=topic_goal.topic,
        lesson_goal=topic_goal.lesson_goal,
        scored_items=scored_items,
        patterns=patterns,
    )
    if plan is not None:
        exercises = _apply_lesson_plan_steps(session, plan, exercises)
    exercises = apply_lesson_format(
        mode,
        exercises,
        [row.item for row in scored_items],
        patterns,
    )
    if material_context:
        exercises = _apply_material_context(exercises, material_context)
    if ai_gateway is not None:
        exercises = enhance_staged_exercises_with_ai(ai_gateway, exercises)
    return exercises


def _filter_scored_items_for_mode(
    scored_items: list[ScoredLearningItem], mode: str
) -> list[ScoredLearningItem]:
    if mode in {"lesson", "mixed", "review"}:
        return scored_items
    allowed = {
        "vocab": {"word", "expression", "chunk"},
        "grammar": {"grammar_rule"},
        "mistakes": {"mistake_pattern"},
        "writing": {"word", "expression", "grammar_rule", "mistake_pattern", "chunk"},
        "mistake_focus": {"mistake_pattern"},
        "diplomatic": {
            "word",
            "expression",
            "mistake_pattern",
            "grammar_rule",
            "chunk",
        },
        "notebook": {"word", "expression", "mistake_pattern", "grammar_rule", "chunk"},
        "discourse": {"word", "expression", "grammar_rule", "chunk"},
        "reading": {"word", "expression", "grammar_rule", "chunk"},
        "genre": {"word", "expression", "grammar_rule", "mistake_pattern", "chunk"},
        "writing_workshop": {
            "word",
            "expression",
            "grammar_rule",
            "mistake_pattern",
            "chunk",
        },
        "sprint": {"word", "expression", "grammar_rule", "mistake_pattern", "chunk"},
    }.get(mode)
    if allowed is None:
        return scored_items
    filtered = [row for row in scored_items if row.item.type in allowed]
    return filtered or scored_items


def _scored_items_for_lesson_plan(
    session: Session, plan: object | None
) -> list[ScoredLearningItem]:
    if plan is None:
        return []
    scored: list[ScoredLearningItem] = []
    recent_ids = _recent_practiced_item_ids(session, getattr(plan, "user_id", 0))
    due_ids = {item.id for item in get_due_items(session, getattr(plan, "user_id", 0))}
    for index, item in enumerate(lesson_items(session, plan)):
        score = 180 - index
        reasons = ["lesson_plan", "teacher_priority"]
        if item.id in due_ids:
            score += 70
            reasons.append("due")
        if item.id in recent_ids:
            score -= 45
            reasons.append("recent_penalty")
        state = _review_state(session, item.id)
        if state is not None and state.review_count == 0:
            score += 25
            reasons.append("novelty")
        if item.type in {"grammar_rule", "mistake_pattern"}:
            score += 20
            reasons.append("grammar_balance")
        scored.append(
            ScoredLearningItem(item=item, score=score, reasons=tuple(reasons))
        )
    return sorted(scored, key=lambda row: row.score, reverse=True)


def _recent_practiced_item_ids(session: Session, user_id: int) -> set[int]:
    from fluentloop.db.models import PracticeAttempt, PracticeSession

    rows = session.execute(
        select(PracticeAttempt.target_learning_item_ids)
        .join(
            PracticeSession,
            PracticeSession.id == PracticeAttempt.practice_session_id,
        )
        .where(PracticeSession.user_id == user_id)
        .order_by(PracticeAttempt.created_at.desc())
        .limit(80)
    )
    ids: set[int] = set()
    for row in rows:
        ids.update(row[0] or [])
    return ids


def build_staged_exercises(
    session: Session,
    user: User,
    *,
    mode: str,
    topic: str,
    lesson_goal: str,
    scored_items: list[ScoredLearningItem],
    patterns: list[MistakePattern],
) -> list[dict[str, Any]]:
    selected = [row.item for row in scored_items]
    steps: list[dict[str, Any]] = [
        build_warmup_step(
            selected[:1], mode=mode, topic=topic, lesson_goal=lesson_goal
        ),
        *build_input_steps(
            selected[:2], mode=mode, topic=topic, lesson_goal=lesson_goal
        ),
        *build_controlled_practice_steps(
            selected, mode=mode, topic=topic, lesson_goal=lesson_goal
        ),
        *build_grammar_or_mistake_focus_steps(
            session,
            selected,
            patterns,
            mode=mode,
            topic=topic,
            lesson_goal=lesson_goal,
        ),
        build_free_production_step(
            selected, mode=mode, topic=topic, lesson_goal=lesson_goal
        ),
        build_recap_step(selected, mode=mode, topic=topic, lesson_goal=lesson_goal),
        build_recap_step(
            selected[4:], mode=mode, topic=topic, lesson_goal=lesson_goal, cold=True
        ),
    ]
    return _dedupe_target_ids(steps[: len(SESSION_STAGES)])


def build_warmup_step(
    items: list[LearningItem], *, mode: str, topic: str, lesson_goal: str
) -> dict[str, Any]:
    target_ids: list[int] = []
    target_hint = ""
    expected = "A concise workplace example."
    if items:
        target_ids = [items[0].id]
        target_hint = f" Try to use: {items[0].text}."
        expected = items[0].text
    exercise = Exercise(
        "follow_up",
        (
            f"Warm-up: in 1-2 sentences, where does {topic.lower()} "
            f"show up in your work?{target_hint}"
        ),
        expected,
        "Keep it specific and natural.",
        "Warm-up activates the topic before controlled practice.",
        target_ids,
    )
    return _with_metadata(
        exercise,
        stage="warmup",
        mode=mode,
        topic=topic,
        lesson_goal=lesson_goal,
        target_skill="activation",
    )


def build_input_steps(
    items: list[LearningItem], *, mode: str, topic: str, lesson_goal: str
) -> list[dict[str, Any]]:
    steps = []
    for index in range(2):
        item = items[index] if len(items) > index else None
        steps.append(
            build_input_step(
                [item] if item is not None else [],
                mode=mode,
                topic=topic,
                lesson_goal=lesson_goal,
            )
        )
    return steps


def build_input_step(
    items: list[LearningItem], *, mode: str, topic: str, lesson_goal: str
) -> dict[str, Any]:
    if items:
        item = items[0]
        meaning = item.meaning or item.explanation or "useful workplace language"
        example = item.examples[0] if item.examples else f"We need to use {item.text}."
        exercise = Exercise(
            "noticing",
            (
                f"Input: notice this language chunk.\n"
                f"{item.text} = {meaning}\n"
                f"Example: {example}\n"
                "Now write one similar sentence for your work."
            ),
            item.text,
            "Reuse the chunk, but change the situation.",
            item.explanation,
            [item.id],
        )
    else:
        exercise = Exercise(
            "noticing",
            (
                "Input: useful phrase for today: I would lean towards...\n"
                "Write one sentence using it for a project decision."
            ),
            "I would lean towards",
            "Use it to make a soft recommendation.",
            "Seed input appears only until enough learning items exist.",
            [],
        )
    return _with_metadata(
        exercise,
        stage="input",
        mode=mode,
        topic=topic,
        lesson_goal=lesson_goal,
        target_skill="input_noticing",
    )


def build_controlled_practice_steps(
    items: list[LearningItem], *, mode: str, topic: str, lesson_goal: str
) -> list[dict[str, Any]]:
    steps: list[dict[str, Any]] = []
    preferred = _preferred_cycle_for_mode(mode)
    for index in range(7):
        item = items[index + 1] if len(items) > index + 1 else None
        if item is None:
            exercise = _seed_controlled_practice(index)
        else:
            exercise_type = _preferred_type(item, preferred[index % len(preferred)])
            exercise = render_for_item(item, exercise_type)
        steps.append(
            _with_metadata(
                exercise,
                stage="controlled_practice",
                mode=mode,
                topic=topic,
                lesson_goal=lesson_goal,
                target_skill="accuracy",
            )
        )
    return steps


def build_grammar_or_mistake_focus_steps(
    session: Session,
    items: list[LearningItem],
    patterns: list[MistakePattern],
    *,
    mode: str,
    topic: str,
    lesson_goal: str,
) -> list[dict[str, Any]]:
    return [
        build_grammar_or_mistake_focus_step(
            session,
            items[index:],
            patterns[index:] or patterns,
            mode=mode,
            topic=topic,
            lesson_goal=lesson_goal,
        )
        for index in range(3)
    ]


def build_grammar_or_mistake_focus_step(
    session: Session,
    items: list[LearningItem],
    patterns: list[MistakePattern],
    *,
    mode: str,
    topic: str,
    lesson_goal: str,
) -> dict[str, Any]:
    if patterns:
        pattern = patterns[0]
        concept = select_focus_concept(session, items=items, patterns=patterns)
        wrong = (pattern.wrong_examples or ["We need align priorities before sprint."])[
            -1
        ]
        expected = (
            pattern.correct_examples
            or ["We need to align on priorities before the sprint."]
        )[-1]
        target_ids = (
            [pattern.linked_learning_item_id]
            if pattern.linked_learning_item_id is not None
            else []
        )
        exercise = Exercise(
            "error_correction",
            _mistake_focus_prompt(pattern, wrong, concept),
            expected,
            _concept_hint(concept) or "Use the recurring mistake pattern as your clue.",
            _concept_explanation(concept) or pattern.description,
            target_ids,
        )
    else:
        grammar_item = next(
            (
                item
                for item in items
                if item.type in {"grammar_rule", "mistake_pattern"}
            ),
            None,
        )
        if grammar_item is not None:
            exercise = render_for_item(grammar_item, "grammar_rewrite")
        else:
            concept = select_focus_concept(session, items=items, patterns=patterns)
            if concept is not None:
                exercise = Exercise(
                    "grammar_rewrite",
                    (
                        f"Grammar focus: {concept.title}.\n"
                        "Rewrite this more naturally for a stakeholder:\n"
                        '"We must change the plan now."'
                    ),
                    "We might need to adjust the plan soon.",
                    concept.description,
                    "Keep the explanation short and practical.",
                    [],
                )
            else:
                exercise = Exercise(
                    "grammar_rewrite",
                    (
                        "Grammar focus: hedging.\n"
                        'Rewrite more diplomatically: "We must change the plan now."'
                    ),
                    "We might need to adjust the plan soon.",
                    "Use might need to / it may be worth.",
                    "Seed grammar prompt appears only as fallback.",
                    [],
                )
    result = _with_metadata(
        exercise,
        stage="grammar_or_mistake_focus",
        mode=mode,
        topic=topic,
        lesson_goal=lesson_goal,
        target_skill="grammar_or_mistake_repair",
    )
    concept = select_focus_concept(session, items=items, patterns=patterns)
    if concept is not None:
        result["grammar_concept_id"] = concept.id
        metadata = result.get("metadata")
        if isinstance(metadata, dict):
            metadata["grammar_concept_id"] = concept.id
    return result


def build_free_production_step(
    items: list[LearningItem], *, mode: str, topic: str, lesson_goal: str
) -> dict[str, Any]:
    targets = items[:3]
    target_text = ", ".join(item.text for item in targets) or "I would lean towards"
    exercise = Exercise(
        "mini_writing",
        (
            f"Free production: write 3-4 sentences about {topic.lower()}.\n"
            f"Use at least two of these: {target_text}."
        ),
        target_text,
        "Make it sound like a real work message.",
        "Free production turns review items into active communication.",
        [item.id for item in targets],
    )
    return _with_metadata(
        exercise,
        stage="free_production",
        mode=mode,
        topic=topic,
        lesson_goal=lesson_goal,
        target_skill="free_production",
    )


def build_recap_step(
    items: list[LearningItem],
    *,
    mode: str,
    topic: str,
    lesson_goal: str,
    cold: bool = False,
) -> dict[str, Any]:
    targets = items[:4]
    target_text = ", ".join(item.text for item in targets) or "today's key phrases"
    prompt = (
        "Cold recall closer: without looking back, write one new workplace "
        f"sentence that uses the most useful language from {topic.lower()}."
        if cold
        else (
            "Recap: without looking back, write three things you want to remember "
            f"from today's practice. Include: {target_text}."
        )
    )
    exercise = Exercise(
        "active_recall",
        prompt,
        target_text,
        "Use active recall; do not just copy a previous answer.",
        "Recap asks for active recall to strengthen retention.",
        [item.id for item in targets],
    )
    return _with_metadata(
        exercise,
        stage="recap",
        mode=mode,
        topic=topic,
        lesson_goal=lesson_goal,
        target_skill="active_recall",
    )


def _preferred_type(item: LearningItem, fallback: str) -> str:
    if item.type in {"grammar_rule", "mistake_pattern"}:
        if fallback in {"error_correction", "register_choice", "sentence_transform"}:
            return fallback
        return "grammar_rewrite"
    return fallback


def _preferred_cycle_for_mode(mode: str) -> tuple[str, ...]:
    if mode == "vocab":
        return (
            "cloze",
            "translate",
            "guess",
            "chunk_builder",
            "collocation_drill",
            "word_family",
            "active_recall",
        )
    if mode in {"grammar", "mistakes", "mistake_focus"}:
        return (
            "grammar_rewrite",
            "error_correction",
            "sentence_transform",
            "register_choice",
            "cloze",
            "collocation_drill",
            "active_recall",
        )
    if mode == "writing":
        return (
            "chunk_builder",
            "sentence_transform",
            "register_choice",
            "mini_writing",
            "follow_up",
            "grammar_rewrite",
            "active_recall",
        )
    if mode == "diplomatic":
        return (
            "register_choice",
            "grammar_rewrite",
            "sentence_transform",
            "follow_up",
            "active_recall",
        )
    if mode == "notebook":
        return (
            "mini_writing",
            "sentence_transform",
            "collocation_drill",
            "grammar_rewrite",
            "active_recall",
        )
    if mode == "discourse":
        return (
            "sentence_transform",
            "chunk_builder",
            "register_choice",
            "mini_writing",
            "active_recall",
        )
    if mode == "reading":
        return (
            "noticing",
            "cloze",
            "collocation_drill",
            "follow_up",
            "active_recall",
        )
    if mode in {"genre", "writing_workshop", "sprint"}:
        return (
            "mini_writing",
            "sentence_transform",
            "register_choice",
            "grammar_rewrite",
            "active_recall",
        )
    return (
        "cloze",
        "translate",
        "guess",
        "chunk_builder",
        "collocation_drill",
        "sentence_transform",
        "cloze",
    )


def _seed_controlled_practice(index: int) -> Exercise:
    if index == 0:
        return Exercise(
            "cloze",
            "Fill the gap:\nWe need to ____ on the priorities before the sprint.",
            "align",
            "One word.",
            "Seed controlled practice appears only until enough items exist.",
            [],
        )
    return Exercise(
        "translate",
        '"Я бы хотел мягко возразить против этого таймлайна."',
        "I'd like to push back on this timeline a bit.",
        "Use a diplomatic meeting phrase.",
        "Seed translation prompt appears only until enough items exist.",
        [],
    )


def _mistake_focus_prompt(
    pattern: MistakePattern, wrong: str, concept: GrammarConcept | None
) -> str:
    if concept is None:
        return f'Fix this recurring {pattern.mistake_type} issue:\n"{wrong}"'
    return (
        f"Grammar focus: {concept.title}.\n"
        f"{concept.description}\n"
        f'Fix this recurring {pattern.mistake_type} issue:\n"{wrong}"'
    )


def _concept_hint(concept: GrammarConcept | None) -> str:
    if concept is None:
        return ""
    if concept.examples:
        return concept.examples[0]
    return concept.description


def _concept_explanation(concept: GrammarConcept | None) -> str:
    if concept is None:
        return ""
    return concept.description


def _with_metadata(
    exercise: Exercise,
    *,
    stage: str,
    mode: str,
    topic: str,
    lesson_goal: str,
    target_skill: str,
) -> dict[str, Any]:
    target_ids = list(exercise.target_learning_item_ids)
    metadata: dict[str, Any] = {
        "stage": stage,
        "mode": mode,
        "topic": topic,
        "lesson_goal": lesson_goal,
        "target_skill": target_skill,
        "target_item_ids": target_ids,
        "why_now": "teacher priority + due review + new material rotation",
    }
    data = {
        **exercise.as_dict(),
        "metadata": metadata,
        **metadata,
        "target_learning_item_ids": target_ids,
    }
    return data


def _dedupe_target_ids(steps: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[int] = set()
    for step in steps:
        original = list(step.get("target_learning_item_ids", []))
        target_ids = [item_id for item_id in original if item_id not in seen]
        seen.update(target_ids)
        step["target_learning_item_ids"] = target_ids
        step["target_item_ids"] = target_ids
        metadata = step.get("metadata")
        if isinstance(metadata, dict):
            metadata["target_item_ids"] = target_ids
    return steps


def _apply_lesson_plan_steps(
    session: Session, plan: object, exercises: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    steps = lesson_steps(session, plan)
    steps_by_type = {step.step_type: step for step in steps}
    default_step = steps[0] if steps else None
    instructed: set[str] = set()
    for exercise in exercises:
        stage = str(exercise.get("stage", ""))
        step = steps_by_type.get(stage) or default_step
        if step is None:
            continue
        exercise["stage"] = step.step_type
        exercise["lesson_plan_id"] = step.lesson_plan_id
        exercise["lesson_step_id"] = step.id
        metadata = exercise.get("metadata")
        if isinstance(metadata, dict):
            metadata["stage"] = step.step_type
            metadata["lesson_plan_id"] = step.lesson_plan_id
            metadata["lesson_step_id"] = step.id
            metadata["lesson_plan_title"] = getattr(plan, "title", "")
            metadata["lesson_language_focus"] = getattr(plan, "language_focus_json", [])
            metadata["lesson_tags"] = getattr(plan, "tags_json", [])
        exercise["lesson_plan_title"] = getattr(plan, "title", "")
        exercise["lesson_language_focus"] = getattr(plan, "language_focus_json", [])
        exercise["lesson_tags"] = getattr(plan, "tags_json", [])
        if step.prompt_template:
            exercise["prompt"] = step.prompt_template
        elif step.instruction and step.step_type not in instructed:
            exercise["prompt"] = f"{step.instruction}\n\n{exercise['prompt']}"
            instructed.add(step.step_type)
    return exercises


def _apply_material_context(
    exercises: list[dict[str, Any]], context: list[dict]
) -> list[dict[str, Any]]:
    if not context:
        return exercises
    snippet = context[0]["text"].strip().replace("\n", " ")
    if len(snippet) > 420:
        snippet = snippet[:417].rstrip() + "..."
    chunk_ids = [chunk["chunk_id"] for chunk in context]
    for exercise in exercises:
        metadata = exercise.get("metadata")
        if isinstance(metadata, dict):
            metadata["material_context_chunk_ids"] = chunk_ids
            metadata["material_context"] = context
    input_step = next(
        (exercise for exercise in exercises if exercise.get("stage") == "input"),
        None,
    )
    if input_step is not None:
        input_step["prompt"] = f"Material context: {snippet}\n\n{input_step['prompt']}"
    return exercises
