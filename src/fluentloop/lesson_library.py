from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from fluentloop.curriculum_b2 import CURRICULUM_TAG, seed_b2_curriculum
from fluentloop.db.models import (
    LearningItem,
    LessonPlan,
    LessonPlanItem,
    LessonStep,
    MaterialChunk,
    PracticeSessionCached,
    SourceMaterial,
    User,
)
from fluentloop.learning import create_learning_item
from fluentloop.lesson_plans import lesson_items, lesson_steps

SEED_LIBRARY_TELEGRAM_USER_ID = 0


@dataclass(frozen=True)
class SubscribeResult:
    plan: LessonPlan
    created_items: int
    reused_items: int
    reused_source: bool


def get_seed_library_user(session: Session) -> User:
    user = session.scalar(
        select(User).where(User.telegram_user_id == SEED_LIBRARY_TELEGRAM_USER_ID)
    )
    if user is not None:
        return user
    user = User(
        telegram_user_id=SEED_LIBRARY_TELEGRAM_USER_ID,
        level="B2+/C1-",
        focus_areas=["business", "IT"],
        timezone="Europe/Moscow",
        reminder_time="20:00",
    )
    session.add(user)
    session.flush()
    return user


def seed_and_publish_catalog_templates(session: Session) -> dict[str, int]:
    library_user = get_seed_library_user(session)
    seeded = seed_b2_curriculum(session, library_user)
    published = publish_seed_catalog_templates(session, library_user)
    return {
        "seeded_lessons": seeded["lessons"],
        "seeded_items": seeded["items"],
        **published,
    }


def publish_seed_catalog_templates(session: Session, owner: User) -> dict[str, int]:
    plans = [
        plan
        for plan in session.scalars(
            select(LessonPlan).where(
                LessonPlan.user_id == owner.id,
                LessonPlan.status.in_(("active", "draft")),
            )
        )
        if CURRICULUM_TAG in (plan.tags_json or [])
    ]
    plan_count = 0
    source_count = 0
    item_count = 0
    for plan in plans:
        if not plan.is_template:
            plan.is_template = True
            plan_count += 1
        session.add(plan)
        if plan.source_material_id is not None:
            source = session.get(SourceMaterial, plan.source_material_id)
            if source is not None and not source.is_template:
                source.is_template = True
                source_count += 1
                session.add(source)
        for item in lesson_items(session, plan):
            if not item.is_template:
                item.is_template = True
                item_count += 1
                session.add(item)
    session.flush()
    return {"templates": plan_count, "sources": source_count, "items": item_count}


def publish_lesson_template(session: Session, owner: User, plan_id: int) -> LessonPlan:
    plan = session.get(LessonPlan, plan_id)
    if (
        plan is None
        or plan.user_id != owner.id
        or plan.status not in {"active", "draft"}
    ):
        raise ValueError("Lesson plan not found")
    plan.is_template = True
    session.add(plan)
    if plan.source_material_id is not None:
        source = session.get(SourceMaterial, plan.source_material_id)
        if source is not None:
            source.is_template = True
            session.add(source)
    for item in lesson_items(session, plan):
        item.is_template = True
        session.add(item)
    session.flush()
    return plan


def library_templates(
    session: Session, *, query: str = "", limit: int = 20
) -> list[LessonPlan]:
    plans = list(
        session.scalars(
            select(LessonPlan)
            .where(
                LessonPlan.is_template.is_(True),
                LessonPlan.status.in_(("active", "draft")),
            )
            .order_by(LessonPlan.title.asc(), LessonPlan.id.asc())
        )
    )
    if query.strip():
        needle = query.casefold().strip()
        plans = [plan for plan in plans if _template_matches(plan, needle)]
    return plans[:limit]


def library_template_by_id(session: Session, template_id: int) -> LessonPlan | None:
    plan = session.get(LessonPlan, template_id)
    if (
        plan is None
        or not plan.is_template
        or plan.status not in {"active", "draft"}
    ):
        return None
    return plan


def subscribe_to_template(
    session: Session, user: User, template_id: int
) -> SubscribeResult:
    template = library_template_by_id(session, template_id)
    if template is None:
        raise ValueError("Template not found")

    source, reused_source = _clone_or_reuse_source(session, user, template)
    item_map: dict[int, LearningItem] = {}
    created_items = 0
    reused_items = 0
    for template_item in lesson_items(session, template):
        item, created = _clone_or_reuse_item(session, user, template_item, source)
        item_map[template_item.id] = item
        if created:
            created_items += 1
        else:
            reused_items += 1

    clone = LessonPlan(
        user_id=user.id,
        source_material_id=source.id if source is not None else None,
        title=template.title,
        topic=template.topic,
        goal=template.goal,
        level=user.level or template.level,
        language_focus_json=list(template.language_focus_json or []),
        tags_json=list(template.tags_json or []),
        format=template.format,
        is_template=False,
        template_of=template.id,
        status="active",
    )
    session.add(clone)
    session.flush()
    _clone_steps(session, template, clone)
    _clone_plan_items(session, template, clone, item_map)
    session.execute(
        delete(PracticeSessionCached).where(PracticeSessionCached.user_id == user.id)
    )
    session.flush()
    return SubscribeResult(clone, created_items, reused_items, reused_source)


