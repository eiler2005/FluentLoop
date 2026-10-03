"""Bounded, fail-closed maintenance of variants on approved personal targets."""

from __future__ import annotations

import asyncio
import re
from copy import deepcopy
from dataclasses import dataclass
from datetime import UTC, datetime
from difflib import SequenceMatcher
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt
from sqlalchemy import select, update
from sqlalchemy.orm import Session, sessionmaker

from fluentloop.config import Settings
from fluentloop.db.models import LearningItem, PracticeAttempt, PracticeSession, User
from fluentloop.learning_prefs import is_simple_mode
from fluentloop.llm.router import llm_gateway, task_profile
from fluentloop.llm.tasks import LLMTask
from fluentloop.simple_learning import CHOICE, question_fingerprint
from fluentloop.vocab_loop import local_date

DAILY_CANDIDATES = 2
MAX_ITEM_VARIANTS = 12
MAX_PROFILE_VARIANTS = 120


class VariantDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    prompt: str = Field(min_length=15, max_length=800)
    options: list[str] = Field(min_length=3, max_length=4)
    correct_index: StrictInt
    explanation_ru: str = Field(min_length=15, max_length=700)
    production_prompt: str = Field(min_length=15, max_length=600)


class QuestionReview(BaseModel):
    model_config = ConfigDict(extra="forbid")

    correct_index: StrictInt = -1
    unambiguous: StrictBool = False
    target_aligned: StrictBool = False
    level_appropriate: StrictBool = False
    explanation_correct: StrictBool = False
    novel_context: StrictBool = False

    def accepts(self, question: dict, *, require_novel: bool = True) -> bool:
        return (
            self.correct_index == question.get("correct_index")
            and self.unambiguous
            and self.target_aligned
            and self.level_appropriate
            and self.explanation_correct
            and (self.novel_context or not require_novel)
        )


@dataclass(frozen=True)
class MaintenanceSummary:
    profiles: int = 0
    attempted: int = 0
    published: int = 0
    rejected: int = 0


def _questions(item: LearningItem) -> list[dict]:
    metadata = item.metadata_json or {}
    return [
        question
        for question in [
            metadata.get("simple_question"),
            *metadata.get("simple_question_variants", []),
        ]
        if isinstance(question, dict)
    ]


def _personal_items(session: Session, user: User) -> list[LearningItem]:
    items = list(
        session.scalars(
            select(LearningItem)
            .where(
                LearningItem.user_id == user.id,
                LearningItem.is_template.is_(False),
                LearningItem.status == "active",
            )
            .order_by(LearningItem.id)
        )
    )
    return [
        item
        for item in items
        if any(
            isinstance((item.metadata_json or {}).get(key), dict)
            for key in ("adaptive_curriculum", "lang_lessons")
        )
    ]


def _lock_user(session: Session, user: User) -> None:
    session.execute(
        update(User).where(User.id == user.id).values(updated_at=User.updated_at)
    )
    session.refresh(user)


def _quarantine(
    item: LearningItem, fingerprint: str, reason: str, now: datetime
) -> bool:
    metadata = deepcopy(item.metadata_json or {})
    quality = metadata.setdefault("question_quality", {})
    if quality.get(fingerprint, {}).get("status") == "quarantined":
        return False
    found = False
    for question in [
        metadata.get("simple_question"),
        *metadata.get("simple_question_variants", []),
    ]:
        if isinstance(question, dict) and question_fingerprint(question) == fingerprint:
            question["quality_status"] = "quarantined"
            found = True
    if not found:
        return False
    quality[fingerprint] = {
        "status": "quarantined",
        "reason": reason,
        "at": now.isoformat(),
    }
    item.metadata_json = metadata
    return True


def report_question_issue(
    session: Session, user: User, run_id: int, index: int
) -> bool:
    """Report one's answered question; foreign/stale forged targets are ignored."""
    _lock_user(session, user)
    attempt = session.scalar(
        select(PracticeAttempt)
        .join(PracticeSession)
        .where(
            PracticeSession.user_id == user.id,
            PracticeSession.id == run_id,
            PracticeAttempt.exercise_index == index,
            PracticeAttempt.exercise_type == CHOICE,
        )
    )
    if attempt is None:
        return False
    fingerprint = (attempt.feedback or {}).get("fingerprint")
    if not fingerprint:
        return False
    changed = False
    for item in session.scalars(
        select(LearningItem).where(
            LearningItem.id.in_(attempt.target_learning_item_ids or []),
            LearningItem.user_id == user.id,
            LearningItem.is_template.is_(False),
        )
    ):
        changed = (
            _quarantine(item, fingerprint, "learner_report", datetime.now(UTC))
            or changed
        )
    session.flush()
    return changed


