from copy import deepcopy

import pytest

from fluentloop.bot.roadmap import handle_roadmap
from fluentloop.users import ensure_user
from fluentloop.workplace_roadmap import (
    default_plan,
    get_plan,
    plan_outline,
    save_plan,
    update_plan,
    validate_plan,
)


def test_legacy_plan_is_normalized_without_changing_preferences(db_session, settings):
    user = ensure_user(db_session, 123456789, settings)
    legacy = default_plan()
    legacy.pop("lexical_share")
    legacy["general_share"] = 70
    user.preferences_json = {"workplace_plan": legacy, "unrelated": {"keep": True}}
    before = deepcopy(user.preferences_json)
    assert get_plan(user)["lexical_share"] == 0
    assert get_plan(user)["general_share"] == 70
    assert user.preferences_json == before
    assert validate_plan(legacy)["lexical_share"] == 0


@pytest.mark.parametrize("share", [-1, 61, True, 30.0, "30", None])
def test_lexical_share_rejects_bad_values(share):
    plan = default_plan()
    plan["lexical_share"] = share
    with pytest.raises(ValueError):
        validate_plan(plan)


def test_invalid_combined_allocation_is_atomic(db_session, settings):
    user = ensure_user(db_session, 123456789, settings)
    save_plan(db_session, user, default_plan())
    before = deepcopy(user.preferences_json)
    with pytest.raises(ValueError, match="at least 10%"):
        update_plan(db_session, user, "general_share", 70)
    assert user.preferences_json == before


def test_three_weekly_parts_sum_to_total_even_with_rounding():
    for minutes in (30, 149, 150, 151, 1200):
        plan = default_plan()
        plan["weekly_minutes"] = minutes
        outline = plan_outline(plan)
        assert (
            sum(
                outline[key]
                for key in ("general_minutes", "work_minutes", "lexical_minutes")
            )
            == minutes
        )
    outline = plan_outline(default_plan())
    assert (
        outline["general_minutes"],
        outline["work_minutes"],
        outline["lexical_minutes"],
    ) == (45, 60, 45)


def test_telegram_lexical_edit_is_personal_and_preserves_other_plan_fields(
    db_session, settings
):
    user = ensure_user(db_session, 123456789, settings)
    other = ensure_user(db_session, 123456790, settings)
    plan = default_plan()
    plan.update(
        lexical_share=0,
        focus="client_discovery",
        notes={"client_discovery": "My priorities"},
    )
    save_plan(db_session, user, plan)
    other_before = deepcopy(other.preferences_json)
    reply = handle_roadmap(db_session, user, "lexical 30")
    assert "Не удалось" not in reply.text
    assert get_plan(user) == {**plan, "lexical_share": 30}
    assert other.preferences_json == other_before
