"""Packaged, owner-curated questions adapted from the lang-lessons bank."""

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
from fluentloop.lesson_library import (
    SubscribeResult,
    get_seed_library_user,
    subscribe_to_template,
)
from fluentloop.lesson_plans import lesson_items

PACK_PATH = Path(__file__).parent / "seeds" / "lang_lessons_v1.json"
SOURCE_NAME = "lang-lessons/errors_bank.json"
SOURCE_SHA256 = "376961255dce533c5bd3c597cdb4575f5968de3b9457027eba37de42595eb243"
PACK_TAG = "lang_lessons:v1"
QUESTION_METADATA_KEY = "simple_question"
PROVENANCE_METADATA_KEY = "lang_lessons"
EXPECTED_TOPIC_COUNT = 19
EXPECTED_ITEM_COUNT = 86


@dataclass(frozen=True)
class PublishSummary:
    source_id: int
    templates: int
    items: int
    reused_templates: int
    reused_items: int


@dataclass(frozen=True)
class PilotSubscribeSummary:
    plans: tuple[LessonPlan, ...]
    created_plans: int
    reused_plans: int


def load_lang_lessons(path: Path | str = PACK_PATH) -> dict[str, Any]:
    """Load and validate the bundled question pack without accessing user state."""

    pack = json.loads(Path(path).read_text(encoding="utf-8"))
    source = pack.get("source", {})
    topics = pack.get("topics", [])
    if pack.get("schema_version") != 1:
        raise ValueError("Unsupported lang-lessons pack schema")
    if source.get("name") != SOURCE_NAME or source.get("sha256") != SOURCE_SHA256:
        raise ValueError("Unexpected lang-lessons source fingerprint")
    if len(topics) != EXPECTED_TOPIC_COUNT:
        raise ValueError("Lang-lessons pack must contain 19 topics")

    records = [record for topic in topics for record in topic.get("records", [])]
    if len(records) != EXPECTED_ITEM_COUNT:
        raise ValueError("Lang-lessons pack must contain 86 records")
    seen: set[str] = set()
    for topic in topics:
        if topic.get("level") not in {"B1", "B2"}:
            raise ValueError(f"Unsupported source level for {topic.get('slug')}")
        if topic.get("category") not in {"phrase", "grammar"}:
            raise ValueError(f"Unsupported category for {topic.get('slug')}")
        for record in topic.get("records", []):
            original = record.get("original", {})
            question = record.get("simple_question", {})
            key = record.get("source_key")
            if not key or key in seen:
                raise ValueError("Lang-lessons source keys must be unique")
            seen.add(key)
            if set(original) != {"wrong", "right", "why"}:
                raise ValueError(f"Invalid original record: {key}")
            options = question.get("options")
            correct_index = question.get("correct_index")
            if (
                not question.get("prompt")
                or not isinstance(options, list)
                or len(options) != 2
                or not 0 <= correct_index < len(options)
                or not question.get("explanation_ru")
                or question.get("category") != topic["category"]
                or question.get("topic") != topic["slug"]
                or question.get("level") != topic["level"]
                or not question.get("fingerprint")
            ):
                raise ValueError(f"Invalid simple question overlay: {key}")
            learning = record.get("learning_item", {})
            if not all(
                learning.get(field)
                for field in ("text", "meaning_en", "meaning_ru", "example")
            ):
                raise ValueError(f"Incomplete learning-card fields: {key}")
            if learning["text"] != options[correct_index]:
                raise ValueError(f"Question answer and item text differ: {key}")
            if learning["text"].casefold() not in learning["example"].casefold():
                raise ValueError(f"Example does not contain item text: {key}")
            recall_field = (
                "target_phrase"
                if topic["category"] == "phrase"
                else "production_prompt"
            )
            if not question.get(recall_field):
                raise ValueError(f"Missing recall prompt: {key}")
            visible_text = question["prompt"] + " ".join(options)
            if any("\u0400" <= char <= "\u04ff" for char in visible_text):
                raise ValueError(f"Question prompt/options must be English: {key}")
    return pack


def _source_material(
    session: Session, owner: User, pack: dict[str, Any]
) -> tuple[SourceMaterial, bool]:
    version = pack["source"]["sha256"]
    summary = f"lang-lessons reviewed question bank v1 · sha256:{version}"
    source = session.scalar(
        select(SourceMaterial).where(
            SourceMaterial.user_id == owner.id,
            SourceMaterial.type == "lesson_notes",
            SourceMaterial.summary == summary,
        )
    )
    if source is not None:
        return source, True
    source = SourceMaterial(
        user_id=owner.id,
        type="lesson_notes",
        raw_text=json.dumps(pack["original_bank"], ensure_ascii=False, sort_keys=True),
        summary=summary,
        is_template=True,
    )
    session.add(source)
    session.flush()
    return source, False


