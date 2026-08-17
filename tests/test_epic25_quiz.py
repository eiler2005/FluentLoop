from __future__ import annotations

from datetime import UTC, datetime

from fluentloop.ai.provider import StubProvider
from fluentloop.bot.handlers import (
    DRILL_STATE,
    handle_drill_answer,
    handle_drill_skip,
    handle_drill_start,
    handle_quiz_answer,
    render_daily_slot,
)
from fluentloop.bot.state import StateStore
from fluentloop.db.models import ReviewState, VocabDelivery
from fluentloop.learning import create_learning_item
from fluentloop.quiz import (
    QUIZ_OPTION_COUNT,
    build_quiz_spec,
    cached_distractors,
    evening_quiz,
    question_for,
    select_distractors,
)
from fluentloop.users import ensure_user

NOW = datetime(2026, 8, 17, 16, 0, tzinfo=UTC)


def _item(session, user, text: str, meaning: str = "a meaning", **kwargs):
    return create_learning_item(
        session, user, type_="word", text=text, meaning=meaning, **kwargs
    )


def _pool(session, user, count: int = 5) -> None:
    for index in range(count):
        _item(session, user, f"filler-{index}")


def _delivery(session, user, slot: str) -> VocabDelivery:
    delivery = VocabDelivery(
        user_id=user.id, local_date=NOW.date(), slot=slot, seq=0, status="claimed"
    )
    session.add(delivery)
    session.flush()
    return delivery


# --- distractors -----------------------------------------------------------


def test_question_matches_the_expected_wording(db_session, settings) -> None:
    user = ensure_user(db_session, 123456789, settings)
    item = _item(db_session, user, "open-minded", "willing to consider new ideas")

    assert question_for(item) == (
        'Which word or phrase means: "willing to consider new ideas"?'
    )


def test_select_distractors_uses_same_type_peers(db_session, settings) -> None:
    user = ensure_user(db_session, 123456789, settings)
    target = _item(db_session, user, "pipeline")
    _pool(db_session, user)
    create_learning_item(
        db_session, user, type_="grammar_rule", text="present perfect"
    )

    distractors = select_distractors(db_session, user, target)

    assert len(distractors) == 3
    assert "pipeline" not in distractors
    assert "present perfect" not in distractors


def test_select_distractors_is_stable(db_session, settings) -> None:
    user = ensure_user(db_session, 123456789, settings)
    target = _item(db_session, user, "pipeline")
    _pool(db_session, user, count=8)

    first = select_distractors(db_session, user, target)
    second = select_distractors(db_session, user, target)

    assert first == second


def test_select_distractors_prefers_shared_tags(db_session, settings) -> None:
    user = ensure_user(db_session, 123456789, settings)
    target = _item(db_session, user, "pipeline", tags=["tech"])
    _item(db_session, user, "tagged-peer", tags=["tech"])
    _pool(db_session, user, count=6)

    assert "tagged-peer" in select_distractors(db_session, user, target)


def test_select_distractors_skips_substring_overlap(db_session, settings) -> None:
    user = ensure_user(db_session, 123456789, settings)
    target = _item(db_session, user, "roll")
    _item(db_session, user, "roll out")
    _pool(db_session, user)

    assert "roll out" not in select_distractors(db_session, user, target)


def test_build_quiz_spec_produces_four_options(db_session, settings) -> None:
    user = ensure_user(db_session, 123456789, settings)
    target = _item(db_session, user, "pipeline", "a chain of build steps")
    _pool(db_session, user)

    spec = build_quiz_spec(db_session, user, target, settings=settings)

    assert spec is not None
    assert len(spec.options) == QUIZ_OPTION_COUNT
    assert spec.options[spec.correct_index] == "pipeline"
    assert len(set(spec.options)) == QUIZ_OPTION_COUNT


def test_build_quiz_spec_caches_distractors(db_session, settings) -> None:
    user = ensure_user(db_session, 123456789, settings)
    target = _item(db_session, user, "pipeline", "a chain of build steps")
    _pool(db_session, user)

    build_quiz_spec(db_session, user, target, settings=settings)

    assert len(cached_distractors(target)) == 3


