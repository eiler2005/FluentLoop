from __future__ import annotations

from collections import Counter
from copy import deepcopy
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select

from fluentloop.db.models import LearningItem, PracticeAttempt, PracticeSession, User
from fluentloop.lexical_learning import (
    _target_present,
    answered_lexical_question,
    candidate_questions,
    lexical_feedback_metadata,
    lexical_progress,
    report_lexical_issue,
    start_lexical_bonus,
    validate_lexicon,
)
from fluentloop.simple_learning import (
    answer_choice,
    start_bonus,
    start_stream,
    stop_stream,
    submit_bonus,
)
from fluentloop.users import ensure_user
from fluentloop.workplace_roadmap import (
    default_plan,
    get_plan,
    load_curriculum,
    save_plan,
    update_plan,
)

NOW = datetime(2026, 10, 3, 8, tzinfo=UTC)
WRITING_A = "I followed up on the museum booking after our family changed its dates."
WRITING_B = "Our neighbours are following up on their missing luggage with the airline."


@pytest.fixture
def lexicon(monkeypatch):
    modules = load_curriculum()["modules"]
    functions = [
        {"id": strand, "title_ru": "Контекст", "strand": strand}
        for strand in ("general", "work")
    ]
    entries = []
    for index in range(40):
        strand = "general" if index % 3 == 0 else "work"
        module = next(m for m in modules if m["strand"] == strand)
        entries.append(
            {
                "id": f"sense_{index:02}",
                "function_id": strand,
                "strand": strand,
                "stage": "b2",
                "headword": "follow up on",
                "meaning_ru": "вернуться к вопросу",
                "meaning_en": "take further action about a matter",
                "example": (
                    "We followed up on the supplier complaint "
                    "before signing the new contract."
                ),
                "grammar": "follow up on + noun",
                "register": "neutral",
                "plain_alternative": "take further action about",
                "source_urls": [
                    "https://dictionary.cambridge.org/dictionary/english/follow-up"
                ],
                "module_ids": [module["id"]],
                "questions": [
                    {
                        "variant_id": variant,
                        "prompt": f"Choose a follow-up for case {index}, {variant}.",
                        "options": [
                            f"We should follow up on case {index}{variant}.",
                            "Ignore the matter.",
                            "Declare it done.",
                        ],
                        "correct_index": 0,
                        "explanation_ru": "Нужно вернуться к вопросу.",
                    }
                    for variant in ("a", "b")
                ],
                "production_prompts": [
                    {
                        "variant_id": "a",
                        "prompt": "Describe a changed reservation needing action.",
                    },
                    {
                        "variant_id": "b",
                        "prompt": "Write about a delayed delivery needing action.",
                    },
                ],
            }
        )
    data = validate_lexicon({"version": 1, "functions": functions, "entries": entries})
    monkeypatch.setattr(
        "fluentloop.lexical_learning.load_lexicon", lambda: deepcopy(data)
    )
    return data


@pytest.fixture
def learner(db_session, settings, lexicon):
    user = ensure_user(db_session, 123456789, settings)
    save_plan(db_session, user, default_plan())
    # Real bank selection participates alongside real module and lexical selection.
    for index in range(20):
        db_session.add(
            LearningItem(
                user_id=user.id,
                type="word",
                text=f"language phrase {index}",
                status="active",
                metadata_json={
                    "simple_question": {
                        "prompt": f"Choose the language pattern for scenario {index}.",
                        "options": [
                            f"We can clarify language case {index}.",
                            "No.",
                            "Maybe.",
                        ],
                        "correct_index": 0,
                        "explanation_ru": "Уточнение.",
                        "category": "grammar",
                    }
                },
            )
        )
    db_session.flush()
    return user


def right(session, user, step, now=NOW):
    return answer_choice(
        session, user, step.run.id, step.index, step.question["correct_index"], now=now
    )


def lexical_step(session, user, now=NOW):
    step = start_stream(session, user, now=now)
    for _ in range(25):
        if step.question.get("lexical"):
            return step
        result = right(session, user, step, now)
        assert result.accepted and result.next_step
        step = result.next_step
    raise AssertionError("Lexical quota never received a slot")


def candidates(session, user, now=NOW, familiar=False, gate=False):
    pools = candidate_questions(
        session, user, now=now, repeat_familiar=familiar, plan=get_plan(user), gate=gate
    )
    return [q for pool in pools.values() for _, q in pool]


