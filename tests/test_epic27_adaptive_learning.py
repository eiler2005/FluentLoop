from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from fluentloop.adaptive_learning import (
    TOPIC_TITLES,
    curriculum_progress,
    generation_need,
    independent_production,
)
from fluentloop.db.models import LearningItem, PracticeAttempt, PracticeSession, User
from fluentloop.simple_learning import (
    answer_choice,
    start_bonus,
    start_stream,
    stop_stream,
    submit_bonus,
)
from fluentloop.users import ensure_user

NOW = datetime(2026, 10, 3, 8, tzinfo=UTC)


def _question(topic="aspect", stage="b2", role="practice", variant="one"):
    return {
        "prompt": f"Choose the natural sentence for {topic}/{stage}/{role}/{variant}",
        "options": [
            f"Wrong sentence {variant}",
            f"I have completed the task {variant}.",
        ],
        "correct_index": 1,
        "category": "grammar",
        "explanation_ru": "Здесь важен результат к настоящему моменту.",
        "fingerprint": f"{topic}/{stage}/{role}/{variant}",
        "adaptive": {
            "version": 1,
            "topic_id": topic,
            "stage": stage,
            "role": role,
            "variant_id": f"{stage}/{role}/{variant}",
        },
    }


def _item(session, user, question):
    item = LearningItem(
        user_id=user.id,
        type="grammar_rule",
        text=question["fingerprint"],
        status="active",
        metadata_json={"simple_question": question},
    )
    session.add(item)
    session.flush()
    return item


def _attempt(
    session,
    user,
    item,
    *,
    now=NOW,
    status="correct",
    overrides=None,
    question=None,
    production=False,
):
    question = question or item.metadata_json["simple_question"]
    run = PracticeSession(
        user_id=user.id,
        target_date_local=now.date(),
        started_at=now,
        status="completed",
        exercises=[],
    )
    session.add(run)
    session.flush()
    feedback = {
        "adaptive": question["adaptive"],
        "fingerprint": question["fingerprint"],
        "answer_modality": "production" if production else "recognition",
        "selection_mode": "normal",
        "first_exposure": True,
        "transfer_eligible": question["adaptive"]["role"] == "transfer",
        "independent_production": production,
        "genuine_evaluation": production,
        **(overrides or {}),
    }
    session.add(
        PracticeAttempt(
            practice_session_id=run.id,
            exercise_index=0,
            exercise_type="simple_production" if production else "simple_choice",
            target_learning_item_ids=[item.id],
            prompt=question["prompt"],
            user_answer="My team has resolved the outage.",
            status=status,
            feedback=feedback,
            created_at=now,
        )
    )
    session.flush()


def _practice(session, user, topic="aspect", stage="b2", *, start=NOW):
    items = []
    for index in range(5):
        item = _item(session, user, _question(topic, stage, variant=str(index)))
        stamp = start + timedelta(days=1 if index == 4 else 0, seconds=index)
        _attempt(session, user, item, now=stamp)
        items.append(item)
    return items


def _master_stage(
    session, user, topic="aspect", stage="b2", *, start=NOW, production=True
):
    items = _practice(session, user, topic, stage, start=start)
    for index in range(1 if stage == "b2" else 2):
        item = _item(session, user, _question(topic, stage, "transfer", str(index)))
        _attempt(session, user, item, now=start + timedelta(days=2, minutes=1 + index))
    if stage != "b2" and production:
        _attempt(
            session,
            user,
            items[-1],
            production=True,
            now=start + timedelta(days=2, minutes=4),
        )
    return items


def _topic(session, user, *, now=NOW + timedelta(days=20)):
    return curriculum_progress(session, user, now=now).topics[0]


