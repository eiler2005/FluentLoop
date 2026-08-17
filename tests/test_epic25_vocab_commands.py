from __future__ import annotations

from datetime import UTC, datetime

import pytest

from fluentloop.bot.handlers import (
    BotReply,
    command_catalog,
    handle_delete,
    handle_learned,
    handle_more,
    handle_pause,
    handle_resume,
    handle_settings,
    handle_vocab_add,
    handle_vocab_cards,
    handle_vocab_undo,
    handle_words,
)
from fluentloop.learning import USER_ADDED_PRIORITY, create_learning_item
from fluentloop.telegram_bot_api import BOT_COMMANDS
from fluentloop.users import ensure_user
from fluentloop.vocab_loop import (
    due_slots,
    guess_item_type,
    local_now,
    looks_like_word_list,
    midday_exercise_type,
    render_cards,
    select_cards,
    split_word_list,
)
from fluentloop.vocab_prefs import get_prefs, update_pref

NEW_COMMANDS = ("/words", "/more", "/learned", "/delete", "/pause", "/resume")


def _card_item(session, user, text: str, meaning: str, example: str):
    return create_learning_item(
        session,
        user,
        type_="expression",
        text=text,
        meaning=meaning,
        examples=[example],
    )


# --- slot timing -----------------------------------------------------------


@pytest.mark.parametrize(
    ("clock", "expected"),
    [
        ("08:00", ["morning"]),
        ("08:45", ["morning"]),
        ("09:29", ["morning"]),
        ("09:31", []),
        ("13:00", ["midday"]),
        ("19:05", ["evening"]),
        ("03:00", []),
    ],
)
def test_due_slots_window(clock, expected) -> None:
    from fluentloop.vocab_prefs import VocabPrefs

    hour, minute = (int(part) for part in clock.split(":"))
    now_local = datetime(2026, 8, 17, hour, minute, tzinfo=UTC)

    assert due_slots(VocabPrefs(), now_local) == expected


def test_due_slots_empty_when_paused() -> None:
    from fluentloop.vocab_prefs import VocabPrefs

    now_local = datetime(2026, 8, 17, 8, 0, tzinfo=UTC)

    assert due_slots(VocabPrefs(paused=True), now_local) == []


def test_local_now_uses_user_timezone(db_session, settings) -> None:
    user = ensure_user(db_session, 123456789, settings)
    user.timezone = "Europe/Moscow"
    moment = datetime(2026, 8, 17, 5, 0, tzinfo=UTC)

    assert local_now(user, now=moment).hour == 8


def test_local_now_falls_back_to_utc_on_bad_timezone(db_session, settings) -> None:
    user = ensure_user(db_session, 123456789, settings)
    user.timezone = "Mars/Olympus"
    moment = datetime(2026, 8, 17, 5, 0, tzinfo=UTC)

    assert local_now(user, now=moment).hour == 5


def test_midday_type_rotates_and_includes_writing() -> None:
    from datetime import date, timedelta

    start = date(2026, 8, 17)
    types = {
        midday_exercise_type(start + timedelta(days=offset)) for offset in range(3)
    }

    assert "mini_writing" in types
    assert len(types) == 3


# --- card rendering --------------------------------------------------------


def test_render_cards_matches_the_expected_shape(db_session, settings) -> None:
    user = ensure_user(db_session, 123456789, settings)
    item = _card_item(
        db_session,
        user,
        "cut corners",
        "to do something the cheapest way",
        "They cut corners on testing.",
    )

    text = render_cards([item])

    assert "🌅 <b>Morning phrases</b>" in text
    assert "1. <b>cut corners</b> — They cut corners on testing." in text
    assert "<i>to do something the cheapest way</i>" in text


def test_render_cards_escapes_user_text(db_session, settings) -> None:
    user = ensure_user(db_session, 123456789, settings)
    item = _card_item(db_session, user, "a < b", "less than", "x < y")

    text = render_cards([item])

    assert "&lt;" in text
    assert "a < b" not in text


def test_render_cards_survives_missing_example_and_meaning(
    db_session, settings
) -> None:
    user = ensure_user(db_session, 123456789, settings)
    item = create_learning_item(db_session, user, type_="word", text="bare")

    text = render_cards([item])

    assert "1. <b>bare</b>" in text
    assert "—" not in text


def test_select_cards_respects_count(db_session, settings) -> None:
    user = ensure_user(db_session, 123456789, settings)
    for index in range(6):
        create_learning_item(db_session, user, type_="word", text=f"word-{index}")

    assert len(select_cards(db_session, user, count=3)) == 3


