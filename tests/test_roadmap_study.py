from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from threading import Barrier
from types import SimpleNamespace

import pytest
from sqlalchemy import func, select

from fluentloop.db.models import (
    LearningItem,
    PracticeAttempt,
    PracticeSession,
    ReviewState,
    User,
)
from fluentloop.db.session import make_engine, make_session_factory
from fluentloop.roadmap_study import (
    answered_module_question,
    enabled,
    load_question_pack,
    module_progress,
    record_module_external,
    report_module_issue,
    start_module_bonus,
    validate_question_pack,
)
from fluentloop.simple_learning import (
    answer_choice,
    get_active_stream,
    start_bonus,
    start_stream,
    stop_stream,
    submit_bonus,
)
from fluentloop.users import ensure_user
from fluentloop.workplace_roadmap import (
    default_plan,
    load_curriculum,
    save_plan,
    update_plan,
)

NOW = datetime(2026, 10, 3, 8, tzinfo=UTC)
WRITING_A = "My neighbour collects rare stamps and volunteers at the local museum."
WRITING_B = (
    "During the journey our group discovered a quiet coastal village near Lisbon."
)


@pytest.fixture
def pack(monkeypatch):
    data = {"version": 1, "modules": []}
    for module in load_curriculum()["modules"]:
        stages = {}
        for stage in ("b2", "b2_plus", "c1_intro"):
            stages[stage] = {
                "prompt": f"Choose a suitable response for {module['id']} at {stage}.",
                "options": [
                    "A suitable model answer for the stated situation.",
                    "No.",
                    "Maybe.",
                ],
                "correct_index": 0,
                "explanation_ru": "Учитывайте ситуацию.",
                "target_construction": "clear explanation and suitable register",
                "production_prompts": [
                    {
                        "variant_id": "a",
                        "prompt": "Explain a neighbourhood activity in English.",
                    },
                    {
                        "variant_id": "b",
                        "prompt": "Describe a recent journey in English.",
                    },
                ],
                "resource_ids": [module["source_ids"][0]],
            }
        data["modules"].append({"module_id": module["id"], "stages": stages})
    monkeypatch.setattr(
        "fluentloop.roadmap_study.load_question_pack", lambda: deepcopy(data)
    )
    return data


@pytest.fixture
def learner(db_session, settings, pack):
    user = ensure_user(db_session, 123456789, settings)
    save_plan(db_session, user, default_plan())
    return user


def right(session, user, step, now=NOW):
    return answer_choice(
        session, user, step.run.id, step.index, step.question["correct_index"], now=now
    )


def progress(session, user, identifier="identity_relationships", now=NOW):
    return next(
        p
        for p in module_progress(session, user, now=now)
        if p["module_id"] == identifier
    )


def write(session, user, parent, answer, now, *, genuine=True):
    bonus = start_module_bonus(session, user, parent.run.id, parent.index, now=now)
    assert bonus.question is not None
    result = submit_bonus(
        session,
        user,
        bonus.run.id,
        answer,
        {"status": "correct", "genuine_evaluation": genuine},
        now=now,
    )
    assert result.accepted
    return bonus, result


@pytest.mark.parametrize("share,count", [(60, 10), (90, 10), (20, 10)])
def test_actual_general_work_allocation_and_restart(db_session, learner, share, count):
    update_plan(db_session, learner, "general_share", share)
    step = start_stream(db_session, learner, now=NOW)
    strands = []
    for index in range(count):
        strands.append(step.question["strand"])
        assert step.question["target_learning_item_ids"] == []
        assert "adaptive" not in step.question
        result = right(db_session, learner, step, NOW + timedelta(seconds=index))
        step = result.next_step
        assert step is not None
        db_session.commit()
        db_session.expire_all()
        resumed = start_stream(db_session, learner, now=NOW)
        assert resumed.question == step.question
    assert strands.count("general") == share // 10


