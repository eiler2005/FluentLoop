from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from fluentloop.db.models import ReviewState
from fluentloop.learning import (
    USER_ADDED_PRIORITY,
    create_learning_item,
    list_items,
    set_item_status,
)
from fluentloop.learning_engine import score_learning_items
from fluentloop.srs import (
    apply_review,
    get_due_items,
    is_graduation_ready,
    record_result,
)
from fluentloop.users import ensure_user
from fluentloop.vocab_prefs import (
    DEFAULT_SLOTS,
    get_prefs,
    mark_onboarded,
    parse_hhmm,
    set_prefs,
    update_pref,
)


def test_prefs_default_for_user_without_preferences(db_session, settings) -> None:
    user = ensure_user(db_session, 123456789, settings)

    prefs = get_prefs(user)

    assert prefs.slots == DEFAULT_SLOTS
    assert prefs.paused is False
    assert prefs.words_per_day == 5
    assert prefs.onboarded_at is None


def test_prefs_roundtrip_survives_commit(db_session, settings) -> None:
    user = ensure_user(db_session, 123456789, settings)

    update_pref(db_session, user, "morning", "07:15")
    update_pref(db_session, user, "words_per_day", 7)
    update_pref(db_session, user, "topics", "tech, business")
    db_session.commit()
    db_session.expire_all()

    prefs = get_prefs(user)
    assert prefs.slots["morning"] == "07:15"
    assert prefs.slots["evening"] == DEFAULT_SLOTS["evening"]
    assert prefs.words_per_day == 7
    assert prefs.topics == ["tech", "business"]


def test_prefs_reject_bad_values(db_session, settings) -> None:
    user = ensure_user(db_session, 123456789, settings)

    with pytest.raises(ValueError):
        update_pref(db_session, user, "morning", "7:15")
    with pytest.raises(ValueError):
        update_pref(db_session, user, "words_per_day", 0)
    with pytest.raises(ValueError):
        update_pref(db_session, user, "words_per_day", 21)
    with pytest.raises(ValueError):
        update_pref(db_session, user, "starter_size", 250)
    with pytest.raises(ValueError):
        update_pref(db_session, user, "nonsense", "x")


def test_prefs_preserve_unrelated_preference_namespaces(db_session, settings) -> None:
    user = ensure_user(db_session, 123456789, settings)
    user.preferences_json = {"other": {"keep": True}}
    db_session.add(user)
    db_session.flush()

    set_prefs(db_session, user, get_prefs(user))

    assert user.preferences_json["other"] == {"keep": True}
    assert "vocab" in user.preferences_json


def test_parse_hhmm_returns_minutes_since_midnight() -> None:
    assert parse_hhmm("00:00") == 0
    assert parse_hhmm("08:30") == 510
    assert parse_hhmm("23:59") == 1439
    with pytest.raises(ValueError):
        parse_hhmm("24:00")
    with pytest.raises(ValueError):
        parse_hhmm("08:60")


def test_mark_onboarded_stamps_timestamp(db_session, settings) -> None:
    user = ensure_user(db_session, 123456789, settings)

    prefs = mark_onboarded(db_session, user)

    assert prefs.onboarded_at is not None
    assert get_prefs(user).onboarded_at == prefs.onboarded_at


def test_graduation_requires_long_interval_and_successes(db_session, settings) -> None:
    user = ensure_user(db_session, 123456789, settings)
    item = create_learning_item(db_session, user, type_="word", text="streamline")
    state = db_session.scalar(
        ReviewState.__table__.select().where(
            ReviewState.__table__.c.learning_item_id == item.id
        )
    )
    assert state is not None

    # A 25-day interval is not enough even with plenty of successes.
    review = record_result(db_session, item.id, "Good")
    review.last_interval_days = 25.0
    review.success_count = 6
    review.last_result = "Good"
    db_session.flush()
    assert is_graduation_ready(review) is False

    review.last_interval_days = 120.0
    review.success_count = 3
    assert is_graduation_ready(review) is False

    review.success_count = 4
    assert is_graduation_ready(review) is True

    review.last_result = "Again"
    assert is_graduation_ready(review) is False


def test_apply_review_graduates_item_once(db_session, settings) -> None:
    user = ensure_user(db_session, 123456789, settings)
    item = create_learning_item(db_session, user, type_="word", text="streamline")
    review = record_result(db_session, item.id, "Good")
    review.last_interval_days = 120.0
    review.success_count = 4
    db_session.flush()

    _, graduated = apply_review(db_session, item, "Good")

    assert graduated is True
    assert item.status == "graduated"

    _, graduated_again = apply_review(db_session, item, "Good")
    assert graduated_again is False


def test_apply_review_keeps_active_item_below_threshold(db_session, settings) -> None:
    user = ensure_user(db_session, 123456789, settings)
    item = create_learning_item(db_session, user, type_="word", text="layoff")

    state, graduated = apply_review(db_session, item, "Good")

    assert graduated is False
    assert item.status == "active"
    assert state.success_count == 1


def test_graduated_items_leave_the_due_queue(db_session, settings) -> None:
    user = ensure_user(db_session, 123456789, settings)
    active = create_learning_item(db_session, user, type_="word", text="pipeline")
    done = create_learning_item(db_session, user, type_="word", text="rollout")
    set_item_status(db_session, done, "graduated")

    due = get_due_items(db_session, user.id)

    assert active in due
    assert done not in due
    graduated = list_items(db_session, user.id, status="graduated")
    assert [item.text for item in graduated] == ["rollout"]


def test_user_added_items_sort_before_seeded_items(db_session, settings) -> None:
    user = ensure_user(db_session, 123456789, settings)
    now = datetime.now(UTC)
    seeded = create_learning_item(db_session, user, type_="word", text="from-bank")
    mine = create_learning_item(
        db_session,
        user,
        type_="word",
        text="my-own",
        priority=USER_ADDED_PRIORITY,
    )
    for item, due_at in ((seeded, now - timedelta(hours=2)), (mine, now)):
        state = db_session.query(ReviewState).filter_by(learning_item_id=item.id).one()
        state.due_at = due_at
    db_session.flush()

    due = get_due_items(db_session, user.id)

    assert [item.text for item in due] == ["my-own", "from-bank"]


def test_score_learning_items_rewards_user_added(db_session, settings) -> None:
    user = ensure_user(db_session, 123456789, settings)
    create_learning_item(
        db_session,
        user,
        type_="word",
        text="my-own",
        priority=USER_ADDED_PRIORITY,
    )

    scored = score_learning_items(db_session, user)

    assert scored
    assert "user_added" in scored[0].reasons


def test_create_learning_item_defaults_to_zero_priority(db_session, settings) -> None:
    user = ensure_user(db_session, 123456789, settings)

    item = create_learning_item(db_session, user, type_="word", text="baseline")

    assert item.priority == 0
