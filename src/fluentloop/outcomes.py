from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from fluentloop.db.models import (
    EvaluationRun,
    LearningItem,
    LearningMetricSnapshot,
    MistakePattern,
    PracticeAttempt,
    PracticeSession,
    User,
)
from fluentloop.evaluation import build_monthly_probe, writing_metrics

PERIOD_DAYS = 30
BASELINE_KIND = "baseline"
ARTICLE_READING_KIND = "article_reading"
SUCCESS_STATUS = {"correct"}


@dataclass(frozen=True)
class OutcomeReport:
    metrics: dict[str, Any]
    summary_text: str


def current_baseline_prompt(session: Session, user: User) -> str:
    probe = build_monthly_probe(session, user)
    held_out = len(probe.held_out_item_ids)
    return (
        f"{probe.prompt}\n\n"
        "Writing baseline task:\n"
        "Write 120-180 words about a real work or engineering situation. "
        "Include one risk, one trade-off, and one recommendation.\n\n"
        f"Held-out learning items reserved for retention tracking: {held_out}.\n"
        "Send your answer as /baseline <your text>."
    )


def record_baseline(
    session: Session, user: User, answer: str, *, now: datetime | None = None
) -> EvaluationRun:
    cleaned = answer.strip()
    if not cleaned:
        raise ValueError("Send /baseline <your 120-180 word answer>.")
    current = now or datetime.now(UTC)
    probe = build_monthly_probe(session, user)
    metrics = writing_metrics(cleaned)
    metrics.update(
        {
            "kind": "monthly_writing_baseline",
            "held_out_item_count": len(probe.held_out_item_ids),
        }
    )
    run = EvaluationRun(
        user_id=user.id,
        kind=BASELINE_KIND,
        prompt=probe.prompt,
        answer_text=cleaned,
        source_reference="telegram:/baseline",
        metrics_json=metrics,
        held_out_item_ids=probe.held_out_item_ids,
        period_start=current.date(),
        period_end=current.date() + timedelta(days=PERIOD_DAYS),
    )
    session.add(run)
    session.flush()
    return run


def record_article_probe(
    session: Session, user: User, source_text: str, *, now: datetime | None = None
) -> EvaluationRun | None:
    cleaned = source_text.strip()
    if not cleaned:
        return None
    current = now or datetime.now(UTC)
    metrics = writing_metrics(cleaned)
    metrics.update(
        {
            "kind": "article_critical_reading",
            "critical_reading_outputs": [
                "main_claim",
                "hedge_marker",
                "assumption_challenge",
                "executive_summary",
            ],
            "source_word_count": metrics["word_count"],
        }
    )
    run = EvaluationRun(
        user_id=user.id,
        kind=ARTICLE_READING_KIND,
        prompt="Article Lab v1 critical-reading probe",
        answer_text=None,
        source_reference=f"telegram:/article:{len(cleaned)}chars",
        metrics_json=metrics,
        held_out_item_ids=[],
        period_start=current.date(),
        period_end=current.date(),
    )
    session.add(run)
    session.flush()
    return run


def latest_baseline(session: Session, user: User) -> EvaluationRun | None:
    return session.scalar(
        select(EvaluationRun)
        .where(EvaluationRun.user_id == user.id, EvaluationRun.kind == BASELINE_KIND)
        .order_by(EvaluationRun.created_at.desc(), EvaluationRun.id.desc())
        .limit(1)
    )


def collect_outcome_metrics(
    session: Session, user: User, *, now: datetime | None = None
) -> dict[str, Any]:
    current = now or datetime.now(UTC)
    period_start, period_end = _period_dates(current)
    attempts = _attempts_in_period(session, user, period_start, period_end)
    answers = [
        attempt.user_answer for attempt in attempts if attempt.user_answer.strip()
    ]
    word_count = sum(_word_count(answer) for answer in answers)
    baseline = latest_baseline(session, user)

    metrics: dict[str, Any] = {
        "period_start": period_start.isoformat(),
        "period_end": period_end.isoformat(),
        "attempts": {
            "total": len(attempts),
            "production": len(answers),
            "word_count": word_count,
        },
        "baseline": _baseline_metrics(baseline),
        "held_out_retention": _held_out_retention(session, user, baseline, attempts),
        "productive_chunks": _chunk_usage(session, user, answers),
        "writing": _writing_section(answers, baseline),
        "l1_density": _l1_density(attempts, word_count),
        "mistake_extinction": _mistake_extinction(session, user, attempts),
        "critical_reading": _critical_reading(
            session, user, attempts, period_start, period_end
        ),
    }
    return metrics