def test_focus_pause_order_and_pending_snapshot(db_session, learner):
    update_plan(db_session, learner, "focus", "travel_culture")
    step = start_stream(db_session, learner, now=NOW)
    assert step.question["roadmap"]["module_id"] == "travel_culture"
    update_plan(db_session, learner, "pause", "travel_culture")
    assert start_stream(db_session, learner, now=NOW).question == step.question
    result = right(db_session, learner, step)
    assert result.next_step.question["roadmap"]["module_id"] == "identity_relationships"
    assert progress(db_session, learner, "travel_culture")["paused"]


def test_language_questions_keep_real_work_strand_and_are_interleaved(
    db_session, learner
):
    for index in range(8):
        db_session.add(
            LearningItem(
                user_id=learner.id,
                type="grammar_rule",
                text=f"Bank target {index}",
                status="active",
                metadata_json={
                    "simple_question": {
                        "prompt": f"Select the workplace response number {index}.",
                        "options": [
                            f"Correct language {index}",
                            f"Wrong language {index}",
                        ],
                        "correct_index": 0,
                        "explanation_ru": "Языковая практика.",
                        "category": "grammar",
                    }
                },
            )
        )
    db_session.flush()
    step = start_stream(db_session, learner, now=NOW)
    sources = []
    for _ in range(10):
        if step.question["strand"] == "work":
            sources.append(step.question["selection_source"])
        step = right(db_session, learner, step).next_step
    assert sources == ["language", "roadmap", "language", "roadmap"]


def test_missing_plan_keeps_existing_flow_then_new_plan_preserves_pending(
    db_session, settings, pack
):
    user = ensure_user(db_session, 123456789, settings)
    item = LearningItem(
        user_id=user.id,
        type="grammar_rule",
        text="Existing target",
        status="active",
        metadata_json={
            "simple_question": {
                "prompt": "An old question",
                "options": ["Right", "Wrong"],
                "correct_index": 0,
                "category": "grammar",
            }
        },
    )
    db_session.add(item)
    db_session.flush()
    assert not enabled(user)
    step = start_stream(db_session, user, now=NOW)
    assert "roadmap" not in step.question
    save_plan(db_session, user, default_plan())
    assert start_stream(db_session, user, now=NOW).question == step.question
    assert right(db_session, user, step).next_step.question["strand"] == "general"


def test_spaced_distinct_writing_advances_without_srs_or_old_mastery(
    db_session, learner
):
    first = start_stream(db_session, learner, now=NOW)
    right(db_session, learner, first)
    assert progress(db_session, learner)["stage"] == "b2"
    bonus_a, result_a = write(db_session, learner, first, WRITING_A, NOW)
    assert bonus_a.question["roadmap"]["production_variant_id"] == "a"
    assert result_a.attempt.feedback["independent_production"]
    next_day = NOW + timedelta(days=1)
    bonus_b, _ = write(db_session, learner, first, WRITING_B, next_day)
    assert bonus_b.question["roadmap"]["production_variant_id"] == "b"
    assert progress(db_session, learner, now=next_day)["stage"] == "b2_plus"
    assert get_active_stream(db_session, learner) is not None
    assert db_session.scalar(select(func.count()).select_from(ReviewState)) == 0
    from fluentloop.adaptive_learning import curriculum_progress

    assert curriculum_progress(db_session, learner, now=next_day).strong_b2_topics == 0


@pytest.mark.parametrize("genuine,copied", [(False, False), (True, True)])
def test_fallback_or_copied_answer_cannot_advance(db_session, learner, genuine, copied):
    first = start_stream(db_session, learner, now=NOW)
    right(db_session, learner, first)
    answer = first.question["expected_answer"] if copied else WRITING_A
    _, result = write(db_session, learner, first, answer, NOW, genuine=genuine)
    assert result.attempt.status == ("correct" if genuine else "unchecked")
    assert progress(db_session, learner)["writing_variants"] == []
    assert progress(db_session, learner)["stage"] == "b2"


def test_duplicate_response_and_model_rewrite_rejected(db_session, learner):
    first = start_stream(db_session, learner, now=NOW)
    right(db_session, learner, first)
    write(db_session, learner, first, WRITING_A, NOW)
    _, result = write(db_session, learner, first, WRITING_A, NOW + timedelta(days=1))
    assert not result.attempt.feedback["independent_production"]
    assert progress(db_session, learner, now=NOW + timedelta(days=1))["stage"] == "b2"


