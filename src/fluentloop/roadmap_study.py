"""Personal roadmap practice, separate from adaptive language mastery (ADR-0016)."""

from __future__ import annotations

import re
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from difflib import SequenceMatcher
from functools import lru_cache
from pathlib import Path

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from fluentloop.adaptive_learning import curriculum_progress, independent_production
from fluentloop.db.models import PracticeAttempt, PracticeSession, User
from fluentloop.vocab_loop import local_date
from fluentloop.workplace_roadmap import (
    PLAN_NAMESPACE,
    get_plan,
    load_curriculum,
    read_json,
)

PACK_PATH = Path(__file__).parent / "seeds" / "roadmap_question_pack_v1.json"
QUALITY_NAMESPACE = "roadmap_question_quality"
STAGES = ("b2", "b2_plus", "c1_intro")
COOLDOWN = timedelta(hours=24)


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def enabled(user: User) -> bool:
    preferences = user.preferences_json or {}
    if not isinstance(preferences, dict) or PLAN_NAMESPACE not in preferences:
        return False
    try:
        get_plan(user)
    except ValueError:
        return False
    return True


def validate_question_pack(data: dict, catalog: dict | None = None) -> dict:
    catalog = catalog or load_curriculum()
    if not isinstance(data, dict) or set(data) != {"version", "modules"}:
        raise ValueError("Question pack requires version and modules")
    if type(data["version"]) is not int or data["version"] != 1:
        raise ValueError("Unsupported roadmap question pack")
    modules = data["modules"]
    if not isinstance(modules, list):
        raise ValueError("Question modules must be a list")
    ids = {module["id"] for module in catalog["modules"]}
    sources = {source["id"] for source in catalog["sources"]}
    found = set()
    fields = {
        "prompt",
        "options",
        "correct_index",
        "explanation_ru",
        "target_construction",
        "production_prompts",
        "resource_ids",
    }
    for module in modules:
        if not isinstance(module, dict) or set(module) != {"module_id", "stages"}:
            raise ValueError("Invalid question module")
        identifier = module["module_id"]
        if (
            not isinstance(identifier, str)
            or identifier not in ids
            or identifier in found
        ):
            raise ValueError("Unknown or duplicate module")
        found.add(identifier)
        if not isinstance(module["stages"], dict) or set(module["stages"]) != set(
            STAGES
        ):
            raise ValueError("Every question module requires three stages")
        for question in module["stages"].values():
            if not isinstance(question, dict) or set(question) != fields:
                raise ValueError("Invalid roadmap question fields")
            for field in ("prompt", "explanation_ru", "target_construction"):
                value = question[field]
                if not isinstance(value, str) or not value.strip() or len(value) > 5000:
                    raise ValueError(f"Invalid question {field}")
            options = question["options"]
            if (
                not isinstance(options, list)
                or len(options) != 3
                or not all(
                    isinstance(x, str) and x.strip() and len(x) <= 1000 for x in options
                )
                or len(set(options)) != len(options)
                or type(question["correct_index"]) is not int
                or not 0 <= question["correct_index"] < len(options)
            ):
                raise ValueError("Invalid roadmap answer options")
            prompts = question["production_prompts"]
            if not isinstance(prompts, list) or len(prompts) != 2:
                raise ValueError("Two writing situations are required")
            variants, texts = set(), set()
            for prompt in prompts:
                if (
                    not isinstance(prompt, dict)
                    or set(prompt) != {"variant_id", "prompt"}
                    or not isinstance(prompt["variant_id"], str)
                    or prompt["variant_id"] not in {"a", "b"}
                    or prompt["variant_id"] in variants
                    or not isinstance(prompt["prompt"], str)
                    or not prompt["prompt"].strip()
                    or len(prompt["prompt"]) > 5000
                    or prompt["prompt"] in texts
                ):
                    raise ValueError("Invalid independent writing scenario")
                variants.add(prompt["variant_id"])
                texts.add(prompt["prompt"])
            resources = question["resource_ids"]
            if (
                not isinstance(resources, list)
                or not all(isinstance(x, str) and x in sources for x in resources)
                or len(set(resources)) != len(resources)
            ):
                raise ValueError("Invalid roadmap resources")
    if found != ids:
        raise ValueError("Question pack must cover every roadmap module")
    return deepcopy(data)


@lru_cache(maxsize=1)
def load_question_pack() -> dict:
    return validate_question_pack(read_json(PACK_PATH))


def attempts(session: Session, user: User) -> list[PracticeAttempt]:
    return list(
        session.scalars(
            select(PracticeAttempt)
            .join(PracticeSession)
            .where(PracticeSession.user_id == user.id)
            .order_by(PracticeAttempt.id)
        )
    )