def test_select_cards_skips_non_card_types(db_session, settings) -> None:
    user = ensure_user(db_session, 123456789, settings)
    create_learning_item(
        db_session, user, type_="grammar_rule", text="present perfect"
    )
    create_learning_item(db_session, user, type_="word", text="pipeline")

    selected = select_cards(db_session, user, count=5)

    assert [item.text for item in selected] == ["pipeline"]


def test_vocab_cards_uses_words_per_day_by_default(db_session, settings) -> None:
    user = ensure_user(db_session, 123456789, settings)
    update_pref(db_session, user, "words_per_day", 2)
    for index in range(5):
        create_learning_item(db_session, user, type_="word", text=f"word-{index}")

    reply = handle_vocab_cards(db_session, user)

    assert reply.text.count("<b>word-") == 2


def test_vocab_cards_clamps_requested_count(db_session, settings) -> None:
    user = ensure_user(db_session, 123456789, settings)
    for index in range(3):
        create_learning_item(db_session, user, type_="word", text=f"word-{index}")

    reply = handle_vocab_cards(db_session, user, 99)

    assert isinstance(reply, BotReply)
    assert reply.text.count("<b>word-") == 3


def test_vocab_cards_without_items_invites_adding(db_session, settings) -> None:
    user = ensure_user(db_session, 123456789, settings)

    reply = handle_vocab_cards(db_session, user)

    assert "Send me any word or phrase" in reply.text


# --- word list detection ---------------------------------------------------


@pytest.mark.parametrize(
    "raw",
    [
        "cut corners",
        "cut corners, push back on, roll out",
        "cut corners\npush back on\nroll out",
        "layoff; level up",
    ],
)
def test_looks_like_word_list_accepts_lists(raw) -> None:
    assert looks_like_word_list(raw) is True


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "   ",
        "/today",
        "We had a long meeting about the roadmap and agreed to postpone.",
        "Hello there.",
        ", ".join(f"word{index}" for index in range(25)),
        "x" * 400,
        "123, 456",
    ],
)
def test_looks_like_word_list_rejects_non_lists(raw) -> None:
    assert looks_like_word_list(raw) is False


def test_split_word_list_dedupes_case_insensitively() -> None:
    assert split_word_list("cut corners, Cut Corners, roll out") == [
        "cut corners",
        "roll out",
    ]


def test_guess_item_type() -> None:
    assert guess_item_type("pipeline") == "word"
    assert guess_item_type("cut corners") == "expression"


# --- bulk add --------------------------------------------------------------


def test_vocab_add_creates_items_with_priority(db_session, settings) -> None:
    user = ensure_user(db_session, 123456789, settings)

    reply = handle_vocab_add(db_session, user, "cut corners, pipeline, roll out")

    assert "Added 3:" in reply.text
    assert "Your own words always get top priority." in reply.text
    items = select_cards(db_session, user, count=10)
    assert {item.text for item in items} == {"cut corners", "pipeline", "roll out"}
    assert all(item.priority == USER_ADDED_PRIORITY for item in items)


def test_vocab_add_reports_duplicates_on_second_call(db_session, settings) -> None:
    user = ensure_user(db_session, 123456789, settings)
    handle_vocab_add(db_session, user, "cut corners")

    reply = handle_vocab_add(db_session, user, "cut corners, pipeline")

    assert "Added 1:" in reply.text
    assert "Already had 1:" in reply.text


def test_vocab_add_offers_material_and_undo_paths(db_session, settings) -> None:
    user = ensure_user(db_session, 123456789, settings)

    reply = handle_vocab_add(db_session, user, "cut corners")

    data = [button.data for row in reply.buttons for button in row]
    assert "upload:confirm:pending" in data
    assert any(item.startswith("vocab:undo:") for item in data)


def test_vocab_add_boosts_priority_of_previously_seeded_item(
    db_session, settings
) -> None:
    user = ensure_user(db_session, 123456789, settings)
    create_learning_item(db_session, user, type_="word", text="pipeline")

    handle_vocab_add(db_session, user, "pipeline")

    items = select_cards(db_session, user, count=5)
    assert items[0].priority == USER_ADDED_PRIORITY


def test_vocab_undo_archives_added_items(db_session, settings) -> None:
    user = ensure_user(db_session, 123456789, settings)
    added = handle_vocab_add(db_session, user, "cut corners")
    undo_data = next(
        button.data
        for row in added.buttons
        for button in row
        if button.data.startswith("vocab:undo:")
    )
    ids = undo_data.split(":", 2)[2]

    reply = handle_vocab_undo(db_session, user, ids)

    assert "Removed 1" in reply.text
    assert select_cards(db_session, user, count=5) == []


