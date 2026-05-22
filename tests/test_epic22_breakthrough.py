from __future__ import annotations

import pytest
from sqlalchemy import select

from fluentloop.ai.provider import StubProvider
from fluentloop.ai.schemas import AnswerFeedback
from fluentloop.bot.handlers import (
    handle_answer,
    handle_article,
    handle_confidence_rating,
    handle_feedback_layer,
    handle_mentor,
    handle_practice,
    handle_scene,
)
from fluentloop.curriculum_chunks import (
    ChunkRecord,
    import_chunk_records,
    import_chunks_jsonl,
)
from fluentloop.db.models import (
    ExtractedCandidate,
    LearningItem,
    LessonPlan,
    MistakeEvent,
    MistakePattern,
    PracticeAttempt,
)
from fluentloop.evaluation import build_monthly_probe, writing_metrics
from fluentloop.genre_curriculum import (
    genre_lesson_seeds,
    render_genre_curriculum_markdown,
    seed_genre_curriculum,
)
from fluentloop.hint_ladder import hint_ladder_for_pattern
from fluentloop.learning import create_learning_item
from fluentloop.lesson_director import decide_lesson_format
from fluentloop.lesson_formats import GENRE_SPECS, scenario_cards
from fluentloop.operational_drills import (
    article_lab_modules,
    debate_card,
    fluency432_card,
    pre_meeting_brief_card,
    translation_lab_pack,
)
from fluentloop.polish import article_lab_30_day_plan, sprint_mode_plan
from fluentloop.practice import start_or_resume_session
from fluentloop.reflections import record_reflection
from fluentloop.russian_l1_filter import detect_l1_interference
from fluentloop.users import ensure_user


class NativeRewriteErrorProvider(StubProvider):
    def light_call(self, task: str, payload: dict) -> AnswerFeedback:
        if task == "epic_22_native_rewrite":
            raise RuntimeError("native rewrite unavailable")
        return super().light_call(task, payload)  # type: ignore[return-value]


def test_layered_feedback_l1_hit_and_confidence_callbacks(db_session, settings) -> None:
    user = ensure_user(db_session, 123456789, settings)
    create_learning_item(db_session, user, type_="expression", text="depend on")
    start_or_resume_session(db_session, user)

    confidence = handle_confidence_rating(db_session, user, 0, 5)
    reply = handle_answer(db_session, user, StubProvider(), "It depends from release.")
    attempt = db_session.scalar(select(PracticeAttempt))

    assert "Confidence recorded" in confidence.text
    assert attempt is not None
    assert attempt.feedback["confidence_rating"] == 5
    assert attempt.feedback["l1_hits"][0]["rule_id"] == "l1_depend_from"
    assert "L1 mechanism" in attempt.feedback["why_layer"]
    assert "L1 trap" in reply.text
    assert "feedback:layer:1:errors" in {
        button.data for row in (reply.buttons or []) for button in row
    }
    assert db_session.scalar(select(MistakeEvent)) is not None

    layer = handle_feedback_layer(db_session, user, attempt.id, "native")
    assert "Native rewrite" in layer.text


def test_epic22_practice_mode_registry_drives_session(db_session, settings) -> None:
    user = ensure_user(db_session, 123456789, settings)
    create_learning_item(
        db_session,
        user,
        type_="expression",
        text="push back on",
        tags=["stakeholder"],
    )

    reply = handle_practice(db_session, user, "diplomatic")

    assert "Diplomatic Rewrite Drill" in reply.text
    assert "practice:confidence:0:5" in {
        button.data for row in (reply.buttons or []) for button in row
    }
    assert len(scenario_cards()) == 40
    assert len(GENRE_SPECS) == 10


def test_reflection_evaluation_and_chunk_import(tmp_path, db_session, settings) -> None:
    user = ensure_user(db_session, 123456789, settings)
    for index in range(12):
        create_learning_item(
            db_session,
            user,
            type_="expression",
            text=f"chunk {index}",
        )

    reflection_path = record_reflection(
        user, "Hardest part: hedging.", base_dir=tmp_path
    )
    probe = build_monthly_probe(db_session, user)
    metrics = writing_metrics("We might need to adjust scope. It could reduce risk.")
    created, skipped = import_chunk_records(
        db_session,
        user,
        [
            ChunkRecord(
                id="chunk_0001",
                text="the underlying assumption is that",
                type="collocation",
                field="UNCERTAINTY",
                register="professional",
                function="hedging",
                genres=["rfc"],
                cefr_target="C1",
                russian_gloss="лежащее в основе предположение",
                example_sentences=[
                    "The underlying assumption is that demand grows linearly."
                ],
            )
        ],
    )
    item = db_session.scalar(
        select(LearningItem).where(
            LearningItem.text == "the underlying assumption is that"
        )
    )

    assert reflection_path.exists()
    assert probe.held_out_item_ids
    assert metrics["hedging_density"] > 0
    assert (created, skipped) == (1, 0)
    assert item is not None
    assert item.type == "chunk"
    assert item.metadata_json["field"] == "UNCERTAINTY"