def test_repeats_same_day_legacy_and_familiar_do_not_unlock(db_session, settings):
    user = ensure_user(db_session, 123456789, settings)
    item = _item(db_session, user, _question())
    for index in range(8):
        _attempt(db_session, user, item, now=NOW + timedelta(days=index))
    assert _topic(db_session, user).practice_successes == 1
    assert not _topic(db_session, user).practice_ready
    for index in range(5):
        other = _item(db_session, user, _question(variant=f"other{index}"))
        _attempt(db_session, user, other, overrides={"selection_mode": "familiar"})
        _attempt(db_session, user, other, overrides={"adaptive": None})
    assert _topic(db_session, user).practice_successes == 1
    for index in range(4):
        other = _item(db_session, user, _question(variant=f"same-day{index}"))
        _attempt(db_session, user, other, now=NOW)
    # The valid spaced repeat cannot substitute for five distinct questions
    # successfully practiced before that repeat.
    assert _topic(db_session, user).stage == "b2"


def test_same_day_bank_can_gain_spacing_through_due_distinct_repeat(
    db_session, settings
):
    user = ensure_user(db_session, 123456789, settings)
    items = [
        _item(db_session, user, _question(variant=str(index))) for index in range(5)
    ]
    for item in items:
        _attempt(db_session, user, item)
    assert not _topic(db_session, user).practice_ready
    _attempt(db_session, user, items[0], now=NOW + timedelta(days=1))
    state = _topic(db_session, user, now=NOW + timedelta(days=1))
    assert state.practice_ready and state.next_action == "transfer_wait"
    assert state.stage == "b2"


def test_transfer_is_delayed_and_abandoned_display_is_never_unseen_again(
    db_session, settings
):
    user = ensure_user(db_session, 123456789, settings)
    _practice(db_session, user)
    transfer = _item(db_session, user, _question(role="transfer", variant="heldout"))
    early = start_stream(db_session, user, now=NOW + timedelta(days=1, minutes=1))
    assert early.question["fingerprint"] != transfer.text
    stop_stream(db_session, user, now=NOW + timedelta(days=1, minutes=2))
    heldout = start_stream(db_session, user, now=NOW + timedelta(days=2, minutes=1))
    assert heldout.question["fingerprint"] == transfer.text
    assert heldout.question["adaptive_evidence"]["first_exposure"] is True
    stop_stream(db_session, user, now=NOW + timedelta(days=2, minutes=2))
    following = start_stream(db_session, user, now=NOW + timedelta(days=2, minutes=3))
    assert following.question["fingerprint"] != transfer.text


def test_transfer_early_or_familiar_evidence_does_not_unlock(db_session, settings):
    user = ensure_user(db_session, 123456789, settings)
    _practice(db_session, user)
    transfer = _item(db_session, user, _question(role="transfer"))
    _attempt(db_session, user, transfer, now=NOW + timedelta(days=1, minutes=1))
    _attempt(
        db_session,
        user,
        transfer,
        now=NOW + timedelta(days=2, minutes=1),
        overrides={"first_exposure": False},
    )
    _attempt(
        db_session,
        user,
        transfer,
        now=NOW + timedelta(days=2, minutes=2),
        overrides={"selection_mode": "familiar"},
    )
    assert _topic(db_session, user).stage == "b2"
    assert _topic(db_session, user).transfer_successes == 0


def test_topic_requires_transfer_then_harder_production_and_global_coverage(
    db_session, settings
):
    user = ensure_user(db_session, 123456789, settings)
    _master_stage(db_session, user)
    assert _topic(db_session, user).stage == "b2_plus"
    harder = _master_stage(
        db_session,
        user,
        stage="b2_plus",
        start=NOW + timedelta(days=3),
        production=False,
    )
    state = _topic(db_session, user)
    assert state.practice_ready and state.transfer_successes == 2
    assert state.next_action == "production" and not state.strong_b2
    _attempt(
        db_session,
        user,
        harder[0],
        now=NOW + timedelta(days=6),
        production=True,
        overrides={"independent_production": False},
    )
    assert not _topic(db_session, user).strong_b2
    _attempt(
        db_session,
        user,
        harder[0],
        now=NOW + timedelta(days=6, minutes=1),
        production=True,
    )
    progress = curriculum_progress(db_session, user, now=NOW + timedelta(days=7))
    assert progress.strong_b2_topics == 1 and not progress.c1_unlocked
    assert progress.topics[0].next_action == "c1_locked"
    for topic in list(TOPIC_TITLES)[1:]:
        _master_stage(db_session, user, topic)
        _master_stage(db_session, user, topic, "b2_plus", start=NOW + timedelta(days=3))
    progress = curriculum_progress(db_session, user, now=NOW + timedelta(days=7))
    assert progress.c1_unlocked and progress.strong_b2_topics == 10
    assert all(topic.stage == "c1_intro" for topic in progress.topics)