def _quarantined(user: User) -> set[str]:
    quality = (user.preferences_json or {}).get(QUALITY_NAMESPACE) or {}
    return {key for key, value in quality.items() if value == "quarantined"}


def _credited(attempt: PracticeAttempt) -> bool:
    feedback = attempt.feedback or {}
    return bool(
        attempt.exercise_type == "simple_production"
        and attempt.status == "correct"
        and feedback.get("genuine_evaluation") is True
        and feedback.get("independent_production") is True
        and feedback.get("selection_mode") != "familiar"
    )


def _stage_ready(records: list[PracticeAttempt], user: User, stage: str) -> bool:
    relevant = [
        a
        for a in records
        if ((a.feedback or {}).get("roadmap") or {}).get("stage") == stage
    ]
    recognition = any(
        a.exercise_type == "simple_choice"
        and a.status == "correct"
        and (a.feedback or {}).get("selection_mode") != "familiar"
        for a in relevant
    )
    writing = [a for a in relevant if _credited(a)]
    for first in writing:
        for second in writing:
            if (
                first.feedback["roadmap"].get("production_variant_id")
                != second.feedback["roadmap"].get("production_variant_id")
                and local_date(user, now=_utc(first.created_at))
                != local_date(user, now=_utc(second.created_at))
                and abs(_utc(first.created_at) - _utc(second.created_at)) >= COOLDOWN
            ):
                return recognition
    return False


def module_progress(
    session: Session, user: User, *, now: datetime | None = None
) -> list[dict]:
    current = _utc(now or datetime.now(UTC))
    history = attempts(session, user)
    quarantine = _quarantined(user)
    gate = curriculum_progress(session, user, now=current).c1_unlocked
    catalog = load_curriculum()
    plan = get_plan(user, catalog)
    result = []
    for module in catalog["modules"]:
        records = [
            a
            for a in history
            if ((a.feedback or {}).get("roadmap") or {}).get("module_id")
            == module["id"]
            and ((a.feedback or {}).get("roadmap") or {}).get("question_id")
            not in quarantine
            and _utc(a.created_at) <= current
        ]
        b2 = _stage_ready(records, user, "b2")
        b2_plus = b2 and _stage_ready(records, user, "b2_plus")
        stage = "c1_intro" if b2_plus and gate else "b2_plus" if b2 else "b2"
        current_records = [
            a for a in records if a.feedback["roadmap"]["stage"] == stage
        ]
        variants = sorted(
            {
                a.feedback["roadmap"].get("production_variant_id")
                for a in current_records
                if _credited(a)
            }
            - {None}
        )
        recognition = sum(
            a.exercise_type == "simple_choice"
            and a.status == "correct"
            and a.feedback.get("selection_mode") != "familiar"
            for a in current_records
        )
        ready = _stage_ready(records, user, stage)
        result.append(
            {
                "module_id": module["id"],
                "title_ru": module["title_ru"],
                "strand": module["strand"],
                "stage": stage,
                "recognition_correct": recognition,
                "recognition_attempts": sum(
                    a.exercise_type == "simple_choice" for a in current_records
                ),
                "writing_attempts": sum(
                    a.exercise_type == "simple_production" for a in current_records
                ),
                "last_attempt_id": max((a.id for a in records), default=0),
                "writing_variants": variants,
                "external_reports": sum(a.status == "reported" for a in records),
                "paused": module["id"] in plan["paused"],
                "completed_stages": [
                    s for s in STAGES if _stage_ready(records, user, s)
                ],
                "next_action": "language_gate"
                if b2_plus and not gate
                else "recognition"
                if not recognition
                else "writing"
                if len(variants) < 2
                else "spacing"
                if not ready
                else "practice",
            }
        )
    return result


