from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from threading import Barrier

import pytest
from sqlalchemy import func, select

from fluentloop.db.models import (
    LearningItem,
    MistakeEvent,
    PracticeAttempt,
    PracticeSession,
    ReviewState,
    User,
)
from fluentloop.db.session import make_engine, make_session_factory
from fluentloop.simple_learning import (
    ACTIVE,
    BONUS,
    PRODUCTION,
    answer_choice,
    get_active_bonus,
    get_active_stream,
    question_fingerprint,
    skip_bonus,
    start_bonus,
    start_stream,
    stop_stream,
    submit_bonus,
    summarize_stream,
)
from fluentloop.users import ensure_user

NOW = datetime(2026, 10, 3, 8, 0, tzinfo=UTC)


def _item(session, user, index, category="phrase", *, template=False):
    item = LearningItem(
        user_id=user.id,
        type="grammar_rule" if category == "grammar" else "expression",
        text=f"Correct answer {index}",
        status="active",
        is_template=template,
        metadata_json={
            "simple_question": {
                "prompt": f"Choose the natural sentence for situation {index}",
                "options": [f"Wrong answer {index}", f"Correct answer {index}"],
                "correct_index": 1,
                "explanation_ru": "Здесь нужна подходящая форма.",
                "category": category,
                "level": "B1" if index % 2 else "B2",
            }
        },
    )
    session.add(item)
    session.flush()
    session.add(ReviewState(learning_item_id=item.id, due_at=NOW))
    session.flush()
    return item


def _pool(session, user, count=12):
    return [
        _item(session, user, index, "grammar" if index % 2 else "phrase")
        for index in range(count)
    ]


def _right(session, user, step, *, now=NOW):
    return answer_choice(
        session, user, step.run.id, step.index, step.question["correct_index"], now=now
    )


def test_fingerprint_does_not_depend_on_option_order():
    first = {"prompt": "Choose", "options": ["bad", "good"], "correct_index": 1}
    reordered = {"prompt": "Choose", "options": ["good", "bad"], "correct_index": 0}
    assert question_fingerprint(first) == question_fingerprint(reordered)


def test_start_resumes_saved_question_across_restart_and_date(db_session, settings):
    user = ensure_user(db_session, 123456789, settings)
    _pool(db_session, user)
    first = start_stream(db_session, user, now=NOW)
    snapshot = first.question
    run_id = first.run.id
    db_session.commit()
    db_session.expire_all()
    resumed = start_stream(db_session, user, now=NOW + timedelta(days=2))
    assert resumed.run.id == run_id
    assert resumed.question == snapshot
    assert resumed.run.target_date_local == NOW.date()


def test_continuous_stream_alternates_and_exhausts_without_recycling(
    db_session, settings
):
    user = ensure_user(db_session, 123456789, settings)
    items = _pool(db_session, user)
    step = start_stream(db_session, user, now=NOW)
    seen, categories = set(), []
    for index in range(len(items)):
        assert step.index == index
        assert len(step.run.exercises) == 1
        assert step.question["fingerprint"] not in seen
        seen.add(step.question["fingerprint"])
        categories.append(step.question["category"])
        result = _right(db_session, user, step, now=NOW + timedelta(seconds=30 * index))
        assert result.accepted
        if result.next_step is not None:
            step = result.next_step
    assert categories == ["phrase", "grammar"] * 6
    assert result.reason == "exhausted"
    assert result.summary.answered == len(items)
    assert result.summary.correct == len(items)
    assert step.run.status == "completed"
    assert get_active_stream(db_session, user) is None


def test_small_bank_has_no_minimum_and_familiar_practice_is_explicit(
    db_session, settings
):
    user = ensure_user(db_session, 123456789, settings)
    item = _item(db_session, user, 1)
    step = start_stream(db_session, user, now=NOW)
    assert _right(db_session, user, step).reason == "exhausted"
    state = db_session.scalar(
        select(ReviewState).where(ReviewState.learning_item_id == item.id)
    )
    before = (
        state.review_count,
        state.success_count,
        state.due_at,
        state.last_interval_days,
    )
    assert start_stream(db_session, user, now=NOW + timedelta(seconds=60)).exhausted
    familiar = start_stream(
        db_session, user, repeat_familiar=True, now=NOW + timedelta(seconds=60)
    )
    result = _right(db_session, user, familiar, now=NOW + timedelta(seconds=60))
    assert result.accepted
    assert not result.attempt.feedback["srs_applied"]
    assert before == (
        state.review_count,
        state.success_count,
        state.due_at,
        state.last_interval_days,
    )
    assert item.status == "active"