def test_vocab_undo_ignores_unknown_ids(db_session, settings) -> None:
    user = ensure_user(db_session, 123456789, settings)

    assert "Nothing to undo" in handle_vocab_undo(db_session, user, "999,abc").text


# --- word management commands ----------------------------------------------


def test_words_lists_counts_and_upcoming(db_session, settings) -> None:
    user = ensure_user(db_session, 123456789, settings)
    handle_vocab_add(db_session, user, "cut corners")
    create_learning_item(db_session, user, type_="word", text="graduated-one")
    handle_learned(db_session, user, "graduated-one")

    reply = handle_words(db_session, user)

    assert "Active: 1" in reply.text
    assert "🎓 Graduated: 1" in reply.text
    assert "cut corners" in reply.text
    assert "(yours)" in reply.text


def test_learned_graduates_and_offers_undo(db_session, settings) -> None:
    user = ensure_user(db_session, 123456789, settings)
    item = create_learning_item(db_session, user, type_="word", text="streamline")

    reply = handle_learned(db_session, user, "Streamline")

    assert "🎓 Graduated" in reply.text
    assert item.status == "graduated"
    assert reply.buttons[0][0].data == f"item:restore:{item.id}"


def test_learned_pushes_due_date_far_out(db_session, settings) -> None:
    from fluentloop.db.models import ReviewState

    user = ensure_user(db_session, 123456789, settings)
    item = create_learning_item(db_session, user, type_="word", text="streamline")

    handle_learned(db_session, user, "streamline")

    state = db_session.query(ReviewState).filter_by(learning_item_id=item.id).one()
    assert (state.due_at.replace(tzinfo=UTC) - datetime.now(UTC)).days > 700


def test_learned_without_match_suggests_near_ones(db_session, settings) -> None:
    user = ensure_user(db_session, 123456789, settings)
    create_learning_item(db_session, user, type_="expression", text="cut corners")

    reply = handle_learned(db_session, user, "corners")

    assert "Did you mean" in reply.text
    assert "cut corners" in reply.text


def test_learned_requires_an_argument(db_session, settings) -> None:
    user = ensure_user(db_session, 123456789, settings)

    assert "Use /learned" in handle_learned(db_session, user, "").text


def test_delete_archives_and_offers_undo(db_session, settings) -> None:
    user = ensure_user(db_session, 123456789, settings)
    item = create_learning_item(db_session, user, type_="word", text="layoff")

    reply = handle_delete(db_session, user, "layoff")

    assert item.status == "archived"
    assert reply.buttons[0][0].data == f"item:restore:{item.id}"


def test_more_renders_stored_details(db_session, settings) -> None:
    user = ensure_user(db_session, 123456789, settings)
    create_learning_item(
        db_session,
        user,
        type_="expression",
        text="cut corners",
        meaning="do it the cheap way",
        examples=["They cut corners on testing."],
        metadata={"synonyms": ["skimp"], "collocations": ["cut corners on"]},
    )

    reply = handle_more(db_session, user, "cut corners")

    assert "<b>Synonyms:</b> skimp" in reply.text
    assert "cut corners on" in reply.text
    assert "They cut corners on testing." in reply.text


def test_more_without_details_says_so(db_session, settings) -> None:
    user = ensure_user(db_session, 123456789, settings)
    create_learning_item(db_session, user, type_="word", text="bare")

    reply = handle_more(db_session, user, "bare")

    assert "No details stored" in reply.text


def test_pause_and_resume_toggle_the_loop(db_session, settings) -> None:
    user = ensure_user(db_session, 123456789, settings)

    paused = handle_pause(db_session, user)
    assert "paused" in paused.text.lower()
    assert get_prefs(user).paused is True

    resumed = handle_resume(db_session, user)
    assert "08:00" in resumed.text
    assert get_prefs(user).paused is False


def test_settings_shows_the_daily_loop(db_session, settings) -> None:
    user = ensure_user(db_session, 123456789, settings)

    reply = handle_settings(db_session, user)

    assert "Daily loop: on" in reply.text
    data = [button.data for row in reply.buttons for button in row]
    assert "settings:vocab_morning:08:00" in data
    assert "settings:vocab_words_per_day:5" in data


