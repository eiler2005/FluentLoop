from __future__ import annotations

from pathlib import Path

from fluentloop.bot.handlers import (
    command_catalog,
    exercise_type_count,
    handle_help,
    handle_start,
    is_allowed,
)
from fluentloop.bot.state import StateStore


def test_app_constructs_and_start_creates_profile(db_session, settings) -> None:
    reply = handle_start(db_session, settings, 123456789)
    assert "FluentLoop is ready" in reply.text
    assert "/start" in command_catalog()
    assert "/help" in handle_help().text
    assert exercise_type_count() == 6


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