def choose_question(
    session: Session,
    user: User,
    *,
    now: datetime,
    repeat_familiar: bool,
    bank_question: dict | None,
    recent: set[str],
) -> dict | None:
    """Balance answered choice units; retain legacy eligibility without relabelling."""
    catalog_data = load_curriculum()
    plan = get_plan(user, catalog_data)
    history = [a for a in attempts(session, user) if a.exercise_type == "simple_choice"]
    units = [
        a
        for a in history
        if (a.feedback or {}).get("strand") in {"general", "work"}
        and a.feedback.get("selection_mode") != "familiar"
        and a.feedback.get("allocation_share") == plan["general_share"]
    ]
    general = sum(a.feedback["strand"] == "general" for a in units)
    desired = (
        "general"
        if general < (len(units) + 1) * plan["general_share"] / 100
        else "work"
    )
    progress = {p["module_id"]: p for p in module_progress(session, user, now=now)}
    catalog = {m["id"]: m for m in catalog_data["modules"]}
    pack = {m["module_id"]: m for m in load_question_pack()["modules"]}
    quarantine = _quarantined(user)
    candidates = {"general": [], "work": []}
    for order, identifier in enumerate(plan["order"]):
        if identifier in plan["paused"]:
            continue
        stage = progress[identifier]["stage"]
        question_id = f"roadmap:v1:{identifier}:{stage}"
        if question_id in quarantine:
            continue
        records = [
            (i, a)
            for i, a in enumerate(history)
            if ((a.feedback or {}).get("roadmap") or {}).get("question_id")
            == question_id
        ]
        if repeat_familiar and not records:
            continue
        meaningful = [
            (i, a) for i, a in records if a.feedback.get("selection_mode") != "familiar"
        ]
        last = meaningful[-1] if meaningful else None
        if not repeat_familiar and last:
            if (
                last[1].status == "correct"
                and _utc(last[1].created_at) + COOLDOWN > now
            ):
                continue
            if last[1].status != "correct" and len(history) - last[0] - 1 < 5:
                continue
        raw = deepcopy(pack[identifier]["stages"][stage])
        module = catalog[identifier]
        question = {
            **raw,
            "category": "grammar",
            "exercise_type": "simple_choice",
            "target_learning_item_ids": [],
            "fingerprint": question_id,
            "expected_answer": raw["options"][raw["correct_index"]],
            "roadmap": {
                "version": 1,
                "module_id": identifier,
                "strand": module["strand"],
                "stage": stage,
                "question_id": question_id,
                "role": "practice",
            },
            "module_title_ru": module["title_ru"],
            "module_task": module["tasks"][stage],
            "module_evidence": list(module["evidence"]),
            "module_resources": [
                deepcopy(source)
                for source in catalog_data["sources"]
                if source["id"] in set(raw["resource_ids"] + module["source_ids"])
            ],
            "strand": module["strand"],
            "selection_source": "roadmap",
        }
        rank = (
            question_id in recent,
            identifier != plan["focus"],
            bool(records),
            order,
        )
        candidates[module["strand"]].append((rank, question))
    last_work = next(
        (
            a.feedback.get("selection_source")
            for a in reversed(units)
            if a.feedback["strand"] == "work"
        ),
        None,
    )
    bank = deepcopy(bank_question) if bank_question else None
    if bank:
        bank.update(strand="work", selection_source="language")
    for strand in (desired, "work" if desired == "general" else "general"):
        module = (
            min(candidates[strand], key=lambda candidate: candidate[0])[1]
            if candidates[strand]
            else None
        )
        selected = (
            (bank if bank and (last_work != "language" or module is None) else module)
            if strand == "work"
            else module
        )
        if selected:
            selected["allocation_share"] = plan["general_share"]
            if strand != desired:
                selected["selection_fallback"] = f"{desired}_unavailable"
            return selected
    return None


def answered_module_question(
    session: Session, user: User, parent_run_id: int, index: int
) -> dict | None:
    attempt = session.scalar(
        select(PracticeAttempt)
        .join(PracticeSession)
        .where(
            PracticeSession.user_id == user.id,
            PracticeAttempt.practice_session_id == parent_run_id,
            PracticeAttempt.exercise_index == index,
            PracticeAttempt.exercise_type == "simple_choice",
        )
    )
    question = (attempt.feedback or {}).get("question") if attempt else None
    return (
        deepcopy(question)
        if isinstance(question, dict) and question.get("roadmap")
        else None
    )