def test_vocab_setting_update_survives_split_on_colon(db_session, settings) -> None:
    from fluentloop.bot.handlers import handle_setting_update

    user = ensure_user(db_session, 123456789, settings)
    # app.py splits callback data with maxsplit=2, so "07:00" arrives whole.
    callback_data = "settings:vocab_morning:07:00"
    field, value = callback_data.split(":", 2)[1:]

    handle_setting_update(db_session, user, field, value)

    assert get_prefs(user).slots["morning"] == "07:00"


def test_new_commands_are_registered_in_both_catalogs() -> None:
    catalog = set(command_catalog())
    menu = {f"/{command}" for command, _ in BOT_COMMANDS}

    for command in NEW_COMMANDS:
        assert command in catalog
        assert command in menu


def test_help_explains_the_daily_loop(db_session, settings) -> None:
    from fluentloop.bot.handlers import handle_help

    text = handle_help().text

    # The three slots, with times, so the learner knows what to expect.
    for marker in ("Morning 08:00", "Midday  13:00", "Evening 19:00"):
        assert marker in text
    # How to answer each kind of prompt.
    assert "reply with a message" in text
    assert "Tap an option" in text
    # The language rule and the graduation rule.
    assert "Russian appears only after you answer" in text
    assert "graduates" in text
    # Adding your own words, and every daily-loop command.
    assert "cut corners, push back on, roll out" in text
    for command in NEW_COMMANDS + ("/setup", "/today 5"):
        assert command in text


def test_help_disambiguates_cards_review_and_lessons() -> None:
    """The four commands train the same words; /help must say which to pick."""

    from fluentloop.bot.handlers import handle_help

    text = handle_help().text

    assert "train the SAME words" in text
    for command in ("/today 5", "/review", "/practice vocab", "/today"):
        assert command in text
    assert "Start here to practise them." in text


def test_pinned_workspace_help_covers_the_daily_loop() -> None:
    from fluentloop.bot.handlers import handle_channel_help

    text = handle_channel_help("-100123").text

    assert "words at 08:00" in text
    assert "/review drills the words that are due" in text
    assert "/practice vocab" in text
    assert "/pause" in text


def test_start_message_points_at_the_loop_and_practice() -> None:
    from fluentloop.bot.messages import start_message

    text = start_message()

    assert "08:00" in text
    assert "/review" in text
    assert "/practice vocab" in text
    assert "/help" in text


# --- the words / lessons fork ---------------------------------------------


def test_today_menu_offers_both_tracks(db_session, settings) -> None:
    from fluentloop.bot.handlers import handle_today_menu

    user = ensure_user(db_session, 123456789, settings)
    create_learning_item(db_session, user, type_="word", text="pipeline")

    reply = handle_today_menu(db_session, user)

    data = [button.data for row in reply.buttons for button in row]
    assert data == ["today:words", "today:lesson"]
    assert "about 2 minutes" in reply.text
    assert "about 15 minutes" in reply.text


def test_today_menu_reports_what_is_due(db_session, settings) -> None:
    from fluentloop.bot.handlers import handle_today_menu

    user = ensure_user(db_session, 123456789, settings)
    empty = handle_today_menu(db_session, user)
    create_learning_item(db_session, user, type_="word", text="pipeline")
    filled = handle_today_menu(db_session, user)

    assert "Nothing due right now" in empty.text
    assert "1 due now" in filled.text


def test_words_menu_offers_the_three_intensities(db_session, settings) -> None:
    from fluentloop.bot.handlers import handle_words_menu

    user = ensure_user(db_session, 123456789, settings)
    create_learning_item(db_session, user, type_="word", text="pipeline")

    reply = handle_words_menu(db_session, user, edit=True)

    data = [button.data for row in reply.buttons for button in row]
    assert data == ["words:cards", "words:review", "words:lesson"]
    assert reply.edit_message is True
    assert "Active: 1" in reply.text


def test_practice_modes_are_grouped() -> None:
    from fluentloop.lesson_formats import (
        LESSON_FORMATS,
        grouped_practice_modes,
        practice_modes_help,
    )

    groups = grouped_practice_modes()
    headings = [heading for heading, _ in groups]
    assert headings[:3] == ["Words", "Grammar and mistakes", "Writing and speaking"]

    # Every mode still appears exactly once.
    listed = [item.mode for _, members in groups for item in members]
    assert sorted(listed) == sorted(item.mode for item in LESSON_FORMATS)
    assert len(listed) == len(set(listed))

    text = practice_modes_help()
    for heading in headings:
        assert f"{heading}:" in text
    assert "/practice vocab" in text


def test_cards_command_is_registered() -> None:
    assert "/cards" in command_catalog()
    assert "cards" in {command for command, _ in BOT_COMMANDS}