def publish_lang_lessons(
    session: Session,
    owner: User | None = None,
    pack: dict[str, Any] | None = None,
) -> PublishSummary:
    """Publish the reviewed pack as 19 owner templates and 86 template items."""

    pack = pack or load_lang_lessons()
    owner = owner or get_seed_library_user(session)
    source, reused_source = _source_material(session, owner, pack)
    source.is_template = True

    existing_items = list(
        session.scalars(
            select(LearningItem).where(
                LearningItem.user_id == owner.id,
                LearningItem.source_material_id == source.id,
            )
        )
    )
    item_by_key = {
        (item.metadata_json or {})
        .get(PROVENANCE_METADATA_KEY, {})
        .get("source_key"): item
        for item in existing_items
        if (item.metadata_json or {}).get(PROVENANCE_METADATA_KEY, {}).get("source_key")
    }
    plan_by_slug: dict[str, LessonPlan] = {}
    for plan in session.scalars(
        select(LessonPlan).where(LessonPlan.user_id == owner.id)
    ):
        tags = plan.tags_json or []
        if PACK_TAG in tags:
            slug = next(
                (
                    tag.removeprefix("topic:")
                    for tag in tags
                    if tag.startswith("topic:")
                ),
                "",
            )
            if slug:
                plan_by_slug[slug] = plan

    created_items = reused_items = created_plans = reused_plans = 0
    for topic in pack["topics"]:
        slug = topic["slug"]
        topic_tag = f"topic:{slug}"
        plan = plan_by_slug.get(slug)
        if plan is None:
            plan = LessonPlan(
                user_id=owner.id,
                source_material_id=source.id,
                title=f"{topic['title']} · English practice",
                topic=topic["title"],
                goal=f"Practice the {topic['category']} questions in this bank.",
                level=topic["level"],
                language_focus_json=[topic["category"], slug],
                tags_json=[
                    PACK_TAG,
                    topic_tag,
                    f"level:{topic['level']}",
                    f"category:{topic['category']}",
                ],
                format="simple_questions",
                is_template=True,
                status="active",
            )
            session.add(plan)
            session.flush()
            session.add(
                LessonStep(
                    lesson_plan_id=plan.id,
                    order_index=1,
                    step_type="controlled_practice",
                    title="Short mixed practice",
                    instruction="Answer one question; read the Russian feedback.",
                    estimated_minutes=5,
                    target_skill=topic["category"],
                    metadata_json={"source": SOURCE_NAME},
                )
            )
            created_plans += 1
        else:
            reused_plans += 1
            plan.source_material_id = source.id
            plan.title = f"{topic['title']} · English practice"
            plan.topic = topic["title"]
            plan.goal = (
                f"Practice {topic['category']} questions from the lang-lessons bank."
            )
            plan.level = topic["level"]
            plan.language_focus_json = [topic["category"], slug]
            plan.tags_json = [
                PACK_TAG,
                topic_tag,
                f"level:{topic['level']}",
                f"category:{topic['category']}",
            ]
            plan.format = "simple_questions"
            plan.is_template = True
            plan.status = "active"
            session.add(plan)

        topic_items: list[LearningItem] = []
        for record in topic["records"]:
            key = record["source_key"]
            learning = record["learning_item"]
            question = record["simple_question"]
            metadata = {
                PROVENANCE_METADATA_KEY: {
                    "source": SOURCE_NAME,
                    "source_sha256": pack["source"]["sha256"],
                    "source_key": key,
                    "topic": slug,
                    "source_index": record["source_index"],
                    "original": record["original"],
                },
                QUESTION_METADATA_KEY: question,
            }
            item = item_by_key.get(key)
            if item is None:
                collision = session.scalar(
                    select(LearningItem).where(
                        LearningItem.user_id == owner.id,
                        LearningItem.type == learning["type"],
                        LearningItem.text == learning["text"],
                    )
                )
                if collision is not None:
                    collision_key = (
                        (collision.metadata_json or {})
                        .get(PROVENANCE_METADATA_KEY, {})
                        .get("source_key")
                    )
                    if collision_key != key:
                        raise ValueError(
                            "Lang-lessons item collides with an existing owner item"
                        )
                    item = collision
                    item_by_key[key] = item
                    reused_items += 1
                else:
                    item = create_learning_item(
                        session,
                        owner,
                        type_=learning["type"],
                        text=learning["text"],
                        meaning=learning["meaning_en"],
                        explanation=learning["meaning_ru"],
                        examples=[learning["example"]],
                        tags=[
                            PACK_TAG,
                            topic_tag,
                            f"level:{topic['level']}",
                            f"category:{topic['category']}",
                        ],
                        source_material_id=source.id,
                        metadata=metadata,
                    )
                    item_by_key[key] = item
                    created_items += 1
            else:
                reused_items += 1
                item.type = learning["type"]
                item.text = learning["text"]
                item.meaning = learning["meaning_en"]
                item.explanation = learning["meaning_ru"]
                item.examples = [learning["example"]]
                item.tags = [
                    PACK_TAG,
                    topic_tag,
                    f"level:{topic['level']}",
                    f"category:{topic['category']}",
                ]
                item.metadata_json = metadata
                item.source_material_id = source.id
                item.status = "active"
                session.add(item)
            item.level = topic["level"]
            item.is_template = True
            item.template_of = None
            session.add(item)
            topic_items.append(item)

        existing_links = {
            link.learning_item_id: link
            for link in session.scalars(
                select(LessonPlanItem).where(LessonPlanItem.lesson_plan_id == plan.id)
            )
        }
        for priority, item in enumerate(topic_items):
            link = existing_links.get(item.id)
            if link is None:
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
            else:
                link.role = (
                    "grammar_focus" if topic["category"] == "grammar" else "target"
                )
                link.priority = priority
                session.add(link)

    session.flush()
    return PublishSummary(
        source_id=source.id,
        templates=created_plans,
        items=created_items,
        reused_templates=reused_plans,
        reused_items=reused_items,
    )