def start_module_bonus(
    session: Session,
    user: User,
    parent_run_id: int,
    index: int,
    *,
    now: datetime | None = None,
):
    from fluentloop.simple_learning import (
        BONUS,
        SimpleStep,
        _lock_user,
        get_active_bonus,
    )

    _lock_user(session, user)
    question = answered_module_question(session, user, parent_run_id, index)
    if not question or question["roadmap"]["question_id"] in _quarantined(user):
        return SimpleStep(None, None)
    active = get_active_bonus(session, user)
    if active is not None:
        return SimpleStep(active, deepcopy(active.exercises[0]))
    history = attempts(session, user)
    namespace = question["roadmap"]
    records = [
        a
        for a in history
        if ((a.feedback or {}).get("roadmap") or {}).get("module_id")
        == namespace["module_id"]
        and a.feedback["roadmap"].get("stage") == namespace["stage"]
        and _credited(a)
    ]
    credited = {a.feedback["roadmap"].get("production_variant_id") for a in records}
    prompts = question["production_prompts"]
    # Once both situations are correct, revisit the first until spacing is present.
    prompt = next((p for p in prompts if p["variant_id"] not in credited), prompts[0])
    current = _utc(now or datetime.now(UTC))
    exercise = {
        "exercise_type": "simple_production",
        "stage": namespace["stage"],
        "prompt": prompt["prompt"],
        "expected_answer": question["target_construction"],
        "target_construction": question["target_construction"],
        "source_example": question["options"][question["correct_index"]],
        "source_fingerprint": question["fingerprint"],
        "target_learning_item_ids": [],
        "explanation": (
            "Evaluate original English writing for this situation, meaning, register "
            "and the target construction. Require task completion; accept independent "
            "wording. The reference is not an answer to copy. Assess text only, "
            "not speaking or listening."
        ),
        "roadmap": {
            **namespace,
            "role": "production",
            "production_variant_id": prompt["variant_id"],
        },
        "metadata": {
            "mode": "simple",
            "stream_index": 0,
            "parent_simple_session_id": parent_run_id,
            "parent_simple_index": index,
            "topic": question.get("module_title_ru", ""),
            "selection_mode": question.get("metadata", {}).get(
                "selection_mode", "normal"
            ),
        },
    }
    run = PracticeSession(
        user_id=user.id,
        target_date_local=local_date(user, now=current),
        started_at=current,
        status=BONUS,
        exercises=[exercise],
    )
    session.add(run)
    session.flush()
    return SimpleStep(run, deepcopy(exercise))


def _near_copy(answer: str, reference: str) -> bool:
    text = re.sub(r"[^\w]+", " ", answer.casefold()).strip()
    source = re.sub(r"[^\w]+", " ", reference.casefold()).strip()
    if not source:
        return False
    return (
        text == source
        or (len(source.split()) >= 4 and f" {source} " in f" {text} ")
        or (
            min(len(text.split()), len(source.split())) >= 6
            and SequenceMatcher(None, text.split(), source.split()).ratio() >= 0.8
        )
    )


def module_feedback_metadata(
    session: Session, user: User, question: dict, answer: str
) -> dict:
    independent = independent_production(answer, question)
    namespace = question["roadmap"]
    for attempt in attempts(session, user):
        saved = attempt.feedback or {}
        if (saved.get("roadmap") or {}).get("module_id") != namespace["module_id"]:
            continue
        references = [
            saved.get("corrected_answer", ""),
            saved.get("natural_answer", ""),
        ]
        if _credited(attempt):
            references.append(attempt.user_answer)
        if any(_near_copy(answer, str(reference)) for reference in references):
            independent = False
    return {"roadmap": deepcopy(namespace), "independent_production": independent}


def record_module_external(
    session: Session, user: User, parent_run_id: int, index: int
) -> bool:
    from fluentloop.simple_learning import _lock_user

    _lock_user(session, user)
    question = answered_module_question(session, user, parent_run_id, index)
    if not question:
        return False
    for attempt in attempts(session, user):
        meta = attempt.feedback or {}
        if (
            attempt.status == "reported"
            and meta.get("parent_simple_session_id") == parent_run_id
            and meta.get("parent_simple_index") == index
        ):
            return False
    now = datetime.now(UTC)
    run = PracticeSession(
        user_id=user.id,
        target_date_local=local_date(user, now=now),
        started_at=now,
        completed_at=now,
        status="completed",
        exercises=[question],
    )
    session.add(run)
    session.flush()
    session.add(
        PracticeAttempt(
            practice_session_id=run.id,
            exercise_index=0,
            exercise_type="roadmap_external",
            target_learning_item_ids=[],
            prompt=question.get("module_task", question["prompt"]),
            user_answer="Self-reported external practice",
            status="reported",
            created_at=now,
            feedback={
                "status": "reported",
                "answer_modality": "self_report",
                "roadmap": {**question["roadmap"], "role": "external"},
                "parent_simple_session_id": parent_run_id,
                "parent_simple_index": index,
            },
        )
    )
    session.flush()
    return True


def report_module_issue(
    session: Session, user: User, parent_run_id: int, index: int
) -> bool:
    session.execute(update(User).where(User.id == user.id).values(id=User.id))
    question = answered_module_question(session, user, parent_run_id, index)
    if not question:
        return False
    session.refresh(user, ["preferences_json"])
    preferences = deepcopy(user.preferences_json or {})
    quality = preferences.setdefault(QUALITY_NAMESPACE, {})
    identifier = question["roadmap"]["question_id"]
    if quality.get(identifier) == "quarantined":
        return False
    quality[identifier] = "quarantined"
    user.preferences_json = preferences
    session.add(user)
    session.flush()
    return True