def test_familiar_wrong_answer_resets_srs(db_session, settings):
    user = ensure_user(db_session, 123456789, settings)
    item = _item(db_session, user, 1)
    _right(db_session, user, start_stream(db_session, user, now=NOW))
    familiar = start_stream(
        db_session, user, repeat_familiar=True, now=NOW + timedelta(seconds=60)
    )
    result = answer_choice(
        db_session,
        user,
        familiar.run.id,
        familiar.index,
        1 - familiar.question["correct_index"],
        now=NOW + timedelta(seconds=60),
    )
    state = db_session.scalar(
        select(ReviewState).where(ReviewState.learning_item_id == item.id)
    )
    assert result.accepted and result.attempt.feedback["srs_applied"]
    assert state.last_result == "Again"


def test_single_question_bank_returns_normally_after_24_hours(db_session, settings):
    user = ensure_user(db_session, 123456789, settings)
    _item(db_session, user, 1)
    first = start_stream(db_session, user, now=NOW)
    _right(db_session, user, first)
    assert start_stream(db_session, user, now=NOW + timedelta(hours=23)).exhausted
    due = start_stream(db_session, user, now=NOW + timedelta(days=1))
    assert due.question["fingerprint"] == first.question["fingerprint"]


def test_explicit_familiar_mode_can_revisit_small_bank_error(db_session, settings):
    user = ensure_user(db_session, 123456789, settings)
    _item(db_session, user, 1)
    first = start_stream(db_session, user, now=NOW)
    answer_choice(db_session, user, first.run.id, first.index, None, now=NOW)
    assert start_stream(db_session, user, now=NOW + timedelta(seconds=10)).exhausted
    familiar = start_stream(db_session, user, repeat_familiar=True, now=NOW)
    assert familiar.question["fingerprint"] == first.question["fingerprint"]


def test_early_familiar_success_does_not_bypass_error_spacing(db_session, settings):
    user = ensure_user(db_session, 123456789, settings)
    _item(db_session, user, 1)
    first = start_stream(db_session, user, now=NOW)
    answer_choice(db_session, user, first.run.id, first.index, None, now=NOW)
    familiar = start_stream(
        db_session, user, repeat_familiar=True, now=NOW + timedelta(minutes=1)
    )
    result = _right(db_session, user, familiar, now=NOW + timedelta(minutes=1))
    assert not result.attempt.feedback["srs_applied"]
    stop_stream(db_session, user, now=NOW + timedelta(minutes=1))
    assert start_stream(db_session, user, now=NOW + timedelta(minutes=2)).exhausted


def test_success_floor_expires_and_familiar_success_does_not_postpone_it(
    db_session, settings
):
    user = ensure_user(db_session, 123456789, settings)
    _pool(db_session, user, 6)
    step = start_stream(db_session, user, now=NOW)
    initial = step.question["fingerprint"]
    for index in range(6):
        result = _right(db_session, user, step, now=NOW + timedelta(seconds=index * 30))
        if result.next_step:
            step = result.next_step
    early = start_stream(
        db_session, user, repeat_familiar=True, now=NOW + timedelta(hours=23)
    )
    assert early.question["fingerprint"] == initial
    _right(db_session, user, early, now=NOW + timedelta(hours=23))
    stop_stream(db_session, user, now=NOW + timedelta(hours=23))
    # Explicit early practice cannot restart the normal 24-hour floor.
    ready = start_stream(db_session, user, now=NOW + timedelta(days=1, minutes=3))
    assert not ready.exhausted


def test_unknown_returns_after_five_other_answers_and_due(db_session, settings):
    user = ensure_user(db_session, 123456789, settings)
    _pool(db_session, user, 8)
    first = start_stream(db_session, user, now=NOW)
    fingerprint = first.question["fingerprint"]
    result = answer_choice(db_session, user, first.run.id, first.index, None, now=NOW)
    assert result.attempt.feedback["unknown"]
    assert result.attempt.user_answer == ""
    step = result.next_step
    for index in range(5):
        assert step.question["fingerprint"] != fingerprint
        result = _right(
            db_session, user, step, now=NOW + timedelta(seconds=(index + 1) * 10)
        )
        step = result.next_step
    if step.question["category"] != first.question["category"]:
        step = _right(db_session, user, step, now=NOW + timedelta(seconds=60)).next_step
    assert step.question["fingerprint"] == fingerprint
    assert summarize_stream(db_session, user, first.run.id).unknown == 1