def _normalized(text: str) -> str:
    return " ".join(re.findall(r"[a-z]+", text.casefold()))


def validate_variant(draft: VariantDraft, source: dict, existing: list[dict]) -> dict:
    """Validate independently of the LLM, preserving target/stage provenance."""
    if not 0 <= draft.correct_index < len(draft.options):
        raise ValueError("Invalid answer key")
    values = [draft.prompt, draft.production_prompt, *draft.options]
    if any(
        not re.search(r"[A-Za-z]", value) or re.search(r"[А-Яа-яЁё]", value)
        for value in values
    ):
        raise ValueError("Questions must be in English")
    if any(not value.strip() or len(value) > 300 for value in draft.options):
        raise ValueError("Invalid option")
    if len({_normalized(value) for value in draft.options}) != len(draft.options):
        raise ValueError("Duplicate options")
    if not re.search(r"[А-Яа-яЁё]", draft.explanation_ru):
        raise ValueError("Russian explanation required")
    adaptive = deepcopy(source.get("adaptive") or {})
    if adaptive and (
        adaptive.get("version") != 1
        or adaptive.get("stage")
        not in {
            "b2",
            "b2_plus",
            "c1_intro",
        }
    ):
        raise ValueError("Approved adaptive source required")
    if adaptive and (
        adaptive.get("role") not in {"practice", "transfer"}
        or not adaptive.get("topic_id")
    ):
        raise ValueError("Approved target required")
    if not adaptive and not source.get("approved_legacy"):
        raise ValueError("Approved source required")
    question = draft.model_dump()
    question["category"] = source.get("category", "grammar")
    question["level"] = source.get("level", "B2")
    for key in ("target_phrase", "target_construction"):
        if source.get(key):
            question[key] = source[key]
    question["fingerprint"] = question_fingerprint(question)
    if adaptive:
        question["adaptive"] = adaptive
        adaptive["variant_id"] = "generated-" + question["fingerprint"][:24]
    new_text = _normalized(draft.prompt)
    for old in existing:
        if question_fingerprint(old) == question["fingerprint"]:
            raise ValueError("Duplicate content")
        if (
            SequenceMatcher(
                None, new_text, _normalized(str(old.get("prompt", "")))
            ).ratio()
            >= 0.86
        ):
            raise ValueError("Near-duplicate context")
    return question


def _audit_payload(question: dict, source: dict, excluded: list[dict]) -> dict:
    # No user answers, names, identifiers or private source material are sent.
    return {
        "topic": (source.get("adaptive") or {}).get(
            "topic_id", source.get("topic", "")
        ),
        "stage": (source.get("adaptive") or {}).get("stage", source.get("level", "B2")),
        "target": source.get("production_prompt", ""),
        "prompt": question["prompt"],
        "options": question["options"],
        "explanation_ru": question.get("explanation_ru", ""),
        "production_prompt": question.get("production_prompt", ""),
        "excluded_contexts": [old["prompt"] for old in excluded][-20:],
    }


def _review(
    gateway: Any, settings: Settings, question: dict, source: dict, excluded: list[dict]
) -> QuestionReview:
    profile = task_profile(LLMTask.QUESTION_REVIEW, settings)
    return gateway.run_json(
        LLMTask.QUESTION_REVIEW,
        _audit_payload(question, source, excluded),
        QuestionReview,
        model=profile.model,
        thinking=profile.thinking,
        reasoning_effort=profile.reasoning_effort,
        fallback=QuestionReview(),
    )


