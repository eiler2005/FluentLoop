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


def build_answer_check_payload(exercise: dict, answer: str) -> dict:
    task_type = exercise.get("exercise_type")
    metadata = exercise.get("metadata")
    metadata = metadata if isinstance(metadata, dict) else {}
    return {
        "stage": exercise.get("stage") or metadata.get("stage", ""),
        "exercise_type": task_type,
        "prompt": exercise.get("prompt", ""),
        "expected_answer": exercise.get("expected_answer", ""),
        "hint": exercise.get("hint", ""),
        "explanation": exercise.get("explanation", ""),
        "topic": exercise.get("topic") or metadata.get("topic", ""),
        "lesson_goal": exercise.get("lesson_goal") or metadata.get("lesson_goal", ""),
        "answer": answer,
    }


def check_answer(provider: AIProvider, exercise: dict, answer: str) -> AnswerFeedback:
    task_type = exercise.get("exercise_type")
    payload = build_answer_check_payload(exercise, answer)
    if task_type in {"grammar_rewrite", "follow_up", "error_correction"}:
        result = provider.heavy_call("epic_10_check_answer", payload)
    else:
        result = provider.light_call("epic_10_check_answer", payload)
    if not isinstance(result, AnswerFeedback):
        raise TypeError("AI provider returned the wrong feedback schema")
    return build_teacher_feedback(result, exercise, answer)


def build_teacher_feedback(
    feedback: AnswerFeedback, exercise: dict, answer: str
) -> AnswerFeedback:
    corrected = feedback.corrected_answer or exercise.get("expected_answer", "")
    natural = feedback.natural_answer or corrected
    mistake_summary = feedback.mistake_summary
    if not mistake_summary and feedback.status != "correct":
        mistake_summary = "The meaning is close, but the form needs adjustment."
    why_wrong = feedback.why_wrong or feedback.explanation
    rule = feedback.rule or feedback.related_rule
    better_variants = feedback.better_variants or ([natural] if natural else [])
    micro_drill = feedback.micro_drill
    if not micro_drill and feedback.status != "correct" and corrected:
        micro_drill = f"Write one new sentence using: {corrected}"
    teacher_note = feedback.teacher_note
    if not teacher_note:
        teacher_note = (
            "Good direction; now tighten accuracy."
            if feedback.status != "correct"
            else "Good answer. Keep reusing it in realistic work contexts."
        )
    return feedback.model_copy(
        update={
            "corrected_answer": corrected,
            "natural_answer": natural,
            "mistake_summary": mistake_summary,
            "why_wrong": why_wrong,
            "rule": rule,
            "better_variants": better_variants,
            "micro_drill": micro_drill,
            "teacher_note": teacher_note,
        }
    )


def render_compact_teacher_feedback(attempt_id: int, feedback: AnswerFeedback) -> str:
    better = feedback.natural_answer or feedback.corrected_answer
    lines = [
        f"Attempt #{attempt_id}",
        f"{feedback.status.title()}.",
    ]
    if better:
        lines.append(f"Better: {better}")
    if feedback.mistake_summary:
        lines.append(f"Mistake: {feedback.mistake_summary}")
    why = feedback.why_wrong or feedback.explanation
    if why:
        lines.append(f"Why: {why}")
    rule = feedback.rule or feedback.related_rule
    if rule:
        lines.append(f"Rule: {rule}")
    if feedback.better_variants:
        lines.append(f"Try: {feedback.better_variants[0]}")
    if feedback.micro_drill:
        lines.append(f"Micro-drill: {feedback.micro_drill}")
    return "\n".join(lines)


def render_detailed_teacher_feedback(feedback: dict) -> str:
    better_variants = feedback.get("better_variants") or []
    lines = [
        "Teacher breakdown",
        f"Verdict: {str(feedback.get('status', 'unchecked')).title()}",
    ]
    corrected = feedback.get("corrected_answer") or feedback.get("natural_answer")
    if corrected:
        lines.append(f"Corrected: {corrected}")
    mistake = feedback.get("mistake_summary")
    if mistake:
        lines.append(f"What went wrong: {mistake}")
    why = feedback.get("why_wrong") or feedback.get("explanation")
    if why:
        lines.append(f"Why it matters: {why}")
    rule = feedback.get("rule") or feedback.get("related_rule")
    if rule:
        lines.append(f"Teacher rule: {rule}")
    if better_variants:
        lines.append("Better variants:")
        lines.extend(f"- {variant}" for variant in better_variants[:3])
    micro_drill = feedback.get("micro_drill")
    if micro_drill:
        lines.append(f"Micro-drill: {micro_drill}")
    note = feedback.get("teacher_note")
    if note:
        lines.append(f"Teacher note: {note}")
    return "\n".join(lines)


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


def queue_micro_drill_from_feedback(
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


def queue_feedback_suggestions(
    session: Session,
    user: User,
    exercise: dict,
    feedback: AnswerFeedback,
) -> tuple[int, int] | None:
    return queue_micro_drill_from_feedback(session, user, exercise, feedback)


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
