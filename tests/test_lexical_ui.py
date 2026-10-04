from copy import deepcopy
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from html import escape
from types import SimpleNamespace

import pytest
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from fluentloop.ai.provider import StubProvider
from fluentloop.bot import app
from fluentloop.bot.handlers import (
    _simple_question_reply,
    handle_progress,
    handle_simple_answer,
    handle_simple_bonus_start,
    handle_simple_bonus_text,
    handle_simple_issue,
    handle_simple_stop,
)
from fluentloop.bot.state import StateStore
from fluentloop.db.models import PracticeAttempt
from fluentloop.learning_prefs import set_learning_mode
from fluentloop.lexical_learning import lexical_progress, load_lexicon
from fluentloop.simple_learning import (
    SimpleStep,
    answer_choice,
    get_active_bonus,
    start_stream,
)
from fluentloop.users import ensure_user
from fluentloop.workplace_roadmap import default_plan, save_plan


def _actions(reply):
    return {button.data for row in reply.buttons or [] for button in row}


@pytest.fixture
def lexical_step(db_session, settings):
    user = ensure_user(db_session, 123456789, settings)
    set_learning_mode(db_session, user, "simple")
    save_plan(db_session, user, default_plan())
    step = start_stream(db_session, user)
    for _ in range(10):
        if step.question.get("lexical"):
            return user, step
        step = answer_choice(
            db_session, user, step.run.id, step.index, step.question["correct_index"]
        ).next_step
    pytest.fail("Lexical question must appear in ordinary Study")


def test_real_lexical_feedback_and_progress_are_readable_and_pending_resumes(
    db_session, lexical_step
):
    user, step = lexical_step
    reply = handle_simple_answer(
        db_session,
        user,
        step.run.id,
        step.index,
        step.question["correct_index"],
        channel_id="-1001234567890",
        message_thread_id=44,
    )
    for field in (
        "headword",
        "meaning_ru",
        "meaning_en",
        "example",
        "grammar",
        "register",
        "plain_alternative",
    ):
        assert escape(step.question["lexical_card"][field], quote=False) in reply.text
    assert f"simple:lexical_write:{step.run.id}:{step.index}" in _actions(reply)
    assert len(reply.text.encode("utf-16-le")) // 2 < 4096
    pending = deepcopy(start_stream(db_session, user).question)
    bonus_reply = handle_simple_bonus_start(
        db_session,
        user,
        step.run.id,
        module_index=step.index,
        channel_id="-1001234567890",
        message_thread_id=44,
    )
    assert bonus_reply.message_thread_id == 44
    assert "необязательно" in bonus_reply.text
    bonus = get_active_bonus(db_session, user)
    progress = handle_progress(db_session, user)
    assert any(
        "Слова и выражения · весь период" in r.text for r in progress.extra_replies
    )
    assert start_stream(db_session, user).question == pending
    result = handle_simple_bonus_text(
        db_session,
        user,
        StubProvider(),
        bonus,
        "This original response requires a real evaluation.",
    )
    assert "проверка сейчас недоступна" in result.text
    attempt = db_session.scalar(
        select(PracticeAttempt).where(
            PracticeAttempt.exercise_type == "simple_production"
        )
    )
    assert attempt.status == "unchecked"
    assert lexical_progress(db_session, user)["independent_writing"] == 0
    assert start_stream(db_session, user).question == pending
    summary = handle_simple_stop(db_session, user, step.run.id)
    assert "Слова и выражения в этой сессии" in summary.text
    assert "Новых: 1" in summary.text
    assert "не является оценкой уровня CEFR" in summary.text


def test_lexical_issue_ownership_and_oversized_writing_guard(
    db_session, settings, lexical_step
):
    user, step = lexical_step
    handle_simple_answer(db_session, user, step.run.id, step.index, None)
    other = ensure_user(db_session, 123456790, settings)
    assert (
        "недоступен"
        in handle_simple_issue(db_session, other, step.run.id, step.index).text
    )
    handle_simple_bonus_start(db_session, user, step.run.id, module_index=step.index)
    bonus = get_active_bonus(db_session, user)

    class Provider:
        def light_call(self, *args):
            raise AssertionError("Oversized input must not reach AI")

    assert (
        "слишком длинный"
        in handle_simple_bonus_text(
            db_session, user, Provider(), bonus, "x" * 10001
        ).text
    )
    assert get_active_bonus(db_session, user).id == bonus.id
    assert (
        "исключён"
        in handle_simple_issue(db_session, user, step.run.id, step.index).text
    )
    assert not (other.preferences_json or {}).get("lexical_question_quality")


