from __future__ import annotations

from fluentloop.bot.handlers import (
    ONBOARDING_STATE,
    command_catalog,
    handle_onboarding_callback,
    handle_onboarding_start,
    handle_start,
)
from fluentloop.bot.state import StateStore
from fluentloop.learning import list_items
from fluentloop.telegram_bot_api import BOT_COMMANDS
from fluentloop.users import ensure_user
from fluentloop.vocab_prefs import get_prefs

CHAT = 555


def _labels(reply) -> list[str]:
    return [button.text for row in reply.buttons for button in row]


def _data(reply) -> list[str]:
    return [button.data for row in reply.buttons for button in row]


def _run_wizard(session, user, *, topics=("tech",), kinds=("idioms",), size=10):
    handle_onboarding_start(session, user, chat_id=CHAT)
    for topic in topics:
        handle_onboarding_callback(session, user, "topic", topic, chat_id=CHAT)
    handle_onboarding_callback(session, user, "done", "topics", chat_id=CHAT)
    for kind in kinds:
        handle_onboarding_callback(session, user, "kind", kind, chat_id=CHAT)
    handle_onboarding_callback(session, user, "done", "kinds", chat_id=CHAT)
    handle_onboarding_callback(session, user, "size", str(size), chat_id=CHAT)
    return handle_onboarding_callback(session, user, "perday", "7", chat_id=CHAT)


def test_wizard_starts_on_the_topic_screen(db_session, settings) -> None:
    user = ensure_user(db_session, 123456789, settings)

    reply = handle_onboarding_start(db_session, user, chat_id=CHAT)

    assert "Pick a few topics" in reply.text
    assert "💻 Tech" in _labels(reply)
    assert "onb:done:topics" in _data(reply)
    assert all(not label.startswith("✅") for label in _labels(reply))


def test_topic_toggles_on_and_off(db_session, settings) -> None:
    user = ensure_user(db_session, 123456789, settings)
    handle_onboarding_start(db_session, user, chat_id=CHAT)

    on = handle_onboarding_callback(db_session, user, "topic", "tech", chat_id=CHAT)
    assert "✅ 💻 Tech" in _labels(on)

    off = handle_onboarding_callback(db_session, user, "topic", "tech", chat_id=CHAT)
    assert "✅ 💻 Tech" not in _labels(off)
    state = StateStore(db_session).get(CHAT, user.telegram_user_id)
    assert state.payload["topics"] == []


def test_kind_screen_separates_kinds_from_fun_sets(db_session, settings) -> None:
    user = ensure_user(db_session, 123456789, settings)
    handle_onboarding_start(db_session, user, chat_id=CHAT)
    handle_onboarding_callback(db_session, user, "done", "topics", chat_id=CHAT)

    reply = handle_onboarding_callback(db_session, user, "kind", "idioms", chat_id=CHAT)
    handle_onboarding_callback(db_session, user, "kind", "sci_fi", chat_id=CHAT)

    assert "fun sets" in reply.text
    state = StateStore(db_session).get(CHAT, user.telegram_user_id)
    assert state.payload["kinds"] == ["idioms"]
    assert state.payload["sets"] == ["sci_fi"]


def test_steps_advance_through_size_and_pace(db_session, settings) -> None:
    user = ensure_user(db_session, 123456789, settings)
    handle_onboarding_start(db_session, user, chat_id=CHAT)
    handle_onboarding_callback(db_session, user, "done", "topics", chat_id=CHAT)

    size_reply = handle_onboarding_callback(
        db_session, user, "done", "kinds", chat_id=CHAT
    )
    assert "starter list" in size_reply.text
    assert "onb:size:500" in _data(size_reply)

    pace_reply = handle_onboarding_callback(
        db_session, user, "size", "100", chat_id=CHAT
    )
    assert "3 — light" in _labels(pace_reply)
    assert "10 — intense" in _labels(pace_reply)