def test_russian_l1_hit_list_is_deterministic() -> None:
    hits = detect_l1_interference(
        "We must discuss about this, it depends from the API."
    )

    assert [hit.rule_id for hit in hits[:2]] == [
        "l1_depend_from",
        "l1_discuss_about",
    ]


def test_russian_l1_hit_list_avoids_correct_phrases() -> None:
    hits = detect_l1_interference("It depends on the API, so we should discuss this.")

    assert hits == []


def test_native_rewrite_error_falls_back_to_answer_feedback(
    db_session, settings
) -> None:
    user = ensure_user(db_session, 123456789, settings)
    create_learning_item(db_session, user, type_="expression", text="align on")
    start_or_resume_session(db_session, user)

    reply = handle_answer(db_session, user, NativeRewriteErrorProvider(), "align on")
    attempt = db_session.scalar(select(PracticeAttempt))

    assert "Feedback" in reply.text
    assert attempt is not None
    assert attempt.feedback["status"] in {"correct", "partial", "incorrect"}
    assert attempt.feedback["native_rewrite"]


def test_malformed_chunk_jsonl_reports_line_and_imports_nothing(
    tmp_path, db_session, settings
) -> None:
    user = ensure_user(db_session, 123456789, settings)
    path = tmp_path / "chunks.jsonl"
    path.write_text(
        "\n".join(
            [
                (
                    '{"id":"chunk_0001","text":"it might be worth considering",'
                    '"type":"collocation","field":"UNCERTAINTY",'
                    '"register":"professional","function":"hedging",'
                    '"cefr_target":"C1"}'
                ),
                (
                    '{"id":"chunk_0002","text":"bad chunk","type":"unknown",'
                    '"field":"UNCERTAINTY","register":"professional",'
                    '"function":"hedging","cefr_target":"C1"}'
                ),
            ]
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="line 2"):
        import_chunks_jsonl(db_session, user, path)

    chunk_count = db_session.scalar(
        select(LearningItem).where(LearningItem.type == "chunk")
    )
    assert chunk_count is None


def test_sprint2_lesson_formats_mine_and_score_core(db_session, settings) -> None:
    user = ensure_user(db_session, 123456789, settings)
    create_learning_item(
        db_session,
        user,
        type_="chunk",
        text="it might be worth considering",
        metadata={
            "field": "NEGOTIATION",
            "register": "professional",
            "function": "hedging",
        },
    )

    notebook = handle_practice(db_session, user, "notebook")
    assert "Notebook" in notebook.text
    handle_answer(db_session, user, StubProvider(), "Bad plan.")
    notebook_attempt = db_session.scalars(select(PracticeAttempt)).first()
    assert notebook_attempt is not None
    notebook_diff = notebook_attempt.feedback["format_feedback"]["notebook_diff"]
    assert notebook_diff["candidate_chunks"]
    assert db_session.scalar(select(ExtractedCandidate)) is not None

    discourse = handle_practice(db_session, user, "discourse")
    assert "Discourse Builder" in discourse.text
    handle_answer(
        db_session,
        user,
        StubProvider(),
        "The plan is risky. However, we can reduce scope. "
        "Therefore we should align today.",
    )
    attempts = list(
        db_session.scalars(select(PracticeAttempt).order_by(PracticeAttempt.id))
    )
    discourse_score = attempts[-1].feedback["format_feedback"]["discourse_score"]
    assert discourse_score["has_counterpoint"] is True
    assert discourse_score["has_recommendation"] is True

    article = handle_article(
        "The author argues that remote work might reduce focus, "
        "although the evidence is thin."
    )
    assert "Critical reading tasks" in article.text
    assert "Name the main claim" in article.text

    writing = handle_practice(db_session, user, "writing_workshop")
    assert "Writing Workshop" in writing.text
    session_exercise = db_session.scalars(select(PracticeAttempt)).all()
    assert session_exercise is not None


def test_sprint2_mistake_extinction_metadata(db_session, settings) -> None:
    user = ensure_user(db_session, 123456789, settings)
    db_session.add(
        MistakePattern(
            user_id=user.id,
            description="Recurring article issue",
            mistake_type="articles",
            confidence="high",
            status="active",
            wrong_examples=["We start before sprint."],
            correct_examples=["We start before the sprint."],
            event_count=3,
        )
    )
    db_session.flush()

    reply = handle_practice(db_session, user, "mistakes")
    assert "Mistake Drill" in reply.text
    handle_answer(db_session, user, StubProvider(), "We start before the sprint.")
    attempt = db_session.scalar(select(PracticeAttempt))

    assert attempt is not None
    extinction = attempt.feedback["format_feedback"]["mistake_extinction"]
    assert extinction["state"] in {"active", "building"}
    assert extinction["target_streak"] == 5


def test_sprint3_genre_curriculum_seed(db_session, settings) -> None:
    user = ensure_user(db_session, 123456789, settings)

    result = seed_genre_curriculum(db_session, user)
    chunk_items = list(
        db_session.scalars(select(LearningItem).where(LearningItem.type == "chunk"))
    )
    genre_plans = list(
        db_session.scalars(select(LessonPlan).where(LessonPlan.format == "genre"))
    )
    markdown = render_genre_curriculum_markdown()

    assert result["lessons"] == 10
    assert result["items"] >= 40
    assert len(genre_lesson_seeds()) == 10
    assert chunk_items
    assert len(genre_plans) == 10
    assert "Genre Curriculum" in markdown


def test_sprint4_teacher_layer_director_journal_scene_and_hints(
    tmp_path, db_session, settings
) -> None:
    user = ensure_user(db_session, 123456789, settings)
    chunk = create_learning_item(
        db_session,
        user,
        type_="chunk",
        text="one constraint we should account for",
    )
    pattern = MistakePattern(
        user_id=user.id,
        description="Recurring article issue",
        mistake_type="articles",
        confidence="high",
        status="active",
        wrong_examples=["before sprint"],
        correct_examples=["before the sprint"],
        event_count=4,
    )
    db_session.add(pattern)
    db_session.flush()

    decision = decide_lesson_format(
        due_items=[],
        scored_items=[chunk],
        patterns=[pattern],
    )
    scene = handle_scene("2")
    journal = handle_mentor(db_session, user, base_dir=tmp_path)
    ladder = hint_ladder_for_pattern(pattern)

    assert decision.mode == "mistakes"
    assert "Code review feedback" in scene.text
    assert "Coach journal" in journal.text
    assert ladder[-1].startswith("4. Rewrite")


def test_sprint5_operational_drill_cards_are_structured() -> None:
    brief = pre_meeting_brief_card("Q3 roadmap review")
    article = article_lab_modules("The author might be wrong about AI adoption.")
    debate = debate_card("remote work improves focus")
    translation = translation_lab_pack("planning")
    fluency = fluency432_card("incident update")

    assert brief["topic"] == "Q3 roadmap review"
    assert len(article) == 5
    assert "counter-argument" in debate["score_axes"]
    assert len(translation["sentences_ru"]) == 5
    assert [round_["minutes"] for round_ in fluency["rounds"]] == [4, 3, 2]


def test_sprint6_polish_article_sprint_and_native_comparison(
    tmp_path, db_session, settings
) -> None:
    user = ensure_user(db_session, 123456789, settings)
    create_learning_item(db_session, user, type_="expression", text="align on")
    start_or_resume_session(db_session, user)
    handle_answer(db_session, user, StubProvider(), "align")

    article = handle_article("AI adoption might reshape engineering teams.")
    sprint = handle_practice(db_session, user, "sprint")
    journal = handle_mentor(db_session, user, base_dir=tmp_path)
    journal_text = next(tmp_path.glob("*.md")).read_text(encoding="utf-8")

    assert len(article_lab_30_day_plan("AI adoption")) == 6
    assert sprint_mode_plan()["duration_days"] == 14
    assert "30-day pipeline" in article.text
    assert "Sprint Mode" in sprint.text
    assert "Rolling Native Comparison" in journal_text
    assert "Coach journal" in journal.text
