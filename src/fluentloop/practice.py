from __future__ import annotations

import shutil
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import select
from sqlalchemy.orm import Session

from fluentloop.db.models import (
    LearningItem,
    LessonPlan,
    MistakePattern,
    PracticeAttempt,
    PracticeSession,
    PracticeSessionCached,
    ReviewState,
    User,
    utc_now,
)
from fluentloop.exercises import EXERCISE_TYPES, Exercise, render_for_item
from fluentloop.grammar import parents_of
from fluentloop.hint_ladder import render_hint_ladder
from fluentloop.learning import active_items
from fluentloop.lesson_plans import available_lesson_plan
from fluentloop.srs import get_due_items

GIR_REFIRE_THRESHOLD_DAYS = 1 / 24
GIR_REFIRE_MAX_PER_ITEM = 3


def _seed_exercises() -> list[Exercise]:
    return [
        Exercise(
            "follow_up",
            (
                "Reply in 2-3 sentences: what delivery risk should we discuss "
                "first?"
            ),
            "We should discuss the highest-impact delivery risk first.",
            "Use concise stakeholder language.",
            "Seed exercise until enough approved learning items exist.",
            [],
        ),
        Exercise(
            "grammar_rewrite",
            (
                "Rewrite this more diplomatically:\n"
                '"We must change the architecture immediately."'
            ),
            "We might need to reconsider the architecture soon.",
            "Use hedging language.",
            "Business English often softens direct recommendations.",
            [],
        ),
        Exercise(
            "error_correction",
            'Find and fix the issue:\n"We need align priorities before sprint."',
            "We need to align on priorities before the sprint.",
            "Check verb pattern, preposition, and article.",
            "Use align on + topic; use the sprint for a specific sprint.",
            [],
        ),
        Exercise(
            "translate",
            '"Можем ли мы согласовать риски до планирования?"',
            "Can we align on the risks before planning?",
            "Keep it natural for a meeting.",
            "Seed business/IT translation prompt.",
            [],
        ),
        Exercise(
            "cloze",
            "We need to ____ on the priorities before the sprint starts.\n"
            "(согласовать)",
            "align",
            "One word.",
            "Seed collocation prompt.",
            [],
        ),
        Exercise(
            "guess",
            '"To politely challenge an idea in a meeting."',
            "push back on",
            "Three-word phrasal expression.",
            "Seed expression prompt.",
            [],
        ),
        Exercise(
            "follow_up",
            (
                "Write a short status update about a delayed delivery. Mention "
                "risk, next step, and owner."
            ),
            "There is a delivery risk; the next step is to align on scope.",
            "Use calm, specific language.",
            "Seed production prompt.",
            [],
        ),
    ]


def _high_confidence_pattern_exercises(session: Session, user: User) -> list[Exercise]:
    exercises: list[Exercise] = []
    patterns = session.scalars(
        select(MistakePattern)
        .where(
            MistakePattern.user_id == user.id,
            MistakePattern.status == "active",
            MistakePattern.confidence == "high",
        )
        .order_by(MistakePattern.event_count.desc())
        .limit(3)
    )
    for pattern in patterns:
        target_ids: list[int] = []
        prompt = (
            f"Fix this recurring {pattern.mistake_type} issue:\n"
            f'"{(pattern.wrong_examples or ["Review this pattern."])[-1]}"'
        )
        expected = (pattern.correct_examples or ["Use the corrected pattern."])[-1]
        if pattern.linked_learning_item_id is not None:
            item = session.get(LearningItem, pattern.linked_learning_item_id)
            if item is not None and item.status == "active":
                target_ids.append(item.id)
        if pattern.linked_grammar_concept_id is not None:
            parents = parents_of(session, pattern.linked_grammar_concept_id, depth=1)
            if parents:
                prompt = (
                    f"Review the parent grammar concept: {parents[0].title}.\n"
                    f"Now fix:\n"
                    f'"{(pattern.wrong_examples or ["Review this pattern."])[-1]}"'
                )
        exercises.append(
            Exercise(
                "error_correction",
                prompt,
                expected,
                render_hint_ladder(pattern),
                pattern.description,
                target_ids,
            )
        )
    return exercises


