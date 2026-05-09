from __future__ import annotations

import random
from collections import Counter
from collections.abc import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from fluentloop.ai.provider import AIProvider
from fluentloop.ai.schemas import LessonPlanDraft
from fluentloop.db.models import (
    LearningItem,
    LessonPlan,
    LessonPlanItem,
    LessonStep,
    SourceMaterial,
    User,
)
from fluentloop.lesson_overview import infer_lesson_overview

LESSON_PLAN_STATUSES = {"draft", "active", "archived", "completed"}
LESSON_PLAN_ITEM_ROLES = {
    "target",
    "supporting",
    "review",
    "grammar_focus",
    "mistake_focus",
}
DEFAULT_LESSON_STEPS = (
    ("warmup", "Warm-up", "Activate the topic with one short workplace answer.", 2),
    ("input", "Input", "Notice the key language from this material.", 2),
    (
        "controlled_practice",
        "Controlled practice",
        "Use one target item accurately.",
        2,
    ),
    (
        "controlled_practice",
        "Controlled practice",
        "Use another target item accurately.",
        2,
    ),
    (
        "grammar_or_mistake_focus",
        "Grammar / mistake focus",
        "Repair one grammar point or recurring weak spot.",
        3,
    ),
    ("free_production", "Free production", "Write a short realistic work message.", 3),
    ("recap", "Recap", "Recall the most useful language without looking back.", 1),
)


def create_lesson_plan_from_source(
    session: Session,
    user: User,
    source: SourceMaterial,
    *,
    items: Iterable[LearningItem] | None = None,
    status: str = "active",
    provider: AIProvider | None = None,
) -> LessonPlan:
    if source.user_id != user.id:
        raise ValueError("Source material does not belong to the user")
    if status not in LESSON_PLAN_STATUSES:
        raise ValueError(f"Unsupported lesson plan status: {status}")

    existing = session.scalar(
        select(LessonPlan).where(
            LessonPlan.user_id == user.id,
            LessonPlan.source_material_id == source.id,
            LessonPlan.status.in_(("draft", "active")),
        )
    )
    if existing is not None:
        return existing

    linked_items = (
        list(items) if items is not None else _items_for_source(session, user, source)
    )
    draft = _draft_lesson_plan(provider, user, source, linked_items)
    topic = draft.topic.strip() if draft and draft.topic.strip() else _infer_topic(
        source, linked_items
    )
    plan = LessonPlan(
        user_id=user.id,
        source_material_id=source.id,
        title=(draft.title.strip() if draft and draft.title.strip() else None)
        or _title_for_source(source, topic),
        topic=topic,
        goal=(draft.goal.strip() if draft and draft.goal.strip() else None)
        or _goal_for_topic(topic, linked_items),
        level=user.level,
        language_focus_json=(
            draft.language_focus[:12] if draft and draft.language_focus else None
        )
        or _language_focus(linked_items),
        tags_json=(draft.tags[:12] if draft and draft.tags else None)
        or _tags_for_items(linked_items),
        status=status,
    )
    session.add(plan)
    session.flush()
    create_default_lesson_steps(session, plan, draft=draft)
    link_lesson_items(session, plan, linked_items, draft=draft)
    return plan


def create_default_lesson_steps(
    session: Session, plan: LessonPlan, *, draft: LessonPlanDraft | None = None
) -> list[LessonStep]:
    existing = list(
        session.scalars(
            select(LessonStep)
            .where(LessonStep.lesson_plan_id == plan.id)
            .order_by(LessonStep.order_index)
        )
    )
    if existing:
        return existing
    steps: list[LessonStep] = []
    draft_steps = {step.step_type: step for step in (draft.steps if draft else [])}
    for index, (step_type, title, instruction, minutes) in enumerate(
        DEFAULT_LESSON_STEPS, start=1
    ):
        draft_step = draft_steps.get(step_type)
        step = LessonStep(
            lesson_plan_id=plan.id,
            order_index=index,
            step_type=step_type,
            title=(draft_step.title if draft_step and draft_step.title else title),
            instruction=(
                draft_step.instruction
                if draft_step and draft_step.instruction
                else instruction
            ),
            estimated_minutes=(
                draft_step.estimated_minutes
                if draft_step and draft_step.estimated_minutes
                else minutes
            ),
            target_skill=(
                draft_step.target_skill
                if draft_step and draft_step.target_skill
                else step_type
            ),
            metadata_json={
                "teacher_rationale": draft_step.rationale if draft_step else "",
                "lesson_teacher_rationale": draft.teacher_rationale if draft else "",
            },
        )
        session.add(step)
        steps.append(step)
    session.flush()
    return steps


