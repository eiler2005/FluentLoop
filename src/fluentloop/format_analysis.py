from __future__ import annotations

import re
from collections.abc import Sequence
from difflib import SequenceMatcher
from typing import Any

from fluentloop.db.models import LearningItem

SIGNPOSTS = {
    "however",
    "therefore",
    "moreover",
    "nevertheless",
    "on the other hand",
    "as a result",
    "in contrast",
    "for example",
}
COUNTERPOINT_MARKERS = {"however", "although", "while", "whereas", "nevertheless"}
RECOMMENDATION_MARKERS = {"recommend", "should", "could", "worth", "next step"}
HEDGE_MARKERS = {"might", "may", "could", "seems", "likely", "appears", "arguably"}


def mine_notebook_diff(user_answer: str, native_rewrite: str) -> dict[str, Any]:
    original = _words(user_answer)
    rewritten = _words(native_rewrite)
    if not original or not rewritten or original == rewritten:
        return {"changed_spans": [], "candidate_chunks": []}
    matcher = SequenceMatcher(a=original, b=rewritten)
    changed_spans: list[str] = []
    candidates: list[str] = []
    for tag, _i1, _i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            continue
        span = " ".join(rewritten[j1:j2]).strip()
        if not span:
            continue
        changed_spans.append(span)
        if 2 <= len(span.split()) <= 8:
            candidates.append(span)
    if not candidates and native_rewrite.strip():
        candidates.append(native_rewrite.strip()[:160])
    return {
        "changed_spans": changed_spans[:8],
        "candidate_chunks": _dedupe(candidates)[:5],
    }


def score_discourse(text: str) -> dict[str, Any]:
    normalized = text.lower()
    sentences = [item for item in re.split(r"[.!?]+", text) if item.strip()]
    signpost_hits = [marker for marker in SIGNPOSTS if marker in normalized]
    has_counterpoint = any(marker in normalized for marker in COUNTERPOINT_MARKERS)
    has_recommendation = any(marker in normalized for marker in RECOMMENDATION_MARKERS)
    score = 25
    score += min(len(sentences), 4) * 10
    score += min(len(signpost_hits), 3) * 10
    score += 15 if has_counterpoint else 0
    score += 10 if has_recommendation else 0
    score = min(score, 100)
    return {
        "sentence_count": len(sentences),
        "signposts": sorted(signpost_hits),
        "has_counterpoint": has_counterpoint,
        "has_recommendation": has_recommendation,
        "cohesion_score": score,
        "next_focus": (
            "Add a counterpoint and a clear recommendation."
            if not (has_counterpoint and has_recommendation)
            else "Tighten transitions and make the final action concrete."
        ),
    }


def critical_reading_card(text: str) -> dict[str, Any]:
    source = text.strip()
    excerpt = re.sub(r"\s+", " ", source)[:700] if source else ""
    hedge_hits = [marker for marker in HEDGE_MARKERS if marker in source.lower()]
    return {
        "source_excerpt": excerpt,
        "tasks": [
            "Name the main claim.",
            "Find one hedge or uncertainty marker.",
            "Challenge one assumption.",
            "Write a two-sentence executive summary.",
        ],
        "hedge_markers_found": sorted(hedge_hits),
        "prompt": (
            "Critical Reading Club\n"
            "1. Main claim:\n"
            "2. Hedge / uncertainty marker:\n"
            "3. Assumption to challenge:\n"
            "4. Two-sentence executive summary:"
        ),
    }


def mistake_extinction_state(statuses: Sequence[str]) -> dict[str, Any]:
    streak = 0
    for status in reversed(list(statuses)):
        if status == "correct":
            streak += 1
        else:
            break
    if streak >= 5:
        state = "extinct"
    elif streak >= 3:
        state = "nearly_extinct"
    elif streak:
        state = "building"
    else:
        state = "active"
    return {
        "correct_streak": streak,
        "state": state,
        "target_streak": 5,
    }


def vocabulary_lab_card(items: Sequence[LearningItem]) -> dict[str, Any]:
    chunks = [item for item in items if item.type in {"chunk", "expression", "word"}]
    fields = _metadata_counts(chunks, "field")
    registers = _metadata_counts(chunks, "register")
    functions = _metadata_counts(chunks, "function")
    return {
        "chunk_count": len(chunks),
        "fields": fields,
        "registers": registers,
        "functions": functions,
        "prompt": (
            "Vocabulary Lab\n"
            "Group today's chunks by field, register, and function, then use "
            "three of them in a realistic work sentence."
        ),
    }


def _metadata_counts(items: Sequence[LearningItem], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        metadata = item.metadata_json if isinstance(item.metadata_json, dict) else {}
        value = str(metadata.get(key) or "").strip()
        if value:
            counts[value] = counts.get(value, 0) + 1
    return dict(sorted(counts.items()))


def _words(text: str) -> list[str]:
    return re.findall(r"[A-Za-z][A-Za-z'-]*", text)


def _dedupe(values: Sequence[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        key = value.lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(value)
    return result
