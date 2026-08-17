from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from fluentloop.learning import list_items
from fluentloop.users import ensure_user
from fluentloop.wordbank import (
    KINDS,
    SETS,
    TOPICS,
    WordBankEntry,
    load_wordbank,
    seed_starter_list,
    seed_wordbank,
    select_starter_entries,
)

VALID = {
    "id": "test-1",
    "text": "cut corners",
    "type": "expression",
    "meaning": "do it the cheap way",
    "example": "They cut corners.",
    "topics": ["business"],
    "kinds": ["idioms"],
    "sets": [],
    "cefr": "B2",
    "distractors": ["a", "b", "c"],
}


# --- the shipped bank ------------------------------------------------------


def test_shipped_bank_parses_and_is_well_formed() -> None:
    entries = load_wordbank()

    assert len(entries) >= 100
    assert len({entry.id for entry in entries}) == len(entries)
    assert len({entry.text.casefold() for entry in entries}) == len(entries)
    for entry in entries:
        assert entry.meaning, entry.id
        assert entry.example, entry.id
        assert len(entry.distractors) >= 3, entry.id
        assert entry.text not in entry.distractors, entry.id


def test_shipped_bank_covers_every_category() -> None:
    entries = load_wordbank()
    topics = {topic for entry in entries for topic in entry.topics}
    kinds = {kind for entry in entries for kind in entry.kinds}
    sets = {name for entry in entries for name in entry.sets}

    assert topics == TOPICS
    assert kinds == KINDS
    assert sets == SETS


def test_missing_bank_file_is_not_an_error(tmp_path) -> None:
    assert load_wordbank(tmp_path / "nope.jsonl") == []


def test_loader_reports_the_offending_line(tmp_path) -> None:
    path = tmp_path / "bad.jsonl"
    path.write_text(
        json.dumps(VALID) + "\n" + json.dumps({**VALID, "cefr": "Z9"}) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match=r":2:"):
        load_wordbank(path)


# --- validation ------------------------------------------------------------


@pytest.mark.parametrize(
    "override",
    [
        {"topics": ["not-a-topic"]},
        {"kinds": ["not-a-kind"]},
        {"sets": ["not-a-set"]},
        {"cefr": "Z9"},
        {"type": "not-a-type"},
    ],
)
def test_entry_rejects_unknown_values(override) -> None:
    with pytest.raises(ValidationError):
        WordBankEntry.model_validate({**VALID, **override})


def test_entry_metadata_carries_prebaked_quiz() -> None:
    entry = WordBankEntry.model_validate(
        {**VALID, "synonyms": ["skimp"], "collocations": ["cut corners on"]}
    )

    metadata = entry.metadata()

    assert metadata["mcq"]["distractors"] == ["a", "b", "c"]
    assert metadata["synonyms"] == ["skimp"]
    assert metadata["source"] == "wordbank"
    assert "wordbank" in entry.tags()


def test_entry_without_enough_distractors_has_no_mcq() -> None:
    entry = WordBankEntry.model_validate({**VALID, "distractors": ["a"]})

    assert "mcq" not in entry.metadata()


# --- selection -------------------------------------------------------------


def test_selection_respects_size_and_is_deterministic() -> None:
    entries = load_wordbank()

    first = select_starter_entries(entries, size=20)
    second = select_starter_entries(entries, size=20)

    assert len(first) == 20
    assert [entry.id for entry in first] == [entry.id for entry in second]


def test_selection_without_filters_uses_the_whole_bank() -> None:
    entries = load_wordbank()

    assert len(select_starter_entries(entries, size=10_000)) == len(entries)


def test_selection_filters_to_the_chosen_categories() -> None:
    entries = load_wordbank()

    selected = select_starter_entries(entries, sets=["sci_fi"], size=50)

    assert selected
    assert all("sci_fi" in entry.sets for entry in selected)


def test_selection_prefers_more_matches_first() -> None:
    entries = load_wordbank()

    selected = select_starter_entries(
        entries, topics=["tech"], kinds=["phrasal_verbs"], size=5
    )

    top = selected[0]
    assert "tech" in top.topics and "phrasal_verbs" in top.kinds


def test_selection_of_zero_returns_nothing() -> None:
    assert select_starter_entries(load_wordbank(), size=0) == []


# --- seeding ---------------------------------------------------------------


def test_seed_wordbank_is_idempotent(db_session, settings) -> None:
    user = ensure_user(db_session, 123456789, settings)
    entries = select_starter_entries(load_wordbank(), size=25)

    created, skipped = seed_wordbank(db_session, user, entries)
    again_created, again_skipped = seed_wordbank(db_session, user, entries)

    assert (created, skipped) == (25, 0)
    assert (again_created, again_skipped) == (0, 25)
    assert len(list_items(db_session, user.id, limit=100)) == 25


def test_seeded_items_carry_metadata_and_tags(db_session, settings) -> None:
    user = ensure_user(db_session, 123456789, settings)
    seed_starter_list(db_session, user, size=5)

    items = list_items(db_session, user.id, limit=10)

    assert items
    for item in items:
        assert "wordbank" in item.tags
        assert item.metadata_json["source"] == "wordbank"
        assert item.priority == 0


def test_seeded_items_are_quiz_ready(db_session, settings) -> None:
    from fluentloop.quiz import build_quiz_spec

    user = ensure_user(db_session, 123456789, settings)
    seed_starter_list(db_session, user, size=10)
    item = list_items(db_session, user.id, limit=10)[0]

    # Pre-baked distractors mean no LLM call is needed at all.
    spec = build_quiz_spec(db_session, user, item, allow_llm=False)

    assert spec is not None
    assert len(spec.options) == 4
