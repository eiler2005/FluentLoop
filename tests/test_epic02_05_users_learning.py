from __future__ import annotations

import pytest

from fluentloop.bot.handlers import (
    handle_add_text,
    handle_favorite_toggle,
    handle_favorites,
    handle_item_status,
    handle_items,
    handle_setting_update,
    handle_settings,
    parse_add_payload,
)
from fluentloop.learning import create_learning_item, favorite_items, toggle_favorite
from fluentloop.users import ensure_user, format_settings, update_setting


def test_settings_update_and_validation(db_session, settings) -> None:
    user = ensure_user(db_session, 123456789, settings)
    before = user.updated_at
    update_setting(db_session, user, "level", "C1")
    update_setting(db_session, user, "focus_areas", "business, architecture")
    update_setting(db_session, user, "reminder_time", "20:30")
    update_setting(db_session, user, "timezone", "Europe/Berlin")
    update_setting(db_session, user, "explanation_language", "en")
    update_setting(db_session, user, "practice_duration_minutes", "25")
    assert user.updated_at > before
    assert "C1" in format_settings(user)
    assert "architecture" in format_settings(user)
    assert "20:30" in format_settings(user)
    assert "Europe/Berlin" in format_settings(user)
    assert "25 min" in format_settings(user)
    with pytest.raises(ValueError):
        update_setting(db_session, user, "timezone", "Mars/Base")

    settings_reply = handle_settings(db_session, user)
    assert settings_reply.buttons is not None
    button_data = {
        button.data for row in settings_reply.buttons for button in row
    }
    assert "settings:practice_duration_minutes:25" in button_data
    assert "settings:explanation_language:mixed" in button_data

    updated = handle_setting_update(
        db_session, user, "practice_duration_minutes", "15"
    )
    assert "15 min" in updated.text
    assert updated.buttons is not None


def test_learning_item_creates_review_state_and_favorite(db_session, settings) -> None:
    user = ensure_user(db_session, 123456789, settings)
    item = create_learning_item(
        db_session,
        user,
        type_="expression",
        text="push back on",
        meaning="мягко возражать",
        tags=["meetings"],
    )
    assert item.review_state is not None
    duplicate = create_learning_item(
        db_session,
        user,
        type_="expression",
        text="push back on",
    )
    assert duplicate.id == item.id
    toggle_favorite(db_session, item)
    assert favorite_items(db_session, user.id)[0].text == "push back on"


def test_add_text_payload_creates_item(db_session, settings) -> None:
    user = ensure_user(db_session, 123456789, settings)
    parsed = parse_add_payload(
        "expression | push back on | мягко возражать | meetings, stakeholders"
    )
    assert parsed == (
        "expression",
        "push back on",
        "мягко возражать",
        ["meetings", "stakeholders"],
    )
    reply = handle_add_text(
        db_session,
        user,
        "expression | align on | согласовать | planning",
    )
    assert "Added #" in reply.text
    assert "expression: align on" in reply.text
    assert reply.buttons is not None
    assert reply.buttons[0][0].data == "favorite:toggle:1"
    duplicate = handle_add_text(
        db_session,
        user,
        "expression | align on | согласовать | planning",
    )
    assert "Duplicate item" in duplicate.text
    assert "Merge" in duplicate.text
    assert "Keep separate" in duplicate.text


def test_add_text_returns_friendly_error(db_session, settings) -> None:
    user = ensure_user(db_session, 123456789, settings)
    reply = handle_add_text(db_session, user, "unknown | something")
    assert "Could not add item" in reply.text


def test_favorite_toggle_command_flow(db_session, settings) -> None:
    user = ensure_user(db_session, 123456789, settings)
    item = create_learning_item(db_session, user, type_="expression", text="align on")
    reply = handle_favorite_toggle(db_session, user, item.id)
    assert "favorite" in reply.text
    assert reply.buttons is not None
    assert reply.buttons[0][0].text == "Unstar #1"
    favorites = handle_favorites(db_session, user)
    assert "#1" in favorites.text
    assert favorites.buttons is not None
    assert favorites.buttons[0][0].data == "favorite:toggle:1"


def test_item_list_and_status_command_flow(db_session, settings) -> None:
    user = ensure_user(db_session, 123456789, settings)
    item = create_learning_item(db_session, user, type_="expression", text="align on")
    active_reply = handle_items(db_session, user)
    assert "#1 [expression] align on" in active_reply.text
    assert active_reply.buttons is not None
    active_data = {button.data for button in active_reply.buttons[0]}
    assert active_data == {
        "favorite:toggle:1",
        "item:archive:1",
        "item:suspend:1",
    }

    archive_reply = handle_item_status(db_session, user, item.id, "archive")
    assert "archived" in archive_reply.text
    assert archive_reply.buttons is not None
    assert archive_reply.buttons[0][1].data == "item:restore:1"
    assert "No active learning items" in handle_items(db_session, user).text
    assert "#1 [expression] align on" in handle_items(
        db_session, user, "archived"
    ).text

    restore_reply = handle_item_status(db_session, user, item.id, "restore")
    assert "active" in restore_reply.text