def link_lesson_items(
    session: Session,
    plan: LessonPlan,
    items: Iterable[LearningItem],
    *,
    draft: LessonPlanDraft | None = None,
) -> list[LessonPlanItem]:
    links: list[LessonPlanItem] = []
    priority_by_text = {
        item.text.strip().lower(): item
        for item in (draft.item_priorities if draft else [])
        if item.text.strip()
    }
    sorted_items = sorted(
        list(items),
        key=lambda item: (
            priority_by_text.get(item.text.strip().lower()).priority
            if item.text.strip().lower() in priority_by_text
            else 10_000,
            item.created_at,
        ),
    )
    for fallback_priority, item in enumerate(sorted_items, start=1):
        priority_draft = priority_by_text.get(item.text.strip().lower())
        role = (
            priority_draft.role
            if priority_draft and priority_draft.role
            else _role_for_item(item)
        )
        priority = (
            priority_draft.priority
            if priority_draft and priority_draft.priority
            else fallback_priority
        )
        existing = session.scalar(
            select(LessonPlanItem).where(
                LessonPlanItem.lesson_plan_id == plan.id,
                LessonPlanItem.learning_item_id == item.id,
                LessonPlanItem.role == role,
            )
        )
        if existing is not None:
            links.append(existing)
            continue
        link = LessonPlanItem(
            lesson_plan_id=plan.id,
            learning_item_id=item.id,
            role=role,
            priority=priority,
        )
        session.add(link)
        links.append(link)
    session.flush()
    return links


def available_lesson_plan(session: Session, user: User) -> LessonPlan | None:
    return session.scalar(
        select(LessonPlan)
        .where(
            LessonPlan.user_id == user.id,
            LessonPlan.status.in_(("active", "draft")),
        )
        .order_by(LessonPlan.status.asc(), LessonPlan.updated_at.desc())
        .limit(1)
    )


def active_lesson_plans(
    session: Session,
    user: User,
    *,
    query: str = "",
    limit: int = 20,
) -> list[LessonPlan]:
    plans = list(
        session.scalars(
            select(LessonPlan)
            .where(
                LessonPlan.user_id == user.id,
                LessonPlan.status.in_(("active", "draft")),
            )
            .order_by(LessonPlan.updated_at.desc(), LessonPlan.id.desc())
        )
    )
    if query.strip():
        needle = query.casefold().strip()
        plans = [plan for plan in plans if _plan_matches(plan, needle)]
    return plans[:limit]


def lesson_plan_by_id(
    session: Session, user: User, lesson_plan_id: int
) -> LessonPlan | None:
    plan = session.get(LessonPlan, lesson_plan_id)
    if (
        plan is None
        or plan.user_id != user.id
        or plan.status not in {"active", "draft"}
    ):
        return None
    return plan


def find_lesson_plan(
    session: Session, user: User, query: str
) -> LessonPlan | None:
    matches = active_lesson_plans(session, user, query=query, limit=10)
    return matches[0] if matches else None


def random_lesson_plan(session: Session, user: User) -> LessonPlan | None:
    plans = active_lesson_plans(session, user, limit=100)
    return random.choice(plans) if plans else None


def lesson_pool_size(session: Session, plan: LessonPlan) -> int:
    return len(lesson_items(session, plan))


def lesson_topic_groups(session: Session, user: User) -> list[tuple[str, int]]:
    counter: Counter[str] = Counter()
    for plan in active_lesson_plans(session, user, limit=500):
        tags = list(plan.tags_json or [])
        areas = [tag for tag in tags if not tag.startswith("curriculum:")]
        labels = areas[:3] or [plan.topic]
        for label in labels:
            counter[label] += 1
    return sorted(counter.items(), key=lambda row: (-row[1], row[0].casefold()))


def lesson_steps(session: Session, plan: LessonPlan) -> list[LessonStep]:
    return list(
        session.scalars(
            select(LessonStep)
            .where(LessonStep.lesson_plan_id == plan.id)
            .order_by(LessonStep.order_index)
        )
    )


def lesson_items(session: Session, plan: LessonPlan) -> list[LearningItem]:
    rows = session.execute(
        select(LearningItem)
        .join(LessonPlanItem, LessonPlanItem.learning_item_id == LearningItem.id)
        .where(
            LessonPlanItem.lesson_plan_id == plan.id,
            LearningItem.status == "active",
        )
        .order_by(LessonPlanItem.priority.asc(), LearningItem.created_at.asc())
    )
    return list(rows.scalars())