def _legacy_compose_session(
    session: Session, user: User, *, target_date: date | None = None
) -> list[dict]:
    selected = get_due_items(session, user.id, limit=7)
    if len(selected) < 7:
        seen = {item.id for item in selected}
        selected.extend(
            item for item in active_items(session, user.id) if item.id not in seen
        )
    exercises: list[Exercise] = []
    type_cycle = list(EXERCISE_TYPES)
    for index, item in enumerate(selected[:7]):
        exercises.append(render_for_item(item, type_cycle[index % len(type_cycle)]))
    seen_item_ids = {
        item_id
        for exercise in exercises
        for item_id in exercise.target_learning_item_ids
    }
    for exercise in _high_confidence_pattern_exercises(session, user):
        already_selected = any(
            item_id in seen_item_ids
            for item_id in exercise.target_learning_item_ids
        )
        if not already_selected:
            exercises.append(exercise)
            seen_item_ids.update(exercise.target_learning_item_ids)
        if len(exercises) >= 7:
            break
    seed_pool = _seed_exercises()
    seed_index = 0
    while len(exercises) < 7:
        exercises.append(seed_pool[seed_index % len(seed_pool)])
        seed_index += 1
    return [exercise.as_dict() for exercise in exercises[:7]]


def compose_session(
    session: Session,
    user: User,
    *,
    target_date: date | None = None,
    mode: str | None = None,
    lesson_plan: LessonPlan | None = None,
) -> list[dict]:
    try:
        from fluentloop.learning_engine import compose_learning_session

        return compose_learning_session(
            session,
            user,
            target_date=target_date,
            mode_override=mode,
            lesson_plan=lesson_plan,
        )
    except Exception:
        return _legacy_compose_session(session, user, target_date=target_date)


def cache_session(
    session: Session, user: User, *, target_date: date
) -> PracticeSessionCached:
    cached = session.scalar(
        select(PracticeSessionCached).where(
            PracticeSessionCached.user_id == user.id,
            PracticeSessionCached.target_date_local == target_date,
        )
    )
    plan = available_lesson_plan(session, user)
    if cached is not None:
        if _cached_session_is_stale_for_plan(cached, plan):
            cached.exercises = compose_session(session, user, target_date=target_date)
            cached.status = "ready"
            session.add(cached)
            session.flush()
        return cached
    cached = PracticeSessionCached(
        user_id=user.id,
        target_date_local=target_date,
        exercises=compose_session(session, user, target_date=target_date),
        status="ready",
    )
    session.add(cached)
    session.flush()
    return cached


def start_or_resume_session(
    session: Session,
    user: User,
    *,
    target_date: date | None = None,
) -> PracticeSession:
    local_date = target_date or _local_date(user)
    current = session.scalar(
        select(PracticeSession).where(
            PracticeSession.user_id == user.id,
            PracticeSession.target_date_local == local_date,
            PracticeSession.status == "in_progress",
        )
    )
    if current is not None:
        if _active_session_is_stale_for_plan(session, user, current):
            current.status = "superseded"
            session.add(current)
            session.flush()
        else:
            return current
    cached = cache_session(session, user, target_date=local_date)
    current = PracticeSession(
        user_id=user.id,
        target_date_local=local_date,
        exercises=cached.exercises,
        status="in_progress",
    )
    session.add(current)
    session.flush()
    return current


def start_explicit_session(
    session: Session,
    user: User,
    *,
    target_date: date | None = None,
    mode: str | None = None,
    lesson_plan: LessonPlan | None = None,
) -> PracticeSession:
    local_date = target_date or _local_date(user)
    current = get_in_progress_session(session, user, target_date=local_date)
    if current is not None:
        current.status = "superseded"
        session.add(current)
        session.flush()
    exercises = compose_session(
        session,
        user,
        target_date=local_date,
        mode=mode,
        lesson_plan=lesson_plan,
    )
    current = PracticeSession(
        user_id=user.id,
        target_date_local=local_date,
        exercises=exercises,
        status="in_progress",
    )
    session.add(current)
    session.flush()
    return current


def _local_date(user: User) -> date:
    try:
        tz = ZoneInfo(user.timezone)
    except ZoneInfoNotFoundError:
        tz = UTC
    return datetime.now(tz).date()