def test_real_stream_balances_three_disjoint_buckets_and_keeps_language(
    db_session, learner
):
    counts, sources, contexts = Counter(), Counter(), Counter()
    for index in range(60):
        now = NOW + timedelta(hours=30 * index)
        step = start_stream(db_session, learner, now=now)
        assert step.question is not None
        question = step.question
        counts[question["allocation_bucket"]] += 1
        sources[question["selection_source"]] += 1
        contexts[question["strand"]] += 1
        assert question["lexical_share"] == 30
        assert question["allocation_share"] == 30
        assert right(db_session, learner, step, now).accepted
        stop_stream(db_session, learner, now=now)
    assert counts == {"general": 18, "work": 24, "lexical": 18}
    assert sources["language"] >= 10 and sources["roadmap"] >= 28
    assert contexts["general"] >= 18 and contexts["work"] >= 24
    assert lexical_progress(db_session, learner, now=now)["introduced"] > 0


def test_bank_contract_rejects_invalid_references_and_bounds(lexicon):
    for mutate in (
        lambda d: d["entries"][0].update(module_ids=["missing"]),
        lambda d: d["entries"][0].update(meaning_en="x" * 2001),
        lambda d: d["entries"][0]["questions"][0].update(correct_index=True),
        lambda d: d["entries"][0]["questions"][1].update(variant_id="a"),
        lambda d: d["entries"][0].update(
            source_urls=["https://person:secret@localhost"]
        ),
        lambda d: d.update(version=True),
        lambda d: d["entries"][0].update(unknown="unsupported"),
        lambda d: d["entries"][0].update(function_id=[]),
        lambda d: d["entries"][0].update(stage={}),
    ):
        data = deepcopy(lexicon)
        mutate(data)
        with pytest.raises(ValueError):
            validate_lexicon(data)


def test_legacy_plan_has_no_lexical_slots(db_session, learner):
    preferences = deepcopy(learner.preferences_json)
    preferences["workplace_plan"].pop("lexical_share")
    learner.preferences_json = preferences
    db_session.flush()
    assert get_plan(learner)["lexical_share"] == 0
    for index in range(12):
        now = NOW + timedelta(hours=30 * index)
        step = start_stream(db_session, learner, now=now)
        assert "lexical" not in step.question
        assert step.question["lexical_share"] == 0
        right(db_session, learner, step, now)
        stop_stream(db_session, learner, now=now)


def test_resume_keeps_snapshot_and_rejects_foreign_duplicate_callbacks(
    db_session, learner
):
    step = lexical_step(db_session, learner)
    saved = deepcopy(step.question)
    stranger = User(telegram_user_id=-1)
    db_session.add(stranger)
    db_session.flush()
    assert not answer_choice(
        db_session, stranger, step.run.id, step.index, 0, now=NOW
    ).accepted
    update_plan(db_session, learner, "lexical_share", 0)
    resumed = start_stream(db_session, learner, now=NOW + timedelta(days=1))
    assert resumed.question == saved
    result = right(db_session, learner, resumed)
    assert result.accepted
    assert not right(db_session, learner, resumed).accepted
    assert result.attempt.feedback["lexical_share"] == 30
    assert result.next_step.question["lexical_share"] == 0
    assert lexical_progress(db_session, stranger, now=NOW)["introduced"] == 0


def test_sense_success_cooldown_familiar_and_spaced_recognition(
    db_session, learner, lexicon
):
    lexicon["entries"][:] = [lexicon["entries"][1]]
    step = lexical_step(db_session, learner)
    identifier = step.question["lexical"]["entry_id"]
    first_variant = step.question["lexical"]["variant_id"]
    result = right(db_session, learner, step)
    stop_stream(db_session, learner, now=NOW)
    assert not candidates(db_session, learner, NOW + timedelta(hours=23))
    familiar = candidates(db_session, learner, familiar=True)
    assert len(familiar) == 1 and familiar[0]["lexical"]["variant_id"] == first_variant
    later = NOW + timedelta(hours=25)
    reviews = candidates(db_session, learner, later)
    assert reviews and all(q["lexical_phase"] == "review" for q in reviews)
    second = lexical_step(db_session, learner, later)
    assert second.question["lexical"]["entry_id"] == identifier
    assert second.question["lexical"]["variant_id"] != first_variant
    assert right(db_session, learner, second, later).accepted
    progress = lexical_progress(db_session, learner, now=later)
    assert progress["recognized"] == 1 and progress["independent_writing"] == 0
    assert result.attempt.target_learning_item_ids == []


