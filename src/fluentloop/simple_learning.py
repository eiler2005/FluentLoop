"""Persisted manual recognition streams and optional production (EPIC-26)."""

from __future__ import annotations

import hashlib
import json
import random
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from fluentloop.ai.schemas import AnswerFeedback
from fluentloop.db.models import (
    LearningItem,
    PracticeAttempt,
    PracticeSession,
    ReviewState,
    User,
)
from fluentloop.feedback import apply_feedback
from fluentloop.quiz import build_quiz_spec
from fluentloop.srs import record_result
from fluentloop.vocab_loop import english_definition, local_date
from fluentloop.word_cards import stored_russian, usable_example

ACTIVE = "simple_active"
BONUS = "simple_bonus"
CHOICE = "simple_choice"
PRODUCTION = "simple_production"
SUCCESS_COOLDOWN = timedelta(hours=24)
RECENT_COUNT = 5
PHRASE_TYPES = {"word", "expression", "chunk"}


@dataclass(frozen=True)
class SimpleStep:
    run: PracticeSession | None
    question: dict | None
    index: int = 0
    exhausted: bool = False


@dataclass(frozen=True)
class SimpleSummary:
    run_id: int | None
    answered: int
    correct: int
    unknown: int = 0


@dataclass(frozen=True)
class SimpleAnswer:
    accepted: bool
    reason: str
    attempt: PracticeAttempt | None = None
    correct: bool | None = None
    next_step: SimpleStep | None = None
    summary: SimpleSummary | None = None


def _now(now: datetime | None) -> datetime:
    value = now or datetime.now(UTC)
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


@contextmanager
def _atomic_answer(session: Session) -> Iterator[None]:
    try:
        with session.begin_nested():
            yield
    except Exception:
        # A raw CAS update is invisible to ORM savepoint dirty tracking.
        session.expire_all()
        raise


def question_fingerprint(question: dict) -> str:
    """Identify content without depending on the displayed option ordering."""
    fingerprint = question.get("fingerprint")
    if isinstance(fingerprint, str) and fingerprint:
        return fingerprint
    options = list(question.get("options") or [])
    correct = int(question.get("correct_index", -1))
    content = {
        "prompt": str(question.get("prompt") or question.get("question") or "").strip(),
        "options": sorted(str(option).strip() for option in options),
        "answer": str(options[correct]).strip() if 0 <= correct < len(options) else "",
    }
    return hashlib.sha256(
        json.dumps(content, ensure_ascii=False, sort_keys=True).encode()
    ).hexdigest()


def _lock_user(session: Session, user: User) -> None:
    # SQLite's writer lock serializes concurrent starts before the active lookup.
    session.execute(update(User).where(User.id == user.id).values(id=User.id))


def _owned_run(session: Session, user: User, run_id: int) -> PracticeSession | None:
    return session.scalar(
        select(PracticeSession)
        .where(PracticeSession.id == run_id, PracticeSession.user_id == user.id)
        .execution_options(populate_existing=True)
    )


def _snapshot(run: PracticeSession) -> dict | None:
    return dict(run.exercises[0]) if run.exercises else None


def get_active_stream(session: Session, user: User) -> PracticeSession | None:
    return session.scalar(
        select(PracticeSession)
        .where(PracticeSession.user_id == user.id, PracticeSession.status == ACTIVE)
        .order_by(PracticeSession.id.desc())
        .execution_options(populate_existing=True)
    )


def get_active_bonus(session: Session, user: User) -> PracticeSession | None:
    return session.scalar(
        select(PracticeSession)
        .where(PracticeSession.user_id == user.id, PracticeSession.status == BONUS)
        .order_by(PracticeSession.id.desc())
        .execution_options(populate_existing=True)
    )


def _history(session: Session, user: User) -> list[PracticeAttempt]:
    return list(
        session.scalars(
            select(PracticeAttempt)
            .join(
                PracticeSession,
                PracticeSession.id == PracticeAttempt.practice_session_id,
            )
            .where(
                PracticeSession.user_id == user.id,
                PracticeAttempt.exercise_type == CHOICE,
            )
            .order_by(PracticeAttempt.id)
        )
    )


