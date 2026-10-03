from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import pytest
from sqlalchemy import func, select

from fluentloop.adaptive_curriculum import (
    ADAPTIVE_TOPICS,
    PACK_TAG,
    STAGES,
    content_fingerprint,
    load_adaptive_curriculum,
    publish_adaptive_curriculum,
    subscribe_adaptive_curriculum,
    validate_adaptive_curriculum,
)
from fluentloop.db.models import LearningItem, LessonStep, ReviewState, User
from fluentloop.db.session import make_engine, make_session_factory
from fluentloop.lang_lessons import load_lang_lessons, publish_lang_lessons
from fluentloop.learning import create_learning_item
from fluentloop.lesson_library import get_seed_library_user
from fluentloop.lesson_plans import lesson_items
from fluentloop.users import ensure_user


def _resign(pack):
    canonical = {key: value for key, value in pack.items() if key != "content_sha256"}
    pack["content_sha256"] = hashlib.sha256(
        json.dumps(
            canonical, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode()
    ).hexdigest()
    return pack


def test_reviewed_pack_has_independent_stage_practice_and_transfer_coverage():
    pack = load_adaptive_curriculum()
    assert tuple(topic["slug"] for topic in pack["topics"]) == ADAPTIVE_TOPICS
    records = [record for topic in pack["topics"] for record in topic["records"]]
    assert len(records) == 270
    assert len({record["learning_item"]["text"] for record in records}) == 270
    assert len({record["simple_question"]["prompt"] for record in records}) == 270
    assert len({record["simple_question"]["fingerprint"] for record in records}) == 270
    for topic in pack["topics"]:
        assert len(topic["stages"]) == 3
        for stage in STAGES:
            questions = [
                record["simple_question"]
                for record in topic["records"]
                if record["simple_question"]["adaptive"]["stage"] == stage
            ]
            assert len(questions) == 9
            assert (
                sum(
                    question["adaptive"]["role"] == "practice" for question in questions
                )
                == 6
            )
            assert (
                sum(
                    question["adaptive"]["role"] == "transfer" for question in questions
                )
                == 3
            )
            assert {question["correct_index"] for question in questions} == {0, 1}
            for question in questions:
                assert question["fingerprint"] == content_fingerprint(question)
                assert question["production_prompt"]
                assert question["target_construction"]
                correct = question["options"][question["correct_index"]]
                assert (
                    correct.casefold().strip(".") not in question["prompt"].casefold()
                )
                if question["category"] == "phrase":
                    assert question["target_phrase"].casefold() in correct.casefold()
    assert "not a CEFR certification" in pack["calibration"]
    assert sum(len(topic["records"]) for topic in load_lang_lessons()["topics"]) == 86


@pytest.mark.parametrize(
    "mutation",
    [
        "checksum",
        "missing_stage",
        "missing_transfer",
        "duplicate_prompt",
        "boolean_index",
        "wrong_topic",
        "fingerprint",
        "missing_gloss",
        "answer_collision",
        "russian_prompt",
    ],
)
def test_pack_rejects_content_or_contract_corruption(mutation):
    pack = copy.deepcopy(load_adaptive_curriculum())
    topic = pack["topics"][0]
    record = topic["records"][0]
    question = record["simple_question"]
    if mutation == "checksum":
        question["prompt"] += " changed"
        with pytest.raises(ValueError, match="fingerprint mismatch"):
            validate_adaptive_curriculum(pack)
        return
    if mutation == "missing_stage":
        topic["stages"].pop()
    elif mutation == "missing_transfer":
        topic["records"].pop()
    elif mutation == "duplicate_prompt":
        question["prompt"] = topic["records"][1]["simple_question"]["prompt"]
        question["fingerprint"] = content_fingerprint(question)
    elif mutation == "boolean_index":
        question["correct_index"] = False
    elif mutation == "wrong_topic":
        question["adaptive"]["topic_id"] = "different"
    elif mutation == "fingerprint":
        question["fingerprint"] = "wrong"
    elif mutation == "missing_gloss":
        record["learning_item"]["meaning_ru"] = ""
    elif mutation == "answer_collision":
        duplicate = topic["records"][1]["learning_item"]
        record["learning_item"] = dict(duplicate)
        question["options"][question["correct_index"]] = duplicate["text"]
        question["fingerprint"] = content_fingerprint(question)
    elif mutation == "russian_prompt":
        question["prompt"] = "Выберите правильный вариант."
        question["fingerprint"] = content_fingerprint(question)
    with pytest.raises(ValueError):
        validate_adaptive_curriculum(_resign(pack))


def test_publish_and_subscribe_are_idempotent_and_preserve_legacy_bank(
    db_session, settings
):
    owner = get_seed_library_user(db_session)
    legacy = publish_lang_lessons(db_session, owner)
    first = publish_adaptive_curriculum(db_session, owner)
    second = publish_adaptive_curriculum(db_session, owner)
    assert (first.templates, first.items) == (10, 270)
    assert (second.templates, second.items) == (0, 0)
    assert (second.reused_templates, second.reused_items) == (10, 270)
    assert (
        db_session.scalar(
            select(func.count())
            .select_from(LearningItem)
            .where(
                LearningItem.source_material_id == legacy.source_id,
            )
        )
        == 86
    )
    pilot = ensure_user(db_session, 123456789, settings)
    subscribed = subscribe_adaptive_curriculum(db_session, pilot)
    repeated = subscribe_adaptive_curriculum(db_session, pilot)
    assert (subscribed.created_plans, subscribed.reused_plans) == (10, 0)
    assert (repeated.created_plans, repeated.reused_plans) == (0, 10)
    assert {plan.id for plan in subscribed.plans} == {
        plan.id for plan in repeated.plans
    }
    cards = [
        item for plan in subscribed.plans for item in lesson_items(db_session, plan)
    ]
    assert len(cards) == 270
    assert all(not item.is_template and item.user_id == pilot.id for item in cards)
    assert {item.level for item in cards} == {"B2", "B2+", "C1-intro"}
    assert (
        sum(
            item.metadata_json["adaptive_curriculum"]["role"] == "transfer"
            for item in cards
        )
        == 90
    )
    assert all(db_session.get(ReviewState, item.id) is not None for item in cards)
    for plan in subscribed.plans:
        assert PACK_TAG in plan.tags_json
        steps = list(
            db_session.scalars(
                select(LessonStep).where(LessonStep.lesson_plan_id == plan.id)
            )
        )
        assert len(steps) == 3
        assert {step.metadata_json["stage"] for step in steps} == set(STAGES)
        assert all("original workplace sentences" in step.instruction for step in steps)


def test_subscribe_preserves_curated_practice_card_and_srs(db_session, settings):
    publish_adaptive_curriculum(db_session)
    pilot = ensure_user(db_session, 123456789, settings)
    record = load_adaptive_curriculum()["topics"][0]["records"][0]
    learning = record["learning_item"]
    personal = create_learning_item(
        db_session,
        pilot,
        type_=learning["type"],
        text=learning["text"],
        meaning="Curated English gloss",
        explanation="Curated note",
        examples=["Curated example"],
        tags=["personal"],
        metadata={"personal": True},
    )
    personal.status = "suspended"
    personal.level = "C1"
    review = db_session.get(ReviewState, personal.id)
    review.review_count = 8
    review.success_count = 6
    subscribed = subscribe_adaptive_curriculum(db_session, pilot)
    assert len(subscribed.plans) == 10
    assert personal.meaning == "Curated English gloss"
    assert personal.explanation == "Curated note"
    assert personal.examples == ["Curated example"]
    assert personal.tags == ["personal"]
    assert personal.status == "suspended"
    assert personal.level == "C1"
    assert personal.metadata_json["personal"] is True
    assert personal.metadata_json["simple_question"] == record["simple_question"]
    assert (review.review_count, review.success_count) == (8, 6)


def test_previously_available_transfer_cannot_be_reclassified_as_held_out(
    db_session, settings
):
    publish_adaptive_curriculum(db_session)
    pilot = ensure_user(db_session, 123456789, settings)
    record = load_adaptive_curriculum()["topics"][0]["records"][6]
    learning = record["learning_item"]
    personal = create_learning_item(
        db_session, pilot, type_=learning["type"], text=learning["text"]
    )
    with pytest.raises(ValueError, match="previously available"):
        subscribe_adaptive_curriculum(db_session, pilot)
    assert not personal.metadata_json


def test_conflicting_practice_question_is_not_overwritten(db_session, settings):
    publish_adaptive_curriculum(db_session)
    pilot = ensure_user(db_session, 123456789, settings)
    record = load_adaptive_curriculum()["topics"][0]["records"][0]
    learning = record["learning_item"]
    personal = create_learning_item(
        db_session,
        pilot,
        type_=learning["type"],
        text=learning["text"],
        metadata={"simple_question": {"fingerprint": "different"}},
    )
    with pytest.raises(ValueError, match="conflicts"):
        subscribe_adaptive_curriculum(db_session, pilot)
    assert personal.metadata_json == {"simple_question": {"fingerprint": "different"}}


def test_importer_dry_run_does_not_load_runtime_settings(monkeypatch, capsys):
    script = (
        Path(__file__).resolve().parents[1]
        / "scripts"
        / "import_adaptive_curriculum.py"
    )
    spec = importlib.util.spec_from_file_location("import_adaptive_curriculum", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(sys, "argv", [str(script)])
    monkeypatch.setattr(
        "fluentloop.config.get_settings", lambda: pytest.fail("dry run loaded settings")
    )
    assert module.main() == 0
    output = capsys.readouterr().out
    assert "topics=10 stages=30 items=270 practice=180 transfer=90" in output


@pytest.mark.parametrize(
    "arguments",
    [
        ["--subscribe-pilot"],
        ["--enable-simple"],
        ["--apply", "--enable-simple"],
    ],
)
def test_importer_requires_explicit_apply_for_pilot_mutations(monkeypatch, arguments):
    script = (
        Path(__file__).resolve().parents[1]
        / "scripts"
        / "import_adaptive_curriculum.py"
    )
    spec = importlib.util.spec_from_file_location(
        "import_adaptive_curriculum_flags", script
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(sys, "argv", [str(script), *arguments])
    with pytest.raises(SystemExit) as exc:
        module.main()
    assert exc.value.code == 2


def test_importer_pilot_opt_in_is_explicit_and_preserves_other_preferences(
    monkeypatch, settings, tmp_path, capsys
):
    database_url = f"sqlite:///{tmp_path / 'pilot.sqlite3'}"
    factory = make_session_factory(make_engine(database_url))
    with factory() as session, session.begin():
        owner = get_seed_library_user(session)
        owner.preferences_json = {"learning": {"mode": "advanced"}, "keep": True}
        pilot = ensure_user(session, 123456789, settings)
        pilot.preferences_json = {
            "learning": {"mode": "advanced", "custom": "keep"},
            "vocab_loop": {"enabled": False},
        }
    script = (
        Path(__file__).resolve().parents[1]
        / "scripts"
        / "import_adaptive_curriculum.py"
    )
    spec = importlib.util.spec_from_file_location(
        "import_adaptive_curriculum_apply", script
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr("fluentloop.config.get_settings", lambda: settings)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            str(script),
            "--apply",
            "--subscribe-pilot",
            "--enable-simple",
            "--db-url",
            database_url,
        ],
    )
    assert module.main() == 0
    assert module.main() == 0
    with factory() as session:
        pilot = session.scalar(select(User).where(User.telegram_user_id == 123456789))
        assert pilot.preferences_json == {
            "learning": {
                "mode": "simple",
                "custom": "keep",
                "adaptive_auto_expand": True,
            },
            "vocab_loop": {"enabled": False},
        }
        owner = get_seed_library_user(session)
        assert owner.preferences_json == {
            "learning": {"mode": "advanced"},
            "keep": True,
        }
        assert (
            session.scalar(
                select(func.count())
                .select_from(LearningItem)
                .where(
                    LearningItem.user_id == pilot.id,
                )
            )
            == 270
        )
    output = capsys.readouterr().out
    assert "templates=0 reused_templates=10 items=0 reused_items=270" in output
