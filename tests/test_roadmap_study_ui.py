from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from html import escape
from types import SimpleNamespace

import pytest
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from fluentloop.ai.provider import StubProvider
from fluentloop.bot import app
from fluentloop.bot.handlers import (
    _simple_question_reply,
    handle_module_external,
    handle_progress,
    handle_simple_answer,
    handle_simple_bonus_start,
    handle_simple_bonus_text,
    handle_simple_issue,
    handle_simple_stop,
    handle_study,
)
from fluentloop.bot.roadmap import handle_roadmap
from fluentloop.bot.state import StateStore
from fluentloop.db.models import LearningItem, PracticeAttempt
from fluentloop.learning_prefs import set_learning_mode
from fluentloop.roadmap_study import load_question_pack, module_progress
from fluentloop.simple_learning import (
    SimpleStep,
    get_active_bonus,
    get_active_stream,
    start_stream,
)
from fluentloop.users import ensure_user
from fluentloop.workplace_roadmap import default_plan, save_plan, update_plan


def _actions(reply):
    return {button.data for row in reply.buttons or [] for button in row}


@pytest.fixture
def learner(db_session, settings):
    user = ensure_user(db_session, 123456789, settings)
    set_learning_mode(db_session, user, "simple")
    legacy = default_plan()
    legacy["lexical_share"] = 0
    save_plan(db_session, user, legacy)
    return user


def _answer(session, user):
    step = start_stream(session, user)
    assert step.question["roadmap"]["strand"] == "general"
    reply = handle_simple_answer(
        session,
        user,
        step.run.id,
        step.index,
        step.question["correct_index"],
        channel_id="-1001234567890",
        message_thread_id=44,
    )
    return step, reply


def test_module_question_feedback_and_next_question_preserve_origin(
    db_session, learner
):
    question = handle_study(db_session, learner)
    assert "Общий английский · B2" in question.text
    step, reply = _answer(db_session, learner)
    assert "Верно" in reply.text
    assert f"simple:module_write:{step.run.id}:0" in _actions(reply)
    assert f"simple:module_external:{step.run.id}:0" in _actions(reply)
    assert reply.extra_replies[0].target_chat_id == "-1001234567890"
    assert reply.extra_replies[0].message_thread_id == 44
    stale = handle_simple_answer(db_session, learner, step.run.id, 0, 0)
    assert "уже закрыт" in stale.text
    assert not any("module_write" in action for action in _actions(stale))


def test_stop_shows_session_plan_snapshot_and_navigation(db_session, learner):
    step, _ = _answer(db_session, learner)

    summary = handle_simple_stop(db_session, learner, step.run.id)

    assert "занятие завершено" in summary.text
    assert "Результат сессии: 1/1 верно" in summary.text
    assert "Точность сессии: 100%" in summary.text
    assert "По личному плану в этой сессии" in summary.text
    assert "Общий английский: 1/1 верно" in summary.text
    assert step.question["module_title_ru"] in summary.text
    assert "не является оценкой уровня CEFR" in summary.text
    assert {"simple:study", "simple:progress", "simple:plan"}.issubset(
        _actions(summary)
    )


