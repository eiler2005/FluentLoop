from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy.orm import Session

from fluentloop.ai.provider import AIProvider
from fluentloop.ai.schemas import AnswerFeedback, NativeRewriteFeedback
from fluentloop.bot.formatting import bold, code, labeled
from fluentloop.db.models import (
    ExtractedCandidate,
    MistakeEvent,
    MistakePattern,
    SourceMaterial,
    User,
)
from fluentloop.format_analysis import (
    mine_notebook_diff,
    mistake_extinction_state,
    score_discourse,
)
from fluentloop.mistakes import ingest_mistake_event
from fluentloop.russian_l1_filter import detect_l1_interference
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
        "confidence_rating": metadata.get("confidence_rating"),
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
    native_rewrite = None
    try:
        rewrite_result = provider.light_call("epic_22_native_rewrite", payload)
    except Exception:
        rewrite_result = None
    if isinstance(rewrite_result, NativeRewriteFeedback):
        native_rewrite = rewrite_result
    return build_teacher_feedback(result, exercise, answer, native_rewrite)


def build_teacher_feedback(
    feedback: AnswerFeedback,
    exercise: dict,
    answer: str,
    native_rewrite: NativeRewriteFeedback | None = None,
) -> AnswerFeedback:
    corrected = feedback.corrected_answer or exercise.get("expected_answer", "")
    natural = feedback.natural_answer or corrected
    if native_rewrite is not None and native_rewrite.native_rewrite:
        natural = native_rewrite.native_rewrite
    mistake_summary = feedback.mistake_summary
    if not mistake_summary and feedback.status != "correct":
        mistake_summary = "The meaning is close, but the form needs adjustment."
    why_wrong = feedback.why_wrong or feedback.explanation
    rule = feedback.rule or feedback.related_rule
    better_variants = feedback.better_variants or ([natural] if natural else [])
    l1_hits = [hit.as_feedback_dict() for hit in detect_l1_interference(answer)]
    if l1_hits and feedback.status == "correct":
        feedback = feedback.model_copy(update={"status": "partial"})
    if l1_hits and not mistake_summary:
        first_hit = l1_hits[0]
        mistake_summary = (
            f"Likely Russian L1 transfer: {first_hit['matched_text']} -> "
            f"{first_hit['suggestion']}."
        )
    error_layer = feedback.error_layer or mistake_summary or feedback.explanation
    native_reason = feedback.native_rewrite_reason
    if native_rewrite is not None and native_rewrite.reason:
        native_reason = native_rewrite.reason
    why_layer = feedback.why_layer or why_wrong or rule
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
    metadata = exercise.get("metadata")
    metadata = metadata if isinstance(metadata, dict) else {}
    lesson_format = str(
        metadata.get("lesson_format") or exercise.get("lesson_format") or ""
    )
    format_feedback = dict(feedback.format_feedback)
    if lesson_format == "notebook":
        diff = mine_notebook_diff(answer, natural)
        format_feedback["notebook_diff"] = diff
    elif lesson_format == "discourse":
        format_feedback["discourse_score"] = score_discourse(answer)
    elif lesson_format == "mistakes":
        format_feedback["mistake_extinction"] = mistake_extinction_state(
            [feedback.status]
        )
    return feedback.model_copy(
        update={
            "corrected_answer": corrected,
            "natural_answer": natural,
            "native_rewrite": natural,
            "native_rewrite_reason": native_reason,
            "mistake_summary": mistake_summary,
            "why_wrong": why_wrong,
            "rule": rule,
            "error_layer": error_layer,
            "why_layer": why_layer,
            "l1_hits": l1_hits,
            "format_feedback": format_feedback,
            "should_create_mistake_event": (
                feedback.should_create_mistake_event or bool(l1_hits)
            ),
            "should_create_or_update_mistake_pattern": (
                feedback.should_create_or_update_mistake_pattern or bool(l1_hits)
            ),
            "better_variants": better_variants,
            "micro_drill": micro_drill,
            "teacher_note": teacher_note,
        }
    )


def render_compact_teacher_feedback(attempt_id: int, feedback: AnswerFeedback) -> str:
    better = feedback.natural_answer or feedback.corrected_answer
    lines = [
        bold(f"Feedback - Attempt #{attempt_id}"),
        labeled("Verdict", f"{feedback.status.title()}."),
    ]
    if better:
        lines.append(f"{bold('Better:')} {code(better)}")
    if feedback.mistake_summary:
        lines.append(labeled("Mistake", feedback.mistake_summary))
    if feedback.error_layer and feedback.error_layer != feedback.mistake_summary:
        lines.append(labeled("Errors", feedback.error_layer))
    why = feedback.why_wrong or feedback.explanation
    if why:
        lines.append(labeled("Why", why))
    rule = feedback.rule or feedback.related_rule
    if rule:
        lines.append(labeled("Rule", rule))
    if feedback.better_variants:
        lines.append(f"{bold('Try:')} {code(feedback.better_variants[0])}")
    if feedback.native_rewrite_reason:
        lines.append(labeled("Native layer", feedback.native_rewrite_reason))
    if feedback.l1_hits:
        first_hit = feedback.l1_hits[0]
        lines.append(
            labeled(
                "L1 trap",
                f"{first_hit['matched_text']} -> {first_hit['suggestion']}",
            )
        )
    if feedback.micro_drill:
        lines.append(labeled("Micro-drill", feedback.micro_drill))
    return "\n".join(lines)