def test_all_shipped_lexical_questions_have_complete_options_in_message_body(
    db_session, settings
):
    user = ensure_user(db_session, 123456789, settings)
    for entry in load_lexicon()["entries"]:
        for variant in entry["questions"]:
            question = {
                **variant,
                "lexical": {"entry_id": entry["id"]},
                "lexical_entry": entry,
                "lexical_phase": "new",
            }
            reply = _simple_question_reply(
                SimpleStep(SimpleNamespace(id=1), question), user
            )
            assert [button.text for button in reply.buttons[0]] == ["A", "B", "C"]
            assert all(
                escape(option, quote=False) in reply.text
                for option in variant["options"]
            )
            assert len(reply.text.encode("utf-16-le")) // 2 < 4096


def test_stop_reports_three_buckets_without_counting_lexical_context_twice(
    db_session, settings
):
    user = ensure_user(db_session, 123456789, settings)
    save_plan(db_session, user, default_plan())
    now = datetime(2026, 10, 4, 8, tzinfo=UTC)
    step = start_stream(db_session, user, now=now)
    for index in range(10):
        step = answer_choice(
            db_session,
            user,
            step.run.id,
            step.index,
            step.question["correct_index"],
            now=now + timedelta(seconds=index),
        ).next_step
    reply = handle_simple_stop(db_session, user)
    assert "Общий английский: 3/3 верно" in reply.text
    assert "Рабочие темы: 4/4 верно" in reply.text
    assert "Слова и выражения: 3/3 верно" in reply.text


@pytest.mark.asyncio
async def test_lexical_callback_captures_writing_in_original_chat_and_keyboard_resumes(
    db_session, settings, lexical_step, monkeypatch
):
    import telethon
    from test_roadmap_study_ui import _Event

    user, step = lexical_step
    handle_simple_answer(db_session, user, step.run.id, step.index, None)
    pending = deepcopy(start_stream(db_session, user).question)
    db_session.commit()
    callbacks, sent = {}, []

    class Client:
        def __init__(self, *args):
            pass

        def on(self, *args):
            def register(function):
                callbacks[function.__name__] = function
                return function

            return register

        async def start(self, **kwargs):
            pass

        async def get_me(self):
            return SimpleNamespace(username="test_bot")

        async def run_until_disconnected(self):
            pass

    async def no_channel(*args):
        return False

    async def capture(client, chat_id, reply, settings):
        sent.append(reply)

    monkeypatch.setattr(telethon, "TelegramClient", Client)
    monkeypatch.setattr(app, "maybe_record_channel", no_channel)
    monkeypatch.setattr(app, "send_reply", capture)
    monkeypatch.setattr(
        app,
        "build_scheduler",
        lambda *args, **kwargs: SimpleNamespace(
            start=lambda: None, shutdown=lambda **kwargs: None
        ),
    )
    routed = replace(
        settings,
        telegram_forum_group_id=-1001234567890,
        telegram_topic_practice_flow_id=44,
    )
    await app.run_bot(routed, sessionmaker(bind=db_session.get_bind()))
    await callbacks["on_callback"](
        _Event(
            data=f"simple:lexical_write:{step.run.id}:{step.index}",
            chat_id=-1001234567890,
        )
    )
    db_session.expire_all()
    state = StateStore(db_session).get(-1001234567890, user.telegram_user_id)
    assert state.name == "simple_bonus"
    assert state.payload["message_thread_id"] == 44
    assert sent[-1].message_thread_id == 44
    await callbacks["on_free_text"](
        _Event("Учиться", chat_id=-1001234567890, thread_id=44)
    )
    db_session.expire_all()
    assert StateStore(db_session).get(-1001234567890, user.telegram_user_id) is None
    assert get_active_bonus(db_session, user) is None
    assert start_stream(db_session, user).question == pending
