"""Reviewed lexical senses in Study, without LearningItems or mastery claims."""

from __future__ import annotations

import re
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlsplit

from sqlalchemy import select
from sqlalchemy.orm import Session

from fluentloop.adaptive_learning import independent_production
from fluentloop.db.models import PracticeAttempt, PracticeSession, User
from fluentloop.vocab_loop import local_date
from fluentloop.workplace_roadmap import load_curriculum, read_json

LEXICON_PATH = Path(__file__).parent / "seeds" / "workplace_lexicon_v1.json"
QUALITY_NAMESPACE = "lexical_question_quality"
COOLDOWN = timedelta(hours=24)
ENTRY_FIELDS = {
    "id",
    "function_id",
    "strand",
    "stage",
    "headword",
    "meaning_ru",
    "meaning_en",
    "example",
    "grammar",
    "register",
    "plain_alternative",
    "source_urls",
    "module_ids",
    "questions",
    "production_prompts",
}


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def _text(value: object, maximum: int = 2000) -> None:
    if (
        not isinstance(value, str)
        or not value.strip()
        or len(value) > maximum
        or any(ord(c) < 32 and c not in "\n\t\r" for c in value)
        or any(0xD800 <= ord(c) <= 0xDFFF for c in value)
    ):
        raise ValueError("Lexicon requires bounded nonempty text")


def _objects(value: object, fields: set[str], maximum: int) -> list[dict]:
    if not isinstance(value, list) or not 1 <= len(value) <= maximum:
        raise ValueError("Lexicon requires a bounded nonempty list")
    identifiers = set()
    for entry in value:
        if not isinstance(entry, dict) or set(entry) != fields:
            raise ValueError("Lexicon has missing or unknown fields")
        identifier = entry.get("id")
        if (
            not isinstance(identifier, str)
            or not re.fullmatch(r"[a-z][a-z0-9_-]{0,79}", identifier)
            or identifier in identifiers
        ):
            raise ValueError("Lexicon has invalid or duplicate ids")
        identifiers.add(identifier)
    return value


def validate_lexicon(data: object, catalog: dict | None = None) -> dict:
    """Validate public content and actual curriculum references before selection."""
    if (
        not isinstance(data, dict)
        or set(data) != {"version", "functions", "entries"}
        or type(data["version"]) is not int
        or data["version"] != 1
    ):
        raise ValueError("Invalid lexical bank envelope")
    functions = _objects(data["functions"], {"id", "title_ru", "strand"}, 64)
    function_map = {f["id"]: f for f in functions}
    modules = {m["id"]: m for m in (catalog or load_curriculum())["modules"]}
    for function in functions:
        _text(function["title_ru"], 200)
        _text(function["strand"], 20)
        if function["strand"] not in {"general", "work"}:
            raise ValueError("Invalid lexical function strand")
    for entry in _objects(data["entries"], ENTRY_FIELDS, 1000):
        for field in ("function_id", "strand", "stage"):
            _text(entry[field], 80)
        if (
            entry["function_id"] not in function_map
            or entry["strand"] != function_map[entry["function_id"]]["strand"]
            or entry["stage"] not in {"b2", "b2_plus", "c1_intro"}
        ):
            raise ValueError("Invalid lexical function, strand or stage")
        for field in (
            "headword",
            "meaning_ru",
            "meaning_en",
            "example",
            "grammar",
            "register",
            "plain_alternative",
        ):
            _text(entry[field], 200 if field == "headword" else 2000)
        for field, maximum in (("module_ids", 30), ("source_urls", 10)):
            values = entry[field]
            if not isinstance(values, list) or not 1 <= len(values) <= maximum:
                raise ValueError("Invalid lexical references")
            for value in values:
                _text(value, 1000)
            if len(set(values)) != len(values):
                raise ValueError("Duplicate lexical references")
        if any(
            identifier not in modules
            or modules[identifier]["strand"] != entry["strand"]
            for identifier in entry["module_ids"]
        ):
            raise ValueError("Unknown or mismatched lexical module reference")
        for source in entry["source_urls"]:
            try:
                url = urlsplit(source)
                valid = (
                    url.scheme == "https"
                    and url.hostname
                    and not (
                        url.username or url.password or any(c.isspace() for c in source)
                    )
                )
            except ValueError as exc:
                raise ValueError("Invalid lexical source URL") from exc
            if not valid:
                raise ValueError("Lexical sources require HTTPS URLs")
        for field in ("questions", "production_prompts"):
            variants = entry[field]
            if not isinstance(variants, list) or len(variants) != 2:
                raise ValueError("Two lexical situations are required")
            ids, texts = set(), set()
            for variant in variants:
                fields = {"variant_id", "prompt"}
                if field == "questions":
                    fields |= {"options", "correct_index", "explanation_ru"}
                if not isinstance(variant, dict) or set(variant) != fields:
                    raise ValueError("Invalid lexical situation fields")
                _text(variant["variant_id"], 10)
                if (
                    variant["variant_id"] not in {"a", "b"}
                    or variant["variant_id"] in ids
                ):
                    raise ValueError("Invalid or duplicate lexical variant")
                _text(variant["prompt"])
                if variant["prompt"] in texts:
                    raise ValueError("Lexical situations must differ")
                ids.add(variant["variant_id"])
                texts.add(variant["prompt"])
                if field == "questions":
                    options = variant["options"]
                    if (
                        not isinstance(options, list)
                        or len(options) != 3
                        or type(variant["correct_index"]) is not int
                        or not 0 <= variant["correct_index"] < 3
                    ):
                        raise ValueError("Invalid lexical answer options")
                    for option in options:
                        _text(option, 1000)
                    if len({option.strip().casefold() for option in options}) != 3:
                        raise ValueError("Duplicate lexical answer options")
                    _text(variant["explanation_ru"])
    return deepcopy(data)


