from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from fluentloop.db.models import LearningItem, PracticeAttempt, PracticeSession, User
from fluentloop.db.session import make_engine, make_session_factory
from fluentloop.llm.tasks import LLMTask
from fluentloop.question_quality import (
    QuestionReview,
    VariantDraft,
    report_question_issue,
    run_question_maintenance,
    validate_variant,
)
from fluentloop.simple_learning import CHOICE, question_fingerprint, start_stream
from fluentloop.users import ensure_user

NOW = datetime(2026, 10, 4, 8, tzinfo=UTC)
SOURCE = {
    "prompt": "The outage ended yesterday. Which sentence reports its duration?",
    "options": ["It lasted two hours.", "It has lasted two hours."],
    "correct_index": 0,
    "explanation_ru": "Завершённый период в прошлом требует Past Simple.",
    "production_prompt": "Describe a finished investigation using the past simple.",
    "category": "grammar",
    "level": "B2",
    "adaptive": {
        "version": 1,
        "topic_id": "aspect",
        "stage": "b2",
        "role": "practice",
        "variant_id": "test-original",
    },
}
DRAFT = VariantDraft(
    prompt="During last week's audit, the security team ___ three unused accounts.",
    options=["disabled", "has disabled", "will disable"],
    correct_index=0,
    explanation_ru="Аудит завершился на прошлой неделе: нужен Past Simple.",
    production_prompt="Describe a completed security improvement from last month.",
)
GOOD_REVIEW = QuestionReview(
    correct_index=0,
    unambiguous=True,
    target_aligned=True,
    level_appropriate=True,
    explanation_correct=True,
    novel_context=True,
)


class Gateway:
    def __init__(self, review=GOOD_REVIEW, *, fail=False):
        self.review = review
        self.fail = fail
        self.calls = []

    def run_json(self, task, payload, schema, **kwargs):
        self.calls.append((task, payload))
        if self.fail:
            raise RuntimeError("unavailable")
        return DRAFT if task == LLMTask.QUESTION_VARIANT else self.review


def _setup(tmp_path, settings, monkeypatch, *, legacy=False):
    monkeypatch.setattr(
        "fluentloop.adaptive_learning.generation_need", lambda *a, **k: None
    )
    factory = make_session_factory(make_engine(f"sqlite:///{tmp_path / 'bank.sqlite'}"))
    with factory.begin() as session:
        user = ensure_user(session, 123456789, settings)
        user.preferences_json = {
            "learning": {"mode": "simple", "adaptive_auto_expand": True}
        }
        question = deepcopy(SOURCE)
        if legacy:
            question.pop("adaptive")
        question["fingerprint"] = question_fingerprint(question)
        item = LearningItem(
            user_id=user.id,
            type="grammar_rule",
            text="Approved past aspect",
            metadata_json={
                "simple_question": question,
                "lang_lessons" if legacy else "adaptive_curriculum": {"version": 1},
            },
        )
        session.add(item)
        session.flush()
        run = PracticeSession(
            user_id=user.id,
            target_date_local=NOW.date(),
            status="completed",
            exercises=[question],
        )
        session.add(run)
        session.flush()
        session.add(
            PracticeAttempt(
                practice_session_id=run.id,
                exercise_index=0,
                exercise_type=CHOICE,
                target_learning_item_ids=[item.id],
                prompt=question["prompt"],
                user_answer="It lasted two hours.",
                status="correct",
                feedback={"fingerprint": question["fingerprint"], "question": question},
            )
        )
        session.flush()
        assert report_question_issue(session, user, run.id, 0)
        return factory, user.id, item.id, run.id


def test_report_is_owned_idempotent_and_excludes_original(
    tmp_path, settings, monkeypatch
):
    factory, uid, iid, rid = _setup(tmp_path, settings, monkeypatch)
    with factory.begin() as session:
        user = session.get(User, uid)
        assert not report_question_issue(session, user, rid, 0)
        assert not report_question_issue(session, user, rid, 1)
        other = User(telegram_user_id=123456780)
        session.add(other)
        session.flush()
        assert not report_question_issue(session, other, rid, 0)
        assert start_stream(session, user, now=NOW).question is None
        original = session.get(LearningItem, iid).metadata_json["simple_question"]
        assert original["options"] == SOURCE["options"]
        assert original["quality_status"] == "quarantined"
        assert session.scalar(select(PracticeAttempt)).status == "correct"