def test_isolated_error_retains_stage_repeated_distinct_errors_trigger_repair(
    db_session, settings
):
    user = ensure_user(db_session, 123456789, settings)
    items = _master_stage(db_session, user)
    _attempt(
        db_session, user, items[0], status="incorrect", now=NOW + timedelta(days=3)
    )
    assert _topic(db_session, user).stage == "b2_plus"
    _attempt(
        db_session, user, items[1], status="incorrect", now=NOW + timedelta(days=4)
    )
    db_session.commit()
    db_session.expire_all()
    state = _topic(db_session, user)
    assert state.stage == "b2" and state.repair
    assert state.practice_successes == 0 and state.transfer_successes == 0


def test_foreign_and_quarantined_evidence_cannot_create_mastery(db_session, settings):
    user = ensure_user(db_session, 123456789, settings)
    other = User(telegram_user_id=-123456789)
    db_session.add(other)
    db_session.flush()
    foreign = _item(db_session, other, _question(variant="foreign"))
    _attempt(db_session, user, foreign)
    assert _topic(db_session, user).practice_successes == 0
    items = _master_stage(db_session, user)
    assert _topic(db_session, user).stage == "b2_plus"
    item = items[0]
    item.metadata_json = {
        **item.metadata_json,
        "question_quality": {item.text: {"status": "quarantined"}},
    }
    db_session.flush()
    assert _topic(db_session, user).stage == "b2"
    assert _topic(db_session, user).practice_successes == 4


def test_variants_use_same_approved_item_and_record_atomic_evidence(
    db_session, settings
):
    user = ensure_user(db_session, 123456789, settings)
    item = _item(db_session, user, _question())
    variant = _question(variant="fresh-context")
    item.metadata_json = {**item.metadata_json, "simple_question_variants": [variant]}
    db_session.flush()
    initial = start_stream(db_session, user, now=NOW)
    result = answer_choice(
        db_session,
        user,
        initial.run.id,
        initial.index,
        initial.question["correct_index"],
        now=NOW,
    )
    assert result.attempt.feedback["adaptive"]["topic_id"] == "aspect"
    assert result.next_step.question["fingerprint"] != initial.question["fingerprint"]
    assert result.next_step.question["target_learning_item_ids"] == [item.id]
    duplicate = answer_choice(
        db_session, user, initial.run.id, initial.index, 0, now=NOW
    )
    assert not duplicate.accepted
    assert _topic(db_session, user).practice_successes == 1
    assert len(list(db_session.scalars(select(LearningItem)))) == 1


def test_written_bonus_copies_topic_and_rejects_example_copy(db_session, settings):
    user = ensure_user(db_session, 123456789, settings)
    item = _item(db_session, user, _question())
    stream = start_stream(db_session, user, now=NOW)
    stop_stream(db_session, user, now=NOW)
    bonus = start_bonus(db_session, user, stream.run.id, now=NOW)
    assert bonus.question["adaptive"]["topic_id"] == "aspect"
    answer = stream.question["options"][stream.question["correct_index"]]
    result = submit_bonus(
        db_session, user, bonus.run.id, answer, {"status": "correct"}, now=NOW
    )
    assert result.accepted
    assert result.attempt.feedback["independent_production"] is False
    assert result.attempt.target_learning_item_ids == [item.id]
    assert not independent_production(answer.upper(), bonus.question)
    assert independent_production("My team has fixed the problem.", bonus.question)