def _recent_displayed(
    session: Session, user: User, history: list[PracticeAttempt]
) -> set[str]:
    displayed: dict[tuple[str, str], tuple[str, int, int, str]] = {}
    for attempt in history:
        feedback = attempt.feedback or {}
        fingerprint = feedback.get("fingerprint")
        if fingerprint:
            stamp = str(
                feedback.get("displayed_at") or _now(attempt.created_at).isoformat()
            )
            displayed[(stamp, str(fingerprint))] = (
                stamp,
                attempt.practice_session_id,
                attempt.exercise_index,
                str(fingerprint),
            )
    # Completed stops keep their unanswered snapshot: these also count as seen.
    for run in session.scalars(
        select(PracticeSession).where(PracticeSession.user_id == user.id)
    ):
        question = _snapshot(run)
        if question and question.get("exercise_type") == CHOICE:
            meta = question.get("metadata") or {}
            fingerprint = str(question.get("fingerprint") or "")
            stamp = str(meta.get("displayed_at") or _now(run.started_at).isoformat())
            if fingerprint:
                displayed[(stamp, fingerprint)] = (
                    stamp,
                    run.id,
                    int(meta.get("stream_index", 0)),
                    fingerprint,
                )
    ordered = sorted(displayed.values(), reverse=True)
    return {entry[-1] for entry in ordered[:RECENT_COUNT]}


def _question_for_item(session: Session, user: User, item: LearningItem) -> dict | None:
    raw = (item.metadata_json or {}).get("simple_question")
    if isinstance(raw, dict):
        question = dict(raw)
    elif item.type in PHRASE_TYPES:
        if (
            not english_definition(item)
            or not stored_russian(item)
            or not usable_example(item)
        ):
            return None
        spec = build_quiz_spec(session, user, item, allow_llm=False)
        if spec is None:
            return None
        question = {
            "prompt": spec.question,
            "options": list(spec.options),
            "correct_index": spec.correct_index,
            "explanation_ru": stored_russian(item),
            "category": "phrase",
        }
    else:
        return None
    options = question.get("options")
    correct = question.get("correct_index")
    if (
        not isinstance(options, list)
        or len(options) < 2
        or not all(isinstance(option, str) and option.strip() for option in options)
        or len(set(options)) != len(options)
        or not isinstance(correct, int)
        or not 0 <= correct < len(options)
        or not str(question.get("prompt") or "").strip()
    ):
        return None
    question["options"] = list(options)
    question["category"] = (
        "grammar" if question.get("category") == "grammar" else "phrase"
    )
    question["fingerprint"] = question_fingerprint(question)
    question["exercise_type"] = CHOICE
    question["target_learning_item_ids"] = [item.id]
    question["expected_answer"] = options[correct]
    return question