def render_detailed_teacher_feedback(feedback: dict) -> str:
    better_variants = feedback.get("better_variants") or []
    lines = [
        bold("Teacher breakdown"),
        labeled("Verdict", str(feedback.get("status", "unchecked")).title()),
    ]
    corrected = feedback.get("corrected_answer") or feedback.get("natural_answer")
    if corrected:
        lines.append(f"{bold('Corrected:')} {code(corrected)}")
    mistake = feedback.get("mistake_summary")
    if mistake:
        lines.append(labeled("What went wrong", mistake))
    why = feedback.get("why_wrong") or feedback.get("explanation")
    if why:
        lines.append(labeled("Why it matters", why))
    rule = feedback.get("rule") or feedback.get("related_rule")
    if rule:
        lines.append(labeled("Teacher rule", rule))
    error_layer = feedback.get("error_layer")
    if error_layer:
        lines.append(labeled("Error layer", str(error_layer)))
    native_rewrite = feedback.get("native_rewrite") or feedback.get("natural_answer")
    if native_rewrite:
        lines.append(f"{bold('Native rewrite:')} {code(native_rewrite)}")
    native_reason = feedback.get("native_rewrite_reason")
    if native_reason:
        lines.append(labeled("Native reason", str(native_reason)))
    why_layer = feedback.get("why_layer")
    if why_layer:
        lines.append(labeled("Why layer", str(why_layer)))
    l1_hits = feedback.get("l1_hits") or []
    if l1_hits:
        lines.append(bold("Russian L1 hits:"))
        for hit in l1_hits[:3]:
            lines.append(f"- {code(hit['matched_text'])} -> {code(hit['suggestion'])}")
    format_feedback = feedback.get("format_feedback") or {}
    if isinstance(format_feedback, dict) and format_feedback:
        lines.append(bold("Format feedback:"))
        if format_feedback.get("notebook_diff"):
            diff = format_feedback["notebook_diff"]
            if isinstance(diff, dict):
                chunks = diff.get("candidate_chunks") or []
                lines.append(labeled("Notebook mined chunks", ", ".join(chunks[:3])))
        if format_feedback.get("discourse_score"):
            score = format_feedback["discourse_score"]
            if isinstance(score, dict):
                lines.append(
                    labeled("Discourse score", str(score.get("cohesion_score", "")))
                )
        if format_feedback.get("mistake_extinction"):
            state = format_feedback["mistake_extinction"]
            if isinstance(state, dict):
                lines.append(labeled("Extinction state", str(state.get("state", ""))))
    if better_variants:
        lines.append(bold("Better variants:"))
        lines.extend(f"- {code(variant)}" for variant in better_variants[:3])
    micro_drill = feedback.get("micro_drill")
    if micro_drill:
        lines.append(labeled("Micro-drill", micro_drill))
    note = feedback.get("teacher_note")
    if note:
        lines.append(labeled("Teacher note", note))
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
        first_l1_hit = feedback.l1_hits[0] if feedback.l1_hits else None
        event = MistakeEvent(
            user_id=user.id,
            wrong_answer=answer,
            corrected_answer=feedback.corrected_answer,
            explanation=(
                str(first_l1_hit.get("explanation"))
                if first_l1_hit
                else feedback.explanation
            ),
            mistake_type=(
                str(first_l1_hit.get("mistake_type"))
                if first_l1_hit
                else feedback.detected_mistake_type or "general"
            ),
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
    suggested = list(feedback.suggested_candidates)
    notebook_diff = feedback.format_feedback.get("notebook_diff")
    if isinstance(notebook_diff, dict):
        from fluentloop.ai.schemas import ExtractedItem

        for chunk in notebook_diff.get("candidate_chunks") or []:
            suggested.append(
                ExtractedItem(
                    type="chunk",
                    text=str(chunk),
                    meaning="",
                    explanation="Mined from Notebook native rewrite diff.",
                    tags=["notebook", "native_diff"],
                    confidence=0.65,
                )
            )
    if not suggested:
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
    for item in suggested:
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
