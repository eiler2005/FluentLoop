from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from fluentloop.db.models import (
    GrammarConcept,
    LearningItem,
    MistakePattern,
    ReviewState,
    User,
)
from fluentloop.exercises import Exercise, render_for_item
from fluentloop.learning import active_items
from fluentloop.lesson_plans import (
    available_lesson_plan,
    lesson_items,
    lesson_steps,
)
from fluentloop.srs import get_due_items

SESSION_STAGES = (
    "warmup",
    "input",
    "controlled_practice",
    "controlled_practice",
    "grammar_or_mistake_focus",
    "free_production",
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
    if len(due_items) >= 5:
        return "review"
    if _active_patterns(session, user.id, limit=1):
        return "mistake_focus"

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
) -> list[dict[str, Any]]:
    plan = available_lesson_plan(session, user)
    mode = "lesson" if plan is not None else choose_session_mode(session, user, now=now)
    scored_items = _scored_items_for_lesson_plan(session, plan)
    if not scored_items:
        scored_items = score_learning_items(session, user, now=now)
    patterns = _active_patterns(session, user.id, limit=3)
    if plan is not None:
        topic_goal = TopicGoal(plan.topic, plan.goal)
    else:
        topic_goal = select_topic_and_goal(scored_items, patterns)
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
    return exercises


def _scored_items_for_lesson_plan(
    session: Session, plan: object | None
) -> list[ScoredLearningItem]:
    if plan is None:
        return []
    return [
        ScoredLearningItem(item=item, score=150 - index, reasons=("lesson_plan",))
        for index, item in enumerate(lesson_items(session, plan))
    ]


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
        build_input_step(
            selected[:1], mode=mode, topic=topic, lesson_goal=lesson_goal
        ),
        *build_controlled_practice_steps(
            selected, mode=mode, topic=topic, lesson_goal=lesson_goal
        ),
        build_grammar_or_mistake_focus_step(
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


def build_input_step(
    items: list[LearningItem], *, mode: str, topic: str, lesson_goal: str
) -> dict[str, Any]:
    if items:
        item = items[0]
        meaning = item.meaning or item.explanation or "useful workplace language"
        example = item.examples[0] if item.examples else f"We need to use {item.text}."
        exercise = Exercise(
            "follow_up",
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
            "follow_up",
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
    preferred = ("cloze", "translate")
    for index in range(2):
        item = items[index + 1] if len(items) > index + 1 else None
        if item is None:
            exercise = _seed_controlled_practice(index)
        else:
            exercise_type = _preferred_type(item, preferred[index])
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
            f"Fix this recurring {pattern.mistake_type} issue:\n\"{wrong}\"",
            expected,
            "Use the recurring mistake pattern as your clue.",
            pattern.description,
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
            concept = session.scalar(select(GrammarConcept).order_by(GrammarConcept.id))
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
    return _with_metadata(
        exercise,
        stage="grammar_or_mistake_focus",
        mode=mode,
        topic=topic,
        lesson_goal=lesson_goal,
        target_skill="grammar_or_mistake_repair",
    )


def build_free_production_step(
    items: list[LearningItem], *, mode: str, topic: str, lesson_goal: str
) -> dict[str, Any]:
    targets = items[:3]
    target_text = ", ".join(item.text for item in targets) or "I would lean towards"
    exercise = Exercise(
        "follow_up",
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
    items: list[LearningItem], *, mode: str, topic: str, lesson_goal: str
) -> dict[str, Any]:
    targets = items[:4]
    target_text = ", ".join(item.text for item in targets) or "today's key phrases"
    exercise = Exercise(
        "follow_up",
        (
            "Recap: without looking back, write three things you want to remember "
            f"from today's practice. Include: {target_text}."
        ),
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
        return "grammar_rewrite"
    return fallback


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
    for exercise, step in zip(exercises, steps, strict=False):
        exercise["stage"] = step.step_type
        exercise["lesson_plan_id"] = step.lesson_plan_id
        exercise["lesson_step_id"] = step.id
        metadata = exercise.get("metadata")
        if isinstance(metadata, dict):
            metadata["stage"] = step.step_type
            metadata["lesson_plan_id"] = step.lesson_plan_id
            metadata["lesson_step_id"] = step.id
        if step.prompt_template:
            exercise["prompt"] = step.prompt_template
        elif step.instruction:
            exercise["prompt"] = f"{step.instruction}\n\n{exercise['prompt']}"
    return exercises