def _cached_session_is_stale_for_plan(
    cached: PracticeSessionCached, plan: object | None
) -> bool:
    if plan is None:
        return False
    return _exercises_are_stale_for_plan(cached.exercises, plan)


def _active_session_is_stale_for_plan(
    session: Session, user: User, current: PracticeSession
) -> bool:
    plan = available_lesson_plan(session, user)
    if plan is None:
        return False
    return _exercises_are_stale_for_plan(current.exercises, plan)


def _exercises_are_stale_for_plan(exercises: list[dict], plan: object) -> bool:
    if not exercises:
        return True
    metadata = exercises[0].get("metadata")
    if not isinstance(metadata, dict):
        metadata = exercises[0]
    plan_id = metadata.get("lesson_plan_id")
    if plan_id != getattr(plan, "id", None):
        return True
    if str(metadata.get("mode", "")) != "lesson":
        return True
    return len(exercises) < 15


def get_in_progress_session(
    session: Session,
    user: User,
    *,
    target_date: date | None = None,
) -> PracticeSession | None:
    local_date = target_date or _local_date(user)
    return session.scalar(
        select(PracticeSession).where(
            PracticeSession.user_id == user.id,
            PracticeSession.target_date_local == local_date,
            PracticeSession.status == "in_progress",
        )
    )


def next_exercise(
    session: Session, practice_session: PracticeSession
) -> tuple[int, dict] | None:
    answered = {
        row.exercise_index
        for row in session.scalars(
            select(PracticeAttempt).where(
                PracticeAttempt.practice_session_id == practice_session.id
            )
        )
    }
    for index, exercise in enumerate(practice_session.exercises):
        if index not in answered:
            return index, exercise
    practice_session.status = "completed"
    practice_session.completed_at = utc_now()
    session.add(practice_session)
    session.flush()
    return None


def record_attempt(
    session: Session,
    practice_session: PracticeSession,
    exercise_index: int,
    exercise: dict,
    answer: str,
    feedback: dict,
) -> PracticeAttempt:
    attempt = PracticeAttempt(
        practice_session_id=practice_session.id,
        exercise_index=exercise_index,
        exercise_type=exercise["exercise_type"],
        target_learning_item_ids=exercise.get("target_learning_item_ids", []),
        prompt=exercise["prompt"],
        user_answer=answer,
        status=feedback.get("status", "unchecked"),
        feedback=feedback,
    )
    session.add(attempt)
    session.flush()
    _append_gir_refire_exercises(
        session,
        practice_session,
        source_exercise_index=exercise_index,
        exercise=exercise,
        feedback=feedback,
    )
    return attempt


def _append_gir_refire_exercises(
    session: Session,
    practice_session: PracticeSession,
    *,
    source_exercise_index: int,
    exercise: dict,
    feedback: dict,
) -> None:
    if feedback.get("status") == "skipped":
        return
    target_ids = _unique_ints(exercise.get("target_learning_item_ids", []))
    if not target_ids:
        return
    exercises = list(practice_session.exercises)
    appended = False
    for item_id in target_ids:
        state = session.scalar(
            select(ReviewState).where(ReviewState.learning_item_id == item_id)
        )
        if state is None or not (
            0 < state.last_interval_days < GIR_REFIRE_THRESHOLD_DAYS
        ):
            continue
        current_count = _gir_refire_count(exercises, item_id)
        if current_count >= GIR_REFIRE_MAX_PER_ITEM:
            continue
        item = session.get(LearningItem, item_id)
        if item is None or item.status != "active":
            continue
        refire = _gir_refire_exercise(
            item,
            source=exercise,
            source_exercise_index=source_exercise_index,
            interval_days=state.last_interval_days,
            refire_count=current_count + 1,
        )
        exercises.append(refire)
        appended = True
    if appended:
        practice_session.exercises = exercises
        session.add(practice_session)
        session.flush()