def test_same_day_writing_leaves_spacing_incomplete(db_session, learner):
    first = start_stream(db_session, learner, now=NOW)
    right(db_session, learner, first)
    write(db_session, learner, first, WRITING_A, NOW)
    write(db_session, learner, first, WRITING_B, NOW + timedelta(hours=2))
    state = progress(db_session, learner, now=NOW + timedelta(hours=2))
    assert state["stage"] == "b2"
    assert state["writing_variants"] == ["a", "b"]
    assert state["next_action"] == "spacing"


def test_stage_c1_still_requires_existing_language_gate(
    db_session, learner, monkeypatch
):
    first = start_stream(db_session, learner, now=NOW)
    right(db_session, learner, first)
    write(db_session, learner, first, WRITING_A, NOW)
    day1 = NOW + timedelta(days=1)
    write(db_session, learner, first, WRITING_B, day1)
    stop_stream(db_session, learner)
    update_plan(db_session, learner, "focus", "identity_relationships")
    second = start_stream(db_session, learner, now=day1)
    assert second.question["roadmap"]["stage"] == "b2_plus"
    right(db_session, learner, second, day1)
    write(
        db_session,
        learner,
        second,
        "The swimming club reopened after repairs to its damaged roof.",
        day1,
    )
    day2 = day1 + timedelta(days=1)
    write(
        db_session,
        learner,
        second,
        "We booked a mountain cabin because the city hotels were expensive.",
        day2,
    )
    state = progress(db_session, learner, now=day2)
    assert state["stage"] == "b2_plus"
    assert state["next_action"] == "language_gate"
    monkeypatch.setattr(
        "fluentloop.roadmap_study.curriculum_progress",
        lambda *args, **kwargs: SimpleNamespace(c1_unlocked=True),
    )
    assert progress(db_session, learner, now=day2)["stage"] == "c1_intro"


def test_owned_callbacks_idempotency_quarantine_and_unknown(db_session, learner):
    step = start_stream(db_session, learner, now=NOW)
    assert not record_module_external(db_session, learner, step.run.id, step.index)
    result = right(db_session, learner, step)
    assert not right(db_session, learner, step).accepted
    assert record_module_external(db_session, learner, step.run.id, step.index)
    assert not record_module_external(db_session, learner, step.run.id, step.index)
    assert answered_module_question(db_session, learner, step.run.id, step.index)
    stranger = User(telegram_user_id=-1)
    db_session.add(stranger)
    db_session.flush()
    assert not record_module_external(db_session, stranger, step.run.id, step.index)
    assert start_module_bonus(db_session, stranger, step.run.id, step.index).run is None
    assert (
        answered_module_question(db_session, stranger, step.run.id, step.index) is None
    )
    assert report_module_issue(db_session, learner, step.run.id, step.index)
    assert not report_module_issue(db_session, learner, step.run.id, step.index)
    assert progress(db_session, learner)["recognition_correct"] == 0
    stop_stream(db_session, learner)
    replacement = start_stream(db_session, learner, now=NOW + timedelta(days=1))
    assert replacement.question["fingerprint"] != step.question["fingerprint"]
    assert result.attempt.status == "correct"


def test_familiar_repetition_and_oversize_writing_do_not_add_evidence(
    db_session, learner
):
    first = start_stream(db_session, learner, now=NOW)
    right(db_session, learner, first)
    stop_stream(db_session, learner)
    familiar = start_stream(db_session, learner, repeat_familiar=True, now=NOW)
    assert (
        familiar.question["roadmap"]["module_id"]
        == first.question["roadmap"]["module_id"]
    )
    right(db_session, learner, familiar)
    bonus = start_module_bonus(
        db_session, learner, familiar.run.id, familiar.index, now=NOW
    )
    assert not submit_bonus(db_session, learner, bonus.run.id, "a" * 10001, {}).accepted
    submit_bonus(
        db_session,
        learner,
        bonus.run.id,
        WRITING_A,
        {"status": "correct", "genuine_evaluation": True},
        now=NOW,
    )
    assert progress(db_session, learner)["writing_variants"] == []