def test_all_module_options_are_readable_in_body_with_compact_safe_buttons(learner):
    for module in load_question_pack()["modules"]:
        for stage, raw in module["stages"].items():
            question = deepcopy(raw)
            question.update(
                roadmap={"strand": "general", "stage": stage},
                module_title_ru=module["module_id"],
            )
            reply = _simple_question_reply(
                SimpleStep(SimpleNamespace(id=1), question), learner
            )
            assert [button.text for button in reply.buttons[0]] == ["A", "B", "C"]
            assert all(
                escape(option, quote=False) in reply.text for option in raw["options"]
            )
            assert len(reply.text.encode("utf-16-le")) // 2 < 4096
            question["options"][0] = "A <client> & another person's view"
            escaped = _simple_question_reply(
                SimpleStep(SimpleNamespace(id=1), question), learner
            )
            assert "&lt;client&gt; &amp;" in escaped.text
            assert "<client>" not in escaped.text

    legacy = {
        "category": "phrase",
        "prompt": "Request an update with a clear, courteous deadline.",
        "options": [
            "Could you send the updated estimate by Thursday afternoon?",
            "Could you send an estimate when convenient, we need it soon?",
        ],
        "correct_index": 0,
    }
    reply = _simple_question_reply(SimpleStep(SimpleNamespace(id=1), legacy), learner)
    assert [button.text for button in reply.buttons[0]] == ["A", "B"]
    assert "<b>Выбери вариант:</b>" in reply.text
    assert all(option in reply.text for option in legacy["options"])


def test_module_writing_fallback_remains_unchecked_and_pending_resumes(
    db_session, learner
):
    step, _ = _answer(db_session, learner)
    pending = get_active_stream(db_session, learner).exercises[0]
    reply = handle_simple_bonus_start(
        db_session,
        learner,
        step.run.id,
        module_index=0,
        channel_id="-1001234567890",
        message_thread_id=44,
    )
    assert "Это необязательно" in reply.text
    assert reply.target_chat_id == "-1001234567890"
    assert reply.message_thread_id == 44
    bonus = get_active_bonus(db_session, learner)
    handle_progress(db_session, learner)
    handle_roadmap(db_session, learner)
    assert get_active_bonus(db_session, learner).id == bonus.id
    result = handle_simple_bonus_text(
        db_session,
        learner,
        StubProvider(),
        bonus,
        "I would suggest a different arrangement because it suits both people.",
    )
    assert "проверка сейчас недоступна" in result.text
    assert "simple:study" in _actions(result)
    writing = db_session.scalar(
        select(PracticeAttempt).where(
            PracticeAttempt.exercise_type == "simple_production"
        )
    )
    assert writing.status == "unchecked"
    assert not any(
        row["writing_variants"] for row in module_progress(db_session, learner)
    )
    assert start_stream(db_session, learner).question == pending


def test_external_activity_is_owned_idempotent_and_separate_from_mastery(
    db_session, learner, settings
):
    step, _ = _answer(db_session, learner)
    before = module_progress(db_session, learner)
    brief = handle_module_external(
        db_session,
        learner,
        step.run.id,
        0,
        channel_id="-1001234567890",
        message_thread_id=44,
    )
    assert "не повышает ступень" in brief.text
    assert "https://" in brief.text
    assert brief.target_chat_id == "-1001234567890"
    assert brief.message_thread_id == 44
    result = handle_module_external(db_session, learner, step.run.id, 0, report=True)
    assert "со слов пользователя" in result.text
    assert (
        "уже отмечена"
        in handle_module_external(db_session, learner, step.run.id, 0, report=True).text
    )
    after = module_progress(db_session, learner)
    assert sum(row["external_reports"] for row in after) == 1
    assert [row["stage"] for row in after] == [row["stage"] for row in before]
    assert [row["writing_variants"] for row in after] == [
        row["writing_variants"] for row in before
    ]
    other = ensure_user(db_session, 123456790, settings)
    assert (
        "недоступно"
        in handle_module_external(db_session, other, step.run.id, 0, report=True).text
    )
    assert (
        "завершено"
        in handle_simple_bonus_start(
            db_session, other, step.run.id, module_index=0
        ).text
    )


def test_plan_edit_keeps_pending_question_but_changes_following_module(
    db_session, learner
):
    update_plan(db_session, learner, "general_share", 60)
    step = start_stream(db_session, learner)
    current_module = step.question["roadmap"]["module_id"]
    target = next(
        row["module_id"]
        for row in module_progress(db_session, learner)
        if row["strand"] == "general" and row["module_id"] != current_module
    )
    update_plan(db_session, learner, "focus", target)
    update_plan(db_session, learner, "pause", current_module)
    assert start_stream(db_session, learner).question == step.question
    handle_simple_answer(db_session, learner, step.run.id, 0, 0)
    next_question = get_active_stream(db_session, learner).exercises[0]
    assert next_question["roadmap"]["module_id"] == target