def test_generation_targets_approved_topic_shortages_and_role(db_session, settings):
    user = ensure_user(db_session, 123456789, settings)
    assert generation_need(db_session, user, now=NOW) is None
    _practice(db_session, user)
    need = generation_need(db_session, user, now=NOW + timedelta(days=2))
    assert need["topic_id"] == "aspect" and need["role"] == "transfer"
    assert need["reason"] == "unseen_transfer_shortage"


def test_real_stream_advances_after_spaced_practice_and_delayed_transfer(
    db_session, settings
):
    user = ensure_user(db_session, 123456789, settings)
    for index in range(5):
        _item(db_session, user, _question(variant=str(index)))
    transfer = _item(db_session, user, _question(role="transfer", variant="new"))
    harder = _item(db_session, user, _question(stage="b2_plus", variant="harder"))
    step = start_stream(db_session, user, now=NOW)
    for index in range(5):
        assert step.question["adaptive"]["stage"] == "b2"
        assert step.question["adaptive"]["role"] == "practice"
        result = answer_choice(
            db_session,
            user,
            step.run.id,
            step.index,
            step.question["correct_index"],
            now=NOW + timedelta(seconds=index),
        )
        step = result.next_step
    assert result.reason == "exhausted"
    next_day = NOW + timedelta(days=1, minutes=1)
    step = start_stream(db_session, user, now=next_day)
    answer_choice(
        db_session,
        user,
        step.run.id,
        step.index,
        step.question["correct_index"],
        now=next_day,
    )
    stop_stream(db_session, user, now=next_day)
    db_session.commit()
    db_session.expire_all()
    later = next_day + timedelta(days=1, minutes=1)
    step = start_stream(db_session, user, now=later)
    assert step.question["fingerprint"] == transfer.text
    result = answer_choice(
        db_session,
        user,
        step.run.id,
        step.index,
        step.question["correct_index"],
        now=later,
    )
    assert result.attempt.feedback["first_exposure"]
    assert result.attempt.feedback["transfer_eligible"]
    assert result.next_step.question["fingerprint"] == harder.text
    assert _topic(db_session, user).stage == "b2_plus"


def test_low_accuracy_requires_more_correct_practice(db_session, settings):
    user = ensure_user(db_session, 123456789, settings)
    difficult = _item(db_session, user, _question(variant="difficult"))
    for index in range(3):
        _attempt(
            db_session,
            user,
            difficult,
            status="incorrect",
            now=NOW + timedelta(minutes=index),
        )
    _practice(db_session, user, start=NOW + timedelta(hours=1))
    state = _topic(db_session, user)
    assert state.practice_successes == 5
    assert state.practice_accuracy == 5 / 8
    assert not state.practice_ready
    for index in range(3):
        item = _item(db_session, user, _question(variant=f"recovery{index}"))
        _attempt(db_session, user, item, now=NOW + timedelta(days=2, minutes=index))
    assert _topic(db_session, user).practice_ready


def test_production_before_practice_readiness_is_not_mastery(db_session, settings):
    user = ensure_user(db_session, 123456789, settings)
    _master_stage(db_session, user)
    items = _master_stage(
        db_session,
        user,
        stage="b2_plus",
        start=NOW + timedelta(days=3),
        production=False,
    )
    _attempt(
        db_session,
        user,
        items[0],
        production=True,
        now=NOW + timedelta(days=3, minutes=1),
    )
    state = _topic(db_session, user)
    assert state.production_successes == 0
    assert state.next_action == "production"