def test_stopped_module_stream_can_start_apply_it(db_session, learner):
    first = start_stream(db_session, learner, now=NOW)
    right(db_session, learner, first)
    stop_stream(db_session, learner)
    assert start_bonus(db_session, learner, first.run.id, now=NOW).question["roadmap"]


def test_pack_rejects_missing_module_ambiguous_options_and_unknown_resource(pack):
    assert len(validate_question_pack(pack)["modules"]) == 48
    for mutation in ("missing", "ambiguous", "resource"):
        invalid = deepcopy(pack)
        if mutation == "missing":
            invalid["modules"].pop()
        elif mutation == "ambiguous":
            invalid["modules"][0]["stages"]["b2"]["options"] = ["Same"] * 3
        else:
            invalid["modules"][0]["stages"]["b2"]["resource_ids"] = ["unknown"]
        with pytest.raises(ValueError):
            validate_question_pack(invalid)


def test_shipped_pack_covers_all_modules_and_stages():
    pack = load_question_pack()
    assert len(pack["modules"]) == 48
    assert sum(len(module["stages"]) for module in pack["modules"]) == 144


@pytest.mark.parametrize("stage", ["b2", "b2_plus", "c1_intro"])
def test_every_module_is_deliverable_at_its_eligible_stage(
    db_session, learner, monkeypatch, stage
):
    stages = ("b2", "b2_plus", "c1_intro")
    # Replay real persisted evidence, rather than overriding module readiness.
    for module in load_curriculum()["modules"]:
        for prior in stages[: stages.index(stage)]:
            run = PracticeSession(
                user_id=learner.id,
                target_date_local=NOW.date(),
                started_at=NOW,
                status="completed",
                exercises=[],
            )
            db_session.add(run)
            db_session.flush()
            namespace = {
                "version": 1,
                "module_id": module["id"],
                "stage": prior,
                "question_id": f"roadmap:v1:{module['id']}:{prior}",
                "role": "practice",
                "strand": module["strand"],
            }
            for index, variant in enumerate((None, "a", "b")):
                db_session.add(
                    PracticeAttempt(
                        practice_session_id=run.id,
                        exercise_index=index,
                        exercise_type="simple_choice"
                        if variant is None
                        else "simple_production",
                        target_learning_item_ids=[],
                        prompt="Reviewed practice",
                        user_answer="A distinct independently written response.",
                        status="correct",
                        created_at=NOW + timedelta(days=index),
                        feedback={
                            "roadmap": {**namespace, "production_variant_id": variant},
                            "selection_mode": "normal",
                            "genuine_evaluation": True,
                            "independent_production": True,
                        },
                    )
                )
    db_session.flush()
    if stage == "c1_intro":
        monkeypatch.setattr(
            "fluentloop.roadmap_study.curriculum_progress",
            lambda *args, **kwargs: SimpleNamespace(c1_unlocked=True),
        )
    current = NOW + timedelta(days=3)
    step = start_stream(db_session, learner, now=current)
    seen = set()
    while step is not None:
        assert step.question["roadmap"]["stage"] == stage
        seen.add(step.question["roadmap"]["module_id"])
        step = right(db_session, learner, step, current).next_step
    assert seen == {module["id"] for module in load_curriculum()["modules"]}


def test_exhausted_general_strand_falls_back_honestly(db_session, learner):
    step = start_stream(db_session, learner, now=NOW)
    fallback_seen = False
    while step is not None:
        if step.question.get("selection_fallback") == "general_unavailable":
            fallback_seen = True
            assert step.question["strand"] == "work"
        step = right(db_session, learner, step).next_step
    assert fallback_seen
    assert start_stream(db_session, learner, now=NOW).exhausted