def test_familiar_answer_and_writing_do_not_add_lexical_evidence(
    db_session, learner, lexicon
):
    lexicon["entries"][:] = [lexicon["entries"][1]]
    original = lexical_step(db_session, learner)
    right(db_session, learner, original)
    stop_stream(db_session, learner, now=NOW)
    familiar = start_stream(db_session, learner, repeat_familiar=True, now=NOW)
    for _ in range(10):
        if familiar.question.get("lexical"):
            break
        familiar = right(db_session, learner, familiar).next_step
    assert (
        familiar.question["lexical"]["variant_id"]
        == original.question["lexical"]["variant_id"]
    )
    right(db_session, learner, familiar)
    bonus = start_lexical_bonus(
        db_session, learner, familiar.run.id, familiar.index, now=NOW
    )
    submit_bonus(
        db_session,
        learner,
        bonus.run.id,
        WRITING_A,
        {"status": "correct", "genuine_evaluation": True},
        now=NOW,
    )
    row = lexical_progress(db_session, learner, now=NOW)["entries"][0]
    assert row["recognition_attempts"] == 1
    assert row["writing_credited"] == 0 and not row["recognized"]


def test_real_selector_requires_existing_c1_language_gate(
    db_session, learner, lexicon, monkeypatch
):
    from fluentloop.roadmap_study import choose_question

    for entry in lexicon["entries"]:
        entry["stage"] = "c1_intro"
    update_plan(db_session, learner, "lexical_share", 60)
    held = choose_question(
        db_session,
        learner,
        now=NOW,
        repeat_familiar=False,
        bank_question=None,
        recent=set(),
    )
    assert not held.get("lexical")
    assert held["selection_fallback"] == "lexical_unavailable"
    monkeypatch.setattr(
        "fluentloop.roadmap_study.curriculum_progress",
        lambda *args, **kwargs: type("Progress", (), {"c1_unlocked": True})(),
    )
    admitted = choose_question(
        db_session,
        learner,
        now=NOW,
        repeat_familiar=False,
        bank_question=None,
        recent=set(),
    )
    assert admitted["lexical_entry"]["stage"] == "c1_intro"


def test_model_rewrites_and_answer_options_cannot_be_original_writing(
    db_session, learner
):
    step = lexical_step(db_session, learner)
    right(db_session, learner, step)
    bonus = start_lexical_bonus(db_session, learner, step.run.id, step.index, now=NOW)
    copied = bonus.question["source_options"][0]
    assert not lexical_feedback_metadata(db_session, learner, bonus.question, copied)[
        "independent_production"
    ]
    rewrite = "I followed up on my neighbour's parcel with the local post office."
    submit_bonus(
        db_session,
        learner,
        bonus.run.id,
        WRITING_A,
        {"status": "incorrect", "genuine_evaluation": True, "natural_answer": rewrite},
        now=NOW,
    )
    assert not lexical_feedback_metadata(db_session, learner, bonus.question, rewrite)[
        "independent_production"
    ]


def test_failed_sense_needs_five_other_normal_answers(db_session, learner, lexicon):
    lexicon["entries"][:] = [lexicon["entries"][1]]
    step = lexical_step(db_session, learner)
    result = answer_choice(db_session, learner, step.run.id, step.index, None, now=NOW)
    assert result.accepted
    step = result.next_step
    for _ in range(5):
        assert not candidates(db_session, learner)
        result = right(db_session, learner, step)
        assert result.accepted and result.next_step
        step = result.next_step
    assert candidates(db_session, learner)


def test_new_and_due_review_rotate_and_focus_pause_c1_are_respected(
    db_session, learner, lexicon
):
    step = lexical_step(db_session, learner)
    first = step.question["lexical"]["entry_id"]
    right(db_session, learner, step)
    stop_stream(db_session, learner, now=NOW)
    later = NOW + timedelta(hours=25)
    second = lexical_step(db_session, learner, later)
    assert second.question["lexical"]["entry_id"] == first
    assert second.question["lexical_phase"] == "review"
    right(db_session, learner, second, later)
    stop_stream(db_session, learner, now=later)
    third = lexical_step(db_session, learner, later + timedelta(hours=25))
    assert third.question["lexical_phase"] == "new"
    assert third.question["lexical"]["entry_id"] != first
    entry = lexicon["entries"][1]
    entry["stage"] = "c1_intro"
    assert entry["id"] not in {
        q["lexical"]["entry_id"] for q in candidates(db_session, learner)
    }
    assert entry["id"] in {
        q["lexical"]["entry_id"] for q in candidates(db_session, learner, gate=True)
    }
    update_plan(db_session, learner, "focus", entry["module_ids"][0])
    update_plan(db_session, learner, "pause", entry["module_ids"][0])
    assert entry["id"] not in {
        q["lexical"]["entry_id"] for q in candidates(db_session, learner, gate=True)
    }