def test_unverified_written_feedback_cannot_establish_or_regress_mastery(
    db_session, settings
):
    user = ensure_user(db_session, 123456789, settings)
    _master_stage(db_session, user)
    items = _master_stage(
        db_session,
        user,
        stage="b2_plus",
        start=NOW + timedelta(days=3),
        production=False,
    )
    for index, item in enumerate(items[:2]):
        _attempt(
            db_session,
            user,
            item,
            production=True,
            now=NOW + timedelta(days=6, minutes=index),
            overrides={"genuine_evaluation": False},
            status="partial",
        )
    _attempt(
        db_session,
        user,
        items[0],
        production=True,
        now=NOW + timedelta(days=6, minutes=4),
        overrides={"genuine_evaluation": False},
    )
    state = _topic(db_session, user)
    assert state.practice_ready and state.next_action == "production"
    assert state.production_successes == 0


def test_adaptive_bonus_saves_unverified_response_without_srs_change(
    db_session, settings
):
    from fluentloop.db.models import ReviewState

    user = ensure_user(db_session, 123456789, settings)
    item = _item(db_session, user, _question())
    stream = start_stream(db_session, user, now=NOW)
    stop_stream(db_session, user, now=NOW)
    bonus = start_bonus(db_session, user, stream.run.id, now=NOW)
    result = submit_bonus(
        db_session,
        user,
        bonus.run.id,
        "My team has completed the security audit.",
        {"status": "correct", "genuine_evaluation": False},
        now=NOW,
    )
    assert result.accepted and result.attempt.status == "unchecked"
    assert (
        db_session.scalar(
            select(ReviewState).where(ReviewState.learning_item_id == item.id)
        )
        is None
    )


def test_copied_sentence_with_filler_or_cosmetic_change_is_not_independent():
    question = {
        "source_example": "Our team has already completed the security audit.",
        "expected_answer": "present perfect",
    }
    assert not independent_production(
        "As requested, our team has already completed the security audit. Thanks.",
        question,
    )
    assert not independent_production(
        "Our team has already completed this security audit.", question
    )
    assert independent_production(
        "The vendor has fixed both authentication failures.", question
    )


def test_same_variant_identifier_on_distinct_fingerprints_cannot_inflate_evidence(
    db_session, settings
):
    user = ensure_user(db_session, 123456789, settings)
    for index in range(8):
        question = _question(variant=f"different-context-{index}")
        question["adaptive"]["variant_id"] = "one-logical-variant"
        item = _item(db_session, user, question)
        _attempt(db_session, user, item, now=NOW + timedelta(days=index))
    state = _topic(db_session, user)
    assert state.practice_successes == 1 and not state.practice_ready


def test_reviewed_pack_stream_unlocks_harder_topics_after_three_day_flow(
    db_session, settings
):
    from fluentloop.adaptive_curriculum import (
        publish_adaptive_curriculum,
        subscribe_adaptive_curriculum,
    )

    user = ensure_user(db_session, 123456789, settings)
    published = publish_adaptive_curriculum(db_session)
    subscribed = subscribe_adaptive_curriculum(db_session, user)
    assert published.items == 270 and len(subscribed.plans) == 10
    for day in range(2):
        current = NOW + timedelta(days=day, minutes=10 * day)
        step = start_stream(db_session, user, now=current)
        count = 0
        while step.question is not None:
            assert step.question["adaptive"]["stage"] == "b2"
            assert step.question["adaptive"]["role"] == "practice"
            result = answer_choice(
                db_session,
                user,
                step.run.id,
                step.index,
                step.question["correct_index"],
                now=current + timedelta(seconds=count),
            )
            count += 1
            step = result.next_step
            if step is None:
                break
        assert count == 60
    current = NOW + timedelta(days=2, minutes=30)
    progress = curriculum_progress(db_session, user, now=current)
    assert all(topic.practice_ready for topic in progress.topics)
    assert all(topic.stage == "b2" for topic in progress.topics)
    step = start_stream(db_session, user, now=current)
    for _ in range(150):
        result = answer_choice(
            db_session,
            user,
            step.run.id,
            step.index,
            step.question["correct_index"],
            now=current,
        )
        step = result.next_step
        progress = curriculum_progress(db_session, user, now=current)
        if all(topic.stage == "b2_plus" for topic in progress.topics):
            break
    else:
        raise AssertionError("Delayed transfer did not unlock all harder topics")
    assert progress.strong_b2_topics == 0 and not progress.c1_unlocked


