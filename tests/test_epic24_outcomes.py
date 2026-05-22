from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from fluentloop.bot.handlers import (
    handle_article,
    handle_baseline,
    handle_mentor,
    handle_outcomes,
)
from fluentloop.db.models import (
    EvaluationRun,
    LearningItem,
    LearningMetricSnapshot,
    MistakePattern,
    PracticeAttempt,
    PracticeSession,
)
from fluentloop.learning import create_learning_item
from fluentloop.outcomes import collect_outcome_metrics
from fluentloop.users import ensure_user


def test_baseline_command_records_writing_probe_and_held_out_items(
    db_session, settings
) -> None:
    user = ensure_user(db_session, 123456789, settings)
    for index in range(12):
        create_learning_item(
            db_session,
            user,
            type_="expression",
            text=f"baseline target {index}",
        )

    prompt = handle_baseline(db_session, user)
    reply = handle_baseline(
        db_session,
        user,
        "We might need to reduce scope because the release risk is unclear. "
        "The trade-off is slower delivery, but it could protect reliability. "
        "I recommend aligning on the smallest safe milestone.",
    )
    run = db_session.scalar(select(EvaluationRun))

    assert "Writing baseline task" in prompt.text
    assert "Baseline saved" in reply.text
    assert run is not None
    assert run.kind == "baseline"
    assert run.metrics_json["word_count"] > 20
    assert run.metrics_json["hedging_density"] > 0
    assert len(run.held_out_item_ids) >= 1


def test_outcome_metrics_cover_retention_chunks_l1_and_template_isolation(
    db_session, settings
) -> None:
    user = ensure_user(db_session, 123456789, settings)
    now = datetime.now(UTC)
    chunk = create_learning_item(
        db_session, user, type_="chunk", text="align on scope"
    )
    create_learning_item(
        db_session, user, type_="chunk", text="reduce the blast radius"
    )
    db_session.add(
        LearningItem(
            user_id=user.id,
            type="chunk",
            text="template only chunk",
            status="active",
            is_template=True,
        )
    )
    db_session.flush()
    baseline = handle_baseline(
        db_session,
        user,
        "We could align on scope first. It might reduce delivery risk and "
        "make the trade-off clearer for stakeholders.",
    )
    run = db_session.scalar(select(EvaluationRun))
    assert "Baseline saved" in baseline.text
    assert run is not None

    _attempt(
        db_session,
        user,
        at=now - timedelta(days=2),
        answer=(
            "We should align on scope, align on scope with product, and align on "
            "scope before we discuss this."
        ),
        status="correct",
        target_ids=[run.held_out_item_ids[0], chunk.id],
        feedback={"l1_hits": [{"rule_id": "l1_discuss_about"}]},
    )
    _attempt(
        db_session,
        user,
        at=now - timedelta(days=1),
        answer="It may depend on capacity, but we could reduce the blast radius.",
        status="incorrect",
        target_ids=[],
        feedback={"l1_hits": [{"rule_id": "l1_depend_from"}]},
    )

    metrics = collect_outcome_metrics(db_session, user, now=now)

    assert metrics["held_out_retention"]["retention"] == 1.0
    assert metrics["productive_chunks"]["productive_count"] == 1
    assert metrics["productive_chunks"]["total_chunks"] == 2
    assert metrics["l1_density"]["hit_count"] == 2
    assert metrics["writing"]["current"]["hedging_per_100_words"] > 0
    chunk_texts = {
        item["text"]
        for item in metrics["productive_chunks"]["top_chunks"]
        + metrics["productive_chunks"]["unused_chunks"]
    }
    assert "template only chunk" not in chunk_texts


def test_outcomes_command_persists_snapshot_and_counts_extinction_and_article(
    tmp_path, db_session, settings
) -> None:
    user = ensure_user(db_session, 123456789, settings)
    item = create_learning_item(
        db_session, user, type_="expression", text="push back on"
    )
    db_session.add(
        MistakePattern(
            user_id=user.id,
            description="Blunt disagreement",
            mistake_type="pragmatics",
            linked_learning_item_id=item.id,
            confidence="low",
            status="active",
            event_count=3,
        )
    )
    now = datetime.now(UTC)
    for index in range(5):
        _attempt(
            db_session,
            user,
            at=now - timedelta(days=5 - index),
            answer="I might push back on the proposal with a clear trade-off.",
            status="correct",
            target_ids=[item.id],
        )

    article = handle_article(
        "This article argues that platform teams need clearer ownership. "
        "It assumes that reliability work is currently invisible.",
        session=db_session,
        user=user,
    )
    reply = handle_outcomes(db_session, user, "full")
    mentor = handle_mentor(db_session, user, base_dir=tmp_path)
    snapshot = db_session.scalar(select(LearningMetricSnapshot))
    article_run = db_session.scalar(
        select(EvaluationRun).where(EvaluationRun.kind == "article_reading")
    )
    journal = next(tmp_path.glob("*.md")).read_text(encoding="utf-8")

    assert "Critical reading tasks" in article.text
    assert article_run is not None
    assert "Mistake extinction: 100%" in reply.text
    assert "Article/Critical Reading: 1 measurable events" in reply.text
    assert snapshot is not None
    assert "Learning outcomes - last 30 days" in snapshot.summary_text
    assert "Coach journal:" in mentor.text
    assert "## Latest Outcomes" in journal
    assert "Learning outcomes - last 30 days" in journal


def test_outcomes_reports_insufficient_data_without_fake_progress(
    db_session, settings
) -> None:
    user = ensure_user(db_session, 123456789, settings)

    reply = handle_outcomes(db_session, user)

    assert "insufficient data" in reply.text
    assert db_session.scalar(select(LearningMetricSnapshot)) is not None


def _attempt(
    db_session,
    user,
    *,
    at: datetime,
    answer: str,
    status: str,
    target_ids: list[int],
    feedback: dict | None = None,
    prompt: str = "Write a work update.",
    exercise_type: str = "follow_up",
) -> PracticeAttempt:
    practice = PracticeSession(
        user_id=user.id,
        target_date_local=at.date(),
        started_at=at,
        created_at=at,
        exercises=[],
        status="completed",
    )
    db_session.add(practice)
    db_session.flush()
    attempt = PracticeAttempt(
        practice_session_id=practice.id,
        exercise_index=0,
        exercise_type=exercise_type,
        target_learning_item_ids=target_ids,
        prompt=prompt,
        user_answer=answer,
        status=status,
        feedback=feedback or {},
        created_at=at,
    )
    db_session.add(attempt)
    db_session.flush()
    return attempt