def _clone_or_reuse_source(
    session: Session, user: User, template: LessonPlan
) -> tuple[SourceMaterial | None, bool]:
    if template.source_material_id is None:
        return None, False
    template_source = session.get(SourceMaterial, template.source_material_id)
    if template_source is None:
        return None, False
    existing = session.scalar(
        select(SourceMaterial)
        .where(
            SourceMaterial.user_id == user.id,
            SourceMaterial.template_of == template_source.id,
        )
        .order_by(SourceMaterial.id.asc())
    )
    if existing is not None:
        return existing, True
    clone = SourceMaterial(
        user_id=user.id,
        type=template_source.type,
        raw_text=template_source.raw_text,
        summary=template_source.summary,
        is_template=False,
        template_of=template_source.id,
    )
    session.add(clone)
    session.flush()
    for chunk in session.scalars(
        select(MaterialChunk)
        .where(MaterialChunk.source_material_id == template_source.id)
        .order_by(MaterialChunk.chunk_index.asc())
    ):
        session.add(
            MaterialChunk(
                source_material_id=clone.id,
                chunk_index=chunk.chunk_index,
                text=chunk.text,
                tags_json=list(chunk.tags_json or []),
            )
        )
    session.flush()
    return clone, False


def _clone_or_reuse_item(
    session: Session,
    user: User,
    template_item: LearningItem,
    source: SourceMaterial | None,
) -> tuple[LearningItem, bool]:
    existing = session.scalar(
        select(LearningItem).where(
            LearningItem.user_id == user.id,
            LearningItem.template_of == template_item.id,
            LearningItem.is_template.is_(False),
        )
    )
    if existing is not None:
        return existing, False
    existing = session.scalar(
        select(LearningItem).where(
            LearningItem.user_id == user.id,
            LearningItem.type == template_item.type,
            LearningItem.text == template_item.text,
            LearningItem.is_template.is_(False),
        )
    )
    if existing is not None:
        return existing, False
    if _template_item_collision(session, user, template_item):
        raise ValueError(
            "Template owner cannot subscribe to this template because item texts "
            "would collide with template rows."
        )
    item = create_learning_item(
        session,
        user,
        type_=template_item.type,
        text=template_item.text,
        meaning=template_item.meaning,
        explanation=template_item.explanation,
        examples=list(template_item.examples or []),
        tags=list(template_item.tags or []),
        source_material_id=source.id if source is not None else None,
        is_favorite=template_item.is_favorite,
        metadata=dict(template_item.metadata_json or {}),
    )
    item.template_of = template_item.id
    item.is_template = False
    item.linked_grammar_concept_id = template_item.linked_grammar_concept_id
    session.add(item)
    session.flush()
    return item, True


def _template_item_collision(
    session: Session, user: User, template_item: LearningItem
) -> bool:
    return (
        session.scalar(
            select(LearningItem.id).where(
                LearningItem.user_id == user.id,
                LearningItem.type == template_item.type,
                LearningItem.text == template_item.text,
                LearningItem.is_template.is_(True),
            )
        )
        is not None
    )


def _clone_steps(session: Session, template: LessonPlan, clone: LessonPlan) -> None:
    for step in lesson_steps(session, template):
        session.add(
            LessonStep(
                lesson_plan_id=clone.id,
                order_index=step.order_index,
                step_type=step.step_type,
                title=step.title,
                instruction=step.instruction,
                exercise_type=step.exercise_type,
                estimated_minutes=step.estimated_minutes,
                target_skill=step.target_skill,
                prompt_template=step.prompt_template,
                metadata_json=dict(step.metadata_json or {}),
            )
        )
    session.flush()


def _clone_plan_items(
    session: Session,
    template: LessonPlan,
    clone: LessonPlan,
    item_map: dict[int, LearningItem],
) -> None:
    for link in session.scalars(
        select(LessonPlanItem)
        .where(LessonPlanItem.lesson_plan_id == template.id)
        .order_by(LessonPlanItem.priority.asc(), LessonPlanItem.id.asc())
    ):
        item = item_map.get(link.learning_item_id)
        if item is None:
            continue
        session.add(
            LessonPlanItem(
                lesson_plan_id=clone.id,
                learning_item_id=item.id,
                role=link.role,
                priority=link.priority,
            )
        )
    session.flush()


def _template_matches(plan: LessonPlan, needle: str) -> bool:
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
