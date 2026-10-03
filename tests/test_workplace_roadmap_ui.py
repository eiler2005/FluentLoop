from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from types import SimpleNamespace

import pytest
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from fluentloop.bot import app
from fluentloop.bot.handlers import handle_help, handle_plan, handle_simple_more_menu
from fluentloop.bot.roadmap import _reply, handle_roadmap, handle_roadmap_callback
from fluentloop.bot.state import StateStore
from fluentloop.db.models import LearningItem, PracticeSession
from fluentloop.telegram_bot_api import BOT_COMMANDS
from fluentloop.users import ensure_user
from fluentloop.workplace_roadmap import PLAN_NAMESPACE, get_plan, load_curriculum


def _actions(reply):
    return {button.data for row in reply.buttons or [] for button in row}


def _text(reply):
    return "\n".join(page.text for page in (reply, *reply.extra_replies))


def test_roadmap_retains_general_base_and_does_not_start_practice(db_session, settings):
    user = ensure_user(db_session, 123456789, settings)
    before = deepcopy(user.preferences_json)
    reply = handle_roadmap(db_session, user)

    assert "Общий английский: 60%" in reply.text
    assert "Основа: 90 мин" in reply.text
    assert "Дополнения: 60 мин" in reply.text
    assert "внешней практики" in reply.text
    assert "CEFR" in reply.text
    assert user.preferences_json == before
    assert db_session.scalar(select(PracticeSession)) is None
    assert db_session.scalar(select(LearningItem)) is None
    assert "simple:roadmap" in _actions(handle_plan(db_session, user))
    assert "simple:roadmap" in _actions(handle_simple_more_menu(db_session, user))
    assert "roadmap" in {command for command, _ in BOT_COMMANDS}
    assert "/roadmap" in handle_help(user).text


def test_roadmap_edits_are_personal_and_preserve_unrelated_settings(
    db_session, settings
):
    user = ensure_user(db_session, 123456789, settings)
    other = ensure_user(db_session, 123456790, settings)
    user.preferences_json = {"unrelated": {"keep": True}}
    other_before = deepcopy(other.preferences_json)
    for command in ("track big_tech", "time 300", "general 70"):
        reply = handle_roadmap(db_session, user, command)
        assert "Не удалось" not in reply.text
    plan = get_plan(user)
    assert (plan["track"], plan["weekly_minutes"], plan["general_share"]) == (
        "big_tech",
        300,
        70,
    )
    assert user.preferences_json["unrelated"] == {"keep": True}
    assert other.preferences_json == other_before
    assert get_plan(other)["track"] == "balanced"
    module_id = plan["order"][0]
    handle_roadmap(db_session, user, f"focus {module_id}")
    assert get_plan(user)["focus"] == module_id
    handle_roadmap(db_session, user, f"pause {module_id}")
    assert module_id in get_plan(user)["paused"]
    assert get_plan(user)["focus"] is None
    handle_roadmap(db_session, user, f"resume {module_id}")
    assert module_id not in get_plan(user)["paused"]


@pytest.mark.parametrize(
    "command",
    [
        "track unknown",
        "time 0",
        "time true",
        "time 1201",
        "general 100",
        "general 10",
        "focus nonexistent",
        "pause nonexistent",
        "resume nonexistent",
        "module nonexistent",
        "module general_nonexistent c1_intro",
        "list private",
        "time 300 extra",
        "track",
        "notes confidential",
        "unknown",
    ],
)
def test_invalid_roadmap_actions_preserve_preferences(db_session, settings, command):
    user = ensure_user(db_session, 123456789, settings)
    handle_roadmap(db_session, user, "time 150")
    before = deepcopy(user.preferences_json)
    reply = handle_roadmap(db_session, user, command)
    assert "Не удалось" in reply.text
    assert user.preferences_json == before


def test_malformed_existing_configuration_is_not_silently_replaced(
    db_session, settings
):
    user = ensure_user(db_session, 123456789, settings)
    user.preferences_json = {PLAN_NAMESPACE: {"track": "broken"}, "other": True}
    before = deepcopy(user.preferences_json)
    assert "Не удалось" in handle_roadmap(db_session, user, "time 300").text
    assert user.preferences_json == before


def test_public_fields_are_escaped_and_private_notes_never_render(db_session, settings):
    user = ensure_user(db_session, 123456789, settings)
    pack = load_curriculum()
    pack["modules"][0]["title_ru"] = 'Risk <owner> & "alignment"'
    module_id = pack["modules"][0]["id"]
    handle_roadmap(db_session, user, "time 150", catalog=pack)
    prefs = deepcopy(user.preferences_json)
    prefs[PLAN_NAMESPACE]["notes"] = {module_id: "PRIVATE_CLIENT_NOTE"}
    user.preferences_json = prefs
    for argument in ("", "list", f"module {module_id}"):
        reply = handle_roadmap(db_session, user, argument, catalog=pack)
        assert "PRIVATE_CLIENT_NOTE" not in _text(reply)
        assert "<owner>" not in _text(reply)
        if argument:
            assert "&lt;owner&gt; &amp; &quot;alignment&quot;" in _text(reply)
        assert reply.parse_mode == "html"