def test_build_quiz_spec_prefers_prebaked_distractors(db_session, settings) -> None:
    user = ensure_user(db_session, 123456789, settings)
    target = _item(
        db_session,
        user,
        "pipeline",
        "a chain of build steps",
        metadata={"mcq": {"distractors": ["alpha", "beta", "gamma"]}},
    )

    spec = build_quiz_spec(db_session, user, target, settings=settings)

    assert set(spec.options) == {"pipeline", "alpha", "beta", "gamma"}


def test_build_quiz_spec_needs_a_definition(db_session, settings) -> None:
    user = ensure_user(db_session, 123456789, settings)
    target = create_learning_item(db_session, user, type_="word", text="bare")
    _pool(db_session, user)

    assert build_quiz_spec(db_session, user, target, settings=settings) is None


def test_build_quiz_spec_needs_enough_peers(db_session, settings) -> None:
    user = ensure_user(db_session, 123456789, settings)
    target = _item(db_session, user, "lonely", "no peers around")

    assert build_quiz_spec(db_session, user, target, settings=settings) is None


def test_evening_quiz_skips_items_it_cannot_ask_about(db_session, settings) -> None:
    user = ensure_user(db_session, 123456789, settings)
    create_learning_item(db_session, user, type_="word", text="no-meaning")
    _item(db_session, user, "askable", "has a definition")
    _pool(db_session, user)

    spec = evening_quiz(db_session, user, now=NOW, settings=settings)

    assert spec is not None
    assert spec.options[spec.correct_index] != "no-meaning"


# --- answering the quiz ----------------------------------------------------


def test_quiz_answer_correct_records_success(db_session, settings) -> None:
    user = ensure_user(db_session, 123456789, settings)
    _item(db_session, user, "pipeline", "a chain of build steps")
    _pool(db_session, user)
    delivery = _delivery(db_session, user, "evening")
    reply = render_daily_slot(
        db_session, user, "evening", delivery, now=NOW, settings=settings
    )
    correct = delivery.payload_json["correct_index"]

    answer = handle_quiz_answer(db_session, user, delivery.id, correct)

    assert "✅ Right" in answer.text
    assert delivery.status == "answered"
    item_id = delivery.learning_item_ids[0]
    state = db_session.query(ReviewState).filter_by(learning_item_id=item_id).one()
    assert state.success_count == 1
    assert "Evening quiz" in reply.text


def test_quiz_answer_wrong_shows_the_right_one(db_session, settings) -> None:
    user = ensure_user(db_session, 123456789, settings)
    _item(db_session, user, "pipeline", "a chain of build steps")
    _pool(db_session, user)
    delivery = _delivery(db_session, user, "evening")
    render_daily_slot(
        db_session, user, "evening", delivery, now=NOW, settings=settings
    )
    correct = delivery.payload_json["correct_index"]
    wrong = (correct + 1) % QUIZ_OPTION_COUNT

    answer = handle_quiz_answer(db_session, user, delivery.id, wrong)

    assert "❌ It was" in answer.text
    item_id = delivery.learning_item_ids[0]
    state = db_session.query(ReviewState).filter_by(learning_item_id=item_id).one()
    assert state.fail_count == 1


def test_quiz_answer_is_recorded_once(db_session, settings) -> None:
    user = ensure_user(db_session, 123456789, settings)
    _item(db_session, user, "pipeline", "a chain of build steps")
    _pool(db_session, user)
    delivery = _delivery(db_session, user, "evening")
    render_daily_slot(
        db_session, user, "evening", delivery, now=NOW, settings=settings
    )

    handle_quiz_answer(db_session, user, delivery.id, 0)
    second = handle_quiz_answer(db_session, user, delivery.id, 0)

    assert "already answered" in second.text


def test_quiz_answer_on_unknown_delivery_is_safe(db_session, settings) -> None:
    user = ensure_user(db_session, 123456789, settings)

    assert "no longer available" in handle_quiz_answer(db_session, user, 999, 0).text


