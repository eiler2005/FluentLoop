from __future__ import annotations

from pathlib import Path

from fluentloop.bot.app import _effective_user_id, _is_forum_chat
from fluentloop.bot.handlers import (
    command_catalog,
    exercise_type_count,
    handle_channel_help,
    handle_channel_hub,
    handle_help,
    handle_materials_channel_hub,
    handle_start,
    is_allowed,
)
from fluentloop.bot.state import StateStore
from fluentloop.telegram_bot_api import bot_commands_payload
from fluentloop.telegram_workspace import workspace_destination, workspace_enabled


def test_app_constructs_and_start_creates_profile(db_session, settings) -> None:
    reply = handle_start(db_session, settings, 123456789)
    assert "FluentLoop is ready" in reply.text
    assert "/start" in command_catalog()
    assert "/library" in command_catalog()
    assert "/subscribe" in command_catalog()
    assert "/howto" in command_catalog()
    assert "/help" in handle_help().text
    assert "/howto" in handle_help().text
    assert "Seed library topics" in handle_help().text
    assert "#materials_upload" in handle_help().text
    assert exercise_type_count() == 14
    help_reply = handle_channel_help("-100123")
    assert help_reply.target_chat_id == "-100123"
    assert help_reply.text.startswith("#help\nHow to use FluentLoop")
    assert help_reply.buttons is not None
    help_actions = {button.data for row in help_reply.buttons for button in row}
    assert {
        "today:start",
        "lessons:list",
        "topics:list",
        "materials:start",
        "practice:modes",
    } <= help_actions
    assert "library:list" in help_actions
    commands = {entry["command"] for entry in bot_commands_payload()}
    assert {"library", "subscribe"} <= commands
    channel = handle_channel_hub("-100123")
    assert channel.target_chat_id == "-100123"
    assert "#practice_flow" in channel.text
    assert channel.buttons is not None
    assert "materials:start" in {
        button.data for row in channel.buttons for button in row
    }
    materials = handle_materials_channel_hub("-100123")
    assert "#materials_upload" in materials.text
    assert "Best paste format" in materials.text
    threaded = handle_channel_help("-100999", message_thread_id=42)
    assert threaded.message_thread_id == 42


def test_forum_workspace_destinations(settings) -> None:
    forum_settings = settings.__class__(
        **{
            **settings.__dict__,
            "telegram_forum_group_id": "-100999",
            "telegram_topic_help_id": 10,
            "telegram_topic_practice_flow_id": 11,
        }
    )
    assert workspace_enabled(forum_settings)
    help_target = workspace_destination(forum_settings, "help")
    assert help_target.chat_id == "-100999"
    assert help_target.message_thread_id == 10
    practice = workspace_destination(forum_settings, "practice_flow")
    assert practice.message_thread_id == 11
    assert _is_forum_chat("-100999", forum_settings)
    assert _effective_user_id(999, "-100999", forum_settings) == 123456789


def test_single_user_gate_and_container_mount_are_configured(settings) -> None:
    compose = Path("docker-compose.yml").read_text()
    assert is_allowed(settings, 123456789)
    assert not is_allowed(settings, 987654321)
    assert "./data:/app/data" in compose
    assert 'CMD ["python", "-m", "fluentloop"]' in Path("Dockerfile").read_text()


def test_state_store_round_trips(db_session) -> None:
    store = StateStore(db_session)
    store.set(1, 2, "upload", {"step": "text"})
    state = store.get(1, 2)
    assert state is not None
    assert state.name == "upload"
    assert state.payload == {"step": "text"}
    store.clear(1, 2)
    assert store.get(1, 2) is None


def test_telegram_command_menu_payload_uses_bare_commands() -> None:
    commands = bot_commands_payload()
    names = {entry["command"] for entry in commands}
    assert "howto" in names
    assert "feedback" in names
    assert all(not entry["command"].startswith("/") for entry in commands)
    assert all(entry["description"] for entry in commands)