def _jobs(session: Session, user: User, now: datetime) -> list[dict]:
    from fluentloop.adaptive_learning import generation_need

    items = _personal_items(session, user)
    if (
        sum(
            len((item.metadata_json or {}).get("simple_question_variants", []))
            for item in items
        )
        >= MAX_PROFILE_VARIANTS
    ):
        return []
    attempts = list(
        session.scalars(
            select(PracticeAttempt)
            .join(PracticeSession)
            .where(
                PracticeSession.user_id == user.id,
                PracticeAttempt.exercise_type == CHOICE,
            )
            .order_by(PracticeAttempt.created_at, PracticeAttempt.id)
        )
    )
    history: dict[str, list[PracticeAttempt]] = {}
    for attempt in attempts:
        history.setdefault(str((attempt.feedback or {}).get("fingerprint")), []).append(
            attempt
        )
    jobs = []
    for item in items:
        metadata = item.metadata_json or {}
        if len(metadata.get("simple_question_variants", [])) >= MAX_ITEM_VARIANTS:
            continue
        for question in _questions(item):
            question = deepcopy(question)
            if not question.get("adaptive") and metadata.get("lang_lessons"):
                question["approved_legacy"] = True
            fingerprint = question_fingerprint(question)
            quality = metadata.get("question_quality", {}).get(fingerprint, {})
            records = history.get(fingerprint, [])
            if quality.get("replacement"):
                continue
            reason = ""
            if quality.get("status") == "quarantined":
                reason = "quarantined"
            elif (
                len(records) >= 5
                and len(records) > quality.get("reviewed_answers", 0)
                and sum(row.status != "correct" for row in records[-5:]) >= 3
            ):
                reason = "repeated_errors"
            if reason:
                jobs.append(
                    {
                        "item_id": item.id,
                        "source": deepcopy(question),
                        "reason": reason,
                        "answers": len(records),
                    }
                )
    need = generation_need(session, user, now=now)
    if need:
        for item in items:
            if (
                len((item.metadata_json or {}).get("simple_question_variants", []))
                >= MAX_ITEM_VARIANTS
            ):
                continue
            for question in _questions(item):
                adaptive = question.get("adaptive") or {}
                if all(
                    adaptive.get(key) == need.get(key)
                    for key in ("topic_id", "stage", "role")
                ):
                    jobs.append(
                        {
                            "item_id": item.id,
                            "source": deepcopy(question),
                            "reason": "shortage",
                            "answers": 0,
                        }
                    )
                    break
            else:
                continue
            break
    unique = {}
    for job in jobs:
        unique.setdefault(job["item_id"], job)
    remaining = MAX_PROFILE_VARIANTS - sum(
        len((item.metadata_json or {}).get("simple_question_variants", []))
        for item in items
    )
    return list(unique.values())[: min(DAILY_CANDIDATES, remaining)]


def _claim(
    session: Session, user: User, now: datetime
) -> tuple[str, list[dict], list[dict]] | None:
    _lock_user(session, user)
    prefs = deepcopy(user.preferences_json or {})
    learning = prefs.setdefault("learning", {})
    if not is_simple_mode(user) or not learning.get("adaptive_auto_expand", False):
        return None
    day = local_date(user, now=now).isoformat()
    if learning.get("bank_maintenance", {}).get("day") == day:
        return None
    jobs = _jobs(session, user, now)
    if not jobs:
        return None
    token = uuid4().hex
    learning["bank_maintenance"] = {
        "day": day,
        "token": token,
        "claimed": len(jobs),
        "published": 0,
        "rejected": 0,
    }
    user.preferences_json = prefs
    existing = [
        deepcopy(question)
        for item in _personal_items(session, user)
        for question in _questions(item)
    ]
    session.flush()
    return token, jobs, existing