@lru_cache(maxsize=1)
def load_lexicon() -> dict:
    return validate_lexicon(read_json(LEXICON_PATH, max_bytes=2 * 1024 * 1024))


def _history(session: Session, user: User, now: datetime) -> list[PracticeAttempt]:
    return [
        a
        for a in session.scalars(
            select(PracticeAttempt)
            .join(PracticeSession)
            .where(PracticeSession.user_id == user.id)
            .order_by(PracticeAttempt.id)
        )
        if _utc(a.created_at) <= now
    ]


def _quarantined(user: User) -> set[str]:
    quality = (user.preferences_json or {}).get(QUALITY_NAMESPACE) or {}
    return {
        identifier for identifier, status in quality.items() if status == "quarantined"
    }


def _displays(
    session: Session, user: User, now: datetime, history: list
) -> dict[str, datetime]:
    displayed = {}
    snapshots = [(a.feedback or {}).get("question") for a in history]
    snapshots += [
        run.exercises[0]
        for run in session.scalars(
            select(PracticeSession).where(PracticeSession.user_id == user.id)
        )
        if run.exercises and _utc(run.started_at) <= now
    ]
    for question in snapshots:
        if not isinstance(question, dict) or not question.get("lexical"):
            continue
        stamp = (question.get("metadata") or {}).get("displayed_at")
        try:
            date = _utc(datetime.fromisoformat(stamp))
        except (ValueError, TypeError):
            continue
        if date <= now:
            identifier = question["lexical"]["entry_id"]
            displayed[identifier] = max(displayed.get(identifier, date), date)
    return displayed


