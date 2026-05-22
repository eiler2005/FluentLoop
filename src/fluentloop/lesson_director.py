from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from fluentloop.ai.provider import AIProvider
from fluentloop.ai.schemas import LessonDirectorDecision
from fluentloop.db.models import LearningItem, MistakePattern


def decide_lesson_format(
    *,
    due_items: Sequence[LearningItem],
    scored_items: Sequence[LearningItem],
    patterns: Sequence[MistakePattern],
    provider: AIProvider | None = None,
) -> LessonDirectorDecision:
    payload = _decision_payload(due_items, scored_items, patterns)
    if provider is not None:
        try:
            result = provider.light_call("epic_22_lesson_director", payload)
        except Exception:
            result = None
        if isinstance(result, LessonDirectorDecision):
            return result
    return _deterministic_decision(payload)


def _decision_payload(
    due_items: Sequence[LearningItem],
    scored_items: Sequence[LearningItem],
    patterns: Sequence[MistakePattern],
) -> dict[str, Any]:
    return {
        "due_count": len(due_items),
        "types": [item.type for item in scored_items[:20]],
        "target_item_ids": [
            item.id for item in scored_items[:8] if item.id is not None
        ],
        "tags": [tag for item in scored_items[:20] for tag in (item.tags or [])],
        "high_confidence_patterns": [
            pattern.mistake_type
            for pattern in patterns
            if pattern.confidence == "high"
        ],
        "active_pattern_count": len(patterns),
    }


def _deterministic_decision(payload: dict[str, Any]) -> LessonDirectorDecision:
    types = list(payload.get("types") or [])
    tags = {str(tag).lower() for tag in payload.get("tags") or []}
    high_patterns = list(payload.get("high_confidence_patterns") or [])
    target_item_ids = list(payload.get("target_item_ids") or [])
    due_count = int(payload.get("due_count") or 0)
    if due_count >= 5:
        return LessonDirectorDecision(
            mode="review",
            reason="Many items are due; consolidate before adding stretch.",
            review_focus="sub-day and due SRS",
            stretch_focus="one cold recall closer",
            target_item_ids=target_item_ids,
        )
    if high_patterns:
        return LessonDirectorDecision(
            mode="mistakes",
            reason="A high-confidence mistake pattern should be extinguished.",
            review_focus=high_patterns[0],
            stretch_focus="hint ladder with final no-hint production",
            target_item_ids=target_item_ids,
        )
    if types.count("chunk") >= 3:
        return LessonDirectorDecision(
            mode="vocab",
            reason="Chunk bank is ready for field/register/function activation.",
            review_focus="chunk recall",
            stretch_focus="productive Vocabulary Lab sentence",
            target_item_ids=target_item_ids,
        )
    if "genre_curriculum" in tags:
        return LessonDirectorDecision(
            mode="genre",
            reason="Genre curriculum items are active.",
            review_focus="schema noticing",
            stretch_focus="short genre artifact",
            target_item_ids=target_item_ids,
        )
    return LessonDirectorDecision(
        mode="mixed",
        reason="Balanced rotation across current active material.",
        review_focus="weak items",
        stretch_focus="one realistic work response",
        target_item_ids=target_item_ids,
    )
