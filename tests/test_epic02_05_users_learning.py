from __future__ import annotations

import pytest

from fluentloop.bot.handlers import handle_add_text, parse_add_payload
from fluentloop.learning import create_learning_item, favorite_items, toggle_favorite
from fluentloop.users import ensure_user, format_settings, update_setting


def test_settings_update_and_validation(db_session, settings) -> None:
    user = ensure_user(db_session, 123456789, settings)
    update_setting(db_session, user, "reminder_time", "20:30")
    update_setting(db_session, user, "timezone", "Europe/Berlin")
    assert "20:30" in format_settings(user)
    assert "Europe/Berlin" in format_settings(user)
    with pytest.raises(ValueError):
        update_setting(db_session, user, "timezone", "Mars/Base")


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
    assert "Added expression: align on" in reply.text


def test_add_text_returns_friendly_error(db_session, settings) -> None:
    user = ensure_user(db_session, 123456789, settings)
    reply = handle_add_text(db_session, user, "unknown | something")
    assert "Could not add item" in reply.text
