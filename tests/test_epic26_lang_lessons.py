from __future__ import annotations

import json

from sqlalchemy import select

from fluentloop.db.models import (
    LearningItem,
    LessonPlan,
    LessonPlanItem,
    ReviewState,
    SourceMaterial,
)
from fluentloop.lang_lessons import (
    PACK_TAG,
    PROVENANCE_METADATA_KEY,
    QUESTION_METADATA_KEY,
    load_lang_lessons,
    publish_lang_lessons,
    record_fingerprint,
    subscribe_lang_lessons,
)
from fluentloop.learning import create_learning_item
from fluentloop.lesson_library import get_seed_library_user
from fluentloop.lesson_plans import lesson_items
from fluentloop.users import ensure_user


def test_lang_lessons_pack_preserves_source_and_validates_curated_overlays() -> None:
    pack = load_lang_lessons()
    topics = pack["topics"]
    records = [record for topic in topics for record in topic["records"]]

    assert pack["source"]["name"] == "lang-lessons/errors_bank.json"
    assert len(topics) == 19
    assert len(records) == 86
    assert sum(topic["level"] == "B1" for topic in topics) == 10
    assert sum(topic["level"] == "B2" for topic in topics) == 9
    assert (
        sum(len(topic["records"]) for topic in topics if topic["category"] == "grammar")
        == 48
    )
    assert (
        sum(len(topic["records"]) for topic in topics if topic["category"] == "phrase")
        == 38
    )
    assert sum(
        len(topic["records"])
        for topic in topics
        if topic["level"] == "B1" and topic["category"] == "grammar"
    ) == 40
    assert sum(
        len(topic["records"])
        for topic in topics
        if topic["level"] == "B1" and topic["category"] == "phrase"
    ) == 5
    assert sum(
        len(topic["records"])
        for topic in topics
        if topic["level"] == "B2" and topic["category"] == "grammar"
    ) == 8
    assert sum(
        len(topic["records"])
        for topic in topics
        if topic["level"] == "B2" and topic["category"] == "phrase"
    ) == 33

    original_bank = pack["original_bank"]
    assert sum(len(topic["errors"]) for topic in original_bank["topics"].values()) == 86
    assert {"audience", "levels", "note"} <= set(original_bank["meta"])

    fingerprints = set()
    phrase_targets = grammar_prompts = 0
    for topic in topics:
        for record in topic["records"]:
            question = record["simple_question"]
            assert set(record["original"]) == {"wrong", "right", "why"}
            assert question["category"] == topic["category"]
            assert question["topic"] == topic["slug"]
            assert question["level"] == topic["level"]
            assert question["fingerprint"] == record_fingerprint(
                topic["slug"], record["original"], question
            )
            assert question["fingerprint"] not in fingerprints
            fingerprints.add(question["fingerprint"])
            if topic["category"] == "phrase":
                assert question["target_phrase"].strip()
                phrase_targets += 1
            else:
                assert question["production_prompt"].startswith(
                    ("Make", "Say", "Ask", "Describe", "Introduce", "Tell", "Give")
                )
                grammar_prompts += 1
    assert (phrase_targets, grammar_prompts) == (38, 48)
    assert all(
        not any(
            "\u0400" <= char <= "\u04ff"
            for char in record["simple_question"]["prompt"]
            + " ".join(record["simple_question"]["options"])
        )
        for record in records
    )

    stop_smoking = next(
        record
        for topic in topics
        if topic["slug"] == "gerund-infinitive"
        for record in topic["records"]
        if record["source_index"] == 4
    )
    assert stop_smoking["original"]["wrong"].startswith("I stopped to smoke")
    assert stop_smoking["simple_question"]["prompt"].startswith(
        "You mean that you quit the habit"
    )
    assert stop_smoking["simple_question"]["explanation_ru"].startswith(
        "Для значения «бросить курить»"
    )


def test_lang_lessons_publish_is_idempotent_and_creates_per_item_srs_rows(
    db_session,
) -> None:
    owner = get_seed_library_user(db_session)
    first = publish_lang_lessons(db_session, owner)
    db_session.flush()
    second = publish_lang_lessons(db_session, owner)
    db_session.flush()

    templates = list(
        db_session.scalars(
            select(LessonPlan).where(
                LessonPlan.user_id == owner.id,
                LessonPlan.is_template.is_(True),
            )
        )
    )
    items = list(
        db_session.scalars(
            select(LearningItem).where(
                LearningItem.user_id == owner.id,
                LearningItem.is_template.is_(True),
            )
        )
    )
    sources = list(
        db_session.scalars(
            select(SourceMaterial).where(
                SourceMaterial.user_id == owner.id,
                SourceMaterial.is_template.is_(True),
            )
        )
    )

    assert (first.templates, first.items) == (19, 86)
    assert (second.templates, second.items) == (0, 0)
    assert (second.reused_templates, second.reused_items) == (19, 86)
    assert len([plan for plan in templates if PACK_TAG in plan.tags_json]) == 19
    assert len(items) == 86
    assert len(sources) == 1
    assert all(item.source_material_id == first.source_id for item in items)
    assert {item.level for item in items} == {"B1", "B2"}
    assert all(QUESTION_METADATA_KEY in item.metadata_json for item in items)
    assert all(PROVENANCE_METADATA_KEY in item.metadata_json for item in items)

    raw_bank = json.loads(sources[0].raw_text)
    assert sum(len(topic["errors"]) for topic in raw_bank["topics"].values()) == 86
    linked = db_session.scalar(
        select(LessonPlanItem).where(LessonPlanItem.lesson_plan_id == templates[0].id)
    )
    assert linked is not None


