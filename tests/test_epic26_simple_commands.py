from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace

from sqlalchemy import select

from fluentloop.ai.provider import StubProvider
from fluentloop.bot.app import (
    _active_simple_bonus_for_state,
    _cancel_simple_answering,
    _keyboard_action_clears_capture,
    _should_clear_simple_bonus_state,
    _simple_bonus_topic_matches,
    _simple_event_authorized,
    _simple_sender_allowed,
    _start_upload_capture,
)
from fluentloop.bot.handlers import (
    handle_answer,
    handle_feedback_explain,
    handle_help,
    handle_practice,
    handle_progress,
    handle_simple_answer,
    handle_simple_bonus_skip,
    handle_simple_bonus_start,
    handle_simple_bonus_text,
    handle_simple_mode_change,
    handle_simple_text_guard,
    handle_start,
    handle_stop,
    handle_study,
    handle_today_entry,
    quick_action_for,
)
from fluentloop.bot.state import StateStore
from fluentloop.db.models import LearningItem, PracticeAttempt, PracticeSession
from fluentloop.learning import create_learning_item
from fluentloop.learning_prefs import get_learning_mode, set_learning_mode
from fluentloop.simple_learning import get_active_stream, start_stream
from fluentloop.telegram_bot_api import BOT_COMMANDS, reply_keyboard
from fluentloop.users import ensure_user
from fluentloop.vocab_prefs import get_prefs, update_pref


def _question_item(session, user, text: str = "align on"):
    return create_learning_item(
        session,
        user,
        type_="expression",
        text=text,
        metadata={
            "simple_question": {
                "prompt": f"Choose the correct phrase: {text}",
                "options": [text, "align with"],
                "correct_index": 0,
                "explanation_ru": "После align используется on.",
                "category": "phrase",
            }
        },
    )


def _button_data(reply):
    return {
        button.data for row in (reply.buttons or []) for button in row if button.data
    }


def test_simple_start_bypasses_wizard_and_exposes_compact_actions(db_session, settings):
    user = ensure_user(db_session, 123456789, settings)
    set_learning_mode(db_session, user, "simple")

    reply = handle_start(db_session, settings, user.telegram_user_id)
    keyboard = reply_keyboard(reply)

    assert reply.simple_keyboard is True
    assert "Учиться" in reply.text and "/study" in reply.text
    assert keyboard["keyboard"] == [
        [{"text": "Учиться"}, {"text": "Прогресс"}, {"text": "Ещё"}]
    ]
    assert quick_action_for("Учиться") == "study"
    assert quick_action_for("Прогресс") == "progress"
    assert quick_action_for("Ещё") == "simple_menu"
    help_reply = handle_help(user)
    assert "/study" in help_reply.text
    assert "baseline" not in help_reply.text.lower()


def test_today_routes_by_saved_mode_and_advanced_default_is_preserved(
    db_session, settings
):
    user = ensure_user(db_session, 123456789, settings)
    _question_item(db_session, user)

    assert get_learning_mode(user) == "advanced"
    advanced = handle_today_entry(db_session, user)
    assert "Choose" in advanced.text or advanced.buttons

    set_learning_mode(db_session, user, "simple")
    simple = handle_today_entry(db_session, user)
    assert "Вопрос 1" in simple.text
    assert "simple:answer:" in " ".join(_button_data(simple))
    assert any(data.startswith("simple:stop:") for data in _button_data(simple))
    assert {"study", "progress"}.issubset({name for name, _ in BOT_COMMANDS})


def test_choice_edits_feedback_then_returns_next_question_in_origin_topic(
    db_session, settings
):
    user = ensure_user(db_session, 123456789, settings)
    _question_item(db_session, user, "align on")
    _question_item(db_session, user, "account for")
    step = start_stream(db_session, user)

    reply = handle_simple_answer(
        db_session,
        user,
        step.run.id,
        step.index,
        0,
        channel_id="-1001234567890",
        message_thread_id=44,
    )

    assert reply.edit_message is True
    assert "✅ Верно" in reply.text
    assert any(data.startswith("feedback:explain:") for data in _button_data(reply))
    detail_attempt_id = int(
        next(
            data for data in _button_data(reply) if data.startswith("feedback:explain:")
        ).split(":")[2]
    )
    details = handle_feedback_explain(
        db_session,
        user,
        detail_attempt_id,
        channel_id="-1001234567890",
        message_thread_id=44,
    )
    assert details.target_chat_id == "-1001234567890"
    assert details.message_thread_id == 44
    assert len(reply.extra_replies) == 1
    next_reply = reply.extra_replies[0]
    assert next_reply.target_chat_id == "-1001234567890"
    assert next_reply.message_thread_id == 44
    assert "Вопрос 2" in next_reply.text
    assert "24" not in next_reply.text