def test_verified_variant_publishes_once_per_day_without_new_item(
    tmp_path, settings, monkeypatch
):
    factory, uid, iid, _ = _setup(tmp_path, settings, monkeypatch)
    gateway = Gateway()
    result = run_question_maintenance(settings, factory, now=NOW, gateway=gateway)
    assert (result.attempted, result.published, result.rejected) == (1, 1, 0)
    again = run_question_maintenance(settings, factory, now=NOW, gateway=gateway)
    assert again.attempted == 0
    assert len(gateway.calls) == 2
    review_payload = gateway.calls[-1][1]
    assert "correct_index" not in review_payload
    assert "user_answer" not in repr(gateway.calls)
    with factory() as session:
        item = session.get(LearningItem, iid)
        questions = item.metadata_json["simple_question_variants"]
        assert len(questions) == 1
        assert questions[0]["adaptive"]["topic_id"] == "aspect"
        assert questions[0]["quality_status"] == "verified"
        assert len(list(session.scalars(select(LearningItem)))) == 1
        assert (
            start_stream(session, session.get(User, uid), now=NOW).question["prompt"]
            == DRAFT.prompt
        )


@pytest.mark.parametrize(
    "review",
    [
        QuestionReview(),
        GOOD_REVIEW.model_copy(update={"correct_index": 1}),
        GOOD_REVIEW.model_copy(update={"novel_context": False}),
    ],
)
def test_review_failure_never_publishes(tmp_path, settings, monkeypatch, review):
    factory, _, iid, _ = _setup(tmp_path, settings, monkeypatch)
    result = run_question_maintenance(
        settings, factory, now=NOW, gateway=Gateway(review)
    )
    assert result.rejected == 1 and result.published == 0
    with factory() as session:
        assert not session.get(LearningItem, iid).metadata_json.get(
            "simple_question_variants"
        )


def test_unavailable_provider_consumes_claim_without_retries_or_original_changes(
    tmp_path, settings, monkeypatch
):
    factory, _, iid, _ = _setup(tmp_path, settings, monkeypatch)
    gateway = Gateway(fail=True)
    assert (
        run_question_maintenance(settings, factory, now=NOW, gateway=gateway).rejected
        == 1
    )
    assert (
        run_question_maintenance(settings, factory, now=NOW, gateway=gateway).attempted
        == 0
    )
    with factory() as session:
        assert (
            session.get(LearningItem, iid).metadata_json["simple_question"]["prompt"]
            == SOURCE["prompt"]
        )


def test_parallel_workers_claim_one_daily_batch(tmp_path, settings, monkeypatch):
    factory, _, _, _ = _setup(tmp_path, settings, monkeypatch)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(
            pool.map(
                lambda _: run_question_maintenance(
                    settings, factory, now=NOW, gateway=Gateway()
                ),
                range(2),
            )
        )
    assert sum(result.attempted for result in results) == 1
    assert sum(result.published for result in results) == 1


def test_legacy_repair_does_not_invent_adaptive_mastery(
    tmp_path, settings, monkeypatch
):
    factory, _, iid, _ = _setup(tmp_path, settings, monkeypatch, legacy=True)
    assert (
        run_question_maintenance(
            settings, factory, now=NOW, gateway=Gateway()
        ).published
        == 1
    )
    with factory() as session:
        variant = session.get(LearningItem, iid).metadata_json[
            "simple_question_variants"
        ][0]
        assert "adaptive" not in variant


def test_optout_and_stub_do_no_network_work(tmp_path, settings, monkeypatch):
    factory, uid, _, _ = _setup(tmp_path, settings, monkeypatch)
    assert run_question_maintenance(settings, factory, now=NOW).attempted == 0
    with factory.begin() as session:
        session.get(User, uid).preferences_json = {"learning": {"mode": "simple"}}
    gateway = Gateway()
    assert (
        run_question_maintenance(settings, factory, now=NOW, gateway=gateway).attempted
        == 0
    )
    assert not gateway.calls