def _choose_question(
    session: Session,
    user: User,
    *,
    now: datetime,
    repeat_familiar: bool,
    previous_category: str | None = None,
) -> dict | None:
    history = _history(session, user)
    if previous_category is None:
        latest = session.scalar(
            select(PracticeSession)
            .where(
                PracticeSession.user_id == user.id,
                func.json_extract(PracticeSession.exercises, "$[0].exercise_type")
                == CHOICE,
            )
            .order_by(PracticeSession.id.desc())
        )
        if latest is not None:
            previous_category = (_snapshot(latest) or {}).get("category")
    recent = _recent_displayed(session, user, history)
    by_fingerprint: dict[str, list[tuple[int, PracticeAttempt]]] = {}
    for position, attempt in enumerate(history):
        fingerprint = (attempt.feedback or {}).get("fingerprint")
        if fingerprint:
            by_fingerprint.setdefault(str(fingerprint), []).append((position, attempt))
    states = {
        state.learning_item_id: state
        for state in session.scalars(
            select(ReviewState)
            .join(LearningItem)
            .where(LearningItem.user_id == user.id)
        )
    }
    candidates: dict[str, list[tuple[tuple, dict]]] = {"phrase": [], "grammar": []}
    for item in session.scalars(
        select(LearningItem)
        .where(
            LearningItem.user_id == user.id,
            LearningItem.status == "active",
            LearningItem.is_template.is_(False),
        )
        .order_by(LearningItem.id)
    ):
        question = _question_for_item(session, user, item)
        if question is None:
            continue
        fingerprint = question["fingerprint"]
        records = by_fingerprint.get(fingerprint, [])
        state = states.get(item.id)
        due_at = _now(state.due_at) if state is not None else now
        eligible_records = [
            record
            for record in records
            if (record[1].feedback or {}).get("selection_mode") != "familiar"
            or record[1].status != "correct"
            or (record[1].feedback or {}).get("srs_applied")
        ]
        last = eligible_records[-1][1] if eligible_records else None
        successes = [
            attempt
            for _, attempt in records
            if attempt.status == "correct"
            and (
                (attempt.feedback or {}).get("selection_mode") != "familiar"
                or (attempt.feedback or {}).get("srs_applied")
            )
        ]
        if not repeat_familiar and last is not None and last.status != "correct":
            last_position = eligible_records[-1][0]
            others = sum(
                (attempt.feedback or {}).get("fingerprint") != fingerprint
                for attempt in history[last_position + 1 :]
            )
            if others < RECENT_COUNT or due_at > now:
                continue
        if repeat_familiar:
            # This button promises familiar practice, never a covert new-item fill.
            if not records:
                continue
        else:
            if last is not None and last.status == "correct":
                deadline = due_at
                if successes:
                    deadline = max(
                        deadline, _now(successes[-1].created_at) + SUCCESS_COOLDOWN
                    )
                if deadline > now:
                    continue
        if records:
            priority = 0 if due_at <= now else 1
            weak = last is not None and last.status != "correct"
            last_seen = _now(records[-1][1].created_at)
        else:
            priority, weak, last_seen = 2, False, datetime.min.replace(tzinfo=UTC)
        rank = (
            fingerprint in recent,
            priority,
            not weak,
            -item.priority,
            last_seen,
            item.id,
        )
        candidates[question["category"]].append((rank, question))
    preferred = "grammar" if previous_category == "phrase" else "phrase"
    for category in (preferred, "phrase" if preferred == "grammar" else "grammar"):
        if candidates[category]:
            return min(candidates[category], key=lambda candidate: candidate[0])[1]
    return None


def _saved_question(
    question: dict, *, run_id: int, index: int, now: datetime, repeat_familiar: bool
) -> dict:
    question = dict(question)
    options = list(question["options"])
    expected = options[question["correct_index"]]
    random.Random(f"{run_id}:{index}:{question['fingerprint']}").shuffle(options)
    question["options"] = options
    question["correct_index"] = options.index(expected)
    question["metadata"] = {
        "mode": "simple",
        "stream_index": index,
        "displayed_at": now.isoformat(),
        "selection_mode": "familiar" if repeat_familiar else "normal",
    }
    return question


def start_stream(
    session: Session,
    user: User,
    *,
    repeat_familiar: bool = False,
    now: datetime | None = None,
) -> SimpleStep:
    current = _now(now)
    _lock_user(session, user)
    active = get_active_stream(session, user)
    if active is not None:
        question = _snapshot(active)
        return SimpleStep(
            active,
            question,
            int((question or {}).get("metadata", {}).get("stream_index", 0)),
        )
    question = _choose_question(
        session, user, now=current, repeat_familiar=repeat_familiar
    )
    if question is None:
        return SimpleStep(None, None, exhausted=True)
    run = PracticeSession(
        user_id=user.id,
        target_date_local=local_date(user, now=current),
        started_at=current,
        status=ACTIVE,
        exercises=[],
    )
    session.add(run)
    session.flush()
    run.exercises = [
        _saved_question(
            question,
            run_id=run.id,
            index=0,
            now=current,
            repeat_familiar=repeat_familiar,
        )
    ]
    session.flush()
    return SimpleStep(run, _snapshot(run))