def test_failed_focus_waits_for_five_other_answers(db_session, learner):
    first = start_stream(db_session, learner, now=NOW)
    fingerprint = first.question["fingerprint"]
    next_step = answer_choice(
        db_session, learner, first.run.id, first.index, None, now=NOW
    ).next_step
    for _ in range(5):
        assert next_step.question["fingerprint"] != fingerprint
        next_step = right(db_session, learner, next_step).next_step
    # Focus then selects the repaired item once the due and recent gates permit it.
    update_plan(db_session, learner, "focus", "identity_relationships")
    while next_step.question["strand"] != "general":
        next_step = right(db_session, learner, next_step).next_step
    # The next pending snapshot may have been selected before changing focus.
    stop_stream(db_session, learner)
    focused = start_stream(db_session, learner, now=NOW)
    assert focused.question["fingerprint"] == fingerprint


def test_model_rewrite_does_not_count_as_second_original_response(db_session, learner):
    first = start_stream(db_session, learner, now=NOW)
    right(db_session, learner, first)
    bonus = start_module_bonus(db_session, learner, first.run.id, first.index, now=NOW)
    model_rewrite = (
        "The local library hosts a reading group for residents every Tuesday."
    )
    submit_bonus(
        db_session,
        learner,
        bonus.run.id,
        WRITING_A,
        {
            "status": "correct",
            "genuine_evaluation": True,
            "natural_answer": model_rewrite,
        },
        now=NOW,
    )
    _, result = write(
        db_session, learner, first, model_rewrite, NOW + timedelta(days=1)
    )
    assert not result.attempt.feedback["independent_production"]


def test_old_adaptive_writing_remains_prioritized_after_module_questions(
    db_session, learner, monkeypatch
):
    item = LearningItem(
        user_id=learner.id,
        type="grammar_rule",
        text="Aspect target",
        status="active",
        metadata_json={
            "simple_question": {
                "prompt": "Choose the natural workplace account.",
                "options": [
                    "We have completed the review.",
                    "We completed review yesterday now.",
                ],
                "correct_index": 0,
                "category": "grammar",
                "adaptive": {
                    "version": 1,
                    "topic_id": "aspect",
                    "stage": "b2",
                    "role": "practice",
                    "variant_id": "reviewed-practice-a",
                },
            }
        },
    )
    db_session.add(item)
    db_session.flush()
    step = start_stream(db_session, learner, now=NOW)
    parent_id = step.run.id
    for _ in range(5):
        step = right(db_session, learner, step).next_step
    stop_stream(db_session, learner)
    monkeypatch.setattr(
        "fluentloop.simple_learning.curriculum_progress",
        lambda *args, **kwargs: SimpleNamespace(
            topics=[
                SimpleNamespace(topic_id="aspect", stage="b2", next_action="production")
            ]
        ),
    )
    bonus = start_bonus(db_session, learner, parent_id, now=NOW)
    assert bonus.question["adaptive"]["topic_id"] == "aspect"
    assert "roadmap" not in bonus.question
    assert bonus.question["target_learning_item_ids"] == [item.id]


def test_changed_share_starts_a_fresh_allocation_without_long_catchup(
    db_session, learner
):
    step = start_stream(db_session, learner, now=NOW)
    for _ in range(10):
        step = right(db_session, learner, step).next_step
    update_plan(db_session, learner, "general_share", 90)
    # The currently displayed question is frozen under the old allocation.
    step = right(db_session, learner, step).next_step
    strands = []
    for _ in range(10):
        assert step.question["allocation_share"] == 90
        strands.append(step.question["strand"])
        step = right(db_session, learner, step).next_step
    assert strands.count("general") == 9
    assert strands.count("work") == 1


def test_external_resources_include_catalog_when_choice_has_no_extra_links(
    db_session, learner, pack
):
    for module in pack["modules"]:
        for question in module["stages"].values():
            question["resource_ids"] = []
    step = start_stream(db_session, learner, now=NOW)
    assert step.question["resource_ids"] == []
    assert step.question["module_resources"]
    assert all(
        source["url"].startswith("https://")
        for source in step.question["module_resources"]
    )