def test_finishing_saves_prefs_seeds_items_and_clears_state(
    db_session, settings
) -> None:
    user = ensure_user(db_session, 123456789, settings)

    reply = _run_wizard(db_session, user, size=10)

    prefs = get_prefs(user)
    assert prefs.onboarded_at is not None
    assert prefs.topics == ["tech"]
    assert prefs.kinds == ["idioms"]
    assert prefs.words_per_day == 7
    assert prefs.starter_size == 10
    assert len(list_items(db_session, user.id, limit=100)) == 10
    assert StateStore(db_session).get(CHAT, user.telegram_user_id) is None
    assert "10 words added" in reply.text
    assert "/today 7" in reply.text


def test_finishing_explains_a_short_bank(db_session, settings) -> None:
    user = ensure_user(db_session, 123456789, settings)

    reply = _run_wizard(db_session, user, topics=("sports",), kinds=(), size=500)

    assert "the target was 500" in reply.text


def test_cancel_clears_the_wizard(db_session, settings) -> None:
    user = ensure_user(db_session, 123456789, settings)
    handle_onboarding_start(db_session, user, chat_id=CHAT)

    reply = handle_onboarding_callback(db_session, user, "cancel", "x", chat_id=CHAT)

    assert "cancelled" in reply.text
    assert StateStore(db_session).get(CHAT, user.telegram_user_id) is None


def test_callback_without_state_restarts_the_wizard(db_session, settings) -> None:
    user = ensure_user(db_session, 123456789, settings)

    reply = handle_onboarding_callback(db_session, user, "topic", "tech", chat_id=CHAT)

    assert "Pick a few topics" in reply.text
    state = StateStore(db_session).get(CHAT, user.telegram_user_id)
    assert state.name == ONBOARDING_STATE


def test_start_runs_the_wizard_only_once(db_session, settings) -> None:
    user = ensure_user(db_session, 123456789, settings)

    first = handle_start(db_session, settings, user.telegram_user_id, chat_id=CHAT)
    assert "Pick a few topics" in first.text

    _run_wizard(db_session, user, size=5)
    second = handle_start(db_session, settings, user.telegram_user_id, chat_id=CHAT)

    assert "Pick a few topics" not in second.text
    assert "/setup" in second.text


def test_setup_is_registered_in_both_catalogs() -> None:
    assert "/setup" in command_catalog()
    assert "setup" in {command for command, _ in BOT_COMMANDS}


def test_wizard_screens_redraw_in_place(db_session, settings) -> None:
    """One message for the whole wizard, not one per tap."""

    user = ensure_user(db_session, 123456789, settings)

    # The opening screen is a fresh message; it has no message to edit yet.
    assert handle_onboarding_start(db_session, user, chat_id=CHAT).edit_message is False

    # Everything driven by a button redraws the message it belongs to.
    toggled = handle_onboarding_callback(
        db_session, user, "topic", "tech", chat_id=CHAT
    )
    advanced = handle_onboarding_callback(
        db_session, user, "done", "topics", chat_id=CHAT
    )
    kind = handle_onboarding_callback(db_session, user, "kind", "idioms", chat_id=CHAT)
    size_screen = handle_onboarding_callback(
        db_session, user, "done", "kinds", chat_id=CHAT
    )
    pace_screen = handle_onboarding_callback(
        db_session, user, "size", "100", chat_id=CHAT
    )
    finished = handle_onboarding_callback(
        db_session, user, "perday", "5", chat_id=CHAT
    )

    for reply in (toggled, advanced, kind, size_screen, pace_screen, finished):
        assert reply.edit_message is True

    # The summary replaces the wizard, so no dead keyboard is left behind.
    assert finished.buttons is None


def test_wizard_tells_you_selection_is_multiple(db_session, settings) -> None:
    user = ensure_user(db_session, 123456789, settings)

    topics = handle_onboarding_start(db_session, user, chat_id=CHAT)
    handle_onboarding_callback(db_session, user, "done", "topics", chat_id=CHAT)
    kinds = handle_onboarding_callback(
        db_session, user, "kind", "idioms", chat_id=CHAT
    )

    assert "Tap to toggle" in topics.text
    assert "Pick as many as you like" in kinds.text