def test_stop_closes_stream_and_free_text_is_not_captured_as_a_word(
    db_session, settings
):
    user = ensure_user(db_session, 123456789, settings)
    _question_item(db_session, user)
    step = start_stream(db_session, user)
    before = db_session.scalar(
        select(LearningItem).where(LearningItem.user_id == user.id)
    )

    guard = handle_simple_text_guard(db_session, user)
    assert guard is not None and "нажми вариант" in guard.text.lower()
    assert (
        db_session.scalar(select(LearningItem).where(LearningItem.user_id == user.id))
        is before
    )

    stopped = handle_stop(db_session, user, chat_id=user.telegram_user_id)
    db_session.flush()
    assert "Готово" in stopped.text
    assert get_active_stream(db_session, user) is None
    run = db_session.get(PracticeSession, step.run.id)
    assert run is not None and run.status == "completed"


def test_unknown_is_recorded_as_recognition_and_owns_question_state(
    db_session, settings
):
    user = ensure_user(db_session, 123456789, settings)
    _question_item(db_session, user)
    step = start_stream(db_session, user)
    question_reply = handle_study(db_session, user)
    answer_data = next(
        data for data in _button_data(question_reply) if data.endswith(":unknown")
    )
    assert answer_data.startswith("simple:answer:")

    reply = handle_simple_answer(db_session, user, step.run.id, step.index, None)
    attempt = db_session.scalar(select(PracticeAttempt))

    assert "Ответ:" in reply.text
    assert attempt is not None
    assert attempt.feedback["answer_modality"] == "recognition"
    assert attempt.feedback["unknown"] is True


def test_optional_writing_is_separate_and_skip_is_not_an_error(db_session, settings):
    user = ensure_user(db_session, 123456789, settings)
    _question_item(db_session, user)
    step = start_stream(db_session, user)
    handle_simple_answer(db_session, user, step.run.id, step.index, 0)
    bonus = handle_simple_bonus_start(db_session, user, step.run.id)
    active = db_session.scalar(
        select(PracticeSession).where(PracticeSession.status == "simple_bonus")
    )
    assert active is not None and "одно предложение" in bonus.text

    result = handle_simple_bonus_text(
        db_session, user, StubProvider(), active, "We need to align on the rollout."
    )
    production = db_session.scalar(
        select(PracticeAttempt).where(
            PracticeAttempt.exercise_type == "simple_production"
        )
    )
    assert "сохранена отдельно" in result.text
    assert production is not None
    assert production.feedback["answer_modality"] == "production"
    set_learning_mode(db_session, user, "simple")
    progress = handle_progress(db_session, user)
    assert "Узнавание: 1/1" in progress.text
    assert "Письменная практика:" in progress.text

    other = ensure_user(db_session, 123456790, settings)
    _question_item(db_session, other, "account for")
    other_step = start_stream(db_session, other)
    handle_simple_answer(db_session, other, other_step.run.id, other_step.index, 0)
    optional = handle_simple_bonus_start(db_session, other, other_step.run.id)
    bonus_run = db_session.scalar(
        select(PracticeSession).where(
            PracticeSession.user_id == other.id,
            PracticeSession.status == "simple_bonus",
        )
    )
    assert bonus_run is not None and optional.buttons
    skipped = handle_simple_bonus_skip(db_session, other, bonus_run.id)
    assert "не считается ошибкой" in skipped.text


def test_bonus_capture_is_state_bound_and_full_practice_closes_simple_prompts(
    db_session, settings
):
    user = ensure_user(db_session, 123456789, settings)
    _question_item(db_session, user)
    stream = start_stream(db_session, user)
    handle_simple_answer(db_session, user, stream.run.id, stream.index, 0)
    bonus_reply = handle_simple_bonus_start(db_session, user, stream.run.id)
    bonus = db_session.scalar(
        select(PracticeSession).where(PracticeSession.status == "simple_bonus")
    )
    state_store = StateStore(db_session)
    state = state_store.set(
        user.telegram_user_id,
        user.telegram_user_id,
        "simple_bonus",
        {"run_id": bonus.id},
    )

    assert bonus_reply.buttons
    assert _active_simple_bonus_for_state(db_session, user, state) is bonus
    assert _active_simple_bonus_for_state(db_session, user, None) is None

    _cancel_simple_answering(db_session, user)

    assert (
        _active_simple_bonus_for_state(
            db_session,
            user,
            state_store.get(user.telegram_user_id, user.telegram_user_id),
        )
        is None
    )
    assert db_session.get(PracticeSession, bonus.id).status == "completed"
    assert get_active_stream(db_session, user) is None
    full_lesson = handle_practice(db_session, user, "vocab")
    assert full_lesson.text
    handle_answer(db_session, user, StubProvider(), "We need to align on this.")
    latest = db_session.scalar(
        select(PracticeAttempt).order_by(PracticeAttempt.id.desc())
    )
    assert latest is not None
    assert latest.exercise_type != "simple_production"