def test_lexical_writing_requires_target_originality_genuine_check_and_spacing(
    db_session, learner, lexicon
):
    lexicon["entries"][:] = [lexicon["entries"][1]]
    step = lexical_step(db_session, learner)
    right(db_session, learner, step)
    stop_stream(db_session, learner, now=NOW)
    bonus = start_bonus(db_session, learner, step.run.id, now=NOW)
    assert bonus.question["lexical"]["role"] == "production"
    example = bonus.question["source_example"]
    assert not lexical_feedback_metadata(db_session, learner, bonus.question, example)[
        "independent_production"
    ]
    assert not lexical_feedback_metadata(
        db_session,
        learner,
        bonus.question,
        "I am discussing our plans for the next year.",
    )["target_present"]
    assert lexical_feedback_metadata(db_session, learner, bonus.question, WRITING_A)[
        "target_present"
    ]
    first = submit_bonus(
        db_session,
        learner,
        bonus.run.id,
        WRITING_A,
        {"status": "correct", "genuine_evaluation": True},
        now=NOW,
    )
    assert first.attempt.feedback["independent_production"]
    assert not start_lexical_bonus(
        db_session, learner, step.run.id, step.index, now=NOW
    ).question
    later = NOW + timedelta(hours=25)
    second = lexical_step(db_session, learner, later)
    right(db_session, learner, second, later)
    bonus = start_lexical_bonus(
        db_session, learner, second.run.id, second.index, now=later
    )
    assert bonus.question["lexical"]["production_variant_id"] == "b"
    assert not lexical_feedback_metadata(
        db_session, learner, bonus.question, WRITING_A, now=later
    )["independent_production"]
    checked = submit_bonus(
        db_session,
        learner,
        bonus.run.id,
        WRITING_B,
        {"status": "correct", "genuine_evaluation": True},
        now=later,
    )
    assert checked.attempt.status == "correct"
    assert lexical_progress(db_session, learner, now=later)["independent_writing"] == 1
    assert db_session.scalar(select(func.count(LearningItem.id))) == 20
    stop_stream(db_session, learner, now=later)
    third = lexical_step(db_session, learner, later + timedelta(hours=25))
    right(db_session, learner, third, later + timedelta(hours=25))
    bonus = start_lexical_bonus(
        db_session, learner, third.run.id, third.index, now=later + timedelta(hours=25)
    )
    fallback = submit_bonus(
        db_session,
        learner,
        bonus.run.id,
        "My colleague followed up on the invoice before travelling.",
        {"status": "correct", "genuine_evaluation": False},
        now=later + timedelta(hours=25),
    )
    assert fallback.attempt.status == "unchecked"


def test_quarantine_is_per_user_and_empty_pool_reports_fallback(
    db_session, learner, lexicon
):
    lexicon["entries"][:] = [lexicon["entries"][1]]
    step = lexical_step(db_session, learner)
    right(db_session, learner, step)
    stranger = User(telegram_user_id=-1)
    db_session.add(stranger)
    db_session.flush()
    save_plan(db_session, stranger, default_plan())
    assert not answered_lexical_question(db_session, stranger, step.run.id, step.index)
    assert not report_lexical_issue(db_session, stranger, step.run.id, step.index)
    assert report_lexical_issue(db_session, learner, step.run.id, step.index)
    assert not report_lexical_issue(db_session, learner, step.run.id, step.index)
    assert not candidates(db_session, learner, NOW + timedelta(days=2))
    assert candidates(db_session, stranger, NOW + timedelta(days=2))
    stop_stream(db_session, learner, now=NOW)
    fallbacks = []
    for index in range(5):
        now = NOW + timedelta(hours=30 * index)
        question = start_stream(db_session, learner, now=now)
        fallbacks.append(question.question.get("selection_fallback"))
        right(db_session, learner, question, now)
        stop_stream(db_session, learner, now=now)
    assert "lexical_unavailable" in fallbacks


