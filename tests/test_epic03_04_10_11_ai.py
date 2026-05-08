from __future__ import annotations

from sqlalchemy import select

from fluentloop.ai.provider import StubProvider
from fluentloop.ai.schemas import Validated
from fluentloop.bot.handlers import (
    handle_approve_all,
    handle_candidate_action,
    handle_candidate_edit_menu,
    handle_candidate_edit_prompt,
    handle_candidate_edit_value,
    handle_candidates,
    handle_mistake_action,
    handle_mistakes,
    handle_skip_all,
    handle_upload,
    handle_upload_prompt,
    handle_upload_start,
    handle_upload_type_choice,
)
from fluentloop.db.models import ExtractedCandidate, LearningItem, MistakeEvent
from fluentloop.feedback import apply_feedback, check_answer
from fluentloop.materials import approve_all, extract_candidates, store_material
from fluentloop.mistakes import ingest_mistake_event, promote_pattern
from fluentloop.users import ensure_user


class MalformedProvider(StubProvider):
    def heavy_call(self, task: str, payload: dict) -> Validated:
        raise RuntimeError("bad model output")


def test_upload_extract_approve_and_feedback(tmp_path, db_session, settings) -> None:
    user = ensure_user(db_session, 123456789, settings)
    provider = StubProvider(tmp_path / "usage.jsonl")
    material = store_material(db_session, user, "push back on; align on; articles")
    candidates = extract_candidates(db_session, material, provider)
    assert len(candidates) >= 3
    assert approve_all(db_session, user, material) == len(candidates)
    exercise = {
        "exercise_type": "translate",
        "prompt": "Translate",
        "expected_answer": "push back on",
        "target_learning_item_ids": [],
    }
    feedback = check_answer(provider, exercise, "push back")
    assert feedback.status in {"partial", "correct"}
    apply_feedback(db_session, user, exercise, "push back", feedback)
    assert (tmp_path / "usage.jsonl").exists()
    typed = store_material(db_session, user, "notes", type_="lesson_notes")
    assert typed.type == "lesson_notes"


def test_upload_handler_returns_approve_command(tmp_path, db_session, settings) -> None:
    user = ensure_user(db_session, 123456789, settings)
    provider = StubProvider(tmp_path / "usage.jsonl")
    reply = handle_upload(db_session, user, provider, "push back on and align on")
    assert "Send /approve" in reply.text
    assert reply.buttons is not None
    assert reply.buttons[0][0].data.startswith("approve:all:")
    assert reply.buttons[1][0].data.startswith("candidates:list:")
    assert reply.buttons[2][0].data.startswith("approve:skip:")
    material_id = int(reply.text.split("/approve ", 1)[1].split()[0])
    listed = handle_candidates(db_session, user, material_id)
    assert "Use /candidate add" in listed.text
    assert listed.buttons is not None
    listed_data = {button.data for row in listed.buttons for button in row}
    assert any(data.startswith("candidate:add:") for data in listed_data)
    assert any(data.startswith("candidate:edit:") for data in listed_data)
    assert any(data.startswith("candidate:skip:") for data in listed_data)
    candidate = db_session.scalar(select(ExtractedCandidate))
    assert candidate is not None
    skipped = handle_candidate_action(db_session, user, "skip", candidate.id)
    assert "Skipped" in skipped.text
    added = handle_candidate_action(db_session, user, "add", candidate.id)
    assert "already handled" in added.text
    approved = handle_approve_all(db_session, user, material_id)
    assert "Added" in approved.text
    item = db_session.scalar(
        select(LearningItem).where(LearningItem.user_id == user.id)
    )
    assert item is not None

    second = handle_upload(db_session, user, provider, "circle back and follow up")
    second_material_id = int(second.text.split("/approve ", 1)[1].split()[0])
    skipped_all = handle_skip_all(db_session, user, second_material_id)
    assert "Skipped" in skipped_all.text


def test_lesson_notes_upload_returns_larger_pool_and_approval_summary(
    tmp_path, db_session, settings
) -> None:
    user = ensure_user(db_session, 123456789, settings)
    provider = StubProvider(tmp_path / "usage.jsonl")
    reply = handle_upload(
        db_session,
        user,
        provider,
        "# Lesson\n\n" + "Stakeholder update and risk mitigation. " * 40,
        type_="lesson_notes",
    )

    assert "Found" in reply.text
    assert "Candidates:" in reply.text
    assert "lesson pool" in reply.text
    assert len(list(db_session.scalars(select(ExtractedCandidate)))) >= 20

    material_id = int(reply.text.split("/approve ", 1)[1].split()[0])
    approved = handle_approve_all(db_session, user, material_id, provider=provider)

    assert "LessonPlan #" in approved.text
    assert "Pool size:" in approved.text
    assert "Rotation:" in approved.text


def test_introverts_lesson_extracts_reported_speech_not_old_business_fallback(
    tmp_path, db_session, settings
) -> None:
    user = ensure_user(db_session, 123456789, settings)
    provider = StubProvider(tmp_path / "usage.jsonl")
    raw = """
    # VB UP

    Do you prefer working with introverts or extroverts?
    I suggested having just one meeting a week.
    People refused to take the idea seriously.
    I insisted on giving it a try.
    I threatened to stop coming to meetings.
    He boasted about having a lot of achievements.
    He claimed that he worked as the manager of a well-known restaurant.
    I questioned him about the details.
    He admitted that it wasn't true.

    Verb-pattern table:
    propose, recommend, admit, deny, regret, suggest, apologize for,
    insist on, boast about, claim, threaten to, accuse someone of,
    question someone about.
    """
    reply = handle_upload(
        db_session,
        user,
        provider,
        raw,
        type_="lesson_notes",
    )

    assert "Lesson: Reported Speech: Introverts" in reply.text
    assert "Knowledge areas:" in reply.text
    assert "expression: suggest having" in reply.text
    assert "grammar_rule: Verb + preposition + gerund patterns" in reply.text
    assert "...and" not in reply.text
    assert "summarize the trade-off" not in reply.text

    material_id = int(reply.text.split("/approve ", 1)[1].split()[0])
    approved = handle_approve_all(db_session, user, material_id, provider=provider)

    assert "LessonPlan #" in approved.text
    assert "Reported Speech: Introverts" in approved.text
    assert "suggest having" in approved.text
    assert "...and" not in approved.text