def test_quiz_answer_rejects_out_of_range_choice(db_session, settings) -> None:
    user = ensure_user(db_session, 123456789, settings)
    _item(db_session, user, "pipeline", "a chain of build steps")
    _pool(db_session, user)
    delivery = _delivery(db_session, user, "evening")
    render_daily_slot(
        db_session, user, "evening", delivery, now=NOW, settings=settings
    )

    assert "no longer available" in handle_quiz_answer(
        db_session, user, delivery.id, 42
    ).text


# --- the midday drill ------------------------------------------------------


def test_midday_slot_arms_the_answer_button(db_session, settings) -> None:
    user = ensure_user(db_session, 123456789, settings)
    _item(db_session, user, "pipeline", "a chain of build steps")
    delivery = _delivery(db_session, user, "midday")

    reply = render_daily_slot(db_session, user, "midday", delivery, now=NOW)

    data = [button.data for row in reply.buttons for button in row]
    assert f"vocab:drill:{delivery.id}" in data
    assert f"vocab:skip:{delivery.id}" in data
    assert delivery.payload_json["exercise"]["prompt"]


def test_drill_start_sets_capture_state(db_session, settings) -> None:
    user = ensure_user(db_session, 123456789, settings)
    _item(db_session, user, "pipeline", "a chain of build steps")
    delivery = _delivery(db_session, user, "midday")
    render_daily_slot(db_session, user, "midday", delivery, now=NOW)

    handle_drill_start(db_session, user, delivery.id, chat_id=555)

    state = StateStore(db_session).get(555, user.telegram_user_id)
    assert state is not None
    assert state.name == DRILL_STATE
    assert state.payload["delivery_id"] == delivery.id


def test_drill_answer_scores_and_clears_state(db_session, settings) -> None:
    user = ensure_user(db_session, 123456789, settings)
    _item(db_session, user, "pipeline", "a chain of build steps")
    delivery = _delivery(db_session, user, "midday")
    render_daily_slot(db_session, user, "midday", delivery, now=NOW)
    handle_drill_start(db_session, user, delivery.id, chat_id=555)

    reply = handle_drill_answer(
        db_session, user, StubProvider(), delivery.id, "pipeline", chat_id=555
    )

    assert "Verdict" in reply.text
    assert delivery.status == "answered"
    assert delivery.payload_json["user_answer"] == "pipeline"
    assert StateStore(db_session).get(555, user.telegram_user_id) is None


def test_drill_skip_reveals_the_answer(db_session, settings) -> None:
    user = ensure_user(db_session, 123456789, settings)
    _item(db_session, user, "pipeline", "a chain of build steps")
    delivery = _delivery(db_session, user, "midday")
    render_daily_slot(db_session, user, "midday", delivery, now=NOW)

    reply = handle_drill_skip(db_session, user, delivery.id, chat_id=555)

    assert "Skipped" in reply.text
    assert delivery.status == "skipped"


def test_morning_slot_records_the_items_it_showed(db_session, settings) -> None:
    user = ensure_user(db_session, 123456789, settings)
    _pool(db_session, user, count=3)
    delivery = _delivery(db_session, user, "morning")

    reply = render_daily_slot(db_session, user, "morning", delivery, now=NOW)

    assert "Morning phrases" in reply.text
    assert len(delivery.learning_item_ids) == 3


def test_slots_return_none_without_content(db_session, settings) -> None:
    user = ensure_user(db_session, 123456789, settings)
    delivery = _delivery(db_session, user, "morning")

    assert render_daily_slot(db_session, user, "morning", delivery, now=NOW) is None
    assert render_daily_slot(db_session, user, "midday", delivery, now=NOW) is None
    assert render_daily_slot(
        db_session, user, "evening", delivery, now=NOW, settings=settings
    ) is None


# --- the other options are explained after answering -----------------------