def test_future_other_user_familiar_and_previous_cohort_do_not_change_allocation(
    db_session, learner
):
    from fluentloop.roadmap_study import choose_question

    baseline = choose_question(
        db_session,
        learner,
        now=NOW,
        repeat_familiar=False,
        bank_question=None,
        recent=set(),
    )
    run = PracticeSession(
        user_id=learner.id,
        target_date_local=NOW.date(),
        started_at=NOW,
        status="completed",
        exercises=[],
    )
    db_session.add(run)
    db_session.flush()
    stranger = User(telegram_user_id=-1)
    db_session.add(stranger)
    db_session.flush()
    foreign_run = PracticeSession(
        user_id=stranger.id,
        target_date_local=NOW.date(),
        started_at=NOW,
        status="completed",
        exercises=[],
    )
    db_session.add(foreign_run)
    db_session.flush()
    db_session.add(
        PracticeAttempt(
            practice_session_id=foreign_run.id,
            exercise_index=0,
            exercise_type="simple_choice",
            target_learning_item_ids=[],
            prompt="Another learner's allocation evidence",
            user_answer="Okay",
            status="correct",
            created_at=NOW,
            feedback={
                "selection_mode": "normal",
                "allocation_share": 30,
                "lexical_share": 30,
                "allocation_bucket": "work",
                "strand": "work",
            },
        )
    )
    for selection_mode, share, stamp in (
        ("familiar", 30, NOW),
        ("normal", 0, NOW),
        ("normal", 30, NOW + timedelta(days=10)),
    ):
        db_session.add(
            PracticeAttempt(
                practice_session_id=run.id,
                exercise_index=1,
                exercise_type="simple_choice",
                target_learning_item_ids=[],
                prompt="Ignored allocation evidence",
                user_answer="Okay",
                status="correct",
                created_at=stamp,
                feedback={
                    "selection_mode": selection_mode,
                    "allocation_share": 30,
                    "lexical_share": share,
                    "allocation_bucket": "work",
                    "strand": "work",
                },
            )
        )
    db_session.flush()
    actual = choose_question(
        db_session,
        learner,
        now=NOW,
        repeat_familiar=False,
        bank_question=None,
        recent=set(),
    )
    assert actual["allocation_bucket"] == baseline["allocation_bucket"]
    assert actual["fingerprint"] == baseline["fingerprint"]


@pytest.mark.parametrize(
    ("answer", "target", "present"),
    [
        ("We rolled it out to three small offices last month.", "roll out", True),
        ("I did not roll the new service out until Friday.", "roll out", True),
        ("They pushed back the review until next week.", "push something back", True),
        ("They pushed the review back until next week.", "push something back", True),
        (
            "We brought two new colleagues up to speed on the issue.",
            "bring someone up to speed",
            True,
        ),
        ("I am taking stock of our options before the move.", "take stock of", True),
        ("We took stocks of the empty warehouse.", "take stock of", False),
        ("Rolls of fabric have run out in the warehouse.", "roll out", False),
        ("They pushed back the review until next week.", "push back on", False),
        (
            "Our adviser raised concerns about the proposed timeline.",
            "raise a concern",
            True,
        ),
        ("The delivery team built on the lessons from that outage.", "build on", True),
        ("We stuck to the agreed scope despite the late request.", "stick to", True),
        (
            "Our designer broke down the prototype into smaller steps.",
            "break down",
            True,
        ),
        (
            "The workshop uncovered three pain points in the old process.",
            "pain point",
            True,
        ),
        ("That decision involved several trade-offs for our team.", "trade-off", True),
        ("What do you mean by priority support?", "by ... mean", True),
        ("I have two audits on my plate this week.", "have ... on one's plate", True),
        ("Please spell it out before we sign anything.", "spell out", True),
        ("The organiser spelt it out before the rehearsal.", "spell out", True),
        ("We can fit a visit in before our evening train.", "fit in", True),
        ("We weighed them up before choosing the cheaper route.", "weigh up", True),
        ("The independent survey bears it out.", "bear out", True),
        ("The experiment bore it out after several trials.", "bear out", True),
        ("The comparison has borne it out over the past year.", "bear out", True),
        ("We can meet you halfway on the revised delivery date.", "meet halfway", True),
        ("They met our supplier halfway during the negotiation.", "meet halfway", True),
        (
            "We need to take into account the constraints.",
            "take ... into account",
            True,
        ),
        ("We took the constraints into account.", "take ... into account", True),
        ("She spelt the word correctly during her outing.", "spell out", False),
        ("The visit was a good fit for the conference.", "fit in", False),
        ("They weighed the box before walking upstairs.", "weigh up", False),
        ("They bore a tunnel without checking the exits.", "bear out", False),
        (
            "We met last Tuesday and are halfway through the project.",
            "meet halfway",
            False,
        ),
        ("We took the account into consideration.", "take ... into account", False),
    ],
)
def test_target_matching_accepts_natural_forms_and_keeps_the_target(
    answer, target, present
):
    assert _target_present(answer, target) is present
