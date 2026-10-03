"""Replay topic evidence without treating repeated recognition as mastery."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from difflib import SequenceMatcher

from sqlalchemy import select
from sqlalchemy.orm import Session

from fluentloop.db.models import LearningItem, PracticeAttempt, PracticeSession, User
from fluentloop.vocab_loop import local_date

TOPIC_TITLES = {
    "aspect": "Времена и аспект",
    "future_planning": "Планы и будущее",
    "conditionals": "Условия и альтернативы",
    "modals": "Модальность",
    "reporting": "Передача чужих слов",
    "information_structure": "Акцент и структура предложения",
    "cohesion": "Связность речи",
    "diplomatic_communication": "Дипломатичное общение",
    "delivery_collocations": "Работа и поставка продукта",
    "incident_communication": "Инциденты и риски",
}
STAGES = ("b2", "b2_plus", "c1_intro")
PRACTICE_REQUIRED = 5
TRANSFER_DELAY = timedelta(hours=24)


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def adaptive_metadata(question: dict) -> dict | None:
    raw = question.get("adaptive")
    if not isinstance(raw, dict):
        return None
    if (
        raw.get("version") != 1
        or raw.get("topic_id") not in TOPIC_TITLES
        or raw.get("stage") not in STAGES
        or raw.get("role") not in {"practice", "transfer"}
        or not isinstance(raw.get("variant_id"), str)
        or not raw["variant_id"].strip()
    ):
        return None
    return {
        key: raw[key] for key in ("version", "topic_id", "stage", "role", "variant_id")
    }


@dataclass(frozen=True)
class TopicProgress:
    topic_id: str
    title: str
    stage: str
    practice_successes: int
    practice_required: int
    practice_accuracy: float
    practice_ready: bool
    transfer_successes: int
    transfer_required: int
    production_successes: int
    production_required: int
    strong_b2: bool
    mastered: bool
    repair: bool
    next_action: str
    practice_ready_at: datetime | None = None


@dataclass(frozen=True)
class CurriculumProgress:
    topics: tuple[TopicProgress, ...]
    strong_b2_topics: int
    total_topics: int
    c1_unlocked: bool


@dataclass
class _Evidence:
    practice: dict[str, tuple[datetime, str]] = field(default_factory=dict)
    outcomes: list[bool] = field(default_factory=list)
    transfers: set[str] = field(default_factory=set)
    production: set[int] = field(default_factory=set)
    failures: list[tuple[datetime, str]] = field(default_factory=list)
    ready_at: datetime | None = None
    practice_dates: set[str] = field(default_factory=set)
    last_success: datetime | None = None
    repair: bool = False

    def ready(self) -> bool:
        if self.ready_at is not None:
            return True
        stamps = [stamp for stamp, _ in self.practice.values()]
        return bool(
            len(stamps) >= PRACTICE_REQUIRED
            and len(self.practice_dates) >= 2
            and self.last_success is not None
            and self.last_success - min(stamps) >= TRANSFER_DELAY
            and self.accuracy >= 0.8
        )

    @property
    def accuracy(self) -> float:
        recent = self.outcomes[-10:]
        return sum(recent) / len(recent) if recent else 0.0

    def mastered(self, stage: str) -> bool:
        return (
            self.ready()
            and len(self.transfers) >= (1 if stage == "b2" else 2)
            and (stage == "b2" or bool(self.production))
        )


def displayed_fingerprints(session: Session, user: User) -> set[str]:
    """Include abandoned snapshots: seeing a key makes a transfer familiar."""
    fingerprints: set[str] = set()
    for run in session.scalars(
        select(PracticeSession).where(PracticeSession.user_id == user.id)
    ):
        for question in run.exercises or []:
            if question.get("fingerprint"):
                fingerprints.add(str(question["fingerprint"]))
    for attempt in session.scalars(
        select(PracticeAttempt)
        .join(PracticeSession)
        .where(PracticeSession.user_id == user.id)
    ):
        if (attempt.feedback or {}).get("fingerprint"):
            fingerprints.add(str(attempt.feedback["fingerprint"]))
    return fingerprints


def _replay(
    session: Session, user: User, now: datetime
) -> dict[tuple[str, str], _Evidence]:
    evidence = {
        (topic, stage): _Evidence() for topic in TOPIC_TITLES for stage in STAGES
    }
    items = list(
        session.scalars(
            select(LearningItem).where(
                LearningItem.user_id == user.id,
                LearningItem.is_template.is_(False),
            )
        )
    )
    owned = {item.id for item in items}
    quarantined = set()
    for item in items:
        metadata = item.metadata_json or {}
        quarantined.update(
            fingerprint
            for fingerprint, state in (metadata.get("question_quality") or {}).items()
            if isinstance(state, dict) and state.get("status") == "quarantined"
        )
        for question in [
            metadata.get("simple_question"),
            *(metadata.get("simple_question_variants") or []),
        ]:
            if (
                isinstance(question, dict)
                and question.get("quality_status") == "quarantined"
            ):
                quarantined.add(question.get("fingerprint"))
    attempts = session.scalars(
        select(PracticeAttempt)
        .join(PracticeSession)
        .where(PracticeSession.user_id == user.id)
        .order_by(PracticeAttempt.created_at, PracticeAttempt.id)
    )
    for attempt in attempts:
        feedback = attempt.feedback or {}
        contract = adaptive_metadata({"adaptive": feedback.get("adaptive")})
        stamp = _utc(attempt.created_at)
        if (
            contract is None
            or stamp > now
            or feedback.get("fingerprint") in quarantined
            or feedback.get("selection_mode") != "normal"
            or not set(attempt.target_learning_item_ids or []).intersection(owned)
        ):
            continue
        topic, stage = contract["topic_id"], contract["stage"]
        current = evidence[topic, stage]
        variant = contract["variant_id"]
        # A stale higher-stage snapshot can be answered after a repair, but
        # cannot bypass the topic prerequisite or global C1 gate.
        if stage != "b2" and not evidence[topic, "b2"].mastered("b2"):
            continue
        if stage == "c1_intro" and not all(
            evidence[other, "b2_plus"].mastered("b2_plus") for other in TOPIC_TITLES
        ):
            continue
        correct = attempt.status == "correct"
        production = feedback.get("answer_modality") == "production"
        if production and feedback.get("genuine_evaluation") is not True:
            continue
        if feedback.get("answer_modality") not in {"production", "recognition"}:
            continue
        if attempt.status in {"incorrect", "partial"}:
            current.failures = [
                (date, key)
                for date, key in current.failures
                if stamp - date <= timedelta(days=14)
            ]
            current.failures.append((stamp, variant))
            if len({key for _, key in current.failures}) >= 2:
                evidence[topic, stage] = current = _Evidence(repair=True)
                for higher in STAGES[STAGES.index(stage) + 1 :]:
                    evidence[topic, higher] = _Evidence(repair=True)
        if production:
            if (
                correct
                and feedback.get("genuine_evaluation") is True
                and current.ready()
                and current.ready_at is not None
                and stamp >= current.ready_at
                and feedback.get("independent_production") is True
            ):
                current.production.add(attempt.id)
            continue
        if contract["role"] == "practice":
            current.outcomes.append(correct)
            if correct:
                current.practice.setdefault(
                    variant, (stamp, local_date(user, now=stamp).isoformat())
                )
                current.practice_dates.add(local_date(user, now=stamp).isoformat())
                current.last_success = stamp
            if current.ready() and current.ready_at is None:
                current.ready_at = stamp
                current.repair = False
        elif (
            correct
            and feedback.get("first_exposure") is True
            and feedback.get("transfer_eligible") is True
            and current.ready()
            and current.ready_at is not None
            and stamp >= current.ready_at + TRANSFER_DELAY
        ):
            current.transfers.add(variant)
    return evidence


def curriculum_progress(
    session: Session, user: User, *, now: datetime | None = None
) -> CurriculumProgress:
    current_time = _utc(now or datetime.now(UTC))
    evidence = _replay(session, user, current_time)
    strong = {
        topic: evidence[topic, "b2"].mastered("b2")
        and evidence[topic, "b2_plus"].mastered("b2_plus")
        for topic in TOPIC_TITLES
    }
    unlocked = all(strong.values())
    topics = []
    for topic, title in TOPIC_TITLES.items():
        stage = "b2"
        if evidence[topic, "b2"].mastered("b2"):
            stage = "b2_plus"
        if strong[topic] and unlocked:
            stage = "c1_intro"
        state = evidence[topic, stage]
        transfer_required = 1 if stage == "b2" else 2
        production_required = 0 if stage == "b2" else 1
        if not state.ready():
            action = (
                "practice"
                if len(state.practice) < PRACTICE_REQUIRED or state.accuracy < 0.8
                else "spaced_practice"
            )
        elif len(state.transfers) < transfer_required:
            action = (
                "transfer_wait"
                if current_time < state.ready_at + TRANSFER_DELAY
                else "transfer"
            )
        elif production_required and not state.production:
            action = "production"
        else:
            action = "maintain" if unlocked else "c1_locked"
        topics.append(
            TopicProgress(
                topic,
                title,
                stage,
                len(state.practice),
                PRACTICE_REQUIRED,
                state.accuracy,
                state.ready(),
                len(state.transfers),
                transfer_required,
                len(state.production),
                production_required,
                strong[topic],
                state.mastered(stage),
                state.repair,
                action,
                state.ready_at,
            )
        )
    return CurriculumProgress(
        tuple(topics), sum(strong.values()), len(topics), unlocked
    )


def topic_progress(
    session: Session, user: User, *, now: datetime | None = None
) -> list[TopicProgress]:
    return list(curriculum_progress(session, user, now=now).topics)


def eligible_question(
    question: dict,
    progress: CurriculumProgress,
    seen_fingerprints: set[str],
    *,
    now: datetime,
    repeat_familiar: bool = False,
) -> bool:
    if question.get("quality_status") == "quarantined":
        return False
    meta = adaptive_metadata(question)
    if meta is None:
        # Fail closed on malformed curriculum contracts, preserve legacy items.
        return "adaptive" not in question
    topic = next(
        entry for entry in progress.topics if entry.topic_id == meta["topic_id"]
    )
    if STAGES.index(meta["stage"]) > STAGES.index(topic.stage):
        return False
    if meta["role"] == "transfer":
        return bool(
            not repeat_familiar
            and meta["stage"] == topic.stage
            and topic.practice_ready
            and topic.practice_ready_at is not None
            and _utc(now) >= topic.practice_ready_at + TRANSFER_DELAY
            and question.get("fingerprint") not in seen_fingerprints
        )
    return True


def question_evidence(
    session: Session, user: User, question: dict, *, now: datetime
) -> dict:
    meta = adaptive_metadata(question)
    if meta is None:
        return {}
    progress = curriculum_progress(session, user, now=now)
    seen = displayed_fingerprints(session, user)
    return {
        "adaptive": meta,
        "first_exposure": question.get("fingerprint") not in seen,
        "transfer_eligible": meta["role"] == "transfer"
        and eligible_question(question, progress, seen, now=now),
    }


def generation_need(
    session: Session, user: User, *, now: datetime | None = None
) -> dict | None:
    """Find a current-stage shortage on an approved personal item."""
    current = _utc(now or datetime.now(UTC))
    progress = curriculum_progress(session, user, now=current)
    seen = displayed_fingerprints(session, user)
    items = list(
        session.scalars(
            select(LearningItem)
            .where(
                LearningItem.user_id == user.id,
                LearningItem.status == "active",
                LearningItem.is_template.is_(False),
            )
            .order_by(LearningItem.id)
        )
    )
    for topic in sorted(
        progress.topics, key=lambda entry: (not entry.repair, entry.strong_b2)
    ):
        if topic.next_action in {"production", "c1_locked", "maintain"}:
            continue
        role = "transfer" if topic.practice_ready else "practice"
        matches = []
        eligible = 0
        for item in items:
            metadata = item.metadata_json or {}
            questions = [
                metadata.get("simple_question"),
                *(metadata.get("simple_question_variants") or []),
            ]
            for question in questions:
                if not isinstance(question, dict):
                    continue
                contract = adaptive_metadata(question)
                if contract is None or contract["topic_id"] != topic.topic_id:
                    continue
                matches.append(item)
                if (
                    contract["stage"] == topic.stage
                    and contract["role"] == role
                    and question.get("quality_status") != "quarantined"
                    and question.get("fingerprint") not in seen
                ):
                    eligible += 1
        if matches and eligible < (2 if role == "transfer" else 3):
            return {
                "item_id": matches[0].id,
                "topic_id": topic.topic_id,
                "stage": topic.stage,
                "role": role,
                "existing_unseen": eligible,
                "reason": "unseen_transfer_shortage"
                if role == "transfer"
                else "practice_shortage",
            }
    return None


def independent_production(answer: str, question: dict) -> bool:
    def normalized(value: str) -> str:
        return re.sub(r"[^\w]+", " ", value.casefold()).strip()

    text = normalized(answer)
    examples = [question.get("source_example", ""), question.get("expected_answer", "")]
    if len(text.split()) < 4:
        return False
    for example in examples:
        reference = normalized(str(example))
        if not reference:
            continue
        if text == reference:
            return False
        # A full model sentence with a preface/suffix is still a copied answer.
        if len(reference.split()) >= 4 and f" {reference} " in f" {text} ":
            return False
        reference_tokens, answer_tokens = reference.split(), text.split()
        if min(len(reference_tokens), len(answer_tokens)) >= 6:
            overlap = len(set(reference_tokens) & set(answer_tokens)) / min(
                len(set(reference_tokens)), len(set(answer_tokens))
            )
            if (
                overlap >= 0.8
                and SequenceMatcher(None, reference_tokens, answer_tokens).ratio()
                >= 0.8
            ):
                return False
    return True


def is_reserved_transfer(item: LearningItem) -> bool:
    metadata = item.metadata_json or {}
    return any(
        isinstance(question, dict)
        and (adaptive_metadata(question) or {}).get("role") == "transfer"
        for question in [
            metadata.get("simple_question"),
            *(metadata.get("simple_question_variants") or []),
        ]
    )


def is_adaptive_item(item: LearningItem) -> bool:
    """Keep curriculum exercises out of generic previews and answer-taking flows."""
    metadata = item.metadata_json or {}
    return bool(metadata.get("adaptive_curriculum")) or any(
        isinstance(question, dict) and "adaptive" in question
        for question in [
            metadata.get("simple_question"),
            *(metadata.get("simple_question_variants") or []),
        ]
    )
