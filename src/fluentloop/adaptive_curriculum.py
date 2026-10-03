"""Validated, owner-curated workplace curriculum for the gated simple stream."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

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
from fluentloop.learning import create_learning_item
from fluentloop.lesson_library import get_seed_library_user, subscribe_to_template
from fluentloop.lesson_plans import lesson_items

PACK_PATH = Path(__file__).parent / "seeds" / "adaptive_curriculum_v1.json"
PACK_TAG = "adaptive_curriculum:v1"
ADAPTIVE_TOPICS = (
    "aspect",
    "future_planning",
    "conditionals",
    "modals",
    "reporting",
    "information_structure",
    "cohesion",
    "diplomatic_communication",
    "delivery_collocations",
    "incident_communication",
)
STAGES = ("b2", "b2_plus", "c1_intro")
STAGE_LEVELS = dict(zip(STAGES, ("B2", "B2+", "C1-intro"), strict=True))
PROVENANCE_METADATA_KEY = "adaptive_curriculum"


@dataclass(frozen=True)
class PublishSummary:
    source_id: int
    templates: int
    items: int
    reused_templates: int
    reused_items: int


@dataclass(frozen=True)
class SubscribeSummary:
    plans: tuple[LessonPlan, ...]
    created_plans: int
    reused_plans: int


def content_fingerprint(question: dict[str, Any]) -> str:
    canonical = {
        "prompt": question["prompt"],
        "options": sorted(question["options"]),
        "answer": question["options"][question["correct_index"]],
    }
    return hashlib.sha256(
        json.dumps(canonical, ensure_ascii=False, sort_keys=True).encode()
    ).hexdigest()


def validate_adaptive_curriculum(pack: dict[str, Any]) -> dict[str, Any]:
    """Reject incomplete, duplicated or mismatched content before any DB write."""

    if (
        pack.get("schema_version") != 1
        or pack.get("pack_id") != PACK_TAG
        or pack.get("review_status") != "editorially_reviewed"
    ):
        raise ValueError("Unsupported adaptive curriculum pack")
    canonical = {key: value for key, value in pack.items() if key != "content_sha256"}
    digest = hashlib.sha256(
        json.dumps(
            canonical, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode()
    ).hexdigest()
    if digest != pack.get("content_sha256"):
        raise ValueError("Adaptive curriculum content fingerprint mismatch")
    topics = pack.get("topics")
    if (
        not isinstance(topics, list)
        or tuple(topic.get("slug") for topic in topics) != ADAPTIVE_TOPICS
    ):
        raise ValueError("Adaptive curriculum must contain the ten covered topics")
    seen_ids: set[str] = set()
    seen_fingerprints: set[str] = set()
    seen_texts: set[tuple[str, str]] = set()
    seen_prompts: set[str] = set()
    for topic in topics:
        slug = topic["slug"]
        if topic.get("category") not in {"grammar", "phrase"} or not topic.get("title"):
            raise ValueError(f"Invalid adaptive topic: {slug}")
        stages = topic.get("stages", [])
        if tuple(stage.get("id") for stage in stages) != STAGES:
            raise ValueError(f"Incomplete adaptive syllabus: {slug}")
        for stage in stages:
            if (
                stage.get("level") != STAGE_LEVELS[stage["id"]]
                or not stage.get("goal")
                or not stage.get("production_task")
                or stage.get("practice_count") != 6
                or stage.get("transfer_count") != 3
            ):
                raise ValueError(f"Invalid adaptive syllabus stage: {slug}")
        records = topic.get("records", [])
        if not isinstance(records, list) or len(records) != 27:
            raise ValueError(f"Adaptive topic requires 27 records: {slug}")
        counts = {
            (stage, role): 0 for stage in STAGES for role in ("practice", "transfer")
        }
        for record in records:
            key = record.get("source_key")
            question = record.get("simple_question", {})
            adaptive = question.get("adaptive", {})
            stage = adaptive.get("stage")
            role = adaptive.get("role")
            if (
                not isinstance(key, str)
                or key in seen_ids
                or adaptive.get("version") != 1
                or adaptive.get("topic_id") != slug
                or adaptive.get("variant_id") != key
                or (stage, role) not in counts
            ):
                raise ValueError(f"Invalid adaptive question identity: {slug}")
            seen_ids.add(key)
            counts[(stage, role)] += 1
            options = question.get("options")
            index = question.get("correct_index")
            prompt = question.get("prompt")
            if (
                not isinstance(prompt, str)
                or not prompt.strip()
                or prompt in seen_prompts
                or not isinstance(options, list)
                or len(options) != 2
                or not all(
                    isinstance(option, str) and option.strip() for option in options
                )
                or len({option.casefold().strip() for option in options}) != 2
                or type(index) is not int
                or not 0 <= index < len(options)
                or not question.get("explanation_ru")
                or not question.get("production_prompt")
                or not question.get("target_construction")
                or question.get("category") != topic["category"]
                or question.get("topic") != slug
                or question.get("level") != STAGE_LEVELS[stage]
            ):
                raise ValueError(f"Invalid adaptive question payload: {key}")
            seen_prompts.add(prompt)
            fingerprint = content_fingerprint(question)
            if (
                question.get("fingerprint") != fingerprint
                or fingerprint in seen_fingerprints
            ):
                raise ValueError(f"Invalid or duplicated adaptive fingerprint: {key}")
            seen_fingerprints.add(fingerprint)
            if any("\u0400" <= char <= "\u04ff" for char in prompt + " ".join(options)):
                raise ValueError(
                    f"Adaptive quiz prompt and options must be English: {key}"
                )
            if topic["category"] == "phrase" and not question.get("target_phrase"):
                raise ValueError(f"Adaptive phrase target missing: {key}")
            correct_answer = options[index]
            if correct_answer.casefold().strip(".") in prompt.casefold():
                raise ValueError(f"Adaptive prompt exposes the complete answer: {key}")
            if (
                topic["category"] == "phrase"
                and question["target_phrase"].casefold()
                not in correct_answer.casefold()
            ):
                raise ValueError(
                    f"Adaptive phrase target absent from its answer: {key}"
                )
            learning = record.get("learning_item", {})
            expected_type = (
                "grammar_rule" if topic["category"] == "grammar" else "expression"
            )
            if (
                learning.get("type") != expected_type
                or not all(
                    isinstance(learning.get(field), str) and learning[field].strip()
                    for field in ("text", "meaning_en", "meaning_ru", "example")
                )
                or learning["text"] != options[index]
                or learning["text"].casefold() not in learning["example"].casefold()
            ):
                raise ValueError(f"Incomplete adaptive learning card: {key}")
            identity = (learning["type"], learning["text"])
            if identity in seen_texts:
                raise ValueError(
                    f"Adaptive cards must have distinct contextual answers: {key}"
                )
            seen_texts.add(identity)
        if any(
            count != (6 if role == "practice" else 3)
            for (_, role), count in counts.items()
        ):
            raise ValueError(f"Adaptive practice/transfer coverage incomplete: {slug}")
    return pack


def load_adaptive_curriculum(path: Path | str = PACK_PATH) -> dict[str, Any]:
    return validate_adaptive_curriculum(
        json.loads(Path(path).read_text(encoding="utf-8"))
    )


def publish_adaptive_curriculum(
    session: Session, owner: User | None = None, pack: dict[str, Any] | None = None
) -> PublishSummary:
    """Publish ten topic templates; all stage/transfer gating remains in /study."""

    pack = (
        validate_adaptive_curriculum(pack)
        if pack is not None
        else load_adaptive_curriculum()
    )
    owner = owner or get_seed_library_user(session)
    summary = f"{PACK_TAG} · sha256:{pack['content_sha256']}"
    source = session.scalar(
        select(SourceMaterial).where(
            SourceMaterial.user_id == owner.id,
            SourceMaterial.type == "lesson_notes",
            SourceMaterial.summary == summary,
        )
    )
    if source is None:
        source = SourceMaterial(
            user_id=owner.id,
            type="lesson_notes",
            raw_text=json.dumps(pack, ensure_ascii=False, sort_keys=True),
            summary=summary,
            is_template=True,
        )
        session.add(source)
        session.flush()
    source.is_template = True
    owner_items = list(
        session.scalars(select(LearningItem).where(LearningItem.user_id == owner.id))
    )
    items_by_key = {
        (item.metadata_json or {})
        .get(PROVENANCE_METADATA_KEY, {})
        .get("variant_id"): item
        for item in owner_items
        if (item.metadata_json or {}).get(PROVENANCE_METADATA_KEY, {}).get("variant_id")
    }
    items_by_content = {(item.type, item.text): item for item in owner_items}
    plans_by_topic = {
        next(
            (tag[6:] for tag in (plan.tags_json or []) if tag.startswith("topic:")), ""
        ): plan
        for plan in session.scalars(
            select(LessonPlan).where(LessonPlan.user_id == owner.id)
        )
        if PACK_TAG in (plan.tags_json or [])
    }
    created_plans = reused_plans = created_items = reused_items = 0
    for topic in pack["topics"]:
        slug = topic["slug"]
        plan = plans_by_topic.get(slug)
        if plan is None:
            plan = LessonPlan(user_id=owner.id)
            session.add(plan)
            created_plans += 1
        else:
            reused_plans += 1
        plan.source_material_id = source.id
        plan.title = f"{topic['title']} · B2 → C1-intro"
        plan.topic = topic["title"]
        plan.goal = " → ".join(stage["goal"] for stage in topic["stages"])
        plan.level = "B2/B2+/C1-intro"
        plan.language_focus_json = [
            slug,
            topic["category"],
            *[stage["goal"] for stage in topic["stages"]],
        ]
        plan.tags_json = [PACK_TAG, f"topic:{slug}", f"category:{topic['category']}"]
        plan.format = "adaptive_questions"
        plan.is_template = True
        plan.status = "active"
        session.flush()
        existing_steps = {
            step.order_index: step
            for step in session.scalars(
                select(LessonStep).where(LessonStep.lesson_plan_id == plan.id)
            )
        }
        for position, stage in enumerate(topic["stages"], 1):
            step = existing_steps.get(position)
            if step is None:
                step = LessonStep(lesson_plan_id=plan.id, order_index=position)
                session.add(step)
            step.step_type = "controlled_practice"
            step.title = f"{stage['level']}: {stage['goal']}"
            step.instruction = stage["production_task"]
            step.estimated_minutes = 5
            step.target_skill = slug
            step.metadata_json = {
                "curriculum": PACK_TAG,
                "topic_id": slug,
                "stage": stage["id"],
            }
        links = {
            link.learning_item_id: link
            for link in session.scalars(
                select(LessonPlanItem).where(LessonPlanItem.lesson_plan_id == plan.id)
            )
        }
        for priority, record in enumerate(topic["records"]):
            question = record["simple_question"]
            learning = record["learning_item"]
            adaptive = dict(question["adaptive"])
            metadata = {PROVENANCE_METADATA_KEY: adaptive, "simple_question": question}
            item = items_by_key.get(record["source_key"])
            if item is None:
                if (learning["type"], learning["text"]) in items_by_content:
                    raise ValueError(
                        "Adaptive template collides with existing owner content"
                    )
                item = create_learning_item(
                    session,
                    owner,
                    type_=learning["type"],
                    text=learning["text"],
                    meaning=learning["meaning_en"],
                    explanation=learning["meaning_ru"],
                    examples=[learning["example"]],
                    tags=[PACK_TAG, f"topic:{slug}"],
                    source_material_id=source.id,
                    metadata=metadata,
                )
                items_by_key[record["source_key"]] = item
                items_by_content[(item.type, item.text)] = item
                created_items += 1
            else:
                if item.type != learning["type"] or item.text != learning["text"]:
                    raise ValueError(
                        "Adaptive template identity changed; publish a new pack version"
                    )
                reused_items += 1
            item.metadata_json = metadata
            item.level = question["level"]
            item.is_template = True
            item.template_of = None
            item.source_material_id = source.id
            session.add(item)
            if item.id not in links:
                session.add(
                    LessonPlanItem(
                        lesson_plan_id=plan.id,
                        learning_item_id=item.id,
                        role="grammar_focus"
                        if topic["category"] == "grammar"
                        else "target",
                        priority=priority,
                    )
                )
    session.flush()
    return PublishSummary(
        source.id, created_plans, created_items, reused_plans, reused_items
    )


def subscribe_adaptive_curriculum(session: Session, user: User) -> SubscribeSummary:
    """Clone the approved templates once per user, preserving curated fields/SRS."""

    templates = [
        plan
        for plan in session.scalars(
            select(LessonPlan)
            .where(LessonPlan.is_template.is_(True), LessonPlan.status == "active")
            .order_by(LessonPlan.id)
        )
        if PACK_TAG in (plan.tags_json or [])
    ]
    plans = []
    created = reused = 0
    for template in templates:
        template_items = lesson_items(session, template)
        personal_by_content = {
            (item.type, item.text): item
            for item in session.scalars(
                select(LearningItem).where(LearningItem.user_id == user.id)
            )
        }
        for template_item in template_items:
            personal = personal_by_content.get((template_item.type, template_item.text))
            if personal is None:
                continue
            expected = template_item.metadata_json or {}
            current = personal.metadata_json or {}
            for key in ("simple_question", PROVENANCE_METADATA_KEY):
                if key in current and current[key] != expected[key]:
                    raise ValueError(
                        "Adaptive subscription conflicts with existing "
                        "question provenance"
                    )
            if (
                expected[PROVENANCE_METADATA_KEY]["role"] == "transfer"
                and PROVENANCE_METADATA_KEY not in current
            ):
                raise ValueError(
                    "A transfer card collides with previously available "
                    "personal content"
                )
        clone = session.scalar(
            select(LessonPlan)
            .where(
                LessonPlan.user_id == user.id,
                LessonPlan.template_of == template.id,
                LessonPlan.status == "active",
            )
            .order_by(LessonPlan.id)
        )
        if clone is None:
            clone = subscribe_to_template(session, user, template.id).plan
            created += 1
        else:
            reused += 1
        template_by_content = {(item.type, item.text): item for item in template_items}
        linked_personal = session.scalars(
            select(LearningItem)
            .join(LessonPlanItem, LessonPlanItem.learning_item_id == LearningItem.id)
            .where(
                LessonPlanItem.lesson_plan_id == clone.id,
                LearningItem.user_id == user.id,
            )
        )
        for personal in linked_personal:
            original = template_by_content.get((personal.type, personal.text))
            if original is None:
                raise ValueError(
                    "Adaptive subscription cannot resolve its template card"
                )
            metadata = dict(personal.metadata_json or {})
            metadata.update(
                {
                    key: (original.metadata_json or {})[key]
                    for key in ("simple_question", PROVENANCE_METADATA_KEY)
                }
            )
            personal.metadata_json = metadata
            if personal.template_of == original.id:
                personal.level = original.level
            session.add(personal)
        plans.append(clone)
    session.flush()
    return SubscribeSummary(tuple(plans), created, reused)
