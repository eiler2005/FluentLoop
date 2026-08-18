"""Filling in what a learner card needs beyond the phrase itself.

A card with only an English gloss is too easy to read past: the eye recognises
the shape without the meaning ever landing. What makes it stick is a Russian
translation to anchor it and an example that actually contains the phrase.

Bank entries ship with an English meaning and an example but no Russian, and a
word the learner types in arrives with nothing at all. Both are filled here,
once per item, and cached on the item.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

from fluentloop.db.models import LearningItem
from fluentloop.vocab_loop import english_definition, has_cyrillic, russian_definition

LOG = logging.getLogger(__name__)

MAX_SYNONYMS = 3
MAX_COLLOCATIONS = 3


def stored_russian(item: LearningItem) -> str:
    """The Russian gloss wherever it ended up.

    It lands in `meaning` or `explanation` when one is free, and in metadata
    when both are taken, so every reader has to look in all three.
    """

    direct = russian_definition(item)
    if direct:
        return direct
    return str((item.metadata_json or {}).get("russian", "")).strip()


def needs_enrichment(item: LearningItem) -> bool:
    """True while the card is still missing a translation or an example.

    Must agree with where enrich_item actually writes: checking only the two
    text fields left metadata-stored translations looking permanently missing,
    so the backfill re-processed the same items on every run.
    """

    return not stored_russian(item) or not (item.examples or [])


def generate_card(item: LearningItem, settings: Any | None = None):
    """Ask the model for the missing pieces. Returns None if unavailable."""

    from fluentloop.config import get_settings
    from fluentloop.llm.router import llm_gateway, task_profile
    from fluentloop.llm.schemas import WordCard
    from fluentloop.llm.tasks import LLMTask

    cfg = settings or get_settings()
    try:
        profile = task_profile(LLMTask.WORD_CARD, cfg)
        return llm_gateway(cfg).run_json(
            LLMTask.WORD_CARD,
            {
                "phrase": item.text,
                "type": item.type,
                "level": item.level,
                "known_meaning": english_definition(item),
            },
            WordCard,
            model=profile.model,
            fallback=lambda: WordCard(),
        )
    except Exception:
        LOG.warning("Word-card generation failed for item %s", item.id)
        return None


def enrich_item(
    session: Session,
    item: LearningItem,
    *,
    settings: Any | None = None,
    card: Any | None = None,
) -> bool:
    """Fill in the gaps on one item. Returns whether anything changed.

    Never overwrites what the learner or the bank already provided - a
    generated gloss is worth less than a curated one.
    """

    if card is None:
        if not needs_enrichment(item):
            return False
        card = generate_card(item, settings)
    if card is None:
        return False

    changed = False

    if not english_definition(item) and card.meaning and not has_cyrillic(card.meaning):
        item.explanation = card.meaning.strip()
        changed = True

    if not russian_definition(item) and card.russian and has_cyrillic(card.russian):
        # The English gloss stays where it is; the Russian one goes to
        # whichever field is still free so both survive.
        if not (item.meaning or "").strip():
            item.meaning = card.russian.strip()
        elif not (item.explanation or "").strip():
            item.explanation = card.russian.strip()
        else:
            metadata = dict(item.metadata_json or {})
            metadata["russian"] = card.russian.strip()
            item.metadata_json = metadata
        changed = True

    example = (card.example or "").strip()
    if not (item.examples or []) and example:
        item.examples = [example]
        changed = True

    metadata = dict(item.metadata_json or {})
    if card.synonyms and not metadata.get("synonyms"):
        metadata["synonyms"] = [
            s.strip() for s in card.synonyms[:MAX_SYNONYMS] if s.strip()
        ]
        changed = True
    if card.collocations and not metadata.get("collocations"):
        metadata["collocations"] = [
            c.strip() for c in card.collocations[:MAX_COLLOCATIONS] if c.strip()
        ]
        changed = True
    if metadata != (item.metadata_json or {}):
        item.metadata_json = metadata

    if changed:
        session.add(item)
        session.flush()
    return changed
