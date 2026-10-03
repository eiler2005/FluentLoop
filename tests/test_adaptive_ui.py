"""Learner-facing adaptive roadmap and question-report controls."""

from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace

from sqlalchemy import select

from fluentloop.adaptive_learning import curriculum_progress
from fluentloop.bot.handlers import (
    handle_favorite_toggle,
    handle_items,
    handle_lesson,
    handle_lessons,
    handle_library,
    handle_library_callback,
    handle_more,
    handle_plan,
    handle_progress,
    handle_simple_answer,
    handle_simple_bonus_text,
    handle_simple_issue,
    handle_simple_more_menu,
    handle_subscribe,
    handle_topics,
    handle_words,
)
from fluentloop.db.models import PracticeSession
from fluentloop.learning import create_learning_item
from fluentloop.learning_prefs import set_learning_mode
from fluentloop.lesson_library import publish_lesson_template
from fluentloop.lesson_plans import create_lesson_plan_from_source
from fluentloop.materials import store_material
from fluentloop.simple_learning import start_stream
from fluentloop.telegram_bot_api import BOT_COMMANDS
from fluentloop.users import ensure_user


def _actions(reply) -> set[str]:
    return {button.data for row in reply.buttons or [] for button in row}


def test_simple_progress_and_plan_show_topic_gaps_without_certification(
    db_session, settings
):
    user = ensure_user(db_session, 123456789, settings)
    set_learning_mode(db_session, user, "simple")

    progress = handle_progress(db_session, user)
    plan = handle_plan(db_session, user)

    assert "Узнавание: 0/0" in progress.text
    assert "Письменная практика: 0/0" in progress.text
    assert "B2 → B2+ → C1 intro" in progress.text
    assert "практика 0/5" in progress.text
    assert "перенос 0/1" in progress.text
    assert "письмо на следующей ступени" in progress.text
    assert "CEFR" in progress.text
    assert len(progress.text) < 4096
    assert "Следующая тема:" in plan.text
    assert "Следующий шаг: практика" in plan.text
    assert "C1 intro: откроется" in plan.text
    assert "Пробелы:" in plan.text
    assert "CEFR" in plan.text
    assert len(plan.text) < 4096
    assert {"simple:study", "simple:progress"} <= _actions(plan)


def test_plan_is_available_without_changing_legacy_advanced_progress(
    db_session, settings
):
    user = ensure_user(db_session, 123456789, settings)

    legacy = handle_progress(db_session, user)
    roadmap = handle_plan(db_session, user)
    menu = handle_simple_more_menu(db_session, user)

    assert "Темы · B2" not in legacy.text
    assert "План обучения" in roadmap.text
    assert "simple:plan" in _actions(menu)
    assert {"/progress", "/plan"} <= {f"/{name}" for name, _ in BOT_COMMANDS}


def test_simple_progress_is_personal_and_origin_target_is_preserved(
    db_session, settings
):
    owner = ensure_user(db_session, 123456789, settings)
    other = ensure_user(db_session, 123456790, settings)
    set_learning_mode(db_session, owner, "simple")
    set_learning_mode(db_session, other, "simple")
    create_learning_item(
        db_session,
        owner,
        type_="expression",
        text="align on",
        metadata={
            "simple_question": {
                "prompt": "Choose the correct phrase: align on",
                "options": ["align on", "align with"],
                "correct_index": 0,
                "explanation_ru": "После align используется on.",
                "category": "phrase",
            }
        },
    )
    step = start_stream(db_session, owner)
    handle_simple_answer(db_session, owner, step.run.id, step.index, 0)

    first = handle_progress(
        db_session, owner, channel_id="-1001234567890", message_thread_id=44
    )
    second = handle_progress(db_session, other)
    plan = handle_plan(
        db_session, owner, channel_id="-1001234567890", message_thread_id=44
    )

    assert "Узнавание: 1/1" in first.text
    assert "Узнавание: 0/0" in second.text
    assert first.target_chat_id == plan.target_chat_id == "-1001234567890"
    assert first.message_thread_id == plan.message_thread_id == 44
    assert second.target_chat_id is None


def test_answer_feedback_reports_only_own_question_once(db_session, settings):
    owner = ensure_user(db_session, 123456789, settings)
    other = ensure_user(db_session, 123456790, settings)
    item = create_learning_item(
        db_session,
        owner,
        type_="expression",
        text="align on",
        metadata={
            "simple_question": {
                "prompt": "Choose the correct phrase: align on",
                "options": ["align on", "align with"],
                "correct_index": 0,
                "explanation_ru": "После align используется on.",
                "category": "phrase",
            }
        },
    )
    step = start_stream(db_session, owner)

    assert (
        "недоступен"
        in handle_simple_issue(db_session, owner, step.run.id, step.index).text
    )
    answer = handle_simple_answer(db_session, owner, step.run.id, step.index, 0)
    assert f"simple:issue:{step.run.id}:{step.index}" in _actions(answer)
    assert (
        "недоступен"
        in handle_simple_issue(db_session, other, step.run.id, step.index).text
    )

    reported = handle_simple_issue(db_session, owner, step.run.id, step.index)
    repeated = handle_simple_issue(db_session, owner, step.run.id, step.index)

    assert "временно исключён" in reported.text
    assert reported.edit_message is True
    assert "уже отмечен" in repeated.text
    assert item.metadata_json["simple_question"]["quality_status"] == "quarantined"