@pytest.mark.parametrize("action", ["answer", "report"])
def test_parallel_module_callbacks_claim_once_on_distinct_sqlite_connections(
    tmp_path, settings, pack, monkeypatch, action
):
    engine = make_engine(f"sqlite:///{tmp_path / 'module-race.sqlite'}")
    factory = make_session_factory(engine)
    with factory() as session:
        user = ensure_user(session, 123456789, settings)
        save_plan(session, user, default_plan())
        step = start_stream(session, user, now=NOW)
        user_id, run_id, correct = user.id, step.run.id, step.question["correct_index"]
        if action == "report":
            right(session, user, step)
        session.commit()
    barrier = Barrier(2)
    if action == "answer":
        from fluentloop import simple_learning

        original_claim = simple_learning._claim

        def concurrent_claim(*args, **kwargs):
            barrier.wait(timeout=5)
            return original_claim(*args, **kwargs)

        monkeypatch.setattr(simple_learning, "_claim", concurrent_claim)

    def callback():
        with factory() as session:
            user = session.get(User, user_id)
            if action == "answer":
                accepted = answer_choice(
                    session, user, run_id, 0, correct, now=NOW
                ).accepted
            else:
                barrier.wait(timeout=5)
                accepted = record_module_external(session, user, run_id, 0)
            session.commit()
            return accepted

    with ThreadPoolExecutor(max_workers=2) as workers:
        assert sorted(workers.map(lambda _: callback(), range(2))) == [False, True]
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(PracticeAttempt)) == (
            1 if action == "answer" else 2
        )
        assert session.scalar(select(func.count()).select_from(ReviewState)) == 0


def test_unchecked_writing_can_retry_same_variant_without_double_credit(
    db_session, learner
):
    first = start_stream(db_session, learner, now=NOW)
    right(db_session, learner, first)
    original, _ = write(db_session, learner, first, WRITING_A, NOW, genuine=False)
    retry = start_module_bonus(db_session, learner, first.run.id, first.index, now=NOW)
    assert retry.run.id != original.run.id
    assert retry.question["roadmap"]["production_variant_id"] == "a"
    resumed = start_module_bonus(
        db_session, learner, first.run.id, first.index, now=NOW
    )
    assert resumed.run.id == retry.run.id
    submit_bonus(
        db_session,
        learner,
        retry.run.id,
        WRITING_A,
        {"status": "correct", "genuine_evaluation": True},
        now=NOW,
    )
    state = progress(db_session, learner)
    assert state["writing_attempts"] == 2
    assert state["writing_variants"] == ["a"]
    assert state["stage"] == "b2"


def test_module_interleaving_does_not_starve_adaptive_grammar_bank(db_session, learner):
    for index, category in enumerate(("phrase", "grammar") * 4):
        db_session.add(
            LearningItem(
                user_id=learner.id,
                type="grammar_rule" if category == "grammar" else "expression",
                text=f"Reviewed bank target {index}",
                status="active",
                metadata_json={
                    "simple_question": {
                        "prompt": f"Select the reviewed language answer {index}.",
                        "options": [
                            f"Correct bank answer {index}",
                            f"Wrong bank answer {index}",
                        ],
                        "correct_index": 0,
                        "category": category,
                        **(
                            {
                                "adaptive": {
                                    "version": 1,
                                    "topic_id": "aspect",
                                    "stage": "b2",
                                    "role": "practice",
                                    "variant_id": f"bank-aspect-{index}",
                                }
                            }
                            if category == "grammar"
                            else {}
                        ),
                    }
                },
            )
        )
    db_session.flush()
    step = start_stream(db_session, learner, now=NOW)
    categories, strands = [], []
    for _ in range(10):
        strands.append(step.question["strand"])
        if step.question["selection_source"] == "language":
            categories.append(step.question["category"])
            if step.question["category"] == "grammar":
                assert step.question["adaptive"]["topic_id"] == "aspect"
        step = right(db_session, learner, step).next_step
        # Even short separate runs preserve the bank's own alternation.
        stop_stream(db_session, learner)
        step = start_stream(db_session, learner, now=NOW)
    assert categories == ["phrase", "grammar"]
    assert strands.count("general") == 6