def ensure_lesson_plan_for_source(
    session: Session,
    user: User,
    source: SourceMaterial,
    *,
    provider: AIProvider | None = None,
) -> LessonPlan | None:
    items = _items_for_source(session, user, source)
    if not items:
        return None
    return create_lesson_plan_from_source(
        session, user, source, items=items, provider=provider
    )


def _draft_lesson_plan(
    provider: AIProvider | None,
    user: User,
    source: SourceMaterial,
    items: list[LearningItem],
) -> LessonPlanDraft | None:
    if provider is None or not items:
        return None
    payload = {
        "source_material": {
            "id": source.id,
            "type": source.type,
            "summary": source.summary or "",
            "raw_text": source.raw_text[:6000],
        },
        "user": {
            "level": user.level,
            "focus_areas": user.focus_areas,
            "practice_duration_minutes": user.practice_duration_minutes,
        },
        "items": [
            {
                "id": item.id,
                "type": item.type,
                "text": item.text,
                "meaning": item.meaning,
                "explanation": item.explanation,
                "examples": item.examples,
                "tags": item.tags,
                "role": _role_for_item(item),
            }
            for item in items
        ],
        "target_exercise_count": 16,
        "candidate_pool_goal": "20-30 targets when material is substantial",
    }
    try:
        result = provider.heavy_call("epic_17_seed_lesson_plan", payload)
    except Exception:
        return None
    return result if isinstance(result, LessonPlanDraft) else None


def _items_for_source(
    session: Session, user: User, source: SourceMaterial
) -> list[LearningItem]:
    return list(
        session.scalars(
            select(LearningItem)
            .where(
                LearningItem.user_id == user.id,
                LearningItem.source_material_id == source.id,
                LearningItem.status == "active",
            )
            .order_by(LearningItem.created_at.asc())
        )
    )


def _infer_topic(source: SourceMaterial, items: list[LearningItem]) -> str:
    overview = infer_lesson_overview(
        source.raw_text,
        item_texts=[item.text for item in items],
        tags=[tag for item in items for tag in (item.tags or [])],
    )
    if overview.topic != "Business/IT communication":
        return overview.topic
    text = " ".join(
        [
            source.summary or "",
            source.raw_text[:800],
            *(item.text for item in items[:8]),
            *(tag for item in items[:8] for tag in (item.tags or [])),
        ]
    ).lower()
    if "introvert" in text or "extrovert" in text or "reported" in text:
        return "Reported speech and workplace personality"
    if "architecture" in text or "trade-off" in text or "tradeoff" in text:
        return "Architecture trade-offs"
    if "incident" in text or "root cause" in text:
        return "Incident and risk updates"
    if "stakeholder" in text or "push back" in text or "hedg" in text:
        return "Stakeholder communication"
    return "Business/IT communication"


def _title_for_source(source: SourceMaterial, topic: str) -> str:
    overview = infer_lesson_overview(source.raw_text)
    if overview.title != "15-minute Workplace English Lesson":
        return overview.title
    marker = source.raw_text.strip().splitlines()[0][:80] if source.raw_text else ""
    if marker.startswith("#"):
        marker = marker.lstrip("#").strip()
    return marker or f"15-minute lesson: {topic}"


def _goal_for_topic(topic: str, items: list[LearningItem]) -> str:
    overview = infer_lesson_overview(item_texts=[item.text for item in items])
    if overview.topic == topic and overview.goal:
        return overview.goal
    if "Reported speech" in topic:
        return "Report opinions and recommendations naturally in workplace English."
    if "Architecture" in topic:
        return "Explain trade-offs, risks, and recommendations diplomatically."
    if items:
        targets = ", ".join(item.text for item in items[:3])
        return f"Use {targets} in a realistic work exchange."
    return "Practice useful workplace language in a staged 15-minute session."


def _language_focus(items: list[LearningItem]) -> list[str]:
    focus = [
        item.text for item in items if item.type in {"grammar_rule", "mistake_pattern"}
    ]
    return focus[:6]


def _tags_for_items(items: list[LearningItem]) -> list[str]:
    tags = sorted({tag for item in items for tag in (item.tags or [])})
    return tags[:12]


def _role_for_item(item: LearningItem) -> str:
    if item.type == "grammar_rule":
        return "grammar_focus"
    if item.type == "mistake_pattern":
        return "mistake_focus"
    return "target"


def _plan_matches(plan: LessonPlan, needle: str) -> bool:
    haystack = " ".join(
        [
            plan.title or "",
            plan.topic or "",
            plan.goal or "",
            " ".join(plan.language_focus_json or []),
            " ".join(plan.tags_json or []),
        ]
    ).casefold()
    return needle in haystack
