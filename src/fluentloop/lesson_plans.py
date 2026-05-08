from __future__ import annotations

from collections.abc import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from fluentloop.db.models import (
    LearningItem,
    LessonPlan,
    LessonPlanItem,
    LessonStep,
    SourceMaterial,
    User,
)

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
    topic = _infer_topic(source, linked_items)
    plan = LessonPlan(
        user_id=user.id,
        source_material_id=source.id,
        title=_title_for_source(source, topic),
        topic=topic,
        goal=_goal_for_topic(topic, linked_items),
        level=user.level,
        language_focus_json=_language_focus(linked_items),
        tags_json=_tags_for_items(linked_items),
        status=status,
    )
    session.add(plan)
    session.flush()
    create_default_lesson_steps(session, plan)
    link_lesson_items(session, plan, linked_items)
    return plan


def create_default_lesson_steps(session: Session, plan: LessonPlan) -> list[LessonStep]:
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
    for index, (step_type, title, instruction, minutes) in enumerate(
        DEFAULT_LESSON_STEPS, start=1
    ):
        step = LessonStep(
            lesson_plan_id=plan.id,
            order_index=index,
            step_type=step_type,
            title=title,
            instruction=instruction,
            estimated_minutes=minutes,
            target_skill=step_type,
            metadata_json={},
        )
        session.add(step)
        steps.append(step)
    session.flush()
    return steps


def link_lesson_items(
    session: Session, plan: LessonPlan, items: Iterable[LearningItem]
) -> list[LessonPlanItem]:
    links: list[LessonPlanItem] = []
    for priority, item in enumerate(items, start=1):
        role = _role_for_item(item)
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
    session: Session, user: User, source: SourceMaterial
) -> LessonPlan | None:
    items = _items_for_source(session, user, source)
    if not items:
        return None
    return create_lesson_plan_from_source(session, user, source, items=items)


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
    marker = source.raw_text.strip().splitlines()[0][:80] if source.raw_text else ""
    if marker.startswith("#"):
        marker = marker.lstrip("#").strip()
    return marker or f"15-minute lesson: {topic}"


def _goal_for_topic(topic: str, items: list[LearningItem]) -> str:
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