def test_stop_completes_and_new_start_reselects_instead_of_resuming(
    db_session, settings
):
    user = ensure_user(db_session, 123456789, settings)
    _pool(db_session, user)
    first = start_stream(db_session, user, now=NOW)
    first_fingerprint = first.question["fingerprint"]
    summary = stop_stream(db_session, user, run_id=first.run.id, now=NOW)
    assert summary.answered == 0
    assert first.run.status == "completed"
    assert first.run.exercises[0]["fingerprint"] == first_fingerprint
    next_run = start_stream(db_session, user, now=NOW + timedelta(seconds=1))
    assert next_run.run.id != first.run.id
    assert next_run.question["fingerprint"] != first_fingerprint
    assert not answer_choice(db_session, user, first.run.id, 0, 0).accepted


def test_duplicate_stale_invalid_and_foreign_callbacks_do_not_change_progress(
    db_session, settings
):
    user = ensure_user(db_session, 123456789, settings)
    other = User(telegram_user_id=123456788)
    db_session.add(other)
    db_session.flush()
    _pool(db_session, user)
    step = start_stream(db_session, user, now=NOW)
    assert not answer_choice(db_session, other, step.run.id, 0, 0).accepted
    assert not answer_choice(db_session, user, step.run.id, 99, 0).accepted
    assert not answer_choice(db_session, user, step.run.id, 0, 99).accepted
    result = _right(db_session, user, step)
    assert result.accepted
    assert not _right(db_session, user, step).accepted
    assert summarize_stream(db_session, user, step.run.id).answered == 1
    assert db_session.scalar(select(func.sum(ReviewState.review_count))) == 1


def test_templates_foreign_and_archived_items_never_selected(db_session, settings):
    user = ensure_user(db_session, 123456789, settings)
    other = User(telegram_user_id=123456788)
    db_session.add(other)
    db_session.flush()
    _item(db_session, user, 1, template=True)
    _item(db_session, other, 2)
    archived = _item(db_session, user, 3)
    archived.status = "archived"
    assert start_stream(db_session, user, now=NOW).exhausted


def test_existing_phrase_uses_cached_quiz_and_preserves_chunk_for_bonus(
    db_session, settings
):
    user = ensure_user(db_session, 123456789, settings)
    phrase = LearningItem(
        user_id=user.id,
        type="expression",
        text="push back on",
        meaning="Challenge a proposal or request.",
        explanation="Возражать против",
        examples=["We need to push back on this proposal."],
        status="active",
        metadata_json={
            "mcq": {
                "distractors": ["roll out", "cut corners", "follow up on"],
            }
        },
    )
    db_session.add(phrase)
    db_session.flush()
    step = start_stream(db_session, user, now=NOW)
    assert step.question["category"] == "phrase"
    assert step.question["explanation_ru"] == "Возражать против"
    assert step.question["target_learning_item_ids"] == [phrase.id]
    _right(db_session, user, step)
    bonus = start_bonus(db_session, user, step.run.id, now=NOW)
    assert bonus.question["expected_answer"] == "push back on"
    assert "push back on" in bonus.question["prompt"]


@pytest.mark.parametrize("missing", ["english", "russian", "example"])
def test_incomplete_legacy_phrase_is_ineligible_without_network(
    db_session, settings, monkeypatch, missing
):
    def forbidden_quiz(*args, **kwargs):
        raise AssertionError("Incomplete cards must be rejected before quiz building")

    monkeypatch.setattr("fluentloop.simple_learning.build_quiz_spec", forbidden_quiz)
    user = ensure_user(db_session, 123456789, settings)
    item = LearningItem(
        user_id=user.id,
        type="expression",
        text="push back on",
        meaning="" if missing == "english" else "Challenge a proposal or request.",
        explanation="" if missing == "russian" else "Возражать против",
        examples=[
            "Write a sentence using push back on."
            if missing == "example"
            else "We need to push back on this proposal."
        ],
        status="active",
        metadata_json={
            "mcq": {"distractors": ["roll out", "cut corners", "follow up on"]}
        },
    )
    db_session.add(item)
    db_session.flush()
    assert start_stream(db_session, user, now=NOW).exhausted