def summarize_stream(session: Session, user: User, run_id: int | None) -> SimpleSummary:
    if run_id is None or _owned_run(session, user, run_id) is None:
        return SimpleSummary(None, 0, 0)
    attempts = list(
        session.scalars(
            select(PracticeAttempt).where(
                PracticeAttempt.practice_session_id == run_id,
                PracticeAttempt.exercise_type == CHOICE,
            )
        )
    )
    return SimpleSummary(
        run_id,
        len(attempts),
        sum(attempt.status == "correct" for attempt in attempts),
        sum(bool((attempt.feedback or {}).get("unknown")) for attempt in attempts),
    )


def _claim(
    session: Session, user: User, run: PracticeSession, index: int, *, status: str
) -> bool:
    marker = dict(run.exercises[0])
    marker["metadata"] = {**(marker.get("metadata") or {}), "stream_index": index + 1}
    result = session.execute(
        update(PracticeSession)
        .where(
            PracticeSession.id == run.id,
            PracticeSession.user_id == user.id,
            PracticeSession.status == status,
            func.json_extract(PracticeSession.exercises, "$[0].metadata.stream_index")
            == index,
        )
        .values(exercises=[marker])
        .execution_options(synchronize_session=False)
    )
    if result.rowcount != 1:
        session.expire(run)
        return False
    session.expire(run)
    return True


def answer_choice(
    session: Session,
    user: User,
    run_id: int,
    index: int,
    choice: int | None,
    *,
    now: datetime | None = None,
) -> SimpleAnswer:
    current = _now(now)
    run = _owned_run(session, user, run_id)
    if run is None:
        return SimpleAnswer(False, "unavailable")
    question = _snapshot(run)
    if run.status != ACTIVE or question is None:
        return SimpleAnswer(
            False, "finished", summary=summarize_stream(session, user, run_id)
        )
    if (question.get("metadata") or {}).get("stream_index") != index:
        return SimpleAnswer(False, "stale")
    options = question["options"]
    if choice is not None and (
        not isinstance(choice, int) or not 0 <= choice < len(options)
    ):
        return SimpleAnswer(False, "invalid_choice")
    with _atomic_answer(session):
        if not _claim(session, user, run, index, status=ACTIVE):
            return SimpleAnswer(False, "stale")
        correct = choice == question["correct_index"]
        familiar = (question.get("metadata") or {}).get("selection_mode") == "familiar"
        applied = False
        prior_history = _history(session, user)
        normal_successes = [
            attempt
            for attempt in prior_history
            if (attempt.feedback or {}).get("fingerprint") == question["fingerprint"]
            and attempt.status == "correct"
            and (
                (attempt.feedback or {}).get("selection_mode") != "familiar"
                or (attempt.feedback or {}).get("srs_applied")
            )
        ]
        familiar_early = (
            familiar
            and bool(normal_successes)
            and (_now(normal_successes[-1].created_at) + SUCCESS_COOLDOWN > current)
        )
        meaningful = [
            (position, attempt)
            for position, attempt in enumerate(prior_history)
            if (attempt.feedback or {}).get("fingerprint") == question["fingerprint"]
            and (
                (attempt.feedback or {}).get("selection_mode") != "familiar"
                or attempt.status != "correct"
                or (attempt.feedback or {}).get("srs_applied")
            )
        ]
        if familiar and meaningful and meaningful[-1][1].status != "correct":
            failure_position = meaningful[-1][0]
            other_answers = sum(
                (attempt.feedback or {}).get("fingerprint") != question["fingerprint"]
                for attempt in prior_history[failure_position + 1 :]
            )
            familiar_early = familiar_early or other_answers < RECENT_COUNT
        for item_id in question["target_learning_item_ids"]:
            item = session.scalar(
                select(LearningItem).where(
                    LearningItem.id == item_id,
                    LearningItem.user_id == user.id,
                    LearningItem.is_template.is_(False),
                    LearningItem.status == "active",
                )
            )
            if item is None:
                continue
            state = session.scalar(
                select(ReviewState).where(ReviewState.learning_item_id == item.id)
            )
            if not correct or (
                not familiar_early and (state is None or _now(state.due_at) <= current)
            ):
                record_result(
                    session, item.id, "Good" if correct else "Again", now=current
                )
                applied = True
        feedback = {
            "status": "correct" if correct else "incorrect",
            "answer_modality": "recognition",
            "fingerprint": question["fingerprint"],
            "category": question["category"],
            "selection_mode": "familiar" if familiar else "normal",
            "srs_applied": applied,
            "chosen_index": choice,
            "unknown": choice is None,
            "corrected_answer": options[question["correct_index"]],
            "explanation": question.get("explanation_ru", ""),
            "displayed_at": (question.get("metadata") or {}).get("displayed_at"),
            "question": question,
        }
        attempt = PracticeAttempt(
            practice_session_id=run.id,
            exercise_index=index,
            exercise_type=CHOICE,
            target_learning_item_ids=question["target_learning_item_ids"],
            prompt=question["prompt"],
            user_answer=options[choice] if choice is not None else "",
            status=feedback["status"],
            feedback=feedback,
            created_at=current,
        )
        session.add(attempt)
        session.flush()
        following = _choose_question(
            session,
            user,
            now=current,
            repeat_familiar=familiar,
            previous_category=question["category"],
        )
        if following is None:
            run.status = "completed"
            run.completed_at = current
            # Keep exactly the last displayed question, not the CAS marker.
            run.exercises = [question]
            session.flush()
            return SimpleAnswer(
                True,
                "exhausted",
                attempt,
                correct,
                summary=summarize_stream(session, user, run.id),
            )
        run.exercises = [
            _saved_question(
                following,
                run_id=run.id,
                index=index + 1,
                now=current,
                repeat_familiar=familiar,
            )
        ]
        session.flush()
        return SimpleAnswer(
            True,
            "answered",
            attempt,
            correct,
            SimpleStep(run, _snapshot(run), index + 1),
        )


