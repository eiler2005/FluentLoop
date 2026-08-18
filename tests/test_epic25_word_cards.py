"""Card enrichment: translation, gloss and an example that contains the word."""

from __future__ import annotations

from fluentloop.learning import create_learning_item
from fluentloop.llm.schemas import WordCard
from fluentloop.users import ensure_user
from fluentloop.word_cards import enrich_item, needs_enrichment, stored_russian


def _bare(session, user, text: str = "cut corners"):
    return create_learning_item(session, user, type_="expression", text=text)


def test_a_bare_phrase_needs_enrichment(db_session, settings) -> None:
    user = ensure_user(db_session, 123456789, settings)

    assert needs_enrichment(_bare(db_session, user)) is True


def test_a_bank_entry_still_needs_a_translation(db_session, settings) -> None:
    """164 bank entries carry an English gloss and an example but no Russian."""

    user = ensure_user(db_session, 123456789, settings)
    item = create_learning_item(
        db_session,
        user,
        type_="expression",
        text="roll out",
        meaning="to release gradually",
        examples=["We roll out the change on Tuesday."],
    )

    assert needs_enrichment(item) is True


def test_enrichment_fills_every_missing_piece(db_session, settings) -> None:
    user = ensure_user(db_session, 123456789, settings)
    item = _bare(db_session, user)
    card = WordCard(
        meaning="to do something the cheapest way",
        russian="срезать углы",
        example="They cut corners on testing.",
        synonyms=["skimp"],
        collocations=["cut corners on"],
    )

    assert enrich_item(db_session, item, card=card) is True
    assert stored_russian(item) == "срезать углы"
    assert item.examples == ["They cut corners on testing."]
    assert item.metadata_json["synonyms"] == ["skimp"]
    assert item.metadata_json["collocations"] == ["cut corners on"]
    assert needs_enrichment(item) is False


def test_enrichment_never_overwrites_curated_content(db_session, settings) -> None:
    """A generated gloss is worth less than one a human or the bank wrote."""

    user = ensure_user(db_session, 123456789, settings)
    item = create_learning_item(
        db_session,
        user,
        type_="expression",
        text="roll out",
        meaning="to release gradually",
        examples=["We roll out the change on Tuesday."],
    )
    card = WordCard(
        meaning="SOMETHING ELSE",
        russian="выкатывать",
        example="A DIFFERENT EXAMPLE.",
    )

    enrich_item(db_session, item, card=card)

    assert item.examples == ["We roll out the change on Tuesday."]
    assert "to release gradually" in (item.meaning or "") + (item.explanation or "")
    # The missing piece is still added.
    assert stored_russian(item) == "выкатывать"


def test_a_russian_meaning_does_not_displace_the_english_one(
    db_session, settings
) -> None:
    user = ensure_user(db_session, 123456789, settings)
    item = create_learning_item(
        db_session,
        user,
        type_="expression",
        text="cut corners",
        meaning="to do it the cheap way",
    )

    enrich_item(db_session, item, card=WordCard(russian="срезать углы"))

    from fluentloop.vocab_loop import english_definition

    assert english_definition(item) == "to do it the cheap way"
    assert stored_russian(item) == "срезать углы"


def test_a_cyrillic_meaning_is_refused_as_the_english_gloss(
    db_session, settings
) -> None:
    """The model sometimes answers in the wrong language; do not store it."""

    user = ensure_user(db_session, 123456789, settings)
    item = _bare(db_session, user)

    enrich_item(db_session, item, card=WordCard(meaning="срезать углы"))

    from fluentloop.vocab_loop import english_definition

    assert english_definition(item) == ""


def test_enrichment_is_a_no_op_without_a_model(db_session, settings) -> None:
    """No API key means the card stays bare rather than the add failing."""

    user = ensure_user(db_session, 123456789, settings)
    item = _bare(db_session, user)

    assert enrich_item(db_session, item, settings=settings) is False
    assert item.text == "cut corners"


# --- the gateway survives a model that mirrors the schema ------------------


def test_schema_shaped_answers_are_unwrapped() -> None:
    """Qwen replied with the JSON Schema envelope, not an instance of it."""

    import json

    from fluentloop.llm.gateway import _unwrap

    payload = {
        "meaning": "to do it the cheap way",
        "russian": "срезать углы",
        "example": "They cut corners on testing.",
    }

    # Flat, as intended.
    assert _unwrap(json.dumps(payload), WordCard) == payload
    # Nested under the schema's own keys, as observed in production.
    wrapped = {"description": "a card", "properties": payload}
    assert _unwrap(json.dumps(wrapped), WordCard) == payload
    # A lone wrapper key.
    assert _unwrap(json.dumps({"result": payload}), WordCard) == payload


def test_unwrap_leaves_unrecognisable_payloads_alone() -> None:
    import json

    from fluentloop.llm.gateway import _unwrap

    assert _unwrap(json.dumps({"nothing": "useful"}), WordCard) == {
        "nothing": "useful"
    }
    assert _unwrap(json.dumps([1, 2]), WordCard) == [1, 2]


def test_prompts_never_hand_over_a_json_schema() -> None:
    """Sending the schema is what caused the mirroring in the first place."""

    from fluentloop.llm.prompts import user_prompt
    from fluentloop.llm.tasks import LLMTask

    text = user_prompt(LLMTask.WORD_CARD, {"phrase": "cut corners"}, WordCard)

    assert "properties" not in text
    assert "$defs" not in text
    for field in WordCard.model_fields:
        assert field in text


def test_a_metadata_stored_translation_counts_as_present(
    db_session, settings
) -> None:
    """Regression: the backfill re-processed these items on every run."""

    user = ensure_user(db_session, 123456789, settings)
    item = create_learning_item(
        db_session,
        user,
        type_="expression",
        text="suggest having",
        meaning="suggest + gerund",
        explanation="Use suggest + -ing to report an idea.",
        examples=["She suggested having one meeting a week."],
    )

    # Both text fields are taken, so the translation goes to metadata.
    enrich_item(db_session, item, card=WordCard(russian="предлагать сделать"))

    assert item.metadata_json["russian"] == "предлагать сделать"
    assert stored_russian(item) == "предлагать сделать"
    assert needs_enrichment(item) is False