def build_outcome_report(
    session: Session,
    user: User,
    *,
    full: bool = False,
    now: datetime | None = None,
    store_snapshot: bool = True,
) -> OutcomeReport:
    metrics = collect_outcome_metrics(session, user, now=now)
    summary = render_outcome_report(metrics, full=full)
    if store_snapshot:
        snapshot = LearningMetricSnapshot(
            user_id=user.id,
            period_start=date.fromisoformat(metrics["period_start"]),
            period_end=date.fromisoformat(metrics["period_end"]),
            metrics_json=metrics,
            summary_text=summary,
        )
        session.add(snapshot)
        session.flush()
    return OutcomeReport(metrics=metrics, summary_text=summary)


def latest_outcome_summary(session: Session, user: User) -> str | None:
    snapshot = session.scalar(
        select(LearningMetricSnapshot)
        .where(LearningMetricSnapshot.user_id == user.id)
        .order_by(
            LearningMetricSnapshot.created_at.desc(),
            LearningMetricSnapshot.id.desc(),
        )
        .limit(1)
    )
    if snapshot is None:
        return None
    lines = snapshot.summary_text.splitlines()
    return "\n".join(lines[:8])


def render_outcome_report(metrics: dict[str, Any], *, full: bool = False) -> str:
    held = metrics["held_out_retention"]
    chunks = metrics["productive_chunks"]
    writing = metrics["writing"]
    l1 = metrics["l1_density"]
    mistakes = metrics["mistake_extinction"]
    reading = metrics["critical_reading"]
    attempts = metrics["attempts"]

    lines = [
        "Learning outcomes - last 30 days",
        f"Period: {metrics['period_start']} -> {metrics['period_end']}",
        f"Practice sample: {attempts['total']} attempts, "
        f"{attempts['word_count']} words",
        "",
        f"1. Held-out retention: {_rate_or_status(held, 'retention')}",
        f"   sample: {held['correct']}/{held['sample_size']} correct, "
        f"{held['held_out_total']} held-out items",
        f"2. Productive chunks: {_rate_or_status(chunks, 'percent')}",
        f"   {chunks['productive_count']}/{chunks['total_chunks']} chunks used >=3x",
        f"3. Notebook/writing: lexical diversity "
        f"{writing['current']['lexical_diversity']:.2f}, "
        f"hedging {writing['current']['hedging_per_100_words']:.1f}/100 words, "
        f"avg sentence {writing['current']['mean_sentence_length']:.1f} words",
        f"4. Diplomatic/L1: {l1['density_per_100_words']:.1f} L1 hits/100 words "
        f"({l1['hit_count']} hits)",
        f"5. Mistake extinction: {_rate_or_status(mistakes, 'rate')}",
        f"   {mistakes['extinct_or_nearly']}/{mistakes['sample_size']} patterns",
        f"6. Article/Critical Reading: {reading['total_events']} measurable events",
        "",
        "Next best loop: /practice notebook for production, "
        "/practice diplomatic or /translate_lab for L1 transfer, "
        "and /baseline once a month.",
    ]
    if full:
        lines.extend(
            [
                "",
                "Full detail",
                f"- Latest baseline: {metrics['baseline']['created_at'] or 'none'}",
                f"- Baseline words: {metrics['baseline']['word_count']}",
                f"- Reading attempts: {reading['reading_attempts']}; "
                f"article probes: {reading['article_runs']}",
                f"- Top L1 hits: {_render_counter(l1['top_hits'])}",
                f"- Top productive chunks: {_render_chunk_list(chunks['top_chunks'])}",
                "- Unused high-value chunks: "
                f"{_render_chunk_list(chunks['unused_chunks'])}",
                f"- Data notes: {_data_notes(metrics)}",
            ]
        )
    return "\n".join(lines)


def _period_dates(current: datetime) -> tuple[date, date]:
    end = current.date()
    start = end - timedelta(days=PERIOD_DAYS - 1)
    return start, end


def _attempts_in_period(
    session: Session, user: User, period_start: date, period_end: date
) -> list[PracticeAttempt]:
    start_dt = datetime.combine(period_start, time.min, tzinfo=UTC)
    end_dt = datetime.combine(period_end + timedelta(days=1), time.min, tzinfo=UTC)
    return list(
        session.scalars(
            select(PracticeAttempt)
            .join(
                PracticeSession,
                PracticeSession.id == PracticeAttempt.practice_session_id,
            )
            .where(
                PracticeSession.user_id == user.id,
                PracticeAttempt.created_at >= start_dt,
                PracticeAttempt.created_at < end_dt,
            )
            .order_by(PracticeAttempt.created_at.asc(), PracticeAttempt.id.asc())
        )
    )