def test_simple_actions_authenticate_actual_forum_sender(db_session, settings):
    owner = ensure_user(db_session, 123456789, settings)
    foreign = 234567890
    assert _simple_sender_allowed(owner.telegram_user_id, settings) is True
    assert _simple_event_authorized(foreign, owner, settings) is True
    assert (
        _simple_event_authorized(foreign, owner, settings, action="simple:answer:1:0:0")
        is False
    )
    assert (
        _simple_event_authorized(foreign, owner, settings, action="progress") is False
    )
    set_learning_mode(db_session, owner, "simple")
    assert _simple_event_authorized(foreign, owner, settings, action="cards") is False


def test_read_only_keyboard_actions_preserve_optional_writing_capture(
    db_session, settings
):
    user = ensure_user(db_session, 123456789, settings)
    state = StateStore(db_session).set(
        user.telegram_user_id,
        user.telegram_user_id,
        "simple_bonus",
        {"run_id": 25},
    )

    assert _keyboard_action_clears_capture("progress", state) is False
    assert _keyboard_action_clears_capture("simple_menu", state) is False
    assert _keyboard_action_clears_capture("cards", state) is False
    assert _keyboard_action_clears_capture("study", state) is False


def test_more_upload_capture_matches_the_forum_materials_destination(
    db_session, settings
):
    user = ensure_user(db_session, 123456789, settings)
    forum_settings = replace(
        settings,
        telegram_forum_group_id=-1001234567890,
        telegram_topic_materials_upload_id=39,
    )
    event = SimpleNamespace(chat_id=-1001234567890)

    reply = _start_upload_capture(
        db_session, user.telegram_user_id, event, forum_settings
    )
    state = StateStore(db_session).get(event.chat_id, user.telegram_user_id)

    assert reply.target_chat_id == -1001234567890
    assert reply.message_thread_id == 39
    assert state is not None and state.name == "upload"


def test_stale_bonus_skip_cannot_clear_the_next_bonus_capture(db_session, settings):
    user = ensure_user(db_session, 123456789, settings)
    state = StateStore(db_session).set(
        user.telegram_user_id,
        user.telegram_user_id,
        "simple_bonus",
        {"run_id": 26},
    )

    assert _should_clear_simple_bonus_state(state, 25, 26) is False
    assert _should_clear_simple_bonus_state(state, 26, 26) is False
    assert _should_clear_simple_bonus_state(state, 26, None) is True


def test_bonus_text_capture_is_limited_to_its_forum_topic(db_session, settings):
    user = ensure_user(db_session, 123456789, settings)
    forum_settings = replace(settings, telegram_forum_group_id=-1001234567890)
    state = StateStore(db_session).set(
        -1001234567890,
        user.telegram_user_id,
        "simple_bonus",
        {"run_id": 27, "message_thread_id": 39},
    )
    same_topic = SimpleNamespace(
        chat_id=-1001234567890,
        message=SimpleNamespace(
            reply_to=SimpleNamespace(reply_to_top_id=39, reply_to_msg_id=100)
        ),
    )
    other_topic = SimpleNamespace(
        chat_id=-1001234567890,
        message=SimpleNamespace(
            reply_to=SimpleNamespace(reply_to_top_id=40, reply_to_msg_id=101)
        ),
    )

    assert _simple_bonus_topic_matches(same_topic, state, forum_settings) is True
    assert _simple_bonus_topic_matches(other_topic, state, forum_settings) is False


def test_mode_switch_is_per_user_and_keeps_advanced_preferences(db_session, settings):
    user = ensure_user(db_session, 123456789, settings)
    other = ensure_user(db_session, 123456790, settings)
    update_pref(db_session, user, "words_per_day", 7)
    update_pref(db_session, user, "paused", True)

    enabled = handle_simple_mode_change(db_session, user, "simple")
    assert get_learning_mode(user) == "simple"
    assert get_learning_mode(other) == "advanced"
    assert get_prefs(user).words_per_day == 7
    assert get_prefs(user).paused is True
    assert enabled.simple_keyboard is True
    assert enabled.message_thread_id is None

    disabled = handle_simple_mode_change(
        db_session, user, "advanced", channel_id="-1001234567890", message_thread_id=44
    )
    assert get_learning_mode(user) == "advanced"
    assert disabled.target_chat_id == "-1001234567890"
    assert disabled.message_thread_id == 44
    assert "сохранены" in disabled.text
