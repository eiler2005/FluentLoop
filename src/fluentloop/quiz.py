"""Multiple-choice question building for the evening slot (EPIC-25).

Distractors come from three sources, cheapest first:

1. Pre-baked in the item's metadata, which is how word-bank entries arrive.
2. The learner's own other items, picked deterministically.
3. The LLM, only for items neither of the above can cover.

Whatever the source, the result is cached back into
``LearningItem.metadata_json["mcq"]`` so the expensive path runs at most once
per item.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from fluentloop.db.models import LearningItem, User, utc_now
from fluentloop.vocab_loop import CARD_ITEM_TYPES, QuizSpec, select_cards

LOG = logging.getLogger(__name__)

DISTRACTOR_COUNT = 3
QUIZ_OPTION_COUNT = DISTRACTOR_COUNT + 1
_MAX_LENGTH_GAP = 12


def question_for(item: LearningItem) -> str:
    definition = (item.meaning or item.explanation or "").strip()
    return f'Which word or phrase means: "{definition}"?'


def cached_distractors(item: LearningItem) -> list[str]:
    mcq = (item.metadata_json or {}).get("mcq") or {}
    values = mcq.get("distractors") or []
    return [str(value) for value in values if str(value).strip()]


def cache_distractors(
    session: Session, item: LearningItem, distractors: list[str]
) -> None:
    # JSON columns are not mutation-tracked, so reassign the whole dict.
    item.metadata_json = {
        **(item.metadata_json or {}),
        "mcq": {
            "distractors": list(distractors),
            "generated_at": utc_now().isoformat(),
        },
    }
    session.add(item)
    session.flush()


def _stable_rank(item_id: int, candidate_id: int) -> int:
    # Deterministic across processes, unlike hash() on str.
    return (item_id * 1_000_003 + candidate_id * 7919) % 100_003


def select_distractors(
    session: Session,
    user: User,
    item: LearningItem,
    *,
    count: int = DISTRACTOR_COUNT,
) -> list[str]:
    """Pick plausible wrong answers from the learner's own items."""

    candidates = session.scalars(
        select(LearningItem).where(
            LearningItem.user_id == user.id,
            LearningItem.id != item.id,
            LearningItem.type == item.type,
            LearningItem.status.in_(("active", "graduated")),
        )
    ).all()

    target_text = item.text.strip().casefold()
    target_tags = {str(tag).casefold() for tag in (item.tags or [])}
    target_register = str((item.metadata_json or {}).get("register", "")).casefold()

    scored: list[tuple[tuple[int, int, int, int], str]] = []
    for candidate in candidates:
        text = candidate.text.strip()
        folded = text.casefold()
        if not text or folded == target_text:
            continue
        if folded in target_text or target_text in folded:
            continue
        tags = {str(tag).casefold() for tag in (candidate.tags or [])}
        tag_overlap = len(target_tags & tags)
        register = str(
            (candidate.metadata_json or {}).get("register", "")
        ).casefold()
        register_match = 1 if target_register and register == target_register else 0
        length_gap = abs(len(text) - len(item.text))
        if length_gap > _MAX_LENGTH_GAP:
            length_gap = _MAX_LENGTH_GAP
        # Sort key: better matches first, then a stable tiebreak so the same
        # item always produces the same quiz.
        key = (
            -tag_overlap,
            -register_match,
            length_gap,
            _stable_rank(item.id, candidate.id),
        )
        scored.append((key, text))

    scored.sort()
    return [text for _, text in scored[:count]]


def llm_distractors(item: LearningItem, settings: Any | None = None) -> list[str]:
    """Last resort: ask the model, once, for a brand-new learner's item.

    A dead or unconfigured LLM degrades to an empty list, which means "skip
    tonight's quiz" rather than an error.
    """

    from fluentloop.config import get_settings
    from fluentloop.llm.router import llm_gateway, task_profile
    from fluentloop.llm.schemas import QuizDistractors
    from fluentloop.llm.tasks import LLMTask

    cfg = settings or get_settings()
    try:
        profile = task_profile(LLMTask.QUIZ_DISTRACTORS, cfg)
        result = llm_gateway(cfg).run_json(
            LLMTask.QUIZ_DISTRACTORS,
            {
                "target": item.text,
                "definition": item.meaning or item.explanation,
                "type": item.type,
                "level": item.level,
            },
            QuizDistractors,
            model=profile.model,
            fallback=lambda: QuizDistractors(options=[]),
        )
    except Exception:
        LOG.warning("Distractor generation failed for item %s", item.id)
        return []
    target = item.text.strip().casefold()
    return [
        option.strip()
        for option in result.options
        if option.strip() and option.strip().casefold() != target
    ][:DISTRACTOR_COUNT]


def option_glossary(
    session: Session,
    user: User,
    options: list[str],
    correct_index: int,
) -> list[tuple[str, str]]:
    """(text, meaning) for the options that were not the answer.

    A wrong option the learner just rejected is a free teaching moment: they
    have already thought about it. Meanings are looked up from the learner's
    own items; bank distractors that are not in their base yet come back with
    an empty meaning and are still listed by name.
    """

    from sqlalchemy import func

    notes: list[tuple[str, str]] = []
    for index, option in enumerate(options):
        if index == correct_index:
            continue
        text = str(option).strip()
        if not text:
            continue
        item = session.scalar(
            select(LearningItem).where(
                LearningItem.user_id == user.id,
                func.lower(LearningItem.text) == text.casefold(),
            )
        )
        meaning = ""
        if item is not None:
            meaning = (item.meaning or item.explanation or "").strip()
        notes.append((text, meaning))
    return notes


def build_quiz_spec(
    session: Session,
    user: User,
    item: LearningItem,
    *,
    distractors: list[str] | None = None,
    settings: Any | None = None,
    allow_llm: bool = True,
) -> QuizSpec | None:
    """Assemble a four-option quiz, or None when there is nothing to ask."""

    definition = (item.meaning or item.explanation or "").strip()
    if not definition:
        return None

    options = distractors if distractors is not None else cached_distractors(item)
    if len(options) < DISTRACTOR_COUNT:
        options = select_distractors(session, user, item)
        if len(options) >= DISTRACTOR_COUNT:
            cache_distractors(session, item, options)
    if len(options) < DISTRACTOR_COUNT and allow_llm:
        options = llm_distractors(item, settings)
        if len(options) >= DISTRACTOR_COUNT:
            cache_distractors(session, item, options)
    if len(options) < DISTRACTOR_COUNT:
        return None

    options = options[:DISTRACTOR_COUNT]
    correct_index = _stable_rank(item.id, item.id) % QUIZ_OPTION_COUNT
    ordered = list(options)
    ordered.insert(correct_index, item.text)
    return QuizSpec(
        item_id=item.id,
        question=question_for(item),
        options=ordered,
        correct_index=correct_index,
        solution=definition,
    )


def evening_quiz(
    session: Session,
    user: User,
    *,
    now: datetime | None = None,
    settings: Any | None = None,
    allow_llm: bool = True,
) -> QuizSpec | None:
    """Pick an item for tonight's quiz and build the question for it."""

    for item in select_cards(session, user, count=5, now=now):
        if item.type not in CARD_ITEM_TYPES:
            continue
        spec = build_quiz_spec(
            session, user, item, settings=settings, allow_llm=allow_llm
        )
        if spec is not None:
            return spec
    return None