def test_quiz_answer_explains_the_other_options(db_session, settings) -> None:
    user = ensure_user(db_session, 123456789, settings)
    _item(db_session, user, "pipeline", "a chain of build steps")
    for text, meaning in (
        ("rollout", "a gradual release"),
        ("backlog", "work that has piled up"),
        ("bottleneck", "the step that limits everything"),
    ):
        _item(db_session, user, text, meaning)
    delivery = _delivery(db_session, user, "evening")
    render_daily_slot(
        db_session, user, "evening", delivery, now=NOW, settings=settings
    )
    correct = delivery.payload_json["correct_index"]
    options = delivery.payload_json["options"]

    reply = handle_quiz_answer(db_session, user, delivery.id, correct)

    assert "The others were:" in reply.text
    for index, option in enumerate(options):
        if index == correct:
            continue
        assert option in reply.text
    # And the meanings, so a rejected option still teaches something.
    assert "a gradual release" in reply.text or "work that has piled up" in reply.text


def test_glossary_lists_unknown_options_by_name(db_session, settings) -> None:
    from fluentloop.quiz import option_glossary

    user = ensure_user(db_session, 123456789, settings)

    notes = option_glossary(db_session, user, ["alpha", "beta"], correct_index=0)

    assert [(n.text, n.english, n.russian) for n in notes] == [("beta", "", "")]


def test_glossary_skips_the_correct_answer(db_session, settings) -> None:
    from fluentloop.quiz import option_glossary

    user = ensure_user(db_session, 123456789, settings)
    _item(db_session, user, "pipeline", "a chain of build steps")

    notes = option_glossary(db_session, user, ["pipeline", "other"], correct_index=0)

    assert [n.text for n in notes] == ["other"]


# --- English prompts, Russian only after the answer ------------------------


def test_question_uses_the_english_gloss(db_session, settings) -> None:
    user = ensure_user(db_session, 123456789, settings)
    item = create_learning_item(
        db_session,
        user,
        type_="expression",
        text="I see one risk",
        meaning="я вижу один риск",
        explanation="a hedge that flags a single concern",
    )

    assert question_for(item) == (
        'Which word or phrase means: "a hedge that flags a single concern"?'
    )


def test_question_falls_back_to_russian_when_that_is_all_there_is(
    db_session, settings
) -> None:
    user = ensure_user(db_session, 123456789, settings)
    item = create_learning_item(
        db_session, user, type_="word", text="risk", meaning="риск"
    )

    assert "риск" in question_for(item)


def test_evening_quiz_prefers_an_item_it_can_ask_in_english(
    db_session, settings
) -> None:
    user = ensure_user(db_session, 123456789, settings)
    create_learning_item(
        db_session, user, type_="word", text="ru-only", meaning="только по-русски"
    )
    create_learning_item(
        db_session, user, type_="word", text="en-item", meaning="an English gloss"
    )
    _pool(db_session, user)

    spec = evening_quiz(db_session, user, now=NOW, settings=settings, allow_llm=False)

    assert spec is not None
    assert "только по-русски" not in spec.question


def test_answer_reveals_the_russian_translation(db_session, settings) -> None:
    user = ensure_user(db_session, 123456789, settings)
    create_learning_item(
        db_session,
        user,
        type_="word",
        text="pipeline",
        meaning="конвейер сборки",
        explanation="a chain of build steps",
    )
    _pool(db_session, user)
    delivery = _delivery(db_session, user, "evening")
    reply = render_daily_slot(
        db_session, user, "evening", delivery, now=NOW, settings=settings
    )
    correct = delivery.payload_json["correct_index"]

    # The question itself stays English.
    assert "конвейер" not in reply.text

    answer = handle_quiz_answer(db_session, user, delivery.id, correct)

    # The translation appears only once the answer is revealed.
    assert "конвейер сборки" in answer.text
    assert "a chain of build steps" in answer.text


def test_glossary_shows_both_languages(db_session, settings) -> None:
    from fluentloop.quiz import option_glossary

    user = ensure_user(db_session, 123456789, settings)
    create_learning_item(
        db_session,
        user,
        type_="word",
        text="rollout",
        meaning="постепенный выпуск",
        explanation="a gradual release",
    )

    note = option_glossary(db_session, user, ["target", "rollout"], correct_index=0)[0]

    assert note.english == "a gradual release"
    assert note.russian == "постепенный выпуск"