def stop_stream(
    session: Session,
    user: User,
    *,
    run_id: int | None = None,
    now: datetime | None = None,
) -> SimpleSummary:
    _lock_user(session, user)
    run = (
        _owned_run(session, user, run_id)
        if run_id is not None
        else get_active_stream(session, user)
    )
    if run is None:
        return SimpleSummary(None, 0, 0)
    if run.status == ACTIVE:
        run.status = "completed"
        run.completed_at = _now(now)
        session.flush()
    return summarize_stream(session, user, run.id)


def start_bonus(
    session: Session,
    user: User,
    parent_run_id: int,
    *,
    now: datetime | None = None,
) -> SimpleStep:
    _lock_user(session, user)
    parent = _owned_run(session, user, parent_run_id)
    if parent is None or parent.status != "completed":
        return SimpleStep(None, None)
    parent_question = _snapshot(parent)
    if parent_question is None or parent_question.get("exercise_type") != CHOICE:
        return SimpleStep(None, None)
    for run in session.scalars(
        select(PracticeSession)
        .where(PracticeSession.user_id == user.id)
        .order_by(PracticeSession.id.desc())
    ):
        question = _snapshot(run)
        if (question or {}).get("metadata", {}).get(
            "parent_simple_session_id"
        ) == parent_run_id:
            return SimpleStep(run, question if run.status == BONUS else None)
    active = get_active_bonus(session, user)
    if active is not None:
        return SimpleStep(active, _snapshot(active))
    attempts = list(
        session.scalars(
            select(PracticeAttempt)
            .where(
                PracticeAttempt.practice_session_id == parent.id,
                PracticeAttempt.exercise_type == CHOICE,
            )
            .order_by(PracticeAttempt.id.desc())
        )
    )
    question = (
        (attempts[0].feedback or {}).get("question", parent_question)
        if attempts
        else parent_question
    )
    example = question["options"][question["correct_index"]]
    item = session.scalar(
        select(LearningItem).where(
            LearningItem.id.in_(question["target_learning_item_ids"]),
            LearningItem.user_id == user.id,
            LearningItem.is_template.is_(False),
        )
    )
    target = str(
        question.get("target_phrase") or (item.text if item is not None else example)
    )
    if question.get("category") == "grammar":
        prompt = (
            "Write one new workplace sentence using the same grammar pattern "
            f"in a different situation. Example: {example}"
        )
    else:
        prompt = f"Write one workplace sentence using this phrase naturally: {target}"
    prompt = str(question.get("production_prompt") or prompt)
    current = _now(now)
    exercise = {
        "exercise_type": PRODUCTION,
        "prompt": prompt,
        "expected_answer": target,
        "explanation": "Use the target in your own sentence.",
        "target_learning_item_ids": question["target_learning_item_ids"],
        "metadata": {
            "mode": "simple",
            "stream_index": 0,
            "parent_simple_session_id": parent.id,
        },
    }
    run = PracticeSession(
        user_id=user.id,
        target_date_local=local_date(user, now=current),
        started_at=current,
        status=BONUS,
        exercises=[exercise],
    )
    session.add(run)
    session.flush()
    return SimpleStep(run, _snapshot(run))