def test_module_issue_quarantines_only_personal_question_and_progress_is_readable(
    db_session, learner, settings
):
    step, _ = _answer(db_session, learner)
    other = ensure_user(db_session, 123456790, settings)
    assert "недоступен" in handle_simple_issue(db_session, other, step.run.id, 0).text
    assert "исключён" in handle_simple_issue(db_session, learner, step.run.id, 0).text
    assert (
        "уже отмечен" in handle_simple_issue(db_session, learner, step.run.id, 0).text
    )
    assert not (other.preferences_json or {}).get("roadmap_question_quality")
    progress = handle_progress(db_session, learner)
    assert len(progress.extra_replies) == 1
    assert "Модули личного плана" in progress.extra_replies[0].text
    assert "не подтверждают освоение" in progress.extra_replies[0].text
    assert len(progress.extra_replies[0].text) < 4096


def test_roadmap_activation_is_explicit_and_enables_real_questions(
    db_session, settings
):
    user = ensure_user(db_session, 123456789, settings)
    preview = handle_roadmap(db_session, user)
    assert "simple:roadmap:activate" in _actions(preview)
    assert "workplace_plan" not in user.preferences_json
    activated = handle_roadmap(db_session, user, "activate")
    assert "План подключён" in activated.text
    assert "simple:study" in _actions(activated)
    assert start_stream(db_session, user).question["roadmap"]


def test_wrong_only_module_is_started_and_focus_recent_modules_are_visible(
    db_session, learner
):
    first = start_stream(db_session, learner)
    first_module = first.question["roadmap"]["module_id"]
    handle_simple_answer(db_session, learner, first.run.id, first.index, None)
    progress = handle_progress(db_session, learner).extra_replies[0].text
    assert "Начаты: 1/48" in progress
    assert "узнавание 0" in progress
    for _ in range(5):
        latest = start_stream(db_session, learner)
        latest_title = latest.question["module_title_ru"]
        handle_simple_answer(db_session, learner, latest.run.id, latest.index, None)
    progress = handle_progress(db_session, learner).extra_replies[0].text
    assert latest_title in progress
    update_plan(db_session, learner, "focus", first_module)
    progress = handle_progress(db_session, learner).extra_replies[0].text
    first_visible = next(line for line in progress.splitlines() if line.startswith("•"))
    assert first.question["module_title_ru"] in first_visible
    assert latest_title in progress


def test_oversized_module_writing_does_not_call_provider_or_close_capture(
    db_session, learner
):
    step, _ = _answer(db_session, learner)
    handle_simple_bonus_start(db_session, learner, step.run.id, module_index=0)
    bonus = get_active_bonus(db_session, learner)

    class Provider:
        def light_call(self, *args):
            raise AssertionError("Oversized writing must not reach the provider")

    result = handle_simple_bonus_text(
        db_session, learner, Provider(), bonus, "x" * 10001
    )
    assert "слишком длинный" in result.text
    assert get_active_bonus(db_session, learner).id == bonus.id
    assert (
        db_session.scalar(
            select(PracticeAttempt).where(
                PracticeAttempt.exercise_type == "simple_production"
            )
        )
        is None
    )


class _Event:
    def __init__(
        self,
        text="",
        *,
        data="",
        sender_id=123456789,
        chat_id=123456789,
        thread_id=None,
    ):
        self.raw_text = text
        self.chat_id = chat_id
        self.data = data.encode()
        self.sender_id = sender_id
        self.answers = []
        self.message = SimpleNamespace(
            reply_to=SimpleNamespace(
                reply_to_top_id=thread_id, reply_to_msg_id=thread_id
            )
        )

    async def get_sender(self):
        return SimpleNamespace(id=self.sender_id, bot=False)

    async def answer(self, text):
        self.answers.append(text)

    async def reply(self, text):
        self.answers.append(text)