def test_legacy_phrase_uses_metadata_russian_without_network(
    db_session, settings, monkeypatch
):
    def forbidden_llm(*args, **kwargs):
        raise AssertionError("Simple recognition must not call the LLM")

    monkeypatch.setattr("fluentloop.quiz.llm_distractors", forbidden_llm)
    user = ensure_user(db_session, 123456789, settings)
    item = LearningItem(
        user_id=user.id,
        type="expression",
        text="push back on",
        meaning="Challenge a proposal or request.",
        explanation="Express disagreement with a proposed approach.",
        examples=["We need to push back on this proposal."],
        status="active",
        metadata_json={
            "russian": "Возражать против",
            "mcq": {"distractors": ["roll out", "cut corners", "follow up on"]},
        },
    )
    db_session.add(item)
    db_session.flush()
    step = start_stream(db_session, user, now=NOW)
    assert step.question["explanation_ru"] == "Возражать против"
    assert "Challenge a proposal or request." in step.question["prompt"]


def test_due_deadline_prevents_successful_early_repetition(db_session, settings):
    user = ensure_user(db_session, 123456789, settings)
    items = _pool(db_session, user, 6)
    step = start_stream(db_session, user, now=NOW)
    for index in range(6):
        result = _right(db_session, user, step, now=NOW + timedelta(seconds=index * 10))
        if result.next_step:
            step = result.next_step
    for item in items:
        state = db_session.scalar(
            select(ReviewState).where(ReviewState.learning_item_id == item.id)
        )
        state.due_at = NOW + timedelta(days=10)
    assert start_stream(db_session, user, now=NOW + timedelta(days=2)).exhausted


def test_global_due_does_not_block_unseen_question_variants(db_session, settings):
    user = ensure_user(db_session, 123456789, settings)
    item = _item(db_session, user, 1, "grammar")
    state = db_session.scalar(
        select(ReviewState).where(ReviewState.learning_item_id == item.id)
    )
    state.due_at = NOW + timedelta(days=10)
    step = start_stream(db_session, user, now=NOW)
    assert step.question["category"] == "grammar"
    result = _right(db_session, user, step)
    assert result.accepted and not result.attempt.feedback["srs_applied"]


def test_bonus_is_optional_owned_linked_and_idempotent(db_session, settings):
    user = ensure_user(db_session, 123456789, settings)
    other = User(telegram_user_id=123456788)
    db_session.add(other)
    db_session.flush()
    item = _item(db_session, user, 1)
    step = start_stream(db_session, user, now=NOW)
    _right(db_session, user, step)
    assert start_bonus(db_session, other, step.run.id).run is None
    bonus = start_bonus(db_session, user, step.run.id, now=NOW)
    assert bonus.run.status == BONUS
    assert bonus.question["metadata"]["parent_simple_session_id"] == step.run.id
    assert bonus.question["target_learning_item_ids"] == [item.id]
    assert start_bonus(db_session, user, step.run.id).run.id == bonus.run.id
    assert get_active_bonus(db_session, user).id == bonus.run.id
    assert not submit_bonus(
        db_session, other, bonus.run.id, "My answer", {"status": "correct"}
    ).accepted
    result = submit_bonus(
        db_session,
        user,
        bonus.run.id,
        "My workplace sentence uses the phrase.",
        {"status": "correct"},
        now=NOW,
    )
    assert result.accepted
    assert result.attempt.exercise_type == PRODUCTION
    assert result.attempt.feedback["answer_modality"] == "production"
    assert not submit_bonus(
        db_session, user, bonus.run.id, "Retry", {"status": "correct"}
    ).accepted
    assert start_bonus(db_session, user, step.run.id).question is None


def test_bonus_skip_never_records_failure(db_session, settings):
    user = ensure_user(db_session, 123456789, settings)
    item = _item(db_session, user, 1)
    step = start_stream(db_session, user, now=NOW)
    stop_stream(db_session, user, now=NOW)
    bonus = start_bonus(db_session, user, step.run.id, now=NOW)
    skip_bonus(db_session, user, bonus.run.id, now=NOW)
    state = db_session.scalar(
        select(ReviewState).where(ReviewState.learning_item_id == item.id)
    )
    assert state.review_count == 0
    assert db_session.scalar(select(func.count()).select_from(PracticeAttempt)) == 0