def test_candidate_edit_flow_before_approval(tmp_path, db_session, settings) -> None:
    user = ensure_user(db_session, 123456789, settings)
    provider = StubProvider(tmp_path / "usage.jsonl")
    reply = handle_upload(db_session, user, provider, "push back on and align on")
    material_id = int(reply.text.split("/approve ", 1)[1].split()[0])
    candidate = db_session.scalar(select(ExtractedCandidate))
    assert candidate is not None

    menu = handle_candidate_edit_menu(db_session, user, candidate.id)
    assert menu.buttons is not None
    assert f"candidate_field:{candidate.id}:text" in {
        button.data for row in menu.buttons for button in row
    }

    prompt = handle_candidate_edit_prompt(candidate.id, "tags")
    assert "comma-separated tags" in prompt.text

    edited = handle_candidate_edit_value(
        db_session,
        user,
        candidate.id,
        "text",
        "push back on a proposal",
    )
    assert "Edited candidate" in edited.text
    assert "push back on a proposal" in edited.text
    assert candidate.status == "edited"
    assert edited.buttons is not None

    tags = handle_candidate_edit_value(
        db_session,
        user,
        candidate.id,
        "tags",
        "meetings, stakeholders",
    )
    assert "meetings, stakeholders" in tags.text

    approved = handle_approve_all(db_session, user, material_id)
    assert "Added" in approved.text
    item = db_session.scalar(
        select(LearningItem).where(LearningItem.text == "push back on a proposal")
    )
    assert item is not None
    assert item.tags == ["meetings", "stakeholders"]


def test_free_text_upload_prompt_buttons() -> None:
    reply = handle_upload_prompt()
    assert "Treat this text as lesson material" in reply.text
    assert reply.buttons is not None
    data = {button.data for row in reply.buttons for button in row}
    assert data == {"upload:confirm:pending", "upload:cancel:pending"}


def test_upload_type_picker_buttons() -> None:
    reply = handle_upload_start()
    assert reply.buttons is not None
    data = {button.data for row in reply.buttons for button in row}
    assert "upload_type:lesson_notes" in data
    assert "upload_type:teacher_feedback" in data
    assert "upload_type:other" in data
    chosen = handle_upload_type_choice("homework")
    assert "Paste homework material" in chosen.text
    rejected = handle_upload_type_choice("pdf")
    assert "Unsupported material type" in rejected.text


def test_upload_handler_returns_friendly_size_error(
    tmp_path, db_session, settings
) -> None:
    user = ensure_user(db_session, 123456789, settings)
    provider = StubProvider(tmp_path / "usage.jsonl")
    reply = handle_upload(db_session, user, provider, "x" * 20_001)
    assert "Could not store material" in reply.text


def test_upload_handler_returns_friendly_extraction_error(
    tmp_path, db_session, settings
) -> None:
    user = ensure_user(db_session, 123456789, settings)
    provider = MalformedProvider(tmp_path / "usage.jsonl")
    reply = handle_upload(db_session, user, provider, "push back on")
    assert "Could not extract material" in reply.text
    assert "try again or rephrase" in reply.text


def test_mistake_pattern_threshold(db_session, settings) -> None:
    user = ensure_user(db_session, 123456789, settings)
    pattern = None
    for index in range(3):
        event = MistakeEvent(
            user_id=user.id,
            wrong_answer=f"wrong {index}",
            corrected_answer="right",
            explanation="because",
            mistake_type="articles",
        )
        db_session.add(event)
        db_session.flush()
        pattern = ingest_mistake_event(db_session, event)
    assert pattern is not None
    assert pattern.confidence == "low"
    promote_pattern(db_session, pattern)
    assert pattern.confidence == "high"


def test_mistake_pattern_actions(db_session, settings) -> None:
    user = ensure_user(db_session, 123456789, settings)
    pattern = None
    for index in range(3):
        event = MistakeEvent(
            user_id=user.id,
            wrong_answer=f"wrong {index}",
            corrected_answer="right",
            explanation="because",
            mistake_type="articles",
        )
        db_session.add(event)
        db_session.flush()
        pattern = ingest_mistake_event(db_session, event)
    assert pattern is not None
    listed = handle_mistakes(db_session, user)
    assert listed.buttons is not None
    listed_data = {button.data for row in listed.buttons for button in row}
    assert f"mistake:focus:{pattern.id}" in listed_data
    assert f"mistake:ignore:{pattern.id}" in listed_data
    assert f"mistake:examples:{pattern.id}" in listed_data
    examples = handle_mistake_action(db_session, user, "examples", pattern.id)
    assert "Examples for pattern" in examples.text
    assert "Wrong:" in examples.text
    reply = handle_mistake_action(db_session, user, "focus", pattern.id)
    assert "Promoted" in reply.text
    assert pattern.confidence == "high"
    reply = handle_mistake_action(db_session, user, "ignore", pattern.id)
    assert "Archived" in reply.text
    assert pattern.status == "archived"