def candidate_questions(
    session: Session,
    user: User,
    *,
    now: datetime,
    repeat_familiar: bool,
    plan: dict,
    gate: bool,
) -> dict[str, list[tuple[tuple, dict]]]:
    """Rank sense-level new/review slots, with shared cooldown across variants."""
    now = _utc(now)
    history = _history(session, user, now)
    normal = [
        a
        for a in history
        if a.exercise_type == "simple_choice"
        and (a.feedback or {}).get("selection_mode") != "familiar"
    ]
    latest = next(
        (a for a in reversed(normal) if (a.feedback or {}).get("lexical")), None
    )
    preferred = (
        "review" if latest and latest.feedback.get("lexical_phase") == "new" else "new"
    )
    displayed = _displays(session, user, now, history)
    quarantine = _quarantined(user)
    order = {identifier: i for i, identifier in enumerate(plan["order"])}
    candidates = {"general": [], "work": []}
    for entry in load_lexicon()["entries"]:
        identifier = entry["id"]
        active = [
            m for m in entry["module_ids"] if m in order and m not in plan["paused"]
        ]
        if (
            not active
            or identifier in quarantine
            or (entry["stage"] == "c1_intro" and not gate)
        ):
            continue
        records = [
            (i, a)
            for i, a in enumerate(normal)
            if ((a.feedback or {}).get("lexical") or {}).get("entry_id") == identifier
        ]
        all_records = [
            a
            for a in history
            if a.exercise_type == "simple_choice"
            and ((a.feedback or {}).get("lexical") or {}).get("entry_id") == identifier
        ]
        if repeat_familiar and not all_records:
            continue
        if not repeat_familiar:
            last = records[-1] if records else None
            if (
                last
                and last[1].status == "correct"
                and (
                    _utc(last[1].created_at) + COOLDOWN > now
                    or local_date(user, now=_utc(last[1].created_at))
                    == local_date(user, now=now)
                )
            ):
                continue
            if last and last[1].status != "correct" and len(normal) - last[0] - 1 < 5:
                continue
            # An abandoned card is still an exposure; siblings cannot bypass it.
            if (
                not records
                and identifier in displayed
                and displayed[identifier] + COOLDOWN > now
            ):
                continue
        phase = "review" if records else "new"
        for variant in entry["questions"]:
            answered = [
                a
                for a in all_records
                if a.feedback["lexical"].get("variant_id") == variant["variant_id"]
            ]
            if repeat_familiar and not answered:
                continue
            question_id = f"lexical:v1:{identifier}:{variant['variant_id']}"
            question = {
                **deepcopy(variant),
                "exercise_type": "simple_choice",
                "category": "phrase",
                "target_learning_item_ids": [],
                "expected_answer": variant["options"][variant["correct_index"]],
                "fingerprint": question_id,
                "strand": entry["strand"],
                "selection_source": "lexical",
                "target_phrase": entry["headword"],
                "source_example": entry["example"],
                "lexical": {
                    "version": 1,
                    "entry_id": identifier,
                    "variant_id": variant["variant_id"],
                    "role": "practice",
                },
                "lexical_entry": deepcopy(entry),
                "lexical_phase": phase,
                "lexical_card": {
                    key: entry[key]
                    for key in (
                        "headword",
                        "meaning_ru",
                        "meaning_en",
                        "example",
                        "grammar",
                        "register",
                        "plain_alternative",
                    )
                },
                "first_exposure": identifier not in displayed,
            }
            rank = (
                phase != preferred,
                plan["focus"] not in active,
                bool(answered),
                _utc(answered[-1].created_at)
                if answered
                else datetime.min.replace(tzinfo=UTC),
                min(order[m] for m in active),
                identifier,
                variant["variant_id"],
            )
            candidates[entry["strand"]].append((rank, question))
    return candidates


def answered_lexical_question(
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
        if isinstance(question, dict) and question.get("lexical")
        else None
    )


def _credited(attempt: PracticeAttempt) -> bool:
    feedback = attempt.feedback or {}
    return bool(
        attempt.exercise_type == "simple_production"
        and attempt.status == "correct"
        and feedback.get("genuine_evaluation") is True
        and feedback.get("independent_production") is True
        and feedback.get("target_present") is True
        and feedback.get("selection_mode") != "familiar"
    )