def subscribe_lang_lessons(session: Session, user: User) -> PilotSubscribeSummary:
    """Clone each bank topic once per profile, preserving per-item source levels."""

    templates = list(
        session.scalars(
            select(LessonPlan)
            .where(
                LessonPlan.is_template.is_(True),
                LessonPlan.status == "active",
            )
            .order_by(LessonPlan.id.asc())
        )
    )
    templates = [plan for plan in templates if PACK_TAG in (plan.tags_json or [])]
    created = reused = 0
    plans: list[LessonPlan] = []
    for template in templates:
        existing = session.scalar(
            select(LessonPlan)
            .where(
                LessonPlan.user_id == user.id,
                LessonPlan.template_of == template.id,
                LessonPlan.status == "active",
            )
            .order_by(LessonPlan.id.asc())
        )
        if existing is not None:
            clone = existing
            reused += 1
        else:
            result: SubscribeResult = subscribe_to_template(session, user, template.id)
            clone = result.plan
            created += 1

        template_items = lesson_items(session, template)
        template_by_id = {item.id: item for item in template_items}
        template_by_content: dict[tuple[str, str], list[LearningItem]] = {}
        for template_item in template_items:
            template_by_content.setdefault(
                (template_item.type, template_item.text), []
            ).append(template_item)
        linked_items = list(
            session.scalars(
                select(LearningItem)
                .join(
                    LessonPlanItem,
                    LessonPlanItem.learning_item_id == LearningItem.id,
                )
                .where(LessonPlanItem.lesson_plan_id == clone.id)
                .order_by(
                    LessonPlanItem.priority.asc(), LearningItem.created_at.asc()
                )
            )
        )
        for item in linked_items:
            template_item = template_by_id.get(item.template_of or -1)
            if template_item is None:
                matches = template_by_content.get((item.type, item.text), [])
                if len(matches) != 1:
                    raise ValueError(
                        "Could not resolve a unique lang-lessons question for "
                        "a subscribed item"
                    )
                template_item = matches[0]

            expected_metadata = template_item.metadata_json or {}
            expected_question = expected_metadata.get(QUESTION_METADATA_KEY)
            expected_provenance = expected_metadata.get(PROVENANCE_METADATA_KEY)
            metadata = dict(item.metadata_json or {})
            current_question = metadata.get(QUESTION_METADATA_KEY)
            current_provenance = metadata.get(PROVENANCE_METADATA_KEY)
            if current_question is not None and (
                current_question.get("fingerprint")
                != (expected_question or {}).get("fingerprint")
            ):
                raise ValueError(
                    "Lang-lessons subscription conflicts with an existing "
                    "simple question for the same item"
                )
            if current_provenance is not None and (
                current_provenance.get("source_key")
                != (expected_provenance or {}).get("source_key")
                or current_provenance.get("source_sha256")
                != (expected_provenance or {}).get("source_sha256")
            ):
                raise ValueError(
                    "Lang-lessons subscription conflicts with existing item "
                    "provenance"
                )

            metadata[QUESTION_METADATA_KEY] = expected_question
            metadata[PROVENANCE_METADATA_KEY] = expected_provenance
            if metadata != (item.metadata_json or {}):
                item.metadata_json = metadata
                session.add(item)

            if item.template_of == template_item.id:
                item.level = template_item.level
                session.add(item)
        plans.append(clone)
    session.flush()
    return PilotSubscribeSummary(tuple(plans), created, reused)


def record_fingerprint(
    topic: str, original: dict[str, str], question: dict[str, Any]
) -> str:
    canonical = {
        "topic": topic,
        "original": original,
        "prompt": question["prompt"],
        "options": sorted(option.strip().casefold() for option in question["options"]),
    }
    payload = json.dumps(
        canonical, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
