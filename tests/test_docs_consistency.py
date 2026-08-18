"""Documentation claims checked against the code.

Docs drift silently: a command gets renamed, a default changes, a keyboard
grows a button, and the guide keeps describing last week's bot. These assert
the specific claims that are cheap to verify and expensive to get wrong,
because a learner following a stale instruction has no way to tell.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from fluentloop.bot.handlers import QUICK_ACTIONS, command_catalog
from fluentloop.bot.polls import QUIZ_SLOTS
from fluentloop.learning_engine import (
    DEFAULT_MICRO_DRILL_COUNT,
    QUICK_REVIEW_DRILL_COUNT,
)
from fluentloop.lesson_formats import grouped_practice_modes
from fluentloop.telegram_bot_api import BOT_COMMANDS
from fluentloop.vocab_prefs import DEFAULTS, QUIZ_SIZES, SLOTS

ROOT = Path(__file__).resolve().parents[1]


def _doc(name: str) -> str:
    return (ROOT / name).read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def docs() -> dict[str, str]:
    return {
        "epic": _doc("docs/features/EPIC-25-daily-vocabulary-loop.md"),
        "readme": _doc("README.md"),
        "guide": _doc("docs/user-guide.md"),
        "arch": _doc("docs/architecture.md"),
        "agents": _doc("AGENTS.md"),
        "adr11": _doc("docs/adr/0011-native-telegram-quiz-polls.md"),
        "adr12": _doc("docs/adr/0012-per-user-slot-dispatcher.md"),
    }


def test_every_keyboard_button_is_documented(docs) -> None:
    """A button nobody documented is a button nobody knows how to use."""

    labels = [label for label, _ in QUICK_ACTIONS]
    for label in labels:
        assert label in docs["epic"], f"{label} missing from the epic"
        assert label in docs["guide"], f"{label} missing from the user guide"


def test_command_catalogs_agree(docs) -> None:
    """The in-bot catalog and the Telegram menu must not diverge."""

    catalog = set(command_catalog())
    menu = {f"/{command}" for command, _ in BOT_COMMANDS}
    for command in ("/quiz", "/stop", "/cards", "/words", "/setup"):
        assert command in catalog, f"{command} missing from command_catalog()"
        assert command in menu, f"{command} missing from BOT_COMMANDS"


def test_quiz_shape_matches_the_adr(docs) -> None:
    for slot in QUIZ_SLOTS:
        assert slot in docs["adr11"], f"slot {slot!r} undocumented"
    assert "a sequence" in docs["adr11"]
    assert "seq=0" in docs["agents"]


def test_quiz_sizes_and_default_are_documented(docs) -> None:
    listed = "/".join(str(size) for size in QUIZ_SIZES)
    assert listed in docs["epic"] or listed in docs["readme"]
    assert str(DEFAULTS.quiz_size) in docs["readme"]


def test_slot_defaults_are_documented(docs) -> None:
    for slot in SLOTS:
        assert DEFAULTS.slots[slot] in docs["guide"], f"{slot} time missing"


def test_review_is_documented_as_the_short_rung(docs) -> None:
    assert QUICK_REVIEW_DRILL_COUNT < DEFAULT_MICRO_DRILL_COUNT
    assert "six-step" in _doc("CHANGELOG.md")


def test_practice_groups_are_documented(docs) -> None:
    for heading, _ in grouped_practice_modes()[:3]:
        assert heading in docs["epic"], f"group {heading!r} undocumented"


def test_savepoint_rule_is_recorded(docs) -> None:
    """The claim-rollback defect cost a production incident; keep it written."""

    assert "SAVEPOINT" in docs["adr12"]
    assert "begin_nested" in docs["adr12"]


def test_card_rules_are_written_down(docs) -> None:
    """The card spec is non-obvious enough that losing it costs a bug.

    Both defects it records - a predicate disagreeing about where the Russian
    gloss lives, and a generation prompt stored as an example - were invisible
    until they reached a learner.
    """

    epic = docs["epic"]
    assert "Card composition rules" in epic
    for helper in ("stored_russian", "usable_example", "enrich_item"):
        assert helper in epic, f"{helper} undocumented"
    # The rule that keeps enrichment off the delivery path.
    assert "word_cards" in docs["arch"]
    assert "stored_russian" in docs["agents"]


def test_scheduler_job_count_is_current(docs, settings) -> None:
    """The diagram claimed three jobs long after there were five."""

    from fluentloop.db.session import make_engine, make_session_factory
    from fluentloop.scheduler import build_scheduler

    class _Client:
        pass

    factory = make_session_factory(make_engine("sqlite:///:memory:"))
    scheduler = build_scheduler(settings, factory, client=_Client())

    assert len(scheduler.get_jobs()) == 5
    assert "five jobs" in docs["arch"]