def test_validation_rejects_key_language_and_cosmetic_variants():
    for update in (
        {"correct_index": 10},
        {"options": ["disabled", "Disabled!", "will disable"]},
        {"prompt": "Выберите правильный ответ для аудита"},
        {"explanation_ru": "Use the past simple for a finished time."},
    ):
        with pytest.raises(ValueError):
            validate_variant(DRAFT.model_copy(update=update), SOURCE, [])
    with pytest.raises(ValueError, match="Near-duplicate"):
        validate_variant(
            DRAFT, SOURCE, [{**SOURCE, "prompt": DRAFT.prompt.replace("three", "four")}]
        )


def test_private_card_context_never_enters_generation_payload(
    tmp_path, settings, monkeypatch
):
    factory, uid, _, _ = _setup(tmp_path, settings, monkeypatch)
    with factory.begin() as session:
        session.add(
            LearningItem(
                user_id=uid,
                type="expression",
                text="private",
                metadata_json={
                    "simple_question": {**SOURCE, "prompt": "PRIVATE_LESSON_CONTEXT"}
                },
            )
        )
    gateway = Gateway()
    run_question_maintenance(settings, factory, now=NOW, gateway=gateway)
    assert "PRIVATE_LESSON_CONTEXT" not in repr(gateway.calls)


def test_daily_claim_uses_profile_timezone(tmp_path, settings, monkeypatch):
    factory, uid, _, _ = _setup(tmp_path, settings, monkeypatch)
    with factory.begin() as session:
        session.get(User, uid).timezone = "Europe/Moscow"
    first = datetime(2026, 10, 4, 20, 55, tzinfo=UTC)
    run_question_maintenance(settings, factory, now=first, gateway=Gateway(fail=True))
    assert (
        run_question_maintenance(
            settings, factory, now=first + timedelta(minutes=10), gateway=Gateway()
        ).attempted
        == 1
    )


def test_review_routes_to_planner(settings):
    from fluentloop.llm.router import task_profile

    cfg = replace(
        settings, deepseek_fast_model="fast", deepseek_planner_model="reviewer"
    )
    assert task_profile(LLMTask.QUESTION_VARIANT, cfg).model == "fast"
    assert task_profile(LLMTask.QUESTION_REVIEW, cfg).model == "reviewer"


def test_item_variant_limit_stops_more_generation(tmp_path, settings, monkeypatch):
    factory, _, iid, _ = _setup(tmp_path, settings, monkeypatch)
    with factory.begin() as session:
        item = session.get(LearningItem, iid)
        metadata = deepcopy(item.metadata_json)
        metadata["simple_question_variants"] = [
            {**SOURCE, "prompt": f"Previously reviewed audit situation {index}"}
            for index in range(12)
        ]
        item.metadata_json = metadata
    gateway = Gateway()
    assert (
        run_question_maintenance(settings, factory, now=NOW, gateway=gateway).attempted
        == 0
    )
    assert not gateway.calls


def test_error_rate_requests_review_without_treating_error_as_invalid_question(
    tmp_path, settings, monkeypatch
):
    factory, uid, iid, rid = _setup(tmp_path, settings, monkeypatch)
    with factory.begin() as session:
        item = session.get(LearningItem, iid)
        item.metadata_json = {
            "adaptive_curriculum": {"version": 1},
            "simple_question": deepcopy(SOURCE),
        }
        for index in range(1, 5):
            session.add(
                PracticeAttempt(
                    practice_session_id=rid,
                    exercise_index=index,
                    exercise_type=CHOICE,
                    target_learning_item_ids=[iid],
                    prompt=SOURCE["prompt"],
                    user_answer="synthetic answer",
                    status="incorrect" if index < 4 else "correct",
                    feedback={"fingerprint": question_fingerprint(SOURCE)},
                )
            )
    gateway = Gateway()
    assert (
        run_question_maintenance(settings, factory, now=NOW, gateway=gateway).published
        == 1
    )
    assert [task for task, _ in gateway.calls] == [
        LLMTask.QUESTION_REVIEW,
        LLMTask.QUESTION_VARIANT,
        LLMTask.QUESTION_REVIEW,
    ]
    with factory() as session:
        item = session.get(LearningItem, iid)
        assert (
            item.metadata_json["simple_question"].get("quality_status") != "quarantined"
        )
        assert (
            item.metadata_json["question_quality"][question_fingerprint(SOURCE)][
                "reviewed_answers"
            ]
            == 5
        )