def _baseline_metrics(baseline: EvaluationRun | None) -> dict[str, Any]:
    if baseline is None:
        return {
            "created_at": None,
            "word_count": 0,
            "held_out_item_count": 0,
            "status": "insufficient data: no baseline yet",
        }
    metrics = baseline.metrics_json or {}
    return {
        "created_at": baseline.created_at.date().isoformat()
        if baseline.created_at
        else None,
        "word_count": int(metrics.get("word_count") or 0),
        "held_out_item_count": len(baseline.held_out_item_ids or []),
        "status": "ok",
    }


def _held_out_retention(
    session: Session,
    user: User,
    baseline: EvaluationRun | None,
    attempts: list[PracticeAttempt],
) -> dict[str, Any]:
    held_out_ids = set((baseline.held_out_item_ids or []) if baseline else [])
    if held_out_ids:
        held_out_ids = set(
            session.scalars(
                select(LearningItem.id).where(
                    LearningItem.user_id == user.id,
                    LearningItem.id.in_(held_out_ids),
                    LearningItem.is_template.is_(False),
                )
            )
        )
    matching = [
        attempt
        for attempt in attempts
        if held_out_ids.intersection(attempt.target_learning_item_ids or [])
    ]
    correct = sum(1 for attempt in matching if attempt.status in SUCCESS_STATUS)
    retention = correct / len(matching) if matching else None
    return {
        "retention": retention,
        "correct": correct,
        "sample_size": len(matching),
        "held_out_total": len(held_out_ids),
        "status": "ok" if matching else "insufficient data: no held-out attempts yet",
    }


def _chunk_usage(
    session: Session, user: User, answers: list[str]
) -> dict[str, Any]:
    chunks = list(
        session.scalars(
            select(LearningItem)
            .where(
                LearningItem.user_id == user.id,
                LearningItem.type == "chunk",
                LearningItem.status == "active",
                LearningItem.is_template.is_(False),
            )
            .order_by(LearningItem.id.asc())
        )
    )
    answer_bank = "\n".join(_normalize_text(answer) for answer in answers)
    counts: list[dict[str, Any]] = []
    for item in chunks:
        normalized = _normalize_text(item.text)
        if not normalized:
            continue
        counts.append(
            {"id": item.id, "text": item.text, "uses": answer_bank.count(normalized)}
        )
    productive = [item for item in counts if item["uses"] >= 3]
    used = [item for item in counts if item["uses"] > 0]
    unused = [item for item in counts if item["uses"] == 0]
    total = len(counts)
    return {
        "percent": (len(productive) / total) if total else None,
        "productive_count": len(productive),
        "total_chunks": total,
        "top_chunks": sorted(used, key=lambda item: (-item["uses"], item["id"]))[:5],
        "unused_chunks": unused[:5],
        "status": "ok" if total else "insufficient data: no active chunks yet",
    }


def _writing_section(
    answers: list[str], baseline: EvaluationRun | None
) -> dict[str, Any]:
    combined = "\n".join(answers)
    current = writing_metrics(combined) if combined.strip() else writing_metrics("")
    current["hedging_per_100_words"] = current["hedging_density"] * 100
    baseline_metrics = dict(baseline.metrics_json or {}) if baseline else {}
    deltas: dict[str, float | None] = {}
    for key in ("lexical_diversity", "hedging_density", "mean_sentence_length"):
        base_value = baseline_metrics.get(key)
        deltas[key] = (
            round(float(current[key]) - float(base_value), 4)
            if base_value is not None
            else None
        )
    return {
        "current": current,
        "baseline": baseline_metrics,
        "delta_vs_baseline": deltas,
        "status": "ok" if answers else "insufficient data: no production answers yet",
    }


def _l1_density(attempts: list[PracticeAttempt], word_count: int) -> dict[str, Any]:
    hits: list[str] = []
    for attempt in attempts:
        for hit in (attempt.feedback or {}).get("l1_hits") or []:
            if isinstance(hit, dict):
                hits.append(str(hit.get("rule_id") or hit.get("id") or "l1_hit"))
            else:
                hits.append(str(hit))
    counter = Counter(hits)
    density = (len(hits) / word_count * 100) if word_count else 0.0
    return {
        "density_per_100_words": density,
        "hit_count": len(hits),
        "word_count": word_count,
        "top_hits": [
            {"rule": key, "count": value}
            for key, value in counter.most_common(5)
        ],
        "status": "ok" if word_count else "insufficient data: no production words yet",
    }


