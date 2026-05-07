from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy.orm import Session

from fluentloop.ai.provider import AIProvider
from fluentloop.ai.schemas import AnswerFeedback
from fluentloop.db.models import (
    ExtractedCandidate,
    MistakeEvent,
    MistakePattern,
    SourceMaterial,
    User,
)
from fluentloop.mistakes import ingest_mistake_event
from fluentloop.srs import record_result


def check_answer(provider: AIProvider, exercise: dict, answer: str) -> AnswerFeedback:
    task_type = exercise.get("exercise_type")
    payload = {
        "exercise_type": task_type,
        "prompt": exercise.get("prompt", ""),
        "expected_answer": exercise.get("expected_answer", ""),
        "answer": answer,
    }
    if task_type in {"grammar_rewrite", "follow_up", "error_correction"}:
        result = provider.heavy_call("epic_10_check_answer", payload)
    else:
        result = provider.light_call("epic_10_check_answer", payload)
    if not isinstance(result, AnswerFeedback):
        raise TypeError("AI provider returned the wrong feedback schema")
    return result


def srs_result_from_feedback(
    feedback: AnswerFeedback, *, hard_override: bool = False
) -> str:
    if hard_override and feedback.status == "correct":
        return "Hard"
    if feedback.status == "correct":
        return "Good"
    if feedback.status == "partial":
        return "Hard"
    return "Again"


def apply_feedback(
    session: Session,
    user: User,
    exercise: dict,
    answer: str,
    feedback: AnswerFeedback,
    *,
    disputed: bool = False,
    hard_override: bool = False,
) -> MistakePattern | None:
    result = srs_result_from_feedback(feedback, hard_override=hard_override)
    for item_id in exercise.get("target_learning_item_ids", []):
        record_result(session, item_id, result)
    if disputed:
        return None
    should_log = result == "Again" or feedback.should_create_mistake_event
    if should_log:
        event = MistakeEvent(
            user_id=user.id,
            wrong_answer=answer,
            corrected_answer=feedback.corrected_answer,
            explanation=feedback.explanation,
            mistake_type=feedback.detected_mistake_type or "general",
            linked_learning_item_id=(
                exercise.get("target_learning_item_ids") or [None]
            )[0],
        )
        session.add(event)
        session.flush()
        return ingest_mistake_event(session, event)
    return None


def queue_feedback_suggestions(
    session: Session,
    user: User,
    exercise: dict,
    feedback: AnswerFeedback,
) -> tuple[int, int] | None:
    if not feedback.suggested_candidates:
        return None
    material = SourceMaterial(
        user_id=user.id,
        type="teacher_feedback",
        raw_text=(
            "Answer feedback suggested new learning candidates.\n\n"
            f"Prompt: {exercise.get('prompt', '')}\n"
            f"Expected: {exercise.get('expected_answer', '')}\n"
            f"Explanation: {feedback.explanation}"
        ),
        summary="Suggested candidates from answer feedback",
    )
    session.add(material)
    session.flush()
    count = 0
    for item in feedback.suggested_candidates:
        candidate = ExtractedCandidate(
            source_material_id=material.id,
            type=item.type,
            text=item.text,
            meaning=item.meaning,
            explanation=item.explanation,
            examples=item.examples,
            tags=item.tags,
            confidence=item.confidence,
            status="pending",
        )
        session.add(candidate)
        count += 1
    session.flush()
    return material.id, count


def write_dispute(
    base_dir: Path,
    *,
    prompt: str,
    answer: str,
    verdict: dict,
    reason: str,
    note: str = "",
) -> Path:
    base_dir.mkdir(parents=True, exist_ok=True)
    path = base_dir / f"{datetime.now(UTC).date().isoformat()}.jsonl"
    row = {
        "ts": datetime.now(UTC).isoformat(),
        "prompt": prompt,
        "answer": answer,
        "verdict": verdict,
        "reason": reason,
        "note": note,
    }
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    return path