def start_lexical_bonus(
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
    question = answered_lexical_question(session, user, parent_run_id, index)
    if not question or question["lexical"]["entry_id"] in _quarantined(user):
        return SimpleStep(None, None)
    active = get_active_bonus(session, user)
    if active is not None:
        return SimpleStep(active, deepcopy(active.exercises[0]))
    # One optional attempt per answered card, including completed/skipped attempts.
    for run in session.scalars(
        select(PracticeSession).where(PracticeSession.user_id == user.id)
    ):
        meta = (run.exercises[0].get("metadata") or {}) if run.exercises else {}
        if (
            meta.get("parent_simple_session_id") == parent_run_id
            and meta.get("parent_simple_index") == index
        ):
            return SimpleStep(run, None)
    current = _utc(now or datetime.now(UTC))
    entry = question["lexical_entry"]
    credited = {
        a.feedback["lexical"].get("production_variant_id")
        for a in _history(session, user, current)
        if ((a.feedback or {}).get("lexical") or {}).get("entry_id") == entry["id"]
        and _credited(a)
    }
    prompt = next(
        (p for p in entry["production_prompts"] if p["variant_id"] not in credited),
        entry["production_prompts"][0],
    )
    exercise = {
        "exercise_type": "simple_production",
        "stage": entry["stage"],
        "prompt": prompt["prompt"],
        "expected_answer": entry["headword"],
        "target_phrase": entry["headword"],
        "source_example": entry["example"],
        "source_options": question["options"],
        "source_fingerprint": question["fingerprint"],
        "target_learning_item_ids": [],
        "lexical_entry": deepcopy(entry),
        "lexical": {
            **question["lexical"],
            "role": "production",
            "production_variant_id": prompt["variant_id"],
        },
        "explanation": (
            "Evaluate original English writing for the requested situation "
            "and target sense. "
            f"Meaning: {entry['meaning_en']}. Grammar: {entry['grammar']}. "
            f"Register: {entry['register']}. "
            "Require task completion and natural use of the target; "
            "accept grammatical inflections. "
            "References are examples, not answers to copy."
        ),
        "metadata": {
            "mode": "simple",
            "stream_index": 0,
            "parent_simple_session_id": parent_run_id,
            "parent_simple_index": index,
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


def _target_present(answer: str, target: str) -> bool:
    """Match lexical forms; the genuine evaluator still checks meaning and use."""
    irregular = {
        "bring": "bring|brings|bringing|brought",
        "take": "take|takes|taking|took|taken",
        "get": "get|gets|getting|got|gotten",
        "go": "go|goes|going|went|gone",
        "keep": "keep|keeps|keeping|kept",
        "make": "make|makes|making|made",
        "set": "set|sets|setting",
        "put": "put|puts|putting",
        "run": "run|runs|running|ran",
        "come": "come|comes|coming|came",
        "cut": "cut|cuts|cutting",
        "hold": "hold|holds|holding|held",
        "have": "have|has|having|had",
        "be": "be|am|is|are|was|were|been|being",
        "draw": "draw|draws|drawing|drew|drawn",
        "give": "give|gives|giving|gave|given",
        "stand": "stand|stands|standing|stood",
        "meet": "meet|meets|meeting|met",
        "build": "build|builds|building|built",
        "stick": "stick|sticks|sticking|stuck",
        "break": "break|breaks|breaking|broke|broken",
        "buy": "buy|buys|buying|bought",
        "find": "find|finds|finding|found",
        "leave": "leave|leaves|leaving|left",
        "speak": "speak|speaks|speaking|spoke|spoken",
        "fall": "fall|falls|falling|fell|fallen",
        "lead": "lead|leads|leading|led",
        "spell": "spell|spells|spelling|spelled|spelt",
        "fit": "fit|fits|fitting|fitted",
        "bear": "bear|bears|bearing|bore|borne",
    }
    tokens = re.findall(r"[a-z]+(?:'[a-z]+)?|\.\.\.|…", target.casefold())
    pieces = []
    placeholders = {"someone", "somebody", "something", "sb", "sth", "...", "…"}
    for index, token in enumerate(tokens):
        if token in {"one's", "someone's", "somebody's"}:
            pieces.append(r"(?:my|your|his|her|its|our|their|one's|[\w-]+'s)")
        elif token in placeholders:
            pieces.append(r"(?:[\w'-]+\s+){0,6}?[\w'-]+")
        elif index > 0:
            pieces.append(re.escape(token))
        elif token in irregular:
            pieces.append(f"(?:{irregular[token]})")
        else:
            forms = {token, token + "s", token + "ed", token + "ing"}
            if token.endswith("e"):
                forms |= {token + "d", token[:-1] + "ing"}
            if token.endswith("y"):
                forms |= {token[:-1] + "ies", token[:-1] + "ied"}
            if len(token) >= 3 and token[-1] not in "aeiouwxy" and token[-2] in "aeiou":
                forms |= {token + token[-1] + "ed", token + token[-1] + "ing"}
            pieces.append("(?:" + "|".join(re.escape(f) for f in sorted(forms)) + ")")
    separator = r"[\s-]+"
    patterns = [separator.join(pieces)]
    if tokens == ["by", "...", "mean"] or tokens == ["by", "…", "mean"]:
        # Clarification frames occur as both 'By X, do you mean Y?' and
        # 'What do you mean by X?' without changing their lexical sense.
        patterns.append(r"mean\s+(?:(?:exactly|precisely)\s+)?by")
    if (
        len(tokens) == 4
        and tokens[0] == "take"
        and tokens[1] in placeholders
        and tokens[2:] == ["into", "account"]
    ):
        patterns.append(separator.join([pieces[0], pieces[2], pieces[3], pieces[1]]))
    noun_endings = {
        "concern",
        "question",
        "issue",
        "expectation",
        "priority",
        "risk",
        "deadline",
        "dependency",
        "requirement",
        "decision",
        "commitment",
        "stakeholder",
        "point",
        "assumption",
        "constraint",
        "resource",
        "outcome",
        "step",
        "action",
        "responsibility",
        "option",
        "opportunity",
        "tradeoff",
    }
    if len(tokens) > 1 and (tokens[-1] in noun_endings or "-" in target):
        noun = tokens[-1]
        plural = noun[:-1] + "ies" if noun.endswith("y") else noun + "s"
        plural_pieces = [*pieces[:-1], f"(?:{re.escape(noun)}|{re.escape(plural)})"]
        patterns.append(separator.join(plural_pieces))
        if len(tokens) == 3 and tokens[1] in {"a", "an"}:
            patterns.append(pieces[0] + separator + plural_pieces[-1])
    separable = {
        "roll",
        "push",
        "put",
        "take",
        "bring",
        "hand",
        "carry",
        "rule",
        "phase",
        "work",
        "sort",
        "point",
        "call",
        "break",
        "set",
        "cut",
        "nail",
        "spell",
        "fit",
        "weigh",
        "bear",
        "meet",
    }
    particles = {
        "up",
        "out",
        "off",
        "back",
        "down",
        "over",
        "in",
        "through",
        "on",
        "away",
    }
    if len(tokens) >= 2 and tokens[0] in separable:
        if tokens[1] in particles or tokens[:2] == ["meet", "halfway"]:
            object_word = (
                r"(?!(?:am|is|are|was|were|have|has|had|do|does|did|can|will|"
                r"would|should|could|must|might|run|go|come)\b)[\w'-]+"
            )
            patterns.append(
                pieces[0]
                + separator
                + r"(?!(?:of|in|on|at|from|to)\b)"
                + "(?:"
                + object_word
                + r"\s+){1,4}?"
                + separator.join(pieces[1:])
            )
        elif len(tokens) >= 3 and tokens[1] in placeholders and tokens[2] in particles:
            patterns.append(
                separator.join([pieces[0], pieces[2], pieces[1], *pieces[3:]])
            )
    text = answer.casefold()
    return bool(
        pieces and any(re.search(r"\b" + pattern + r"\b", text) for pattern in patterns)
    )


def lexical_feedback_metadata(
    session: Session,
    user: User,
    question: dict,
    answer: str,
    *,
    now: datetime | None = None,
) -> dict:
    from fluentloop.roadmap_study import _near_copy

    independent = independent_production(answer, question)
    references = list(question.get("source_options") or [])
    for attempt in _history(session, user, _utc(now or datetime.now(UTC))):
        feedback = attempt.feedback or {}
        if ((feedback.get("lexical") or {}).get("entry_id")) == question["lexical"][
            "entry_id"
        ]:
            references += [
                attempt.user_answer,
                feedback.get("corrected_answer", ""),
                feedback.get("natural_answer", ""),
            ]
    if any(_near_copy(answer, str(reference)) for reference in references):
        independent = False
    present = _target_present(answer, question["target_phrase"])
    return {
        "lexical": deepcopy(question["lexical"]),
        "target_present": present,
        "independent_production": independent and present,
    }


def _spaced_pair(records: list[PracticeAttempt], user: User, variant_key: str) -> bool:
    return any(
        first.feedback["lexical"].get(variant_key)
        != second.feedback["lexical"].get(variant_key)
        and local_date(user, now=_utc(first.created_at))
        != local_date(user, now=_utc(second.created_at))
        and abs(_utc(first.created_at) - _utc(second.created_at)) >= COOLDOWN
        for i, first in enumerate(records)
        for second in records[i + 1 :]
    )


def lexical_progress(
    session: Session, user: User, *, now: datetime | None = None
) -> dict:
    current = _utc(now or datetime.now(UTC))
    history = _history(session, user, current)
    displayed = _displays(session, user, current, history)
    quarantine = _quarantined(user)
    rows = []
    for entry in load_lexicon()["entries"]:
        records = [
            a
            for a in history
            if ((a.feedback or {}).get("lexical") or {}).get("entry_id") == entry["id"]
        ]
        recognition = [
            a
            for a in records
            if a.exercise_type == "simple_choice"
            and a.feedback.get("selection_mode") != "familiar"
        ]
        correct = [a for a in recognition if a.status == "correct"]
        writing = [a for a in records if _credited(a)]
        recognized = entry["id"] not in quarantine and _spaced_pair(
            correct, user, "variant_id"
        )
        independent = entry["id"] not in quarantine and _spaced_pair(
            writing, user, "production_variant_id"
        )
        rows.append(
            {
                "entry_id": entry["id"],
                "headword": entry["headword"],
                "meaning_ru": entry["meaning_ru"],
                "strand": entry["strand"],
                "stage": entry["stage"],
                "seen": entry["id"] in displayed,
                "introduced": bool(recognition),
                "recognized": recognized,
                "independent_writing": independent,
                "recognition_attempts": len(recognition),
                "recognition_correct": len(correct),
                "writing_attempts": sum(
                    a.exercise_type == "simple_production" for a in records
                ),
                "writing_credited": len(writing),
                "new": sum(
                    a.feedback.get("lexical_phase") == "new" for a in recognition
                ),
                "reviews": sum(
                    a.feedback.get("lexical_phase") == "review" for a in recognition
                ),
                "quarantined": entry["id"] in quarantine,
                "next_action": "quarantined"
                if entry["id"] in quarantine
                else "introduction"
                if not recognition
                else "spaced_recognition"
                if not recognized
                else "independent_writing"
                if not independent
                else "practice",
            }
        )
    summary = {
        key: sum(bool(row[key]) for row in rows)
        for key in ("seen", "introduced", "recognized", "independent_writing")
    }
    summary.update(
        total=len(rows),
        new=sum(r["new"] for r in rows),
        reviews=sum(r["reviews"] for r in rows),
    )
    return {**summary, "summary": summary, "entries": rows}


def report_lexical_issue(
    session: Session, user: User, parent_run_id: int, index: int
) -> bool:
    from fluentloop.simple_learning import _lock_user

    _lock_user(session, user)
    question = answered_lexical_question(session, user, parent_run_id, index)
    if not question:
        return False
    session.refresh(user, ["preferences_json"])
    preferences = deepcopy(user.preferences_json or {})
    quality = preferences.setdefault(QUALITY_NAMESPACE, {})
    identifier = question["lexical"]["entry_id"]
    if quality.get(identifier) == "quarantined":
        return False
    quality[identifier] = "quarantined"
    user.preferences_json = preferences
    session.add(user)
    session.flush()
    return True