def _gir_refire_exercise(
    item: LearningItem,
    *,
    source: dict,
    source_exercise_index: int,
    interval_days: float,
    refire_count: int,
) -> dict:
    rendered = render_for_item(item, "active_recall").as_dict()
    metadata = dict(rendered.get("metadata") or {})
    source_metadata = (
        source.get("metadata") if isinstance(source.get("metadata"), dict) else {}
    )
    metadata.update(
        {
            "stage": "gir_refire",
            "mode": source_metadata.get("mode") or source.get("mode") or "review",
            "topic": source_metadata.get("topic") or source.get("topic", ""),
            "lesson_goal": source_metadata.get("lesson_goal")
            or source.get("lesson_goal", ""),
            "target_skill": "sub_day_recall",
            "target_item_ids": [item.id],
            "gir_refire": True,
            "source_exercise_index": source_exercise_index,
            "gir_interval_days": interval_days,
            "gir_refire_count": refire_count,
        }
    )
    rendered["prompt"] = (
        f"Sub-day recall ({_format_gir_interval(interval_days)}):\n"
        f"{rendered['prompt']}"
    )
    rendered["hint"] = "Recall it without scrolling back; this is the Pimsleur loop."
    rendered["metadata"] = metadata
    rendered.update(metadata)
    rendered["target_learning_item_ids"] = [item.id]
    return rendered


def _gir_refire_count(exercises: list[dict], item_id: int) -> int:
    count = 0
    for exercise in exercises:
        metadata = exercise.get("metadata")
        metadata = metadata if isinstance(metadata, dict) else {}
        if not metadata.get("gir_refire"):
            continue
        if item_id in _unique_ints(exercise.get("target_learning_item_ids", [])):
            count += 1
    return count


def _unique_ints(values: object) -> list[int]:
    result: list[int] = []
    seen: set[int] = set()
    if not isinstance(values, list):
        return result
    for value in values:
        if not isinstance(value, int) or value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def _format_gir_interval(interval_days: float) -> str:
    seconds = round(interval_days * 86_400)
    if seconds < 60:
        return f"{seconds}s"
    minutes = round(seconds / 60)
    if minutes < 60:
        return f"{minutes}m"
    hours = round(minutes / 60)
    return f"{hours}h"


def record_confidence_rating(
    session: Session,
    practice_session: PracticeSession,
    exercise_index: int,
    rating: int,
) -> None:
    if rating < 1 or rating > 5:
        raise ValueError("Confidence must be between 1 and 5.")
    if exercise_index < 0 or exercise_index >= len(practice_session.exercises):
        raise ValueError("Exercise not found.")
    exercises = list(practice_session.exercises)
    exercise = dict(exercises[exercise_index])
    metadata = exercise.get("metadata")
    if not isinstance(metadata, dict):
        metadata = {}
    metadata["confidence_rating"] = rating
    exercise["metadata"] = metadata
    exercise["confidence_rating"] = rating
    exercises[exercise_index] = exercise
    practice_session.exercises = exercises
    session.add(practice_session)
    session.flush()


def summarize_session(session: Session, practice_session: PracticeSession) -> str:
    attempts = list(
        session.scalars(
            select(PracticeAttempt)
            .where(PracticeAttempt.practice_session_id == practice_session.id)
            .order_by(PracticeAttempt.exercise_index)
        )
    )
    counts = {"correct": 0, "partial": 0, "incorrect": 0, "skipped": 0}
    for attempt in attempts:
        if attempt.status in counts:
            counts[attempt.status] += 1
    return (
        "Session complete.\n"
        f"Correct: {counts['correct']}\n"
        f"Partial: {counts['partial']}\n"
        f"Incorrect: {counts['incorrect']}\n"
        f"Skipped: {counts['skipped']}\n"
        f"Answered: {len(attempts)}/{len(practice_session.exercises)}\n"
        "Reflect: /reflect <what was hardest today?>"
    )


def backup_sqlite(db_path: Path, backup_dir: Path, *, retention_days: int = 14) -> Path:
    backup_dir.mkdir(parents=True, exist_ok=True)
    target = backup_dir / f"db-{datetime.now(UTC).date().isoformat()}.sqlite"
    if db_path.exists():
        shutil.copy2(db_path, target)
    cutoff = datetime.now(UTC) - timedelta(days=retention_days)
    for path in backup_dir.glob("db-*.sqlite"):
        if datetime.fromtimestamp(path.stat().st_mtime, UTC) < cutoff:
            path.unlink()
    return target