def test_lang_lessons_subscribe_reuses_one_plan_and_preserves_source_levels(
    db_session, settings
) -> None:
    owner = get_seed_library_user(db_session)
    publish_lang_lessons(db_session, owner)
    pilot = ensure_user(db_session, 123456789, settings)

    first = subscribe_lang_lessons(db_session, pilot)
    second = subscribe_lang_lessons(db_session, pilot)

    assert len(first.plans) == 19
    assert (first.created_plans, first.reused_plans) == (19, 0)
    assert (second.created_plans, second.reused_plans) == (0, 19)
    assert {plan.id for plan in first.plans} == {plan.id for plan in second.plans}

    clones = list(
        db_session.scalars(
            select(LessonPlan).where(
                LessonPlan.user_id == pilot.id,
                LessonPlan.template_of.is_not(None),
                LessonPlan.status == "active",
            )
        )
    )
    assert len([plan for plan in clones if PACK_TAG in plan.tags_json]) == 19
    clone_items = [item for plan in clones for item in lesson_items(db_session, plan)]
    assert len(clone_items) == 86
    assert all(
        item.user_id == pilot.id and not item.is_template for item in clone_items
    )
    assert {item.level for item in clone_items} == {"B1", "B2"}
    assert all(QUESTION_METADATA_KEY in item.metadata_json for item in clone_items)


def test_lang_lessons_subscribe_adds_questions_to_matching_personal_items(
    db_session, settings
) -> None:
    owner = get_seed_library_user(db_session)
    publish_lang_lessons(db_session, owner)
    pilot = ensure_user(db_session, 123456789, settings)
    pack = load_lang_lessons()
    first_topic = pack["topics"][0]
    first_record = first_topic["records"][0]
    learning = first_record["learning_item"]
    personal = create_learning_item(
        db_session,
        pilot,
        type_=learning["type"],
        text=learning["text"],
        meaning="My curated gloss",
        explanation="My own note",
        examples=["My own example."],
        tags=["personal-tag"],
        metadata={"personal": "keep this"},
    )
    personal.status = "paused"
    personal.level = "C1"
    personal.is_favorite = True
    review = db_session.get(ReviewState, personal.id)
    assert review is not None
    review.review_count = 7
    review.fail_count = 2
    review.success_count = 5
    db_session.flush()

    subscribed = subscribe_lang_lessons(db_session, pilot)
    db_session.flush()

    assert len(subscribed.plans) == 19
    assert personal.meaning == "My curated gloss"
    assert personal.explanation == "My own note"
    assert personal.examples == ["My own example."]
    assert personal.tags == ["personal-tag"]
    assert personal.status == "paused"
    assert personal.level == "C1"
    assert personal.is_favorite is True
    assert personal.template_of is None
    assert personal.metadata_json["personal"] == "keep this"
    assert personal.metadata_json[QUESTION_METADATA_KEY]["fingerprint"] == (
        first_record["simple_question"]["fingerprint"]
    )
    assert personal.metadata_json[PROVENANCE_METADATA_KEY]["source_key"] == (
        first_record["source_key"]
    )
    assert (review.review_count, review.fail_count, review.success_count) == (7, 2, 5)

    all_items = list(
        db_session.scalars(select(LearningItem).where(LearningItem.user_id == pilot.id))
    )
    bank_questions = [
        item
        for item in all_items
        if (item.metadata_json or {}).get(PROVENANCE_METADATA_KEY, {}).get(
            "source_key"
        )
    ]
    assert len(bank_questions) == 86
    assert all(QUESTION_METADATA_KEY in item.metadata_json for item in bank_questions)


def test_lang_lessons_subscribe_surfaces_conflicting_personal_question(
    db_session, settings
) -> None:
    owner = get_seed_library_user(db_session)
    publish_lang_lessons(db_session, owner)
    pilot = ensure_user(db_session, 123456789, settings)
    record = load_lang_lessons()["topics"][0]["records"][0]
    learning = record["learning_item"]
    create_learning_item(
        db_session,
        pilot,
        type_=learning["type"],
        text=learning["text"],
        metadata={QUESTION_METADATA_KEY: {"fingerprint": "different-question"}},
    )

    try:
        subscribe_lang_lessons(db_session, pilot)
    except ValueError as exc:
        assert "conflicts with an existing simple question" in str(exc)
    else:
        raise AssertionError("conflicting question overlay should not be replaced")