@pytest.mark.asyncio
@pytest.mark.parametrize("chat_id,thread_id", [(123456789, None), (-1001234567890, 44)])
@pytest.mark.parametrize("continuation", ["keyboard", "choice"])
async def test_module_callbacks_capture_writing_and_study_keyboard_cancels_it(
    db_session, learner, settings, monkeypatch, chat_id, thread_id, continuation
):
    import telethon

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
    step, _ = _answer(db_session, learner)
    pending = get_active_stream(db_session, learner).exercises[0]
    db_session.commit()
    routed = replace(
        settings,
        telegram_forum_group_id=-1001234567890,
        telegram_topic_practice_flow_id=44,
    )
    await app.run_bot(routed, sessionmaker(bind=db_session.get_bind()))
    await callbacks["on_callback"](
        _Event(data=f"simple:module_write:{step.run.id}:0", chat_id=chat_id)
    )
    db_session.expire_all()
    state = StateStore(db_session).get(chat_id, learner.telegram_user_id)
    assert state.name == "simple_bonus"
    original_bonus_id = state.payload["run_id"]
    assert state.payload["message_thread_id"] == thread_id
    assert sent[-1].message_thread_id == thread_id
    await callbacks["on_callback"](
        _Event(data=f"simple:answer:{step.run.id}:0:0", chat_id=chat_id)
    )
    db_session.expire_all()
    assert (
        StateStore(db_session).get(chat_id, learner.telegram_user_id).name
        == "simple_bonus"
    )
    if thread_id is not None:
        before = len(sent)
        await callbacks["on_free_text"](
            _Event("An answer in the wrong topic.", chat_id=chat_id, thread_id=99)
        )
        db_session.expire_all()
        assert len(sent) == before
        assert (
            StateStore(db_session).get(chat_id, learner.telegram_user_id).name
            == "simple_bonus"
        )
    before = len(sent)
    forbidden = _Event(
        data=f"simple:module_report:{step.run.id}:0",
        sender_id=123456790,
        chat_id=-1001234567890,
    )
    await callbacks["on_callback"](forbidden)
    assert len(sent) == before
    assert "personal" in forbidden.answers[-1]
    if continuation == "keyboard":
        await callbacks["on_free_text"](
            _Event("Учиться", chat_id=chat_id, thread_id=thread_id)
        )
    else:
        await callbacks["on_callback"](
            _Event(data=f"simple:answer:{step.run.id}:1:0", chat_id=chat_id)
        )
    db_session.expire_all()
    assert StateStore(db_session).get(chat_id, learner.telegram_user_id) is None
    assert get_active_bonus(db_session, learner) is None
    if continuation == "keyboard":
        assert get_active_stream(db_session, learner).exercises[0] == pending
    else:
        assert get_active_stream(db_session, learner).exercises[0] != pending
    assert db_session.scalar(select(LearningItem)) is None
    await callbacks["on_callback"](
        _Event(data=f"simple:module_write:{step.run.id}:0", chat_id=chat_id)
    )
    db_session.expire_all()
    resumed = StateStore(db_session).get(chat_id, learner.telegram_user_id)
    assert resumed.name == "simple_bonus"
    assert resumed.payload["run_id"] != original_bonus_id
    await callbacks["on_callback"](
        _Event(data=f"simple:bonus-skip:{original_bonus_id}", chat_id=chat_id)
    )
    db_session.expire_all()
    assert (
        StateStore(db_session).get(chat_id, learner.telegram_user_id).payload["run_id"]
        == resumed.payload["run_id"]
    )
    assert get_active_bonus(db_session, learner).id == resumed.payload["run_id"]