def _mistake_extinction(
    session: Session, user: User, attempts: list[PracticeAttempt]
) -> dict[str, Any]:
    patterns = list(
        session.scalars(
            select(MistakePattern)
            .where(
                MistakePattern.user_id == user.id,
                MistakePattern.confidence == "low",
            )
            .order_by(MistakePattern.id.asc())
        )
    )
    sample = 0
    extinct = 0
    nearly = 0
    for pattern in patterns:
        if pattern.status in {"extinct", "archived"}:
            sample += 1
            extinct += 1
            continue
        if pattern.status == "nearly_extinct":
            sample += 1
            nearly += 1
            continue
        if pattern.linked_learning_item_id is None:
            continue
        statuses = [
            attempt.status
            for attempt in attempts
            if pattern.linked_learning_item_id
            in (attempt.target_learning_item_ids or [])
        ]
        if not statuses:
            continue
        sample += 1
        if len(statuses) >= 5 and all(
            status in SUCCESS_STATUS for status in statuses[-5:]
        ):
            extinct += 1
        elif len(statuses) >= 3 and all(
            status in SUCCESS_STATUS for status in statuses[-3:]
        ):
            nearly += 1
    rate = ((extinct + nearly) / sample) if sample else None
    return {
        "rate": rate,
        "extinct": extinct,
        "nearly_extinct": nearly,
        "extinct_or_nearly": extinct + nearly,
        "sample_size": sample,
        "status": "ok"
        if sample
        else "insufficient data: no trackable low-confidence patterns yet",
    }


def _critical_reading(
    session: Session,
    user: User,
    attempts: list[PracticeAttempt],
    period_start: date,
    period_end: date,
) -> dict[str, Any]:
    reading_attempts = [
        attempt
        for attempt in attempts
        if "critical reading" in attempt.prompt.lower()
        or "reading" in attempt.exercise_type.lower()
        or "critical_reading" in ((attempt.feedback or {}).get("format_feedback") or {})
    ]
    start_dt = datetime.combine(period_start, time.min, tzinfo=UTC)
    end_dt = datetime.combine(period_end + timedelta(days=1), time.min, tzinfo=UTC)
    article_runs = list(
        session.scalars(
            select(EvaluationRun)
            .where(
                EvaluationRun.user_id == user.id,
                EvaluationRun.kind == ARTICLE_READING_KIND,
                EvaluationRun.created_at >= start_dt,
                EvaluationRun.created_at < end_dt,
            )
            .order_by(EvaluationRun.created_at.asc())
        )
    )
    correct = sum(1 for attempt in reading_attempts if attempt.status in SUCCESS_STATUS)
    attempt_score = correct / len(reading_attempts) if reading_attempts else None
    return {
        "reading_attempts": len(reading_attempts),
        "article_runs": len(article_runs),
        "total_events": len(reading_attempts) + len(article_runs),
        "attempt_score": attempt_score,
        "status": "ok"
        if reading_attempts or article_runs
        else "insufficient data: no critical-reading events yet",
    }


def _word_count(text: str) -> int:
    return int(writing_metrics(text)["word_count"])


def _normalize_text(text: str) -> str:
    return " ".join(text.lower().split())


def _rate_or_status(section: dict[str, Any], key: str) -> str:
    value = section.get(key)
    if value is None:
        return str(section.get("status") or "insufficient data")
    return f"{float(value) * 100:.0f}%"


def _render_counter(items: list[dict[str, Any]]) -> str:
    if not items:
        return "none"
    return ", ".join(f"{item['rule']} ({item['count']})" for item in items)


def _render_chunk_list(items: list[dict[str, Any]]) -> str:
    if not items:
        return "none"
    return "; ".join(
        f"#{item['id']} {item['text']} ({item['uses']}x)" for item in items
    )


def _data_notes(metrics: dict[str, Any]) -> str:
    statuses = [
        section["status"]
        for section in (
            metrics["baseline"],
            metrics["held_out_retention"],
            metrics["productive_chunks"],
            metrics["writing"],
            metrics["l1_density"],
            metrics["mistake_extinction"],
            metrics["critical_reading"],
        )
        if str(section.get("status", "")).startswith("insufficient")
    ]
    return "; ".join(statuses) if statuses else "enough data for v1 trend reading"