def test_repair_topic_is_prioritized_ahead_of_other_eligible_transfer(
    db_session, settings
):
    user = ensure_user(db_session, 123456789, settings)
    items = _master_stage(db_session, user)
    _practice(db_session, user, "conditionals")
    _item(db_session, user, _question("conditionals", role="transfer"))
    _attempt(
        db_session, user, items[0], status="incorrect", now=NOW + timedelta(days=3)
    )
    _attempt(
        db_session, user, items[1], status="incorrect", now=NOW + timedelta(days=4)
    )
    step = start_stream(db_session, user, now=NOW + timedelta(days=4, minutes=1))
    assert step.question["adaptive"]["topic_id"] == "aspect"
    assert step.question["adaptive"]["role"] == "practice"


def test_bonus_selects_missing_production_stage_not_latest_easier_same_topic(
    db_session, settings
):
    user = ensure_user(db_session, 123456789, settings)
    easier = _master_stage(db_session, user)
    harder = _master_stage(
        db_session,
        user,
        stage="b2_plus",
        start=NOW + timedelta(days=3),
        production=False,
    )
    harder_question = {
        **harder[0].metadata_json["simple_question"],
        "exercise_type": "simple_choice",
        "target_learning_item_ids": [harder[0].id],
        "target_construction": "past perfect for an earlier workplace event",
        "metadata": {"selection_mode": "normal"},
    }
    easier_question = {
        **easier[0].metadata_json["simple_question"],
        "exercise_type": "simple_choice",
        "target_learning_item_ids": [easier[0].id],
        "metadata": {"selection_mode": "normal"},
    }
    parent = PracticeSession(
        user_id=user.id,
        target_date_local=NOW.date(),
        status="completed",
        exercises=[easier_question],
    )
    db_session.add(parent)
    db_session.flush()
    for index, question in enumerate((harder_question, easier_question)):
        db_session.add(
            PracticeAttempt(
                practice_session_id=parent.id,
                exercise_index=index,
                exercise_type="simple_choice",
                target_learning_item_ids=question["target_learning_item_ids"],
                prompt=question["prompt"],
                user_answer="",
                status="unchecked",
                feedback={"question": question},
            )
        )
    db_session.flush()
    bonus = start_bonus(db_session, user, parent.id, now=NOW + timedelta(days=7))
    assert bonus.question["adaptive"]["stage"] == "b2_plus"
    assert bonus.question["target_learning_item_ids"] == [harder[0].id]
    assert bonus.question["expected_answer"] == harder_question["target_construction"]
    assert bonus.question["source_example"] == harder_question["options"][1]
    result = submit_bonus(
        db_session,
        user,
        bonus.run.id,
        "By the time the review began, our team had validated the backups. "
        "We restored the staging service within minutes.",
        {"status": "correct", "genuine_evaluation": True},
        now=NOW + timedelta(days=7),
    )
    assert result.accepted and _topic(db_session, user).strong_b2


def test_phrase_bonus_keeps_phrase_target_and_independent_grammar_rubric(
    db_session, settings
):
    from fluentloop.feedback import build_answer_check_payload

    user = ensure_user(db_session, 123456789, settings)
    question = _question("delivery_collocations")
    question.update(
        category="phrase",
        target_phrase="get buy-in",
        target_construction="get buy-in from stakeholders",
    )
    _item(db_session, user, question)
    stream = start_stream(db_session, user, now=NOW)
    stop_stream(db_session, user, now=NOW)
    bonus = start_bonus(db_session, user, stream.run.id, now=NOW)
    assert bonus.question["expected_answer"] == "get buy-in"
    payload = build_answer_check_payload(
        bonus.question, "We need to get buy-in before the pilot."
    )
    assert payload["reference_example"] == question["options"][1]
    assert payload["target_construction"] == question["target_construction"]
    assert "not an exact answer" in payload["explanation"]
