from __future__ import annotations

from fluentloop.bot.handlers import (
    command_catalog,
    exercise_type_count,
    handle_help,
    handle_start,
)
from fluentloop.bot.state import StateStore


def test_app_constructs_and_start_creates_profile(db_session, settings) -> None:
    reply = handle_start(db_session, settings, 123456789)
    assert "FluentLoop is ready" in reply.text
    assert "/start" in command_catalog()
    assert "/help" in handle_help().text
    assert exercise_type_count() == 6


def test_state_store_round_trips(db_session) -> None:
    store = StateStore(db_session)
    store.set(1, 2, "upload", {"step": "text"})
    state = store.get(1, 2)
    assert state is not None
    assert state.name == "upload"
    assert state.payload == {"step": "text"}
    store.clear(1, 2)
    assert store.get(1, 2) is None