def test_progress_renders_transfer_and_production_without_unsafe_html(
    db_session, settings, monkeypatch
):
    user = ensure_user(db_session, 123456789, settings)
    set_learning_mode(db_session, user, "simple")
    original = curriculum_progress(db_session, user)
    topic = replace(
        original.topics[0],
        title="Risk <owner> & alignment",
        stage="b2_plus",
        practice_successes=5,
        practice_accuracy=0.8,
        transfer_successes=1,
        transfer_required=2,
        production_successes=0,
        production_required=1,
        repair=True,
        next_action="production",
    )
    changed = replace(original, topics=(topic, *original.topics[1:]))
    monkeypatch.setattr(
        "fluentloop.adaptive_learning.curriculum_progress",
        lambda session, user: changed,
    )

    progress = handle_progress(db_session, user)
    plan = handle_plan(db_session, user)

    assert "Risk &lt;owner&gt; &amp; alignment · B2+" in progress.text
    assert "практика 5/5, точность 80%" in progress.text
    assert "перенос 1/2, письмо 0/1" in progress.text
    assert "→ своё предложение" in progress.text
    assert "Следующий шаг: своё предложение" in plan.text
    assert "Risk &lt;owner&gt; &amp; alignment" in plan.text


def test_adaptive_answer_keys_stay_out_of_generic_previews(db_session, settings):
    user = ensure_user(db_session, 123456789, settings)
    material = store_material(db_session, user, "# Adaptive grammar topic")
    hidden = create_learning_item(
        db_session,
        user,
        type_="expression",
        text="UNSEEN_TRANSFER_ANSWER",
        source_material_id=material.id,
        metadata={"adaptive_curriculum": True},
    )
    plan = create_lesson_plan_from_source(db_session, user, material)
    plan.title = "UNSEEN_TRANSFER_ANSWER"
    plan.topic = "UNSEEN_TRANSFER_ANSWER"
    plan.goal = "UNSEEN_TRANSFER_ANSWER"
    plan.language_focus_json = ["UNSEEN_TRANSFER_ANSWER"]

    assert (
        "UNSEEN_TRANSFER_ANSWER"
        not in handle_lesson(db_session, user, str(plan.id)).text
    )
    assert "UNSEEN_TRANSFER_ANSWER" not in handle_lessons(db_session, user).text
    assert "UNSEEN_TRANSFER_ANSWER" not in handle_topics(db_session, user).text
    assert "UNSEEN_TRANSFER_ANSWER" not in handle_items(db_session, user).text
    assert "UNSEEN_TRANSFER_ANSWER" not in handle_words(db_session, user).text
    assert (
        "Learning item not found"
        in handle_favorite_toggle(db_session, user, hidden.id).text
    )
    assert (
        "Nothing to expand"
        in handle_more(db_session, user, "UNSEEN_TRANSFER_ANSWER").text
    )
    started = handle_lesson(db_session, user, f"start {plan.id}")
    assert "/study" in started.text and "/plan" in started.text
    assert "UNSEEN_TRANSFER_ANSWER" not in started.text
    assert db_session.scalar(select(PracticeSession)) is None

    publish_lesson_template(db_session, user, plan.id)
    other = ensure_user(db_session, 123456790, settings)
    assert "UNSEEN_TRANSFER_ANSWER" not in handle_library(db_session, other).text
    assert (
        "UNSEEN_TRANSFER_ANSWER"
        not in handle_library_callback(db_session, other, "details", str(plan.id)).text
    )
    assert (
        "UNSEEN_TRANSFER_ANSWER"
        not in handle_subscribe(db_session, other, plan.id).text
    )


def test_unverified_adaptive_writing_is_shown_as_saved_not_scored(
    db_session, settings, monkeypatch
):
    user = ensure_user(db_session, 123456789, settings)
    feedback = SimpleNamespace(
        status="correct",
        genuine_evaluation=False,
        model_dump=lambda: {"status": "correct", "genuine_evaluation": False},
    )
    monkeypatch.setattr("fluentloop.bot.handlers.check_answer", lambda *args: feedback)
    monkeypatch.setattr(
        "fluentloop.simple_learning.submit_bonus",
        lambda *args: SimpleNamespace(
            accepted=True, attempt=SimpleNamespace(status="unchecked")
        ),
    )
    bonus = SimpleNamespace(id=1, exercises=[{"adaptive": {"stage": "b2_plus"}}])

    reply = handle_simple_bonus_text(
        db_session, user, object(), bonus, "My own sentence."
    )

    assert "проверка сейчас недоступна" in reply.text
    assert "не засчитана" in reply.text
    assert "Correct" not in reply.text


def test_tagged_empty_adaptive_plan_keeps_safe_topic_and_blocks_generic_start(
    db_session, settings
):
    from fluentloop.db.models import LessonPlan

    user = ensure_user(db_session, 123456789, settings)
    plan = LessonPlan(
        user_id=user.id,
        title="HIDDEN_MODEL_SENTENCE",
        goal="HIDDEN_MODEL_SENTENCE",
        topic="HIDDEN_MODEL_SENTENCE",
        tags_json=["adaptive_curriculum:v1", "topic:aspect"],
        format="adaptive_questions",
        status="active",
    )
    db_session.add(plan)
    db_session.flush()
    details = handle_lesson(db_session, user, str(plan.id))
    assert "HIDDEN_MODEL_SENTENCE" not in details.text
    assert "B2 → C1 intro" in details.text
    assert "/study" in handle_lesson(db_session, user, f"start {plan.id}").text
    assert db_session.scalar(select(PracticeSession)) is None