def submit_bonus(
    session: Session,
    user: User,
    bonus_run_id: int,
    answer: str,
    feedback: dict,
    *,
    now: datetime | None = None,
) -> SimpleAnswer:
    run = _owned_run(session, user, bonus_run_id)
    if run is None or run.status != BONUS or not answer.strip():
        return SimpleAnswer(False, "unavailable")
    question = _snapshot(run)
    if question is None:
        return SimpleAnswer(False, "unavailable")
    current = _now(now)
    with _atomic_answer(session):
        if not _claim(session, user, run, 0, status=BONUS):
            return SimpleAnswer(False, "stale")
        saved_feedback = {
            **feedback,
            "answer_modality": "production",
            "parent_simple_session_id": question["metadata"][
                "parent_simple_session_id"
            ],
        }
        status = str(feedback.get("status") or "unchecked")
        if status in {"correct", "partial", "incorrect"}:
            owned_ids = []
            for item_id in question["target_learning_item_ids"]:
                item = session.scalar(
                    select(LearningItem).where(
                        LearningItem.id == item_id,
                        LearningItem.user_id == user.id,
                        LearningItem.status == "active",
                        LearningItem.is_template.is_(False),
                    )
                )
                if item is not None:
                    owned_ids.append(item.id)
            apply_feedback(
                session,
                user,
                {**question, "target_learning_item_ids": owned_ids},
                answer.strip(),
                AnswerFeedback.model_validate(feedback),
            )
        attempt = PracticeAttempt(
            practice_session_id=run.id,
            exercise_index=0,
            exercise_type=PRODUCTION,
            target_learning_item_ids=question["target_learning_item_ids"],
            prompt=question["prompt"],
            user_answer=answer.strip(),
            status=status,
            feedback=saved_feedback,
            created_at=current,
        )
        session.add(attempt)
        run.status = "completed"
        run.completed_at = current
        run.exercises = [question]
        session.flush()
        return SimpleAnswer(
            True,
            "answered",
            attempt,
            status == "correct",
            summary=SimpleSummary(run.id, 1, int(status == "correct")),
        )


def skip_bonus(
    session: Session,
    user: User,
    bonus_run_id: int,
    *,
    now: datetime | None = None,
) -> SimpleSummary:
    _lock_user(session, user)
    run = _owned_run(session, user, bonus_run_id)
    if run is None or run.status != BONUS:
        return SimpleSummary(None, 0, 0)
    run.status = "completed"
    run.completed_at = _now(now)
    session.flush()
    return SimpleSummary(run.id, 0, 0)