def test_bonus_duplicate_records_one_mistake_and_srs_change(db_session, settings):
    user = ensure_user(db_session, 123456789, settings)
    item = _item(db_session, user, 1)
    step = start_stream(db_session, user, now=NOW)
    stop_stream(db_session, user, now=NOW)
    bonus = start_bonus(db_session, user, step.run.id, now=NOW)
    feedback = {
        "status": "incorrect",
        "corrected_answer": "We depend on the service.",
        "explanation": "Use depend on.",
        "detected_mistake_type": "preposition",
        "should_create_mistake_event": True,
    }
    answer = "We depend from the service."
    assert submit_bonus(db_session, user, bonus.run.id, answer, feedback).accepted
    assert not submit_bonus(db_session, user, bonus.run.id, answer, feedback).accepted
    assert db_session.scalar(select(func.count()).select_from(PracticeAttempt)) == 1
    assert db_session.scalar(select(func.count()).select_from(MistakeEvent)) == 1
    state = db_session.scalar(
        select(ReviewState).where(ReviewState.learning_item_id == item.id)
    )
    assert state.review_count == 1


def test_grammar_bonus_applies_pattern_in_new_situation(db_session, settings):
    user = ensure_user(db_session, 123456789, settings)
    _item(db_session, user, 1, "grammar")
    step = start_stream(db_session, user, now=NOW)
    stop_stream(db_session, user, now=NOW)
    bonus = start_bonus(db_session, user, step.run.id, now=NOW)
    assert "same grammar pattern" in bonus.question["prompt"]
    assert "different situation" in bonus.question["prompt"]


def test_legacy_practice_is_not_superseded(db_session, settings):
    user = ensure_user(db_session, 123456789, settings)
    _pool(db_session, user)
    legacy = PracticeSession(
        user_id=user.id,
        target_date_local=NOW.date(),
        status="in_progress",
        exercises=[{"prompt": "Existing lesson"}],
    )
    db_session.add(legacy)
    db_session.flush()
    step = start_stream(db_session, user, now=NOW)
    assert step.run.status == ACTIVE
    stop_stream(db_session, user, now=NOW)
    assert legacy.status == "in_progress"


def test_parallel_answers_claim_once_on_separate_sqlite_connections(
    tmp_path, settings, monkeypatch
):
    engine = make_engine(f"sqlite:///{tmp_path / 'simple.sqlite'}")
    factory = make_session_factory(engine)
    with factory() as session:
        user = ensure_user(session, 123456789, settings)
        _pool(session, user)
        step = start_stream(session, user, now=NOW)
        user_id, run_id = user.id, step.run.id
        correct = step.question["correct_index"]
        session.commit()
    from fluentloop import simple_learning

    original_claim = simple_learning._claim
    barrier = Barrier(2)

    def concurrent_claim(*args, **kwargs):
        barrier.wait(timeout=5)
        return original_claim(*args, **kwargs)

    monkeypatch.setattr(simple_learning, "_claim", concurrent_claim)

    def answer():
        with factory() as session:
            user = session.get(User, user_id)
            result = answer_choice(session, user, run_id, 0, correct, now=NOW)
            session.commit()
            return result.accepted

    with ThreadPoolExecutor(max_workers=2) as workers:
        assert sorted(workers.map(lambda _: answer(), range(2))) == [False, True]
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(PracticeAttempt)) == 1
        assert session.scalar(select(func.sum(ReviewState.review_count))) == 1


def test_parallel_starts_create_one_stream(tmp_path, settings):
    engine = make_engine(f"sqlite:///{tmp_path / 'starts.sqlite'}")
    factory = make_session_factory(engine)
    with factory() as session:
        user = ensure_user(session, 123456789, settings)
        _pool(session, user)
        user_id = user.id
        session.commit()
    barrier = Barrier(2)

    def start():
        with factory() as session:
            user = session.get(User, user_id)
            barrier.wait(timeout=5)
            step = start_stream(session, user, now=NOW)
            session.commit()
            return step.run.id

    with ThreadPoolExecutor(max_workers=2) as workers:
        ids = list(workers.map(lambda _: start(), range(2)))
    assert ids[0] == ids[1]


def test_selection_failure_rolls_back_answer_srs_and_claim(
    db_session, settings, monkeypatch
):
    user = ensure_user(db_session, 123456789, settings)
    _pool(db_session, user)
    step = start_stream(db_session, user, now=NOW)
    original_question = step.question
    from fluentloop import simple_learning

    def broken_selector(*args, **kwargs):
        raise RuntimeError("selection failed")

    monkeypatch.setattr(simple_learning, "_choose_question", broken_selector)
    with pytest.raises(RuntimeError, match="selection failed"):
        _right(db_session, user, step)
    assert _snapshot_for_test(step.run) == original_question
    assert db_session.scalar(select(func.count()).select_from(PracticeAttempt)) == 0
    assert db_session.scalar(select(func.sum(ReviewState.review_count))) == 0


def _snapshot_for_test(run):
    return run.exercises[0]