def test_every_module_stage_has_task_evidence_resources_and_safe_pages(
    db_session, settings
):
    user = ensure_user(db_session, 123456789, settings)
    pack = load_curriculum()
    for module in pack["modules"]:
        for stage in ("b2", "b2_plus", "c1_intro"):
            reply = handle_roadmap(
                db_session,
                user,
                f"module {module['id']} {stage}",
                catalog=pack,
                channel_id="-1001234567890",
                message_thread_id=44,
            )
            assert "Результат:" in _text(reply)
            assert "Задание:" in _text(reply)
            assert "Свидетельства результата:" in _text(reply)
            assert "https://" in _text(reply)
            for page in (reply, *reply.extra_replies):
                assert len(page.text.encode("utf-16-le")) // 2 < 4096
                assert page.target_chat_id == "-1001234567890"
                assert page.message_thread_id == 44
            assert all(len(data.encode()) <= 64 for data in _actions(reply))
    assert db_session.scalar(select(PracticeSession)) is None


def test_list_pagination_keeps_all_modules_and_original_destination(
    db_session, settings
):
    user = ensure_user(db_session, 123456789, settings)
    pack = load_curriculum()
    for module in pack["modules"]:
        module["title_ru"] += " · " + "подробное название " * 8
    reply = handle_roadmap(
        db_session,
        user,
        "list",
        channel_id="-1001234567890",
        message_thread_id=44,
        catalog=pack,
    )
    assert reply.extra_replies
    for module in load_curriculum()["modules"]:
        assert f"/roadmap module {module['id']}" in _text(reply)
    for page in (reply, *reply.extra_replies):
        assert len(page.text) < 4096
        assert page.target_chat_id == "-1001234567890"
        assert page.message_thread_id == 44


def test_roadmap_callbacks_and_actual_sender_authorization(db_session, settings):
    user = ensure_user(db_session, 123456789, settings)
    for action in ("/roadmap", "simple:roadmap", "simple:roadmap:track:big_tech"):
        assert app._simple_event_authorized(123456789, user, settings, action=action)
        assert not app._simple_event_authorized(
            123456790, user, settings, action=action
        )
    reply = handle_roadmap_callback(
        db_session, user, "simple:roadmap:track:client_facing"
    )
    assert "Не удалось" not in reply.text
    assert get_plan(user)["track"] == "client_facing"
    before = deepcopy(user.preferences_json)
    assert (
        "Не удалось"
        in handle_roadmap_callback(db_session, user, "other:track:big_tech").text
    )
    assert user.preferences_json == before


def test_unicode_and_html_expansion_paginate_without_breaking_entities():
    from html import unescape

    text = "🙂<&>" * 2500
    reply = _reply(text, "-1001234567890", 44)
    pages = (reply, *reply.extra_replies)
    assert "".join(unescape(page.text) for page in pages) == text
    assert all(len(page.text.encode("utf-16-le")) // 2 <= 3800 for page in pages)


class _Event:
    def __init__(self, text, chat_id, sender_id=123456789, data=b""):
        self.raw_text = text
        self.chat_id = chat_id
        self.data = data
        self.sender_id = sender_id
        self.answers = []

    async def get_sender(self):
        return SimpleNamespace(id=self.sender_id, bot=False)

    async def answer(self, text):
        self.answers.append(text)

    async def reply(self, text):
        self.answers.append(text)


@pytest.mark.asyncio
async def test_command_callback_routing_and_command_capture_guard(
    db_session, settings, monkeypatch
):
    import telethon

    callbacks = {}
    sent = []

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
        sent.append((chat_id, reply))

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
    factory = sessionmaker(bind=db_session.get_bind())
    routed = replace(
        settings,
        telegram_forum_group_id=-1001234567890,
        telegram_topic_practice_flow_id=44,
    )
    await app.run_bot(routed, factory)
    await callbacks["on_command"](_Event("/roadmap", 123456789))
    assert sent[-1][1].target_chat_id is None
    assert sent[-1][1].message_thread_id is None
    await callbacks["on_command"](_Event("/roadmap", -1001234567890))
    assert sent[-1][1].target_chat_id == "-1001234567890"
    assert sent[-1][1].message_thread_id == 44
    before = len(sent)
    unauthorized = _Event("", -1001234567890, 123456790, b"simple:roadmap:time:300")
    await callbacks["on_callback"](unauthorized)
    assert len(sent) == before
    assert "personal" in unauthorized.answers[-1]
    unauthorized_command = _Event("/roadmap time 300", -1001234567890, 123456790)
    await callbacks["on_command"](unauthorized_command)
    assert len(sent) == before
    await callbacks["on_callback"](
        _Event("", 123456789, data=b"simple:roadmap:time:300")
    )
    assert "В неделю: 300 мин" in sent[-1][1].text
    assert sent[-1][1].target_chat_id is None
    owner = ensure_user(db_session, 123456789, settings)
    StateStore(db_session).set(123456789, 123456789, "add", {})
    await callbacks["on_free_text"](_Event("/roadmap time 150", 123456789))
    assert db_session.scalar(select(LearningItem)) is None
    assert StateStore(db_session).get(123456789, owner.telegram_user_id).name == "add"