def _store_result(
    session: Session,
    user: User,
    token: str,
    job: dict,
    question: dict | None,
    review: QuestionReview | None,
    original_bad: bool,
    now: datetime,
) -> bool:
    _lock_user(session, user)
    prefs = deepcopy(user.preferences_json or {})
    learning = prefs.setdefault("learning", {})
    state = learning.get("bank_maintenance", {})
    if (
        state.get("token") != token
        or not learning.get("adaptive_auto_expand")
        or not is_simple_mode(user)
    ):
        return False
    item = session.scalar(
        select(LearningItem)
        .where(
            LearningItem.id == job["item_id"],
            LearningItem.user_id == user.id,
            LearningItem.is_template.is_(False),
            LearningItem.status == "active",
        )
        .execution_options(populate_existing=True)
    )
    published = False
    if item is not None:
        source_fingerprint = question_fingerprint(job["source"])
        if original_bad:
            _quarantine(item, source_fingerprint, "review_failed", now)
        metadata = deepcopy(item.metadata_json or {})
        quality = metadata.setdefault("question_quality", {}).setdefault(
            source_fingerprint, {}
        )
        quality["reviewed_answers"] = job["answers"]
        quality["last_checked_at"] = now.isoformat()
        variants = metadata.setdefault("simple_question_variants", [])
        existing = [
            candidate
            for owned in _personal_items(session, user)
            for candidate in _questions(owned)
        ]
        total_variants = sum(
            len((owned.metadata_json or {}).get("simple_question_variants", []))
            for owned in _personal_items(session, user)
        )
        if question is not None:
            try:
                validate_variant(
                    VariantDraft.model_validate(
                        {key: question[key] for key in VariantDraft.model_fields}
                    ),
                    job["source"],
                    existing,
                )
            except (ValueError, KeyError):
                question = None
        if (
            question is not None
            and review is not None
            and review.accepts(question)
            and len(variants) < MAX_ITEM_VARIANTS
            and total_variants < MAX_PROFILE_VARIANTS
            and question_fingerprint(question)
            not in {question_fingerprint(candidate) for candidate in existing}
        ):
            question = deepcopy(question)
            question["quality_status"] = "verified"
            question["provenance"] = {
                "method": "generated_and_independently_reviewed",
                "version": 1,
                "parent_fingerprint": source_fingerprint,
                "created_at": now.isoformat(),
            }
            variants.append(question)
            if quality.get("status") == "quarantined":
                quality["replacement"] = question["fingerprint"]
            published = True
        if not published:
            quality["last_result"] = "rejected_or_unavailable"
        item.metadata_json = metadata
    key = "published" if published else "rejected"
    state[key] = state.get(key, 0) + 1
    user.preferences_json = prefs
    session.flush()
    return published


def run_question_maintenance(
    settings: Settings,
    session_factory: sessionmaker,
    *,
    now: datetime | None = None,
    gateway: Any | None = None,
) -> MaintenanceSummary:
    """No network under DB locks; day claims survive restarts and concurrent workers."""
    current = now or datetime.now(UTC)
    if gateway is None and settings.ai_provider not in {"deepseek", "qwen"}:
        return MaintenanceSummary()
    gateway = gateway or llm_gateway(settings)
    if getattr(gateway, "api_key", True) == "":
        return MaintenanceSummary()
    with session_factory() as session:
        user_ids = list(session.scalars(select(User.id).order_by(User.id)))
    profiles = attempted = published = rejected = 0
    for user_id in user_ids:
        with session_factory.begin() as session:
            claim = _claim(session, session.get(User, user_id), current)
        if claim is None:
            continue
        profiles += 1
        token, jobs, existing = claim
        for job in jobs:
            attempted += 1
            question = review = None
            original_bad = False
            source = job["source"]
            try:
                if job["reason"] == "repeated_errors":
                    original = _review(gateway, settings, source, source, [])
                    # An unavailable review is not evidence against the original.
                    original_bad = original.correct_index >= 0 and not original.accepts(
                        source, require_novel=False
                    )
                profile = task_profile(LLMTask.QUESTION_VARIANT, settings)
                draft = gateway.run_json(
                    LLMTask.QUESTION_VARIANT,
                    {
                        "source": {
                            key: source.get(key)
                            for key in (
                                "prompt",
                                "options",
                                "explanation_ru",
                                "production_prompt",
                                "adaptive",
                            )
                        },
                        "reason": job["reason"],
                        "excluded_contexts": [old["prompt"] for old in existing][-20:],
                    },
                    VariantDraft,
                    model=profile.model,
                )
                question = validate_variant(draft, source, existing)
                review = _review(gateway, settings, question, source, existing)
            except Exception:
                # Do not log provider payloads or private learner content.
                question = None
            with session_factory.begin() as session:
                accepted = _store_result(
                    session,
                    session.get(User, user_id),
                    token,
                    job,
                    question,
                    review,
                    original_bad,
                    current,
                )
            if accepted:
                published += 1
                existing.append(question)
            else:
                rejected += 1
    return MaintenanceSummary(profiles, attempted, published, rejected)


async def maintain_question_bank(
    settings: Settings, session_factory: sessionmaker
) -> MaintenanceSummary:
    return await asyncio.to_thread(run_question_maintenance, settings, session_factory)
