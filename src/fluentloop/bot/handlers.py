from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from fluentloop.adaptive_learning import is_adaptive_item
from fluentloop.ai.provider import AIProvider
from fluentloop.bot.formatting import (
    HTML_PARSE_MODE,
    bold,
    code,
    html_escape,
    italic,
    labeled,
)
from fluentloop.bot.messages import (
    HELP,
    SIMPLE_HELP,
    candidate_summary,
    mistake_patterns,
    start_message,
)
from fluentloop.bot.state import StateStore
from fluentloop.coach_journal import write_coach_journal
from fluentloop.config import Settings
from fluentloop.db.models import LearningItem, User, VocabDelivery
from fluentloop.exercises import EXERCISE_TYPES
from fluentloop.feedback import (
    apply_feedback,
    check_answer,
    queue_feedback_suggestions,
    render_compact_teacher_feedback,
    render_detailed_teacher_feedback,
    write_dispute,
)
from fluentloop.grammar import seed_concepts
from fluentloop.learning import (
    create_learning_item,
    favorite_items,
    list_items,
    set_item_status,
    toggle_favorite,
)
from fluentloop.lesson_formats import (
    article_lab_prompt,
    debate_prompt,
    fluency432_prompt,
    format_for_mode,
    mentor_question,
    normalize_practice_mode,
    practice_modes_help,
    pre_meeting_brief,
    scene_builder,
    translation_lab_prompt,
)
from fluentloop.lesson_library import (
    library_template_by_id,
    library_templates,
    publish_lesson_template,
    subscribe_to_template,
)
from fluentloop.lesson_plans import (
    active_lesson_plans,
    find_lesson_plan,
    lesson_items,
    lesson_plan_by_id,
    lesson_pool_size,
    random_lesson_plan,
)
from fluentloop.lesson_types import format_target_mix, lesson_type_for_plan
from fluentloop.materials import (
    MATERIAL_TYPES,
    approve_all,
    approve_candidate,
    edit_candidate,
    extract_candidates,
    skip_all,
    skip_candidate,
    store_material,
)
from fluentloop.mistakes import active_patterns, archive_pattern, promote_pattern
from fluentloop.outcomes import (
    build_outcome_report,
    current_baseline_prompt,
    record_article_probe,
    record_baseline,
)
from fluentloop.practice import (
    get_in_progress_session,
    next_exercise,
    record_attempt,
    record_confidence_rating,
    start_explicit_session,
    start_or_resume_session,
    summarize_session,
)
from fluentloop.reflections import record_reflection, reflection_prompt
from fluentloop.srs import convert_last_good_to_hard
from fluentloop.stats import collect_stats, render_stats
from fluentloop.users import ensure_user, format_settings, update_setting

ITEM_STATUS_USAGE = "Use /item archive <id>, /item suspend <id>, or /item restore <id>."


@dataclass(frozen=True)
class InlineButton:
    text: str
    data: str


@dataclass(frozen=True)
class BotReply:
    text: str
    target_chat_id: int | str | None = None
    buttons: list[list[InlineButton]] | None = None
    message_thread_id: int | None = None
    extra_replies: tuple[BotReply, ...] = ()
    parse_mode: str | None = None
    # Callback replies that redraw their own message instead of posting a new
    # one. A multi-select keyboard would otherwise spam the chat with one
    # message per tap.
    edit_message: bool = False
    # Attach the always-visible keyboard under the input field. Commands are
    # discoverable only if you already know them; this makes starting practice
    # a tap from anywhere in the chat.
    persistent_keyboard: bool = False
    # Take it away again. Mutually exclusive with the flag above.
    clear_keyboard: bool = False
    # The sender delivers this quiz question (poll or buttons) right after
    # the reply itself. Handlers stay Telegram-free; app.py does the sending.
    quiz_question_delivery_id: int | None = None
    # The personal simple pilot uses a compact three-action persistent keyboard.
    simple_keyboard: bool = False
    # Let callback routing cancel a writing capture only after an accepted choice.
    simple_choice_accepted: bool = False


def _button(text: str, data: str) -> InlineButton:
    return InlineButton(text=text, data=data)


def _settings_buttons(user: User) -> list[list[InlineButton]]:
    from fluentloop.learning_prefs import is_simple_mode

    mode_action = "advanced" if is_simple_mode(user) else "simple"
    mode_label = "Advanced mode" if mode_action == "advanced" else "Try simple mode"
    return [
        [
            _button("B2+", "settings:level:B2+"),
            _button("B2+/C1-", "settings:level:B2+/C1-"),
            _button("C1-", "settings:level:C1-"),
        ],
        [
            _button("Business+IT", "settings:focus_areas:business,IT"),
            _button("Grammar", "settings:focus_areas:grammar"),
            _button(
                "All focus",
                "settings:focus_areas:business,IT,conversational,grammar",
            ),
        ],
        [
            _button("10 min", "settings:practice_duration_minutes:10"),
            _button("15 min", "settings:practice_duration_minutes:15"),
            _button("25 min", "settings:practice_duration_minutes:25"),
        ],
        [
            _button("RU", "settings:explanation_language:ru"),
            _button("EN", "settings:explanation_language:en"),
            _button("Mixed", "settings:explanation_language:mixed"),
        ],
        [
            _button("20:00", "settings:reminder_time:20:00"),
            _button("20:30", "settings:reminder_time:20:30"),
            _button("21:00", "settings:reminder_time:21:00"),
        ],
        [
            _button("Moscow TZ", "settings:timezone:Europe/Moscow"),
            _button("Berlin TZ", "settings:timezone:Europe/Berlin"),
        ],
        [
            _button("Morning 07:00", "settings:vocab_morning:07:00"),
            _button("08:00", "settings:vocab_morning:08:00"),
            _button("09:00", "settings:vocab_morning:09:00"),
        ],
        [
            _button("Midday 12:00", "settings:vocab_midday:12:00"),
            _button("13:00", "settings:vocab_midday:13:00"),
            _button("Evening 19:00", "settings:vocab_evening:19:00"),
        ],
        [
            _button("3 words", "settings:vocab_words_per_day:3"),
            _button("5 words", "settings:vocab_words_per_day:5"),
            _button("7 words", "settings:vocab_words_per_day:7"),
        ],
        [
            _button("Quiz 5", "settings:vocab_quiz_size:5"),
            _button("10", "settings:vocab_quiz_size:10"),
            _button("15", "settings:vocab_quiz_size:15"),
            _button("20", "settings:vocab_quiz_size:20"),
        ],
        [_button("Refresh", "settings:refresh:now")],
        [_button(mode_label, f"simple:mode:{mode_action}")],
    ]


def _candidate_buttons(candidate_id: int) -> list[InlineButton]:
    return [
        _button(f"Add #{candidate_id}", f"candidate:add:{candidate_id}"),
        _button(f"Edit #{candidate_id}", f"candidate:edit:{candidate_id}"),
        _button(f"Skip #{candidate_id}", f"candidate:skip:{candidate_id}"),
    ]


def _favorite_button(item_id: int, is_favorite: bool) -> InlineButton:
    marker = "Unstar" if is_favorite else "Star"
    return _button(f"{marker} #{item_id}", f"favorite:toggle:{item_id}")


def _item_buttons(item_id: int, status: str, is_favorite: bool) -> list[InlineButton]:
    buttons = [_favorite_button(item_id, is_favorite)]
    if status == "active":
        buttons.extend(
            [
                _button(f"Archive #{item_id}", f"item:archive:{item_id}"),
                _button(f"Suspend #{item_id}", f"item:suspend:{item_id}"),
            ]
        )
    else:
        buttons.append(_button(f"Restore #{item_id}", f"item:restore:{item_id}"))
    return buttons


def _dispute_buttons(
    attempt_id: int, *, allow_hard: bool = False
) -> list[list[InlineButton]]:
    buttons = [
        [
            _button("Got it", f"attempt:ack:{attempt_id}"),
            _button("I disagree", f"dispute:{attempt_id}:equally_valid"),
        ],
        [
            _button("AI was wrong", f"dispute:{attempt_id}:ai_wrong"),
            _button("Style issue", f"dispute:{attempt_id}:style_preference"),
        ],
    ]
    if allow_hard:
        buttons.insert(1, [_button("Hard", f"attempt:hard:{attempt_id}")])
    return buttons


def _attempt_buttons(
    attempt_id: int, *, allow_hard: bool = False
) -> list[list[InlineButton]]:
    buttons = _dispute_buttons(attempt_id, allow_hard=allow_hard)
    buttons.append(
        [
            _button("Errors", f"feedback:layer:{attempt_id}:errors"),
            _button("Native", f"feedback:layer:{attempt_id}:native"),
            _button("Why", f"feedback:layer:{attempt_id}:why"),
        ]
    )
    buttons.append([_button("Teacher details", f"feedback:explain:{attempt_id}")])
    return buttons


def _practice_buttons(exercise_index: int | None = None) -> list[list[InlineButton]]:
    buttons = [[_button("Skip / show answer", "practice:skip")]]
    if exercise_index is not None:
        buttons.append(
            [
                _button(str(rating), f"practice:confidence:{exercise_index}:{rating}")
                for rating in range(1, 6)
            ]
        )
    return buttons


def _attempt_and_practice_buttons(
    attempt_id: int, *, allow_hard: bool = False, exercise_index: int | None = None
) -> list[list[InlineButton]]:
    return [
        *_attempt_buttons(attempt_id, allow_hard=allow_hard),
        *_practice_buttons(exercise_index),
    ]


def handle_upload_prompt() -> BotReply:
    return BotReply(
        "No active exercise. Treat this text as lesson material?",
        buttons=[
            [
                _button("Treat as lesson material", "upload:confirm:pending"),
                _button("Cancel", "upload:cancel:pending"),
            ]
        ],
    )


def _upload_type_buttons() -> list[list[InlineButton]]:
    return [
        [
            _button("Lesson notes", "upload_type:lesson_notes"),
            _button("Word list", "upload_type:word_list"),
        ],
        [
            _button("Expressions", "upload_type:expression_list"),
            _button("Homework", "upload_type:homework"),
        ],
        [
            _button("Exercise", "upload_type:exercise"),
            _button("Teacher feedback", "upload_type:teacher_feedback"),
        ],
        [_button("Other", "upload_type:other")],
    ]


def handle_upload_start() -> BotReply:
    return BotReply(
        "Choose material type, or paste the material now to use other.",
        buttons=_upload_type_buttons(),
    )


def handle_upload_type_choice(type_: str) -> BotReply:
    if type_ not in MATERIAL_TYPES:
        return BotReply("Unsupported material type.")
    return BotReply(f"Paste {type_} material in the next message.")


def handle_channel_hub(
    channel_id: str, *, message_thread_id: int | None = None
) -> BotReply:
    return BotReply(
        "#practice_flow\n"
        "FluentLoop English practice hub.\n\n"
        "Practice flow lives here in the workspace:\n"
        "- #practice_flow / Practice Flow for session starts\n"
        "- #feedback for answer feedback\n"
        "- #next_prompt for the next exercise\n"
        "- #summary for session results\n\n"
        "In the forum group, you can answer in the active practice topic. "
        "In the announcement channel, free-text answers still go to the bot DM.",
        channel_id,
        buttons=[
            [_button("Start practice", "today:start")],
            [_button("Upload material", "materials:start")],
        ],
        message_thread_id=message_thread_id,
    )


def handle_channel_help(
    channel_id: str, *, message_thread_id: int | None = None
) -> BotReply:
    return BotReply(
        "#help\n"
        "How to use FluentLoop\n\n"
        "Your day: words at 08:00, a drill at 13:00, a quiz at 19:00, in your "
        "own timezone. /pause and /resume control them, /settings changes the "
        "times. Send any word or phrase to add it - commas for several.\n\n"
        "Practising the same words, from lightest to hardest:\n"
        "- /today 5 shows cards; you only read them.\n"
        "- /review is a short 2-3 minute pass over what is due - start here.\n"
        "- /practice vocab is a full vocabulary lesson around them.\n"
        "- /today is the general 15-minute lesson from your lesson plans.\n\n"
        "1. Start with /today for the automatic 15-minute lesson, or choose a "
        "lesson with /lessons and /lesson.\n"
        "2. Browse shared seed lessons with /library, then copy one into your "
        "own lesson base with /subscribe <template_id>.\n"
        "3. Answer in text. Use /skip or Skip / show answer when you want the "
        "model answer first.\n"
        "4. Read compact teacher feedback. Use /feedback explain <attempt_id> "
        "for the full breakdown.\n"
        "5. Upload lesson notes in Materials Upload with /upload; approve "
        "candidates before they become active learning items.\n"
        "6. Record /baseline monthly and check /outcomes for learning-quality "
        "progress.\n\n"
        "Workspace map:\n"
        "- Practice Flow: current lesson and answers\n"
        "- Materials Upload: lesson notes, word lists, homework, feedback\n"
        "- Feedback: corrections and explanations\n"
        "- Next Prompts: follow-up prompts\n"
        "- Mistakes, Summaries, Stats: weak points and progress\n\n"
        "Useful commands: /today, /review, /practice vocab, /words, /more, "
        "/learned, /setup, /baseline, /outcomes, /library, /subscribe, "
        "/practice, /topics, /lessons, /lesson random, /lesson topic <query>, "
        "/upload, /skip, /help, /howto.",
        channel_id,
        buttons=[
            [_button("Today", "today:start"), _button("Lessons", "lessons:list")],
            [_button("Library", "library:list")],
            [
                _button("Topics", "topics:list"),
                _button("Upload material", "materials:start"),
            ],
            [_button("Practice modes", "practice:modes")],
        ],
        message_thread_id=message_thread_id,
    )


def handle_materials_channel_hub(
    channel_id: str, *, message_thread_id: int | None = None
) -> BotReply:
    return BotReply(
        "#materials_upload\n"
        "Lesson materials inbox.\n\n"
        "Use this topic for lesson notes, word lists, homework, exercises, "
        "and teacher feedback. Send /upload here, or tap Upload material and "
        "paste the text in the bot DM. New learning items still require "
        "approval before they become active.\n\n"
        "Best paste format:\n"
        "Context / Vocabulary or chunks / Grammar or patterns / Mistakes or "
        "teacher feedback / My examples.",
        channel_id,
        buttons=[[_button("Upload material", "materials:start")]],
        message_thread_id=message_thread_id,
    )


def is_allowed(settings: Settings, telegram_user_id: int) -> bool:
    return (
        settings.telegram_allowed_user_id is None
        or settings.telegram_allowed_user_id == telegram_user_id
    )


def handle_start(
    session: Session,
    settings: Settings,
    telegram_user_id: int,
    *,
    chat_id: int | None = None,
) -> BotReply:
    from fluentloop.learning_prefs import is_simple_mode
    from fluentloop.vocab_prefs import get_prefs

    user = ensure_user(session, telegram_user_id, settings)
    seed_concepts(session)
    if is_simple_mode(user):
        return BotReply(
            start_message(
                bool(settings.telegram_forum_group_id or settings.telegram_channel_id),
                simple=True,
            ),
            user.telegram_user_id,
            persistent_keyboard=get_prefs(user).keyboard,
            simple_keyboard=True,
        )
    if get_prefs(user).onboarded_at is None:
        return handle_onboarding_start(
            session, user, chat_id=chat_id if chat_id is not None else telegram_user_id
        )
    return BotReply(
        start_message(
            bool(settings.telegram_forum_group_id or settings.telegram_channel_id)
        )
        + "\n\nRun /setup to redo the setup wizard."
        + ("" if get_prefs(user).keyboard else "\n/keyboard brings the buttons back."),
        user.telegram_user_id,
        persistent_keyboard=get_prefs(user).keyboard,
    )


def handle_help(user: User | None = None) -> BotReply:
    if user is not None:
        from fluentloop.learning_prefs import is_simple_mode

        if is_simple_mode(user):
            return BotReply(SIMPLE_HELP)
    return BotReply(HELP)


def handle_settings(
    session: Session,
    user: User,
    *,
    channel_id: str | None = None,
    message_thread_id: int | None = None,
) -> BotReply:
    return BotReply(
        format_settings(user),
        channel_id,
        buttons=_settings_buttons(user),
        message_thread_id=message_thread_id,
    )


def handle_setting_update(
    session: Session, user: User, field: str, value: str
) -> BotReply:
    try:
        update_setting(session, user, field, value)
    except ValueError as exc:
        return BotReply(f"Could not update setting: {exc}")
    return BotReply(
        "Updated.\n" + format_settings(user), buttons=_settings_buttons(user)
    )


def handle_add(
    session: Session,
    user: User,
    *,
    type_: str,
    text: str,
    meaning: str = "",
    tags: list[str] | None = None,
) -> BotReply:
    from sqlalchemy import select

    from fluentloop.db.models import LearningItem

    existing = session.scalar(
        select(LearningItem).where(
            LearningItem.user_id == user.id,
            LearningItem.type == type_,
            LearningItem.text == text.strip(),
        )
    )
    if existing is not None:
        return BotReply(
            f"Duplicate item #{existing.id} already exists: {existing.text}.\n"
            "Merge: keep using the existing item.\n"
            "Keep separate: add a clarifying suffix or tag, then send /add again."
        )
    try:
        item = create_learning_item(
            session,
            user,
            type_=type_,
            text=text,
            meaning=meaning,
            tags=tags or [],
        )
    except ValueError as exc:
        return BotReply(f"Could not add item: {exc}")
    return BotReply(
        f"Added #{item.id} {item.type}: {item.text}",
        buttons=[[_favorite_button(item.id, item.is_favorite)]],
    )


def parse_add_payload(raw: str) -> tuple[str, str, str, list[str]]:
    parts = [part.strip() for part in raw.split("|")]
    if len(parts) < 2:
        raise ValueError("Use: type | text | meaning | tag1,tag2")
    type_ = parts[0]
    text = parts[1]
    meaning = parts[2] if len(parts) >= 3 else ""
    tags = (
        [tag.strip() for tag in parts[3].split(",") if tag.strip()]
        if len(parts) >= 4
        else []
    )
    return type_, text, meaning, tags


def handle_add_text(session: Session, user: User, raw: str) -> BotReply:
    try:
        type_, text, meaning, tags = parse_add_payload(raw)
    except ValueError as exc:
        return BotReply(str(exc))
    return handle_add(session, user, type_=type_, text=text, meaning=meaning, tags=tags)


def handle_upload(
    session: Session,
    user: User,
    provider: AIProvider,
    raw_text: str,
    *,
    type_: str = "other",
) -> BotReply:
    try:
        material = store_material(session, user, raw_text, type_=type_)
    except ValueError as exc:
        return BotReply(f"Could not store material: {exc}")
    try:
        candidates = extract_candidates(session, material, provider)
    except ValueError as exc:
        return BotReply(f"Could not extract material: {exc}")
    material_id = candidates[0].source_material_id if candidates else material.id
    buttons: list[list[InlineButton]] = [
        [_button("Approve all", f"approve:all:{material_id}")],
        [_button("Review one by one", f"candidates:list:{material_id}")],
        [_button("Skip all", f"approve:skip:{material_id}")],
    ]
    return BotReply(
        candidate_summary(
            candidates,
            raw_text=material.raw_text,
            material_type=material.type,
        ),
        buttons=buttons,
    )


def handle_approve_all(
    session: Session,
    user: User,
    material_id: int,
    provider: AIProvider | None = None,
) -> BotReply:
    from fluentloop.db.models import LearningItem, LessonPlan, SourceMaterial

    source = session.get(SourceMaterial, material_id)
    if source is None:
        return BotReply("Material not found.")
    count = approve_all(session, user, source, provider=provider)
    items = list(
        session.scalars(
            select(LearningItem)
            .where(
                LearningItem.user_id == user.id,
                LearningItem.source_material_id == source.id,
                LearningItem.status == "active",
            )
            .order_by(LearningItem.created_at.asc())
        )
    )
    plan = session.scalar(
        select(LessonPlan)
        .where(
            LessonPlan.user_id == user.id,
            LessonPlan.source_material_id == source.id,
            LessonPlan.status.in_(("active", "draft")),
        )
        .order_by(LessonPlan.updated_at.desc())
    )
    lines = [f"Added {count} learning items."]
    if items:
        lines.append("Lesson pool:")
        for item in items:
            meaning = item.meaning or item.explanation
            suffix = f" - {meaning[:80]}" if meaning else ""
            lines.append(f"- {item.type}: {item.text}{suffix}")
    if plan is not None:
        lines.extend(
            [
                "",
                f"LessonPlan #{plan.id}: {plan.title}",
                f"Topic: {plan.topic}",
                f"Goal: {plan.goal}",
                f"Pool size: {len(items)} target(s)",
                (
                    "Rotation: /today will sample micro-drills by teacher "
                    "priority, SRS due status, novelty, and recent practice."
                ),
            ]
        )
    return BotReply("\n".join(lines))


def handle_skip_all(session: Session, user: User, material_id: int) -> BotReply:
    from fluentloop.db.models import SourceMaterial

    source = session.get(SourceMaterial, material_id)
    if source is None or source.user_id != user.id:
        return BotReply("Material not found.")
    count = skip_all(session, source)
    return BotReply(f"Skipped {count} pending candidates.")


def handle_candidates(session: Session, user: User, material_id: int) -> BotReply:
    from sqlalchemy import select

    from fluentloop.db.models import ExtractedCandidate, SourceMaterial

    source = session.get(SourceMaterial, material_id)
    if source is None or source.user_id != user.id:
        return BotReply("Material not found.")
    candidates = session.scalars(
        select(ExtractedCandidate)
        .where(ExtractedCandidate.source_material_id == source.id)
        .order_by(ExtractedCandidate.id)
    ).all()
    if not candidates:
        return BotReply("No candidates for this material.")
    lines = [f"Candidates for material #{source.id}"]
    for candidate in candidates:
        lines.append(
            f"- #{candidate.id} [{candidate.status}] {candidate.type}: {candidate.text}"
        )
    buttons = [
        _candidate_buttons(candidate.id)
        for candidate in candidates
        if candidate.status == "pending"
    ]
    lines.append("Use /candidate add <id> or /candidate skip <id>.")
    return BotReply("\n".join(lines), buttons=buttons or None)


def handle_candidate_action(
    session: Session,
    user: User,
    action: str,
    candidate_id: int,
    provider: AIProvider | None = None,
) -> BotReply:
    from fluentloop.db.models import ExtractedCandidate

    candidate = session.get(ExtractedCandidate, candidate_id)
    if candidate is None:
        return BotReply("Candidate not found.")
    try:
        if action == "add":
            changed = approve_candidate(session, user, candidate, provider=provider)
            text = (
                f"Added candidate #{candidate.id}."
                if changed
                else "Candidate already handled."
            )
            return BotReply(text)
        if action == "skip":
            changed = skip_candidate(session, user, candidate)
            text = (
                f"Skipped candidate #{candidate.id}."
                if changed
                else "Candidate already handled."
            )
            return BotReply(text)
    except ValueError:
        return BotReply("Candidate not found.")
    return BotReply("Use /candidate add <id> or /candidate skip <id>.")


def handle_candidate_edit_menu(
    session: Session, user: User, candidate_id: int
) -> BotReply:
    from fluentloop.db.models import ExtractedCandidate, SourceMaterial

    candidate = session.get(ExtractedCandidate, candidate_id)
    if candidate is None:
        return BotReply("Candidate not found.")
    source = session.get(SourceMaterial, candidate.source_material_id)
    if source is None or source.user_id != user.id:
        return BotReply("Candidate not found.")
    if candidate.status not in {"pending", "edited"}:
        return BotReply("Candidate already handled.")
    return BotReply(
        f"Edit candidate #{candidate.id}\n"
        f"Text: {candidate.text}\n"
        f"Meaning: {candidate.meaning}\n"
        f"Tags: {', '.join(candidate.tags)}",
        buttons=[
            [
                _button("Text", f"candidate_field:{candidate.id}:text"),
                _button("Meaning", f"candidate_field:{candidate.id}:meaning"),
                _button("Tags", f"candidate_field:{candidate.id}:tags"),
            ]
        ],
    )


def handle_candidate_edit_prompt(candidate_id: int, field: str) -> BotReply:
    if field not in {"text", "meaning", "tags"}:
        return BotReply("Use text, meaning, or tags.")
    hint = "comma-separated tags" if field == "tags" else f"new {field}"
    return BotReply(f"Send {hint} for candidate #{candidate_id}.")


def handle_candidate_edit_value(
    session: Session, user: User, candidate_id: int, field: str, value: str
) -> BotReply:
    from fluentloop.db.models import ExtractedCandidate

    candidate = session.get(ExtractedCandidate, candidate_id)
    if candidate is None:
        return BotReply("Candidate not found.")
    try:
        edit_candidate(session, user, candidate, field, value)
    except ValueError as exc:
        return BotReply(f"Could not edit candidate: {exc}")
    return BotReply(
        f"Edited candidate #{candidate.id}.\n"
        f"[{candidate.status}] {candidate.type}: {candidate.text}\n"
        f"Meaning: {candidate.meaning}\n"
        f"Tags: {', '.join(candidate.tags)}",
        buttons=[_candidate_buttons(candidate.id)],
    )


def handle_today(
    session: Session,
    user: User,
    *,
    channel_id: str | None = None,
    message_thread_id: int | None = None,
) -> BotReply:
    practice_session = start_or_resume_session(session, user)
    return _practice_session_reply(
        session,
        user,
        practice_session,
        channel_id=channel_id,
        message_thread_id=message_thread_id,
    )


def handle_today_menu(session: Session, user: User) -> BotReply:
    """The fork between the two things FluentLoop actually offers.

    Words and lessons train different units on different timescales; putting
    both behind bare /today (and cards behind /today <n>) meant the command
    did not say what it would do.
    """

    from fluentloop.srs import get_due_items
    from fluentloop.vocab_prefs import get_prefs

    due = len(get_due_items(session, user.id, limit=99))
    per_day = get_prefs(user).words_per_day
    lines = [
        bold("What's on today?"),
        "",
        f"🃏 {bold('Words')} — about 2 minutes."
        + (f" {due} due now." if due else " Nothing due right now."),
        f"📚 {bold('Lesson')} — about 15 minutes, from your lesson base.",
    ]
    return BotReply(
        "\n".join(lines),
        buttons=[
            [
                _button(f"🃏 Words · {per_day}", "today:words"),
                _button("📚 Lesson", "today:lesson"),
            ]
        ],
        parse_mode=HTML_PARSE_MODE,
    )


def handle_words_menu(session: Session, user: User, *, edit: bool = False) -> BotReply:
    """Second screen: the three ways to work on the same vocabulary."""

    from fluentloop.srs import get_due_items
    from fluentloop.vocab_prefs import get_prefs

    counts = {
        status: len(list_items(session, user.id, status=status, limit=1000))
        for status in ("active", "graduated")
    }
    due = len(get_due_items(session, user.id, limit=99))
    per_day = get_prefs(user).words_per_day
    lines = [
        bold("📖 Words"),
        f"Active: {counts['active']} · 🎓 Graduated: {counts['graduated']} "
        f"· Due now: {due}",
        "",
        f"{bold('Show cards')} — {per_day} to read. Nothing is asked.",
        f"{bold('Review due')} — 2-3 minutes: five recall drills, then a cold recall.",
        f"{bold('Vocabulary lesson')} — the full 15-minute session.",
    ]
    return BotReply(
        "\n".join(lines),
        buttons=[
            [
                _button("🃏 Show cards", "words:cards"),
                _button("🔁 Review due", "words:review"),
            ],
            [_button("📖 Vocabulary lesson", "words:lesson")],
        ],
        parse_mode=HTML_PARSE_MODE,
        edit_message=edit,
    )


def handle_today_entry(
    session: Session,
    user: User,
    *,
    channel_id: str | None = None,
    message_thread_id: int | None = None,
) -> BotReply:
    from fluentloop.learning_prefs import is_simple_mode

    if is_simple_mode(user):
        return handle_study(
            session,
            user,
            channel_id=channel_id,
            message_thread_id=message_thread_id,
        )
    return handle_today_menu(session, user)


def handle_practice(
    session: Session,
    user: User,
    mode: str,
    *,
    channel_id: str | None = None,
    message_thread_id: int | None = None,
) -> BotReply:
    normalized = normalize_practice_mode(mode)
    if format_for_mode(normalized) is None:
        return BotReply(practice_modes_help())
    engine_mode = "mistake_focus" if normalized == "mistakes" else normalized
    practice_session = start_explicit_session(session, user, mode=engine_mode)
    return _practice_session_reply(
        session,
        user,
        practice_session,
        channel_id=channel_id,
        message_thread_id=message_thread_id,
    )


def _simple_question_reply(
    step, user: User, *, channel_id=None, message_thread_id=None
) -> BotReply:
    if step.exhausted or step.question is None or step.run is None:
        return BotReply(
            "На сегодня новых вопросов нет. Можно повторить знакомое "
            "или вернуться позже.",
            channel_id or user.telegram_user_id,
            buttons=[
                [_button("Повторить знакомое", "simple:repeat")],
                [_button("Ещё", "simple:menu")],
            ],
            message_thread_id=message_thread_id,
            parse_mode=HTML_PARSE_MODE,
        )

    question = step.question
    category = "Фраза" if question.get("category") == "phrase" else "Грамматика"
    roadmap = question.get("roadmap")
    if isinstance(roadmap, dict):
        strand = (
            "Общий английский"
            if roadmap.get("strand") == "general"
            else "Рабочее дополнение"
        )
        stage = {"b2": "B2", "b2_plus": "B2+", "c1_intro": "C1 intro"}.get(
            roadmap.get("stage"), "B2"
        )
        category = f"{strand} · {stage}"
    lines = [
        bold(f"Вопрос {step.index + 1} · {category}"),
        "",
        html_escape(question["prompt"]),
    ]
    if isinstance(roadmap, dict):
        lines.insert(1, html_escape(str(question.get("module_title_ru") or "")))
    if question.get("selection_fallback"):
        lines.append(
            "Доступные вопросы другой части плана: к выбранной вернёмся позже."
        )
    options = question.get("options") or []
    # Telegram truncates long inline-button labels on narrow screens.  Keep the
    # complete answer text in the message and use fixed A/B/C controls for every
    # question, not only roadmap modules.
    lines.extend(
        [
            "",
            "<b>Выбери вариант:</b>",
            *(
                f"{bold(chr(65 + index) + '.')} {html_escape(str(option))}"
                for index, option in enumerate(options)
            ),
        ]
    )
    buttons = [
        [
            _button(
                chr(65 + index),
                f"simple:answer:{step.run.id}:{step.index}:{index}",
            )
            for index, _option in enumerate(options)
        ]
    ]
    buttons.append(
        [
            _button("Не знаю", f"simple:answer:{step.run.id}:{step.index}:unknown"),
            _button("Хватит", f"simple:stop:{step.run.id}"),
        ]
    )
    return BotReply(
        "\n".join(lines),
        channel_id or user.telegram_user_id,
        buttons=buttons,
        message_thread_id=message_thread_id,
        parse_mode=HTML_PARSE_MODE,
    )


def handle_study(
    session: Session,
    user: User,
    *,
    repeat_familiar: bool = False,
    channel_id: str | None = None,
    message_thread_id: int | None = None,
) -> BotReply:
    from fluentloop.simple_learning import start_stream

    return _simple_question_reply(
        start_stream(session, user, repeat_familiar=repeat_familiar),
        user,
        channel_id=channel_id,
        message_thread_id=message_thread_id,
    )


def _simple_summary_reply(
    session: Session, user: User, summary, *, edit_message: bool = False
) -> BotReply:
    """Close a Study run with a small, actionable progress snapshot.

    The full evidence view remains available through /progress.  The summary
    deliberately describes only answers from this run, so stopping a session
    never implies that a topic or a CEFR level was completed.
    """

    lines = [
        "🏁 <b>Готово — занятие завершено</b>",
        f"Результат сессии: {summary.correct}/{summary.answered} верно; "
        f"«Не знаю»: {summary.unknown}.",
    ]
    if summary.answered:
        lines.append(f"Точность сессии: {summary.correct / summary.answered:.0%}.")

    if summary.run_id is not None:
        from fluentloop.db.models import PracticeAttempt

        attempts = list(
            session.scalars(
                select(PracticeAttempt).where(
                    PracticeAttempt.practice_session_id == summary.run_id,
                    PracticeAttempt.exercise_type == "simple_choice",
                )
            )
        )
        roadmap_ids = []
        strands = {"general": [0, 0], "work": [0, 0]}
        for attempt in attempts:
            roadmap = (attempt.feedback or {}).get("roadmap") or {}
            identifier = roadmap.get("module_id")
            strand = roadmap.get("strand")
            if not isinstance(identifier, str) or strand not in strands:
                continue
            if identifier not in roadmap_ids:
                roadmap_ids.append(identifier)
            strands[strand][1] += 1
            strands[strand][0] += attempt.status == "correct"
        strand_lines = [
            f"{label}: {correct}/{total} верно"
            for key, label in (
                ("general", "Общий английский"),
                ("work", "Рабочие темы"),
            )
            for correct, total in [strands[key]]
            if total
        ]
        if strand_lines:
            lines.extend(["", "<b>По личному плану в этой сессии</b>", *strand_lines])
            from fluentloop.roadmap_study import module_progress

            progress = {
                row["module_id"]: row for row in module_progress(session, user)
            }
            actions = {
                "recognition": "ответить на вопрос по теме",
                "writing": "написать свой короткий ответ",
                "spacing": "вернуться к новому применению через ≥24 ч",
                "language_gate": "закрепить языковые темы для C1",
                "practice": "поддерживать навык",
            }
            for identifier in roadmap_ids[:3]:
                row = progress.get(identifier)
                if row is None:
                    continue
                stage = {"b2": "B2", "b2_plus": "B2+", "c1_intro": "C1 intro"}[
                    row["stage"]
                ]
                lines.append(
                    f"• {html_escape(row['title_ru'])} · {stage}: "
                    f"дальше — {actions.get(row['next_action'], 'практика')}."
                )
            if len(roadmap_ids) > 3:
                lines.append(f"Ещё тем в сессии: {len(roadmap_ids) - 3}.")

    lines.extend(
        [
            "",
            "Открой «Прогресс» для всех тем и доказательств; «План» покажет "
            "следующий языковой шаг.",
            "Итог отражает эту сессию и не является оценкой уровня CEFR.",
        ]
    )
    buttons = [
        [_button("Учиться ещё", "simple:study")],
        [_button("Прогресс", "simple:progress"), _button("План", "simple:plan")],
        [_button("Применить письменно", f"simple:bonus:{summary.run_id}")]
        if summary.run_id is not None
        else [],
    ]
    buttons = [row for row in buttons if row]
    return BotReply(
        "\n".join(lines),
        buttons=buttons,
        parse_mode=HTML_PARSE_MODE,
        edit_message=edit_message,
    )


def handle_simple_answer(
    session: Session,
    user: User,
    run_id: int,
    index: int,
    choice: int | None,
    *,
    channel_id: str | None = None,
    message_thread_id: int | None = None,
) -> BotReply:
    from fluentloop.simple_learning import answer_choice

    result = answer_choice(session, user, run_id, index, choice)
    if not result.accepted or result.attempt is None:
        text = {
            "stale": "Этот вопрос уже закрыт. Отправьте /study, чтобы продолжить.",
            "finished": "Этот поток уже завершён. Отправьте /study, "
            "чтобы начать снова.",
            "unavailable": "Этот вопрос больше недоступен.",
            "invalid_choice": "Этот вариант ответа недоступен.",
        }.get(
            result.reason,
            "Не удалось сохранить ответ. Отправьте /study, чтобы продолжить.",
        )
        return BotReply(text, edit_message=True)

    feedback = result.attempt.feedback or {}
    answer = str(feedback.get("corrected_answer") or "")
    if choice is None:
        lines = [f"Ответ: {bold(html_escape(answer))}"]
    elif result.correct:
        lines = [f"✅ Верно — {bold(html_escape(answer))}"]
    else:
        lines = [f"❌ Правильный ответ: {bold(html_escape(answer))}"]
    explanation = str(feedback.get("explanation") or "").strip()
    if explanation:
        lines.append(html_escape(explanation))
    buttons = [
        [_button("Подробнее", f"feedback:explain:{result.attempt.id}")],
        [_button("Ошибка в вопросе", f"simple:issue:{run_id}:{index}")],
    ]
    if isinstance((feedback.get("question") or {}).get("roadmap"), dict):
        buttons.extend(
            [
                [
                    _button(
                        "Применить письменно", f"simple:module_write:{run_id}:{index}"
                    )
                ],
                [
                    _button(
                        "Практика вне бота", f"simple:module_external:{run_id}:{index}"
                    )
                ],
            ]
        )
    if result.next_step is not None:
        next_reply = _simple_question_reply(
            result.next_step,
            user,
            channel_id=channel_id,
            message_thread_id=message_thread_id,
        )
        return BotReply(
            "\n".join(lines),
            buttons=buttons,
            parse_mode=HTML_PARSE_MODE,
            edit_message=True,
            extra_replies=(next_reply,),
            simple_choice_accepted=True,
        )

    summary = result.summary
    if summary is not None:
        lines.extend(
            [
                "",
                f"Готово: {summary.correct}/{summary.answered} верно. "
                f"«Не знаю»: {summary.unknown}.",
            ]
        )
        buttons.extend(_simple_summary_reply(session, user, summary).buttons or [])
        buttons.append([_button("Повторить знакомое", "simple:repeat")])
    return BotReply(
        "\n".join(lines),
        buttons=buttons,
        parse_mode=HTML_PARSE_MODE,
        edit_message=True,
        simple_choice_accepted=True,
    )


def handle_simple_stop(
    session: Session,
    user: User,
    run_id: int | None = None,
    *,
    edit_message: bool = False,
) -> BotReply:
    from fluentloop.simple_learning import stop_stream

    return _simple_summary_reply(
        session,
        user,
        stop_stream(session, user, run_id=run_id),
        edit_message=edit_message,
    )


def handle_simple_issue(
    session: Session,
    user: User,
    run_id: int,
    index: int,
) -> BotReply:
    """Quarantine an answered personal question reported by its learner."""

    from fluentloop.question_quality import report_question_issue
    from fluentloop.roadmap_study import answered_module_question, report_module_issue

    reported = (
        report_module_issue(session, user, run_id, index)
        if answered_module_question(session, user, run_id, index) is not None
        else report_question_issue(session, user, run_id, index)
    )
    text = (
        "Вопрос отмечен для проверки; он временно исключён."
        if reported
        else "Этот вопрос уже отмечен или недоступен."
    )
    return BotReply(text, edit_message=True)


def handle_simple_bonus_start(
    session: Session,
    user: User,
    parent_run_id: int,
    *,
    module_index: int | None = None,
    channel_id: str | None = None,
    message_thread_id: int | None = None,
) -> BotReply:
    from fluentloop.simple_learning import start_bonus

    if module_index is None:
        step = start_bonus(session, user, parent_run_id)
    else:
        from fluentloop.roadmap_study import start_module_bonus

        step = start_module_bonus(session, user, parent_run_id, module_index)
    if step.run is None or step.question is None:
        return BotReply("Это письменное задание уже завершено.")
    writing_hint = (
        "Ответь по-английски по заданию выше. Это необязательно."
        if step.question.get("adaptive") or step.question.get("roadmap")
        else "Напиши одно предложение по-английски. Это необязательно."
    )
    return BotReply(
        html_escape(step.question["prompt"]) + "\n\n" + writing_hint,
        channel_id or user.telegram_user_id,
        buttons=[[_button("Пропустить письмо", f"simple:bonus-skip:{step.run.id}")]],
        message_thread_id=message_thread_id,
        parse_mode=HTML_PARSE_MODE,
    )


def handle_simple_bonus_text(
    session: Session,
    user: User,
    provider: AIProvider,
    bonus_run,
    answer: str,
    *,
    channel_id: str | None = None,
    message_thread_id: int | None = None,
) -> BotReply:
    from fluentloop.simple_learning import submit_bonus

    exercise = bonus_run.exercises[0] if bonus_run.exercises else {}
    if exercise.get("roadmap") and len(answer) > 10000:
        return BotReply(
            "Ответ слишком длинный. Сократи его до 10 000 символов.",
            channel_id,
            message_thread_id=message_thread_id,
        )
    feedback = check_answer(provider, exercise, answer)
    result = submit_bonus(session, user, bonus_run.id, answer, feedback.model_dump())
    if not result.accepted:
        return BotReply(
            "Не удалось сохранить ответ. Напиши предложение ещё раз "
            "или нажми «Пропустить письмо»."
        )
    if (exercise.get("adaptive") or exercise.get("roadmap")) and not getattr(
        feedback, "genuine_evaluation", False
    ):
        return BotReply(
            "Письмо сохранено; проверка сейчас недоступна и в освоение темы "
            "не засчитана.",
            channel_id,
            buttons=[[_button("Продолжить учиться", "simple:study")]],
            message_thread_id=message_thread_id,
        )
    lines = [f"{bold('Оценка')}: {result.attempt.status.title()}."]
    corrected = feedback.natural_answer or feedback.corrected_answer
    if corrected:
        lines.append(f"{bold('Лучше:')} {code(corrected)}")
    if feedback.explanation:
        lines.append(html_escape(feedback.explanation))
    lines.append("Письменная практика сохранена отдельно от узнавания.")
    if exercise.get("roadmap"):
        if not (result.attempt.feedback or {}).get("independent_production"):
            lines.append(
                "Повтор или копия образца не засчитывается "
                "как самостоятельное применение."
            )
        lines.append(
            "Для следующей ступени нужны два разных самостоятельных задания "
            "с интервалом ≥24 ч."
        )
    return BotReply(
        "\n".join(lines),
        channel_id,
        buttons=[[_button("Продолжить учиться", "simple:study")]],
        message_thread_id=message_thread_id,
        parse_mode=HTML_PARSE_MODE,
    )


def handle_simple_bonus_skip(
    session: Session, user: User, bonus_run_id: int
) -> BotReply:
    from fluentloop.simple_learning import skip_bonus

    skip_bonus(session, user, bonus_run_id)
    return BotReply(
        "Письменная практика пропущена. Это не считается ошибкой.",
        edit_message=True,
    )


def handle_module_external(
    session: Session,
    user: User,
    parent_run_id: int,
    index: int,
    *,
    report: bool = False,
    channel_id: str | None = None,
    message_thread_id: int | None = None,
) -> BotReply:
    """Offer an owned answered module's external brief, with honest self-report."""

    from fluentloop.bot.roadmap import _reply
    from fluentloop.roadmap_study import (
        answered_module_question,
        record_module_external,
    )

    question = answered_module_question(session, user, parent_run_id, index)
    if question is None:
        return BotReply("Это задание недоступно.", edit_message=True)
    if report:
        recorded = record_module_external(session, user, parent_run_id, index)
        return BotReply(
            "Отмечено со слов пользователя. "
            "Бот не оценивал аудирование или устную речь."
            if recorded
            else "Эта практика уже отмечена или недоступна.",
            channel_id,
            buttons=[[_button("Продолжить учиться", "simple:study")]],
            message_thread_id=message_thread_id,
            edit_message=True,
        )
    lines = [
        f"Практика вне бота · {question.get('module_title_ru', '')}",
        str(
            question.get("module_task")
            or "Выберите материал по теме и обсудите его с собеседником."
        ),
        "",
        "Эту часть выполняйте с подходящим внешним материалом или собеседником. "
        "Кнопка ниже сохраняет только вашу отметку о выполнении; "
        "она не повышает ступень и не подтверждает навык речи или аудирования.",
        "",
        "Ресурсы:",
        *(
            f"• {resource['title']}: {resource['url']}"
            for resource in question.get("module_resources", [])
        ),
    ]
    return _reply(
        "\n".join(lines),
        channel_id,
        message_thread_id,
        [
            [
                _button(
                    "Отметить выполнение",
                    f"simple:module_report:{parent_run_id}:{index}",
                )
            ],
            [_button("Продолжить учиться", "simple:study")],
        ],
    )


def _module_progress_reply(
    session: Session, user: User, *, channel_id=None, message_thread_id=None
) -> BotReply | None:
    from fluentloop.bot.roadmap import _reply
    from fluentloop.roadmap_study import enabled, module_progress
    from fluentloop.workplace_roadmap import get_plan

    if not enabled(user):
        return None
    modules = module_progress(session, user)
    attempted = [
        row
        for row in modules
        if row["recognition_attempts"]
        or row["writing_attempts"]
        or row["external_reports"]
        or row["completed_stages"]
    ]
    focus = get_plan(user)["focus"]
    attempted.sort(key=lambda row: (row["module_id"] != focus, -row["last_attempt_id"]))
    lines = [
        "Модули личного плана · весь период",
        f"Начаты: {len(attempted)}/{len(modules)}. Подробнее: /roadmap module ID.",
    ]
    actions = {
        "recognition": "вопрос по теме",
        "writing": "своё письмо",
        "spacing": "новое применение через ≥24 ч",
        "language_gate": "закрепить 10 языковых тем",
        "practice": "поддерживать навык",
    }
    for row in attempted[:5]:
        stage = {"b2": "B2", "b2_plus": "B2+", "c1_intro": "C1 intro"}[row["stage"]]
        lines.append(
            f"• {row['title_ru']} · {stage}: узнавание {row['recognition_correct']}, "
            f"самостоятельное письмо {len(row['writing_variants'])}/2 "
            f"→ {actions.get(row['next_action'], 'практика')}."
        )
    lines.append(
        "Внешние отметки учитываются отдельно и не подтверждают освоение. "
        "Это не оценка CEFR."
    )
    return _reply("\n".join(lines), channel_id, message_thread_id)


def handle_simple_more_menu(
    session: Session,
    user: User,
    *,
    channel_id: str | None = None,
    message_thread_id: int | None = None,
) -> BotReply:
    from fluentloop.learning_prefs import is_simple_mode

    buttons = [
        [
            _button("🗺 План", "simple:plan"),
            _button("Общий план", "simple:roadmap"),
        ],
        [_button("🃏 Карточки", "words:cards"), _button("🔁 Повтор", "words:review")],
        [
            _button("📚 Полный урок", "today:lesson"),
            _button("📖 Библиотека", "library:list"),
        ],
        [
            _button("📤 Загрузить материал", "simple:upload"),
            _button("⚙️ Настройки", "simple:settings"),
        ],
    ]
    if is_simple_mode(user):
        buttons.append([_button("Расширенный режим", "simple:mode:advanced")])
    else:
        buttons.append([_button("Простой режим", "simple:mode:simple")])
    return BotReply(
        "Что открыть?",
        channel_id,
        buttons=buttons,
        message_thread_id=message_thread_id,
    )


def handle_simple_mode_change(
    session: Session,
    user: User,
    mode: str,
    *,
    channel_id: str | None = None,
    message_thread_id: int | None = None,
) -> BotReply:
    from fluentloop.learning_prefs import set_learning_mode
    from fluentloop.vocab_prefs import get_prefs

    set_learning_mode(session, user, mode)
    simple = mode == "simple"
    text = (
        "Простой режим включён. Учебные сообщения приходят только по твоему запросу."
        if simple
        else "Расширенный режим включён. Прежние настройки и расписание сохранены."
    )
    return BotReply(
        text,
        channel_id,
        message_thread_id=message_thread_id,
        persistent_keyboard=get_prefs(user).keyboard,
        simple_keyboard=simple,
    )


def _is_adaptive_plan(session: Session, plan, items=None) -> bool:
    return (
        "adaptive_curriculum:v1" in (plan.tags_json or [])
        or getattr(plan, "format", "") == "adaptive_questions"
        or any(
            is_adaptive_item(item)
            for item in (lesson_items(session, plan) if items is None else items)
        )
    )


def _adaptive_plan_title(plan) -> str:
    from fluentloop.adaptive_learning import TOPIC_TITLES

    for tag in plan.tags_json or []:
        if tag.startswith("topic:") and tag[6:] in TOPIC_TITLES:
            return TOPIC_TITLES[tag[6:]] + " · B2 → C1 intro"
    return "Adaptive curriculum"


def handle_library(session: Session, user: User, query: str = "") -> BotReply:
    templates = library_templates(session, query=query, limit=20)
    if not templates:
        suffix = f" matching {query!r}" if query else ""
        return BotReply(
            f"No shared seed lessons found{suffix}. "
            "Run the seed-library publish step first."
        )
    title = "Shared seed library" if not query else f"Shared library matching {query}"
    lines = [bold(title)]
    buttons: list[list[InlineButton]] = []
    for template in templates:
        items = lesson_items(session, template)
        adaptive = _is_adaptive_plan(session, template, items)
        lesson_type = lesson_type_for_plan(template, items)
        pool_size = lesson_pool_size(session, template)
        title = _adaptive_plan_title(template) if adaptive else template.title
        topic = "See /plan" if adaptive else template.topic
        lines.append(
            f"#{template.id} {html_escape(title)} - "
            f"{html_escape(topic)} - "
            f"{html_escape(lesson_type.title)} - pool {pool_size}"
        )
        buttons.append(
            [
                _button(
                    f"Subscribe #{template.id}",
                    f"library:subscribe:{template.id}",
                ),
                _button(f"Details #{template.id}", f"library:details:{template.id}"),
            ]
        )
    lines.extend(
        [
            "",
            "Use /subscribe <template_id> to copy a lesson into your own lesson base.",
            "After subscribe: /lessons, /lesson <id>, or /today.",
        ]
    )
    return BotReply("\n".join(lines), buttons=buttons, parse_mode=HTML_PARSE_MODE)


def handle_subscribe(session: Session, user: User, template_id: int) -> BotReply:
    try:
        result = subscribe_to_template(session, user, template_id)
    except ValueError as exc:
        return BotReply(f"Could not subscribe: {exc}")
    note = ""
    if result.reused_items or result.reused_source:
        note = (
            "\nRepeated subscription is allowed: I reused your existing item bank "
            "where it already matched this template."
        )
    adaptive = _is_adaptive_plan(session, result.plan)
    title = _adaptive_plan_title(result.plan) if adaptive else result.plan.title
    topic = "See /plan" if adaptive else result.plan.topic
    return BotReply(
        "\n".join(
            [
                f"Subscribed to template #{template_id}.",
                f"LessonPlan #{result.plan.id}: {title}",
                f"Topic: {topic}",
                f"Created items: {result.created_items}",
                f"Reused items: {result.reused_items}",
                f"Open it with /lesson {result.plan.id}, or let /today rotate it in.",
            ]
        )
        + note,
        buttons=[
            [
                _button(f"Start #{result.plan.id}", f"lesson:start:{result.plan.id}"),
                _button(
                    f"Details #{result.plan.id}",
                    f"lesson:details:{result.plan.id}",
                ),
            ]
        ],
    )


def handle_publish(
    session: Session,
    user: User,
    plan_id: int,
    *,
    owner_telegram_user_id: int | None,
) -> BotReply:
    if (
        owner_telegram_user_id is None
        or user.telegram_user_id != owner_telegram_user_id
    ):
        return BotReply("Owner-only command.")
    try:
        plan = publish_lesson_template(session, user, plan_id)
    except ValueError as exc:
        return BotReply(f"Could not publish lesson: {exc}")
    return BotReply(
        f"Published template #{plan.id}: {plan.title}. It is now visible in /library."
    )


def handle_library_callback(
    session: Session, user: User, action: str, payload: str
) -> BotReply:
    try:
        template_id = int(payload)
    except ValueError:
        return BotReply("Template not found.")
    if action == "subscribe":
        return handle_subscribe(session, user, template_id)
    if action == "details":
        template = library_template_by_id(session, template_id)
        if template is None:
            return BotReply("Template not found.")
        return _template_details_reply(session, template)
    return BotReply("Unknown library action.")


def handle_topics(session: Session, user: User) -> BotReply:
    from collections import Counter

    counts: Counter[str] = Counter()
    for plan in active_lesson_plans(session, user, limit=500):
        if _is_adaptive_plan(session, plan):
            counts[_adaptive_plan_title(plan)] += 1
            continue
        tags = list(plan.tags_json or [])
        areas = [tag for tag in tags if not tag.startswith("curriculum:")]
        for label in areas[:3] or [plan.topic]:
            counts[label] += 1
    groups = sorted(counts.items(), key=lambda row: (-row[1], row[0].casefold()))
    if not groups:
        return BotReply("No active lesson topics yet. Seed or upload lessons first.")
    lines = [bold("Topics")]
    for topic, count in groups[:30]:
        lines.append(f"- {html_escape(topic)} ({count})")
    lines.append("")
    lines.append("Use /lessons <topic> to browse, or /lesson topic <topic> to start.")
    return BotReply(
        "\n".join(lines),
        buttons=[[_button("Random lesson", "lesson:random:0")]],
        parse_mode=HTML_PARSE_MODE,
    )


def handle_lessons(session: Session, user: User, query: str = "") -> BotReply:
    plans = active_lesson_plans(session, user, query=query, limit=20)
    if not plans:
        suffix = f" for {query!r}" if query else ""
        return BotReply(f"No active lessons found{suffix}.")
    title = "Lessons" if not query else f"Lessons matching {query}"
    lines = [bold(title)]
    buttons: list[list[InlineButton]] = []
    for plan in plans:
        items = lesson_items(session, plan)
        adaptive = _is_adaptive_plan(session, plan, items)
        lesson_type = lesson_type_for_plan(plan, items)
        pool_size = lesson_pool_size(session, plan)
        title = _adaptive_plan_title(plan) if adaptive else plan.title
        topic = "See /plan" if adaptive else plan.topic
        lines.append(
            f"#{plan.id} {html_escape(title)} - "
            f"{html_escape(topic)} - "
            f"{html_escape(lesson_type.title)} - pool {pool_size}"
        )
        buttons.append(
            [
                _button(f"Start #{plan.id}", f"lesson:start:{plan.id}"),
                _button(f"Details #{plan.id}", f"lesson:details:{plan.id}"),
            ]
        )
    buttons.append([_button("Random", "lesson:random:0")])
    return BotReply("\n".join(lines), buttons=buttons, parse_mode=HTML_PARSE_MODE)


def handle_lesson(
    session: Session,
    user: User,
    payload: str,
    *,
    channel_id: str | None = None,
    message_thread_id: int | None = None,
) -> BotReply:
    payload = payload.strip()
    if payload == "random":
        plan = random_lesson_plan(session, user)
        if plan is None:
            return BotReply("No active lessons yet. Seed or upload lessons first.")
        return _start_lesson_reply(
            session,
            user,
            plan,
            channel_id=channel_id,
            message_thread_id=message_thread_id,
        )
    if payload.startswith("topic "):
        query = payload.removeprefix("topic ").strip()
        if not query:
            return BotReply("Use /lesson topic <query>.")
        plan = find_lesson_plan(session, user, query)
        if plan is None:
            return BotReply(
                f"No active lesson matched {query!r}. Try /lessons {query}."
            )
        return _start_lesson_reply(
            session,
            user,
            plan,
            channel_id=channel_id,
            message_thread_id=message_thread_id,
        )
    start_requested = payload.startswith("start ")
    if start_requested:
        payload = payload.removeprefix("start ").strip()
    try:
        lesson_plan_id = int(payload)
    except ValueError:
        return BotReply("Use /lesson <id>, /lesson random, or /lesson topic <query>.")
    plan = lesson_plan_by_id(session, user, lesson_plan_id)
    if plan is None:
        return BotReply("Lesson not found.")
    if start_requested:
        return _start_lesson_reply(
            session,
            user,
            plan,
            channel_id=channel_id,
            message_thread_id=message_thread_id,
        )
    return _lesson_details_reply(session, plan)


def handle_lesson_callback(
    session: Session,
    user: User,
    action: str,
    payload: str,
    *,
    channel_id: str | None = None,
    message_thread_id: int | None = None,
) -> BotReply:
    if action == "random":
        plan = random_lesson_plan(session, user)
        if plan is None:
            return BotReply("No active lessons yet.")
        return _start_lesson_reply(
            session,
            user,
            plan,
            channel_id=channel_id,
            message_thread_id=message_thread_id,
        )
    try:
        lesson_plan_id = int(payload)
    except ValueError:
        return BotReply("Lesson not found.")
    plan = lesson_plan_by_id(session, user, lesson_plan_id)
    if plan is None:
        return BotReply("Lesson not found.")
    if action == "start":
        return _start_lesson_reply(
            session,
            user,
            plan,
            channel_id=channel_id,
            message_thread_id=message_thread_id,
        )
    if action == "details":
        return _lesson_details_reply(session, plan)
    return BotReply("Unknown lesson action.")


def _start_lesson_reply(
    session: Session,
    user: User,
    plan,
    *,
    channel_id: str | None = None,
    message_thread_id: int | None = None,
) -> BotReply:
    if _is_adaptive_plan(session, plan):
        return BotReply(
            "Этот план открывается через /study: задания идут по этапам. "
            "Текущая тема и следующий шаг — в /plan.",
            channel_id or user.telegram_user_id,
            message_thread_id=message_thread_id,
        )
    practice_session = start_explicit_session(
        session, user, mode="lesson", lesson_plan=plan
    )
    return _practice_session_reply(
        session,
        user,
        practice_session,
        channel_id=channel_id,
        message_thread_id=message_thread_id,
    )


def _practice_session_reply(
    session: Session,
    user: User,
    practice_session,
    *,
    channel_id: str | None = None,
    message_thread_id: int | None = None,
) -> BotReply:
    current = next_exercise(session, practice_session)
    if current is None:
        text = "Today's practice is complete."
        if channel_id:
            text = "#summary\n" + text
        return BotReply(
            text,
            channel_id or user.telegram_user_id,
            message_thread_id=message_thread_id,
            parse_mode=HTML_PARSE_MODE,
        )
    index, exercise = current
    title = _practice_header(practice_session.exercises)
    if channel_id:
        title = "#practice_flow\n" + title
    rendered_step = _render_step(index, exercise, len(practice_session.exercises))
    text = f"{title}\n\n{rendered_step}"
    return BotReply(
        text,
        channel_id or user.telegram_user_id,
        buttons=_practice_buttons(index),
        message_thread_id=message_thread_id,
        parse_mode=HTML_PARSE_MODE,
    )


def _lesson_details_reply(session: Session, plan) -> BotReply:
    items = lesson_items(session, plan)
    visible_items = [item for item in items if not is_adaptive_item(item)]
    adaptive = _is_adaptive_plan(session, plan, items)
    lesson_type = lesson_type_for_plan(plan, items)
    chunks = [
        item.text
        for item in visible_items
        if item.type in {"word", "expression", "chunk"}
    ][:8]
    grammar = [item.text for item in visible_items if item.type == "grammar_rule"][:6]
    mistakes = [item.text for item in visible_items if item.type == "mistake_pattern"][
        :5
    ]
    lines = [
        f"{bold('Lesson')} #{plan.id}",
        labeled("Title", _adaptive_plan_title(plan) if adaptive else plan.title),
        labeled("Topic", "See /plan" if adaptive else plan.topic),
        labeled(
            "Goal",
            "Practice this topic in the simple stream." if adaptive else plan.goal,
        ),
        labeled("Lesson type", lesson_type.title),
        labeled("What you train", lesson_type.goal),
        labeled("Target mix", format_target_mix(visible_items)),
        labeled("Format", getattr(plan, "format", "lesson")),
    ]
    if plan.language_focus_json and not adaptive:
        lines.append(labeled("Language focus", ", ".join(plan.language_focus_json[:8])))
    if chunks:
        lines.append(labeled("Target chunks", ", ".join(chunks)))
    if grammar:
        lines.append(labeled("Grammar", ", ".join(grammar)))
    if mistakes:
        lines.append(labeled("Mistake risks", ", ".join(mistakes)))
    lines.append(labeled("Lesson pool", str(len(items))))
    return BotReply(
        "\n".join(lines),
        buttons=[
            [_button("Start", f"lesson:start:{plan.id}")],
            [_button("Random", "lesson:random:0")],
        ],
        parse_mode=HTML_PARSE_MODE,
    )


def _template_details_reply(session: Session, template) -> BotReply:
    items = lesson_items(session, template)
    visible_items = [item for item in items if not is_adaptive_item(item)]
    adaptive = _is_adaptive_plan(session, template, items)
    lesson_type = lesson_type_for_plan(template, items)
    chunks = [
        item.text
        for item in visible_items
        if item.type in {"word", "expression", "chunk"}
    ][:8]
    grammar = [item.text for item in visible_items if item.type == "grammar_rule"][:6]
    mistakes = [item.text for item in visible_items if item.type == "mistake_pattern"][
        :5
    ]
    lines = [
        f"{bold('Shared library lesson')} #{template.id}",
        labeled(
            "Title", _adaptive_plan_title(template) if adaptive else template.title
        ),
        labeled("Topic", "See /plan" if adaptive else template.topic),
        labeled(
            "Goal",
            "Practice this topic in the simple stream." if adaptive else template.goal,
        ),
        labeled("Lesson type", lesson_type.title),
        labeled("What you train", lesson_type.goal),
        labeled("Target mix", format_target_mix(visible_items)),
    ]
    if template.language_focus_json and not adaptive:
        lines.append(
            labeled("Language focus", ", ".join(template.language_focus_json[:8]))
        )
    if chunks:
        lines.append(labeled("Target chunks", ", ".join(chunks)))
    if grammar:
        lines.append(labeled("Grammar", ", ".join(grammar)))
    if mistakes:
        lines.append(labeled("Mistake risks", ", ".join(mistakes)))
    lines.append(labeled("Template pool", str(len(items))))
    lines.append("Subscribe to copy this lesson into your own lesson base.")
    return BotReply(
        "\n".join(lines),
        buttons=[[_button("Subscribe", f"library:subscribe:{template.id}")]],
        parse_mode=HTML_PARSE_MODE,
    )


def handle_answer(
    session: Session,
    user: User,
    provider: AIProvider,
    answer: str,
    *,
    channel_id: str | None = None,
    message_thread_id: int | None = None,
    next_channel_id: str | None = None,
    next_message_thread_id: int | None = None,
    feedback_copy_channel_id: str | None = None,
    feedback_copy_message_thread_id: int | None = None,
    summary_channel_id: str | None = None,
    summary_message_thread_id: int | None = None,
    progress_channel_id: str | None = None,
    progress_message_thread_id: int | None = None,
) -> BotReply:
    practice_session = get_in_progress_session(session, user)
    if practice_session is None:
        return BotReply(
            "No active exercise. Send /today, or send /upload and paste this "
            "text as lesson material."
        )
    current = next_exercise(session, practice_session)
    if current is None:
        return BotReply("No active exercise. Send /today.")
    index, exercise = current
    feedback = check_answer(provider, exercise, answer)
    metadata = exercise.get("metadata")
    confidence_rating = None
    if isinstance(metadata, dict):
        confidence_rating = metadata.get("confidence_rating")
    if isinstance(confidence_rating, int):
        feedback = feedback.model_copy(update={"confidence_rating": confidence_rating})
        if confidence_rating >= 4 and feedback.status != "correct":
            feedback = feedback.model_copy(update={"should_create_mistake_event": True})
    pattern = apply_feedback(session, user, exercise, answer, feedback)
    suggestion_queue = queue_feedback_suggestions(session, user, exercise, feedback)
    attempt = record_attempt(
        session, practice_session, index, exercise, answer, feedback.model_dump()
    )
    follow_up = next_exercise(session, practice_session)
    heading = "#feedback\n" if channel_id else ""
    extra_replies: list[BotReply] = []
    message = heading + render_compact_teacher_feedback(attempt.id, feedback)
    if feedback.should_create_mistake_event:
        message += "\nI'll add this as a weak point unless you dispute it."
    if pattern is not None and pattern.confidence == "low":
        message += (
            f"\n#mistakes Recurring pattern #{pattern.id} detected. "
            f"Use /mistakes focus {pattern.id} or /mistakes ignore {pattern.id}."
        )
    if suggestion_queue is not None:
        material_id, count = suggestion_queue
        message += (
            f"\nSuggested {count} new candidate(s) queued for approval: "
            f"/candidates {material_id}."
        )
    message += (
        f"\nDetails: /feedback explain {attempt.id}"
        f"\nDisagree? Use the buttons or send /dispute {attempt.id} &lt;reason&gt;."
    )
    if feedback_copy_channel_id:
        extra_replies.append(
            BotReply(
                message,
                feedback_copy_channel_id,
                buttons=_attempt_buttons(
                    attempt.id, allow_hard=feedback.status == "correct"
                ),
                message_thread_id=feedback_copy_message_thread_id,
                parse_mode=HTML_PARSE_MODE,
            )
        )
    if follow_up is not None:
        next_index, next_item = follow_up
        next_heading = "#next_prompt\n" if channel_id else ""
        next_text = next_heading + _render_step(
            next_index, next_item, len(practice_session.exercises)
        )
        if next_channel_id:
            extra_replies.append(
                BotReply(
                    next_text,
                    next_channel_id,
                    buttons=_practice_buttons(next_index),
                    message_thread_id=next_message_thread_id,
                    parse_mode=HTML_PARSE_MODE,
                )
            )
        message += "\n\n" + next_text
    else:
        summary_heading = "#summary\n" if channel_id else ""
        summary_text = summary_heading + summarize_session(session, practice_session)
        if summary_channel_id:
            extra_replies.append(
                BotReply(
                    summary_text,
                    summary_channel_id,
                    message_thread_id=summary_message_thread_id,
                    parse_mode=HTML_PARSE_MODE,
                )
            )
        message += "\n\n" + summary_text
    buttons = (
        _attempt_and_practice_buttons(
            attempt.id,
            allow_hard=feedback.status == "correct",
            exercise_index=next_index if follow_up is not None else None,
        )
        if follow_up is not None
        else _attempt_buttons(attempt.id, allow_hard=feedback.status == "correct")
    )
    return BotReply(
        message,
        channel_id or user.telegram_user_id,
        buttons=buttons,
        message_thread_id=message_thread_id,
        extra_replies=tuple(extra_replies),
        parse_mode=HTML_PARSE_MODE,
    )


def handle_skip_current(
    session: Session,
    user: User,
    *,
    channel_id: str | None = None,
    message_thread_id: int | None = None,
    next_channel_id: str | None = None,
    next_message_thread_id: int | None = None,
    summary_channel_id: str | None = None,
    summary_message_thread_id: int | None = None,
) -> BotReply:
    practice_session = get_in_progress_session(session, user)
    if practice_session is None:
        return BotReply("No active exercise. Send /today.")
    current = next_exercise(session, practice_session)
    if current is None:
        return BotReply("No active exercise. Send /today.")
    index, exercise = current
    feedback = _skip_feedback(exercise)
    attempt = record_attempt(
        session,
        practice_session,
        index,
        exercise,
        "[skipped]",
        feedback,
    )
    follow_up = next_exercise(session, practice_session)
    heading = "#feedback\n" if channel_id else ""
    message = heading + _render_skip_feedback(attempt.id, exercise, feedback)
    extra_replies: list[BotReply] = []
    if follow_up is not None:
        next_index, next_item = follow_up
        next_heading = "#next_prompt\n" if channel_id else ""
        next_text = next_heading + _render_step(
            next_index, next_item, len(practice_session.exercises)
        )
        if next_channel_id:
            extra_replies.append(
                BotReply(
                    next_text,
                    next_channel_id,
                    buttons=_practice_buttons(next_index),
                    message_thread_id=next_message_thread_id,
                    parse_mode=HTML_PARSE_MODE,
                )
            )
        message += "\n\n" + next_text
        buttons = _practice_buttons(next_index)
    else:
        summary_heading = "#summary\n" if channel_id else ""
        summary_text = summary_heading + summarize_session(session, practice_session)
        if summary_channel_id:
            extra_replies.append(
                BotReply(
                    summary_text,
                    summary_channel_id,
                    message_thread_id=summary_message_thread_id,
                    parse_mode=HTML_PARSE_MODE,
                )
            )
        message += "\n\n" + summary_text
        buttons = None
    return BotReply(
        message,
        channel_id or user.telegram_user_id,
        buttons=buttons,
        message_thread_id=message_thread_id,
        extra_replies=tuple(extra_replies),
        parse_mode=HTML_PARSE_MODE,
    )


def _skip_feedback(exercise: dict) -> dict:
    expected = str(exercise.get("expected_answer") or "").strip()
    explanation = str(exercise.get("explanation") or "").strip()
    hint = str(exercise.get("hint") or "").strip()
    rule = explanation or hint or "Review the target pattern, then try the next one."
    return {
        "status": "skipped",
        "corrected_answer": expected,
        "natural_answer": expected,
        "explanation": explanation or hint,
        "related_rule": rule,
        "mistake_summary": "Skipped.",
        "why_wrong": "No answer was submitted; use this as a quick reveal.",
        "rule": rule,
        "better_variants": [expected] if expected else [],
        "micro_drill": "Repeat the correct answer once, then continue.",
        "teacher_note": "Skipping is fine when you want the model answer first.",
        "should_create_mistake_event": False,
        "should_create_or_update_mistake_pattern": False,
    }


def _render_skip_feedback(attempt_id: int, exercise: dict, feedback: dict) -> str:
    expected = feedback.get("corrected_answer") or "Open answer; compare with the rule."
    explanation = feedback.get("explanation") or exercise.get("hint") or ""
    rule = feedback.get("rule") or feedback.get("related_rule") or ""
    lines = [
        bold(f"Skipped attempt #{attempt_id}"),
        f"{bold('Correct answer:')} {code(expected) if expected else ''}",
    ]
    if explanation:
        lines.append(labeled("Why", explanation))
    if rule and rule != explanation:
        lines.append(labeled("Rule", rule))
    lines.append(
        labeled("Next time", "try the answer first, then use skip to compare.")
    )
    return "\n".join(lines)


def _practice_header(exercises: list[dict]) -> str:
    metadata = _exercise_metadata(exercises[0] if exercises else {})
    mode = str(metadata.get("mode", "mixed")).replace("_", " ")
    format_title = str(metadata.get("format_title") or "").strip()
    lesson_title = str(metadata.get("lesson_plan_title") or "").strip()
    topic = metadata.get("topic", "Business/IT communication")
    goal = metadata.get("lesson_goal", "Practice useful workplace English.")
    focus = metadata.get("target_skill", "micro-drills")
    why_now = metadata.get(
        "why_now",
        "teacher priority + due review + new material rotation",
    )
    lines = [bold("Today's English practice - 15 min")]
    if lesson_title:
        lines.append(labeled("Lesson", lesson_title))
    if format_title:
        lines.append(labeled("Format", format_title))
    lines.extend(
        [
            labeled("Mode", mode),
            labeled("Topic", str(topic)),
            labeled("Goal", str(goal)),
            labeled("Focus", str(focus)),
            labeled("Why now", str(why_now)),
        ]
    )
    return "\n".join(lines)


def _exercise_metadata(exercise: dict) -> dict:
    metadata = exercise.get("metadata")
    if isinstance(metadata, dict):
        return metadata
    return exercise


def _stage_label(stage: str) -> str:
    labels = {
        "warmup": "Warm-up",
        "input": "Input",
        "controlled_practice": "Controlled practice",
        "grammar_or_mistake_focus": "Grammar / mistake focus",
        "free_production": "Free production",
        "recap": "Recap",
    }
    return labels.get(stage, stage.replace("_", " ").title())


def _render_step(index: int, exercise: dict, total: int) -> str:
    metadata = _exercise_metadata(exercise)
    stage = _stage_label(str(metadata.get("stage", "practice")))
    lesson_title = str(metadata.get("lesson_plan_title") or "").strip()
    target = ", ".join(str(item) for item in metadata.get("target_item_ids", [])[:3])
    lines = [bold(f"Step {index + 1}/{total} - {stage}")]
    if lesson_title:
        lines.append(labeled("Lesson", lesson_title))
    if metadata.get("topic"):
        lines.append(labeled("Topic", str(metadata["topic"])))
    if metadata.get("target_skill"):
        lines.append(labeled("Focus", str(metadata["target_skill"])))
    if target:
        lines.append(labeled("Target", target))
    lines.append(labeled("Task", str(exercise["prompt"])))
    if exercise.get("hint"):
        lines.append(labeled("Hint", str(exercise["hint"])))
    return "\n".join(lines)


def handle_attempt_ack(session: Session, user: User, attempt_id: int) -> BotReply:
    from fluentloop.db.models import PracticeAttempt, PracticeSession

    attempt = session.get(PracticeAttempt, attempt_id)
    if attempt is None:
        return BotReply("Attempt not found.")
    practice_session = session.get(PracticeSession, attempt.practice_session_id)
    if practice_session is None or practice_session.user_id != user.id:
        return BotReply("Attempt not found.")
    return BotReply(f"Got it. Keeping attempt #{attempt.id} as-is.")


def handle_feedback_explain(
    session: Session,
    user: User,
    attempt_id: int,
    *,
    channel_id: str | None = None,
    message_thread_id: int | None = None,
) -> BotReply:
    from fluentloop.db.models import PracticeAttempt, PracticeSession

    attempt = session.get(PracticeAttempt, attempt_id)
    if attempt is None:
        return BotReply("Attempt not found.")
    practice_session = session.get(PracticeSession, attempt.practice_session_id)
    if practice_session is None or practice_session.user_id != user.id:
        return BotReply("Attempt not found.")
    return BotReply(
        render_detailed_teacher_feedback(attempt.feedback),
        channel_id,
        message_thread_id=message_thread_id,
        parse_mode=HTML_PARSE_MODE,
    )


def handle_feedback_layer(
    session: Session, user: User, attempt_id: int, layer: str
) -> BotReply:
    from fluentloop.db.models import PracticeAttempt, PracticeSession

    attempt = session.get(PracticeAttempt, attempt_id)
    if attempt is None:
        return BotReply("Attempt not found.")
    practice_session = session.get(PracticeSession, attempt.practice_session_id)
    if practice_session is None or practice_session.user_id != user.id:
        return BotReply("Attempt not found.")
    feedback = attempt.feedback
    if layer == "errors":
        text = feedback.get("error_layer") or feedback.get("mistake_summary")
        title = "Error layer"
    elif layer == "native":
        text = feedback.get("native_rewrite") or feedback.get("natural_answer")
        reason = feedback.get("native_rewrite_reason")
        if reason:
            text = f"{text}\n\n{reason}" if text else str(reason)
        title = "Native rewrite"
    elif layer == "why":
        text = feedback.get("why_layer") or feedback.get("why_wrong")
        title = "Why layer"
    else:
        return BotReply("Unknown feedback layer.")
    if not text:
        text = "No extra detail was stored for this layer."
    return BotReply(
        f"{bold(title)}\n{html_escape(str(text))}",
        parse_mode=HTML_PARSE_MODE,
    )


def handle_confidence_rating(
    session: Session, user: User, exercise_index: int, rating: int
) -> BotReply:
    practice_session = get_in_progress_session(session, user)
    if practice_session is None:
        return BotReply("No active exercise. Send /today.")
    try:
        record_confidence_rating(session, practice_session, exercise_index, rating)
    except ValueError as exc:
        return BotReply(str(exc))
    return BotReply(f"Confidence recorded: {rating}/5.")


def handle_reflect(session: Session, user: User, text: str) -> BotReply:
    if not text.strip():
        return BotReply(reflection_prompt())
    path = record_reflection(user, text)
    return BotReply(f"Reflection saved for weekly review: {path.name}.")


def handle_brief(payload: str) -> BotReply:
    return BotReply(pre_meeting_brief(payload))


def handle_scene(payload: str) -> BotReply:
    return BotReply(scene_builder(payload))


def handle_mentor(
    session: Session, user: User, *, base_dir: Path = Path("data/coach_journal")
) -> BotReply:
    path = write_coach_journal(session, user, base_dir=base_dir)
    return BotReply(f"{mentor_question()}\n\nCoach journal: {path.name}")


def handle_baseline(session: Session, user: User, payload: str = "") -> BotReply:
    if not payload.strip():
        return BotReply(current_baseline_prompt(session, user))
    try:
        run = record_baseline(session, user, payload)
    except ValueError as exc:
        return BotReply(str(exc))
    metrics = run.metrics_json or {}
    return BotReply(
        "Baseline saved.\n"
        f"Words: {int(metrics.get('word_count') or 0)}\n"
        f"Lexical diversity: {float(metrics.get('lexical_diversity') or 0):.2f}\n"
        f"Hedging: {float(metrics.get('hedging_density') or 0) * 100:.1f}/100 words\n"
        f"Avg sentence: {float(metrics.get('mean_sentence_length') or 0):.1f} words\n"
        f"Held-out items: {len(run.held_out_item_ids or [])}\n\n"
        "Now use /today and /practice notebook; check /outcomes after a few sessions."
    )


def handle_outcomes(session: Session, user: User, payload: str = "") -> BotReply:
    full = payload.strip().lower() == "full"
    report = build_outcome_report(session, user, full=full)
    return BotReply(report.summary_text)


def handle_article(
    payload: str, *, session: Session | None = None, user: User | None = None
) -> BotReply:
    if session is not None and user is not None and payload.strip():
        record_article_probe(session, user, payload)
    return BotReply(article_lab_prompt(payload))


def handle_debate(payload: str) -> BotReply:
    return BotReply(debate_prompt(payload))


def handle_translate_lab(payload: str) -> BotReply:
    return BotReply(translation_lab_prompt(payload))


def handle_fluency432(payload: str) -> BotReply:
    return BotReply(fluency432_prompt(payload))


def handle_attempt_hard(session: Session, user: User, attempt_id: int) -> BotReply:
    from fluentloop.db.models import PracticeAttempt, PracticeSession

    attempt = session.get(PracticeAttempt, attempt_id)
    if attempt is None:
        return BotReply("Attempt not found.")
    practice_session = session.get(PracticeSession, attempt.practice_session_id)
    if practice_session is None or practice_session.user_id != user.id:
        return BotReply("Attempt not found.")
    if attempt.status != "correct":
        return BotReply("Hard override is only available for correct answers.")
    for item_id in attempt.target_learning_item_ids:
        convert_last_good_to_hard(session, item_id)
    attempt.feedback = {**attempt.feedback, "srs_override": "Hard"}
    session.add(attempt)
    session.flush()
    return BotReply(f"Marked attempt #{attempt.id} as Hard for SRS.")


def handle_dispute(
    session: Session,
    user: User,
    attempt_id: int,
    reason: str,
    *,
    base_dir: Path = Path("data/feedback_disputes"),
) -> BotReply:
    from fluentloop.db.models import MistakeEvent, PracticeAttempt, PracticeSession

    attempt = session.get(PracticeAttempt, attempt_id)
    if attempt is None:
        return BotReply("Attempt not found.")
    practice_session = session.get(PracticeSession, attempt.practice_session_id)
    if practice_session is None or practice_session.user_id != user.id:
        return BotReply("Attempt not found.")
    write_dispute(
        base_dir,
        prompt=attempt.prompt,
        answer=attempt.user_answer,
        verdict=attempt.feedback,
        reason=reason,
    )
    mistake = session.scalar(
        select(MistakeEvent)
        .where(
            MistakeEvent.user_id == user.id,
            MistakeEvent.wrong_answer == attempt.user_answer,
        )
        .order_by(MistakeEvent.created_at.desc())
    )
    if mistake is not None:
        session.delete(mistake)
    attempt.status = "disputed"
    session.add(attempt)
    session.flush()
    return BotReply(f"Dispute logged for attempt #{attempt.id}.")


def handle_stats(session: Session, user: User) -> BotReply:
    return BotReply(render_stats(collect_stats(session, user)))


def handle_progress(
    session: Session,
    user: User,
    *,
    channel_id: str | None = None,
    message_thread_id: int | None = None,
) -> BotReply:
    """Show simple-mode recognition and written production as separate signals."""

    from datetime import UTC, datetime, timedelta

    from sqlalchemy import func, select

    from fluentloop.db.models import PracticeAttempt, PracticeSession
    from fluentloop.learning_prefs import is_simple_mode
    from fluentloop.simple_learning import CHOICE, PRODUCTION

    if not is_simple_mode(user):
        return BotReply(
            render_stats(collect_stats(session, user)),
            channel_id,
            message_thread_id=message_thread_id,
        )

    rows = session.execute(
        select(PracticeAttempt.exercise_type, PracticeAttempt.status, func.count())
        .join(
            PracticeSession, PracticeSession.id == PracticeAttempt.practice_session_id
        )
        .where(
            PracticeSession.user_id == user.id,
            PracticeAttempt.exercise_type.in_((CHOICE, PRODUCTION)),
            PracticeAttempt.created_at >= datetime.now(UTC) - timedelta(days=30),
        )
        .group_by(PracticeAttempt.exercise_type, PracticeAttempt.status)
    )
    recognition_total = recognition_correct = production_total = production_correct = 0
    production_unchecked = 0
    for exercise_type, status, count in rows:
        if exercise_type == CHOICE:
            recognition_total += count
            if status == "correct":
                recognition_correct += count
        else:
            if status == "unchecked":
                production_unchecked += count
                continue
            if status == "disputed":
                continue
            production_total += count
            if status == "correct":
                production_correct += count
    from fluentloop.adaptive_learning import curriculum_progress

    curriculum = curriculum_progress(session, user)
    topic_lines = []
    for topic in curriculum.topics:
        stage = {"b2": "B2", "b2_plus": "B2+", "c1_intro": "C1 intro"}[topic.stage]
        status = _curriculum_action(topic.next_action)
        accuracy = (
            f", точность {topic.practice_accuracy:.0%}"
            if topic.practice_successes
            else ""
        )
        topic_lines.append(
            f"• {html_escape(topic.title)} · {stage}: "
            f"практика {topic.practice_successes}/{topic.practice_required}{accuracy}, "
            f"перенос {topic.transfer_successes}/{topic.transfer_required}, "
            + (
                f"письмо {topic.production_successes}/{topic.production_required} "
                if topic.production_required
                else "письмо на следующей ступени "
            )
            + f"→ {status}"
        )
    module_reply = _module_progress_reply(
        session, user, channel_id=channel_id, message_thread_id=message_thread_id
    )
    return BotReply(
        "📈 <b>Прогресс · 30 дней</b>\n"
        f"Узнавание: {recognition_correct}/{recognition_total} верных ответов.\n"
        f"Письменная практика: {production_correct}/{production_total} верных; "
        "считается отдельно.\n"
        + (
            f"Без оценки: {production_unchecked}; в точность письма не включены.\n"
            if production_unchecked
            else ""
        )
        + "\n"
        "Узнавание проверяет, что ты распознаёшь; письмо — что умеешь использовать.\n\n"
        "<b>Темы · весь период · B2 → B2+ → C1 intro</b>\n"
        + "\n".join(topic_lines)
        + "\n\nЭто ориентиры по упражнениям, а не подтверждение уровня CEFR. "
        "Следующий шаг: /plan.",
        channel_id,
        message_thread_id=message_thread_id,
        parse_mode=HTML_PARSE_MODE,
        extra_replies=(module_reply,) if module_reply is not None else (),
    )


def _curriculum_action(action: str) -> str:
    return {
        "practice": "практика",
        "spaced_practice": "повтор позже",
        "transfer_wait": "новый контекст позже",
        "transfer": "новый контекст",
        "production": "своё предложение",
        "c1_locked": "C1 пока закрыт",
        "maintain": "поддерживать",
    }.get(action, "практика")


def handle_plan(
    session: Session,
    user: User,
    *,
    channel_id: str | None = None,
    message_thread_id: int | None = None,
) -> BotReply:
    """Show the next personal curriculum step without starting a session."""

    from fluentloop.adaptive_learning import curriculum_progress
    from fluentloop.learning_prefs import is_simple_mode

    progress = curriculum_progress(session, user)
    focus = next((topic for topic in progress.topics if topic.repair), None)
    focus = focus or next(
        (
            topic
            for topic in progress.topics
            if not topic.mastered
            and topic.next_action in {"practice", "transfer", "production"}
        ),
        None,
    )
    focus = focus or next(
        (topic for topic in progress.topics if not topic.mastered), None
    )
    lines = [
        "🗺 <b>План обучения</b>",
        f"B2/B2+: устойчивые темы {progress.strong_b2_topics}/{progress.total_topics}.",
        "B2+: закрепление и перенос в новом контексте по каждой теме.",
        (
            "C1 intro: открыт для новых заданий."
            if progress.c1_unlocked
            else "C1 intro: откроется после устойчивого B2+ по всем темам."
        ),
    ]
    if focus is not None:
        focus_stage = {"b2": "B2", "b2_plus": "B2+", "c1_intro": "C1 intro"}[
            focus.stage
        ]
        lines.extend(
            [
                "",
                f"Следующая тема: <b>{html_escape(focus.title)}</b> ({focus_stage}).",
                f"Следующий шаг: {_curriculum_action(focus.next_action)}.",
            ]
        )
    gaps = ", ".join(
        html_escape(topic.title) for topic in progress.topics if not topic.mastered
    )
    lines.extend(
        [
            "",
            "Пробелы: " + gaps[:700]
            if gaps
            else "Все текущие темы закрыты; возвращайся для повторения.",
            "Это план по сохранённым ответам, а не оценка уровня CEFR.",
            "/roadmap — общий английский и дополнительные рабочие направления.",
        ]
    )
    study_action = "simple:study" if is_simple_mode(user) else "today:lesson"
    return BotReply(
        "\n".join(lines),
        channel_id,
        buttons=[
            [
                _button("Учиться", study_action),
                _button("Прогресс", "simple:progress"),
            ],
            [_button("Общий план", "simple:roadmap")],
        ],
        message_thread_id=message_thread_id,
        parse_mode=HTML_PARSE_MODE,
    )


def handle_simple_text_guard(session: Session, user: User) -> BotReply | None:
    """Keep arbitrary text out of the vocabulary-add path during a quiz."""

    from fluentloop.simple_learning import get_active_stream

    if get_active_stream(session, user) is None:
        return None
    return BotReply(
        "Нажми вариант ответа или «Не знаю». Текстовый ответ здесь не сохраняется."
    )


def handle_mistakes(session: Session, user: User) -> BotReply:
    patterns = active_patterns(session, user.id)
    buttons = [
        [
            _button(f"Focus #{pattern.id}", f"mistake:focus:{pattern.id}"),
            _button(f"Ignore #{pattern.id}", f"mistake:ignore:{pattern.id}"),
            _button(f"Examples #{pattern.id}", f"mistake:examples:{pattern.id}"),
        ]
        for pattern in patterns
    ]
    return BotReply(mistake_patterns(patterns), buttons=buttons or None)


def handle_mistake_action(
    session: Session, user: User, action: str, pattern_id: int
) -> BotReply:
    from fluentloop.db.models import MistakePattern

    pattern = session.get(MistakePattern, pattern_id)
    if pattern is None or pattern.user_id != user.id:
        return BotReply("Mistake pattern not found.")
    if action == "focus":
        promote_pattern(session, pattern)
        return BotReply(f"Promoted pattern #{pattern.id}: {pattern.description}")
    if action == "ignore":
        archive_pattern(session, pattern)
        return BotReply(f"Archived pattern #{pattern.id}: {pattern.description}")
    if action == "examples":
        wrong = pattern.wrong_examples or ["No wrong examples stored."]
        correct = pattern.correct_examples or ["No corrected examples stored."]
        lines = [f"Examples for pattern #{pattern.id}: {pattern.description}"]
        for index, (wrong_example, correct_example) in enumerate(
            zip(wrong[-5:], correct[-5:], strict=False),
            start=1,
        ):
            lines.append(f"{index}. Wrong: {wrong_example}")
            lines.append(f"   Better: {correct_example}")
        return BotReply("\n".join(lines))
    return BotReply(
        "Use /mistakes focus <id>, /mistakes ignore <id>, or /mistakes examples <id>."
    )


def handle_favorites(session: Session, user: User) -> BotReply:
    items = [
        item for item in favorite_items(session, user.id) if not is_adaptive_item(item)
    ]
    if not items:
        return BotReply("No favorites yet.")
    buttons = [[_favorite_button(item.id, item.is_favorite)] for item in items]
    return BotReply(
        "Favorites\n" + "\n".join(f"- #{item.id} {item.text}" for item in items),
        buttons=buttons,
    )


def handle_favorite_toggle(session: Session, user: User, item_id: int) -> BotReply:
    from fluentloop.db.models import LearningItem

    item = session.get(LearningItem, item_id)
    if item is None or item.user_id != user.id or is_adaptive_item(item):
        return BotReply("Learning item not found.")
    toggle_favorite(session, item)
    marker = "favorite" if item.is_favorite else "not favorite"
    return BotReply(
        f"Marked #{item.id} as {marker}: {item.text}",
        buttons=[[_favorite_button(item.id, item.is_favorite)]],
    )


def handle_items(session: Session, user: User, status: str = "active") -> BotReply:
    try:
        items = [
            item
            for item in list_items(session, user.id, status=status, limit=50)
            if not is_adaptive_item(item)
        ][:20]
    except ValueError as exc:
        return BotReply(f"Could not list items: {exc}")
    if not items:
        return BotReply(f"No {status} learning items.")
    lines = [f"Learning items ({status})"]
    for item in items:
        favorite = " *" if item.is_favorite else ""
        lines.append(f"- #{item.id} [{item.type}] {item.text}{favorite}")
    buttons = [_item_buttons(item.id, item.status, item.is_favorite) for item in items]
    return BotReply("\n".join(lines), buttons=buttons)


def handle_item_status(
    session: Session, user: User, item_id: int, action: str
) -> BotReply:
    from fluentloop.db.models import LearningItem

    item = session.get(LearningItem, item_id)
    if item is None or item.user_id != user.id or is_adaptive_item(item):
        return BotReply("Learning item not found.")
    target = {
        "archive": "archived",
        "suspend": "suspended",
        "restore": "active",
    }.get(action)
    if target is None:
        return BotReply(ITEM_STATUS_USAGE)
    set_item_status(session, item, target)
    return BotReply(
        f"Marked #{item.id} as {target}: {item.text}",
        buttons=[_item_buttons(item.id, item.status, item.is_favorite)],
    )


def _find_item_by_text(
    session: Session, user: User, word: str, *, exclude_graduated: bool = False
) -> LearningItem | None:
    from sqlalchemy import func

    normalized = word.strip().casefold()
    if not normalized:
        return None
    stmt = select(LearningItem).where(
        LearningItem.user_id == user.id,
        func.lower(LearningItem.text) == normalized,
    )
    if exclude_graduated:
        stmt = stmt.where(LearningItem.status != "graduated")
    matches = list(session.scalars(stmt.order_by(LearningItem.created_at)))
    return next((item for item in matches if not is_adaptive_item(item)), None)


def _near_matches(
    session: Session, user: User, word: str, *, limit: int = 5
) -> list[str]:
    needle = word.strip()
    if not needle:
        return []
    rows = session.scalars(
        select(LearningItem)
        .where(LearningItem.user_id == user.id, LearningItem.text.ilike(f"%{needle}%"))
        .order_by(LearningItem.created_at)
        .limit(limit)
    )
    return [row.text for row in rows if not is_adaptive_item(row)]


def _not_found_reply(session: Session, user: User, word: str, action: str) -> BotReply:
    near = _near_matches(session, user, word)
    if near:
        listing = "\n".join(f"- {html_escape(text)}" for text in near)
        return BotReply(
            f"No exact match for {code(word)}. Did you mean:\n{listing}",
            parse_mode=HTML_PARSE_MODE,
        )
    return BotReply(
        f"Nothing to {action}: no item matches {code(word)}.",
        parse_mode=HTML_PARSE_MODE,
    )


def handle_words(session: Session, user: User) -> BotReply:
    from fluentloop.srs import get_due_items

    counts = {
        status: len(list_items(session, user.id, status=status, limit=1000))
        for status in ("active", "graduated", "archived")
    }
    lines = [
        bold("Your words"),
        f"Active: {counts['active']}",
        f"🎓 Graduated: {counts['graduated']}",
    ]
    if counts["archived"]:
        lines.append(f"Archived: {counts['archived']}")

    upcoming = get_due_items(session, user.id, limit=20)
    if upcoming:
        lines.append("")
        lines.append(bold("Coming up"))
        for item in upcoming:
            if is_adaptive_item(item):
                continue
            marker = " ⭐" if item.is_favorite else ""
            mine = " (yours)" if item.priority > 0 else ""
            lines.append(f"- {html_escape(item.text)}{marker}{mine}")
    elif not counts["active"]:
        lines.append("")
        lines.append("Send me any word or phrase to add it.")
    return BotReply("\n".join(lines), parse_mode=HTML_PARSE_MODE)


def handle_more(session: Session, user: User, word: str) -> BotReply:
    if not word.strip():
        return BotReply("Use /more <word>.")
    item = _find_item_by_text(session, user, word)
    if item is None:
        return _not_found_reply(session, user, word, "expand")
    metadata = item.metadata_json or {}
    lines = [bold(item.text)]
    meaning = (item.meaning or item.explanation or "").strip()
    if meaning:
        lines.append(html_escape(meaning))
    synonyms = metadata.get("synonyms") or []
    if synonyms:
        lines.append("")
        lines.append(labeled("Synonyms", ", ".join(str(s) for s in synonyms)))
    collocations = metadata.get("collocations") or []
    if collocations:
        lines.append(labeled("Collocations", ", ".join(str(c) for c in collocations)))
    if item.examples:
        lines.append("")
        lines.append(bold("Examples"))
        for example in item.examples[:3]:
            lines.append(f"- {html_escape(example)}")
    if len(lines) == 1:
        lines.append("No details stored for this item yet.")
    return BotReply(
        "\n".join(lines),
        buttons=[_item_buttons(item.id, item.status, item.is_favorite)],
        parse_mode=HTML_PARSE_MODE,
    )


def handle_learned(session: Session, user: User, word: str) -> BotReply:
    from datetime import timedelta

    from fluentloop.db.models import ReviewState, utc_now

    if not word.strip():
        return BotReply("Use /learned <word>.")
    item = _find_item_by_text(session, user, word, exclude_graduated=True)
    if item is None:
        return _not_found_reply(session, user, word, "graduate")
    set_item_status(session, item, "graduated")
    state = session.scalar(
        select(ReviewState).where(ReviewState.learning_item_id == item.id)
    )
    if state is not None:
        # Park it far out so a later restore does not dump it straight back
        # into the due queue.
        state.due_at = utc_now() + timedelta(days=730)
        session.add(state)
        session.flush()
    return BotReply(
        f"🎓 Graduated: {bold(item.text)}",
        buttons=[[_button("Undo", f"item:restore:{item.id}")]],
        parse_mode=HTML_PARSE_MODE,
    )


def handle_delete(session: Session, user: User, word: str) -> BotReply:
    if not word.strip():
        return BotReply("Use /delete <word>.")
    item = _find_item_by_text(session, user, word)
    if item is None:
        return _not_found_reply(session, user, word, "delete")
    set_item_status(session, item, "archived")
    return BotReply(
        f"Removed {bold(item.text)}.",
        buttons=[[_button("Undo", f"item:restore:{item.id}")]],
        parse_mode=HTML_PARSE_MODE,
    )


def handle_keyboard_toggle(session: Session, user: User) -> BotReply:
    """Show or hide the button panel.

    It collapses after each tap anyway, but on a small screen even a collapsed
    panel is one more thing in the way, so it can be switched off entirely.
    """

    from fluentloop.learning_prefs import is_simple_mode
    from fluentloop.vocab_prefs import get_prefs, update_pref

    wanted = not get_prefs(user).keyboard
    simple = is_simple_mode(user)
    update_pref(session, user, "keyboard", wanted)
    if wanted:
        if simple:
            return BotReply(
                "Кнопки возвращены. Они сворачиваются после нажатия; "
                "значок клавиатуры открывает их снова.\n"
                "/keyboard скрывает кнопки.",
                persistent_keyboard=True,
                simple_keyboard=True,
            )
        return BotReply(
            "Buttons are back. They collapse after each tap - the keyboard "
            "icon in the input field brings them up again.\n"
            "/keyboard hides them.",
            persistent_keyboard=True,
        )
    return BotReply(
        "Buttons hidden. Everything still works as a command:\n"
        "/cards · /review · /quiz · /today · /words · /stop\n"
        "/keyboard brings them back.",
        clear_keyboard=True,
    )


def handle_pause(session: Session, user: User) -> BotReply:
    from fluentloop.learning_prefs import is_simple_mode
    from fluentloop.vocab_prefs import update_pref

    update_pref(session, user, "paused", True)
    if is_simple_mode(user):
        return BotReply(
            "В простом режиме нет автоматических сообщений. Пауза "
            "сохранена для расширенного режима."
        )
    return BotReply("Daily messages paused. Send /resume to turn them back on.")


def handle_resume(session: Session, user: User) -> BotReply:
    from fluentloop.learning_prefs import is_simple_mode
    from fluentloop.vocab_prefs import SLOTS, update_pref

    prefs = update_pref(session, user, "paused", False)
    if is_simple_mode(user):
        return BotReply(
            "В простом режиме автоматических сообщений нет. Прежнее "
            "расписание сохранено; переключи режим в «Ещё» или /settings, "
            "чтобы вернуться к нему."
        )
    slots = " / ".join(prefs.slots[slot] for slot in SLOTS)
    return BotReply(f"Daily messages on again: {slots}.")


def handle_vocab_cards(
    session: Session, user: User, count: int | None = None
) -> BotReply:
    from fluentloop.vocab_loop import render_cards, select_cards
    from fluentloop.vocab_prefs import MAX_WORDS_PER_DAY, MIN_WORDS_PER_DAY, get_prefs

    wanted = count if count is not None else get_prefs(user).words_per_day
    wanted = max(MIN_WORDS_PER_DAY, min(MAX_WORDS_PER_DAY, wanted))
    items = select_cards(session, user, count=wanted)
    if not items:
        return BotReply("No words to show yet. Send me any word or phrase to add it.")
    # Reading the cards is the passive half; offer the active half right here
    # rather than leaving the learner at a dead end.
    return BotReply(
        render_cards(items),
        buttons=[
            [
                _button("🔁 Practise these", "words:review"),
                _button("📖 Vocabulary lesson", "words:lesson"),
            ]
        ],
        parse_mode=HTML_PARSE_MODE,
    )


def handle_vocab_add(
    session: Session, user: User, raw: str, *, settings: Settings | None = None
) -> BotReply:
    from fluentloop.learning import USER_ADDED_PRIORITY
    from fluentloop.vocab_loop import guess_item_type, split_word_list
    from fluentloop.word_cards import enrich_item

    segments = split_word_list(raw)
    if not segments:
        return BotReply("Nothing to add.")
    added: list[str] = []
    existing: list[str] = []
    added_ids: list[int] = []
    added_items: list[LearningItem] = []
    for segment in segments:
        type_ = guess_item_type(segment)
        # create_learning_item returns the existing row on collision, so ask
        # first to tell "added" from "already had".
        was_present = (
            session.scalar(
                select(LearningItem).where(
                    LearningItem.user_id == user.id,
                    LearningItem.type == type_,
                    LearningItem.text == segment,
                )
            )
            is not None
        )
        item = create_learning_item(
            session,
            user,
            type_=type_,
            text=segment,
            tags=["user_added"],
            metadata={"source": "user_added"},
            priority=USER_ADDED_PRIORITY,
        )
        if item.priority < USER_ADDED_PRIORITY:
            item.priority = USER_ADDED_PRIORITY
            session.add(item)
            session.flush()
        if was_present:
            existing.append(item.text)
        else:
            # A bare phrase is not a card yet: fill in the translation, gloss
            # and an example before it ever reaches the learner.
            enrich_item(session, item, settings=settings)
            added.append(item.text)
            added_ids.append(item.id)
            added_items.append(item)

    lines: list[str] = []
    if added:
        from fluentloop.vocab_loop import render_cards

        lines.append(f"Added {len(added)}:")
        # Show the card that was built, so the learner sees at once whether the
        # translation and example are right - and can fix them if not.
        lines.append(render_cards(added_items, title="New words"))
    if existing:
        lines.append(f"Already had {len(existing)}:")
        lines.extend(f"- {html_escape(text)}" for text in existing)
    lines.append("")
    lines.append(italic("Your own words always get top priority."))
    buttons = [[_button("Treat as material instead", "upload:confirm:pending")]]
    if added_ids:
        joined = ",".join(str(item_id) for item_id in added_ids)
        buttons.append([_button("Undo", f"vocab:undo:{joined}")])
    return BotReply(
        "\n".join(lines),
        buttons=buttons,
        parse_mode=HTML_PARSE_MODE,
    )


QUICK_ACTIONS: tuple[tuple[str, str], ...] = (
    ("🃏 Cards", "cards"),
    ("🔁 Review", "review"),
    ("📚 Lesson", "lesson"),
    ("📖 My words", "words"),
    ("➕ Add words", "add"),
    ("🎯 Quiz", "quiz"),
    ("⏹ Stop", "stop"),
)
SIMPLE_QUICK_ACTIONS: tuple[tuple[str, str], ...] = (
    ("Учиться", "study"),
    ("Прогресс", "progress"),
    ("Ещё", "simple_menu"),
)
QUICK_ACTION_BY_LABEL: dict[str, str] = {
    label: action for label, action in (*QUICK_ACTIONS, *SIMPLE_QUICK_ACTIONS)
}


def quick_action_for(text: str) -> str | None:
    """Map a tap on the persistent keyboard back to an action.

    These arrive as ordinary text messages, so this has to run before the
    free-text paths - otherwise "🃏 Cards" gets added as a vocabulary item.
    """

    return QUICK_ACTION_BY_LABEL.get((text or "").strip())


DRILL_STATE = "vocab_drill"
ADD_WORDS_STATE = "vocab_add"


def set_add_words_state(session: Session, user: User, *, chat_id: int) -> None:
    StateStore(session).set(chat_id, user.telegram_user_id, ADD_WORDS_STATE, {})


def handle_add_words_prompt(session: Session, user: User, *, chat_id: int) -> BotReply:
    """Arm an explicit add, so the material heuristic cannot get in the way."""

    set_add_words_state(session, user, chat_id=chat_id)
    return BotReply(
        "Send the word or phrase you want to add.\n"
        "Several at once: separate them with commas or new lines.\n\n"
        "cut corners, push back on, roll out",
    )


ONBOARDING_STATE = "onboarding"

TOPIC_CHOICES: tuple[tuple[str, str], ...] = (
    ("sports", "⚽ Sports"),
    ("tech", "💻 Tech"),
    ("food", "🍳 Food & cooking"),
    ("travel", "✈️ Travel"),
    ("business", "📈 Business"),
    ("science", "🔬 Science"),
    ("gaming", "🎮 Gaming"),
    ("books", "📚 Books"),
    ("fitness", "🏋️ Fitness"),
    ("art", "🎨 Art & design"),
)
KIND_CHOICES: tuple[tuple[str, str], ...] = (
    ("phrasal_verbs", "🧩 Phrasal verbs"),
    ("idioms", "💬 Idioms"),
    ("business_english", "💼 Business English"),
    ("academic_ielts", "🎓 Academic / IELTS"),
    ("everyday_talk", "🗣 Everyday talk"),
    ("collocations", "🔗 Collocations"),
    ("news", "📰 News & current events"),
    ("small_talk", "🤝 Small talk"),
)
SET_CHOICES: tuple[tuple[str, str], ...] = (
    ("pulp_fiction", "🔫 Pulp Fiction"),
    ("film_noir", "🕵️ Film noir"),
    ("fantasy_epic", "🐉 Fantasy epic"),
    ("sci_fi", "🚀 Sci-fi"),
    ("internet_speak", "😂 Internet speak"),
    ("hiphop_slang", "🎤 Hip-hop slang"),
    ("posh_british", "👑 Posh British"),
    ("horror_true_crime", "🔪 Horror & true crime"),
    ("rom_com", "🍿 Rom-com"),
)
SIZE_CHOICES = (100, 200, 300, 500)
PER_DAY_CHOICES: tuple[tuple[int, str], ...] = (
    (3, "3 — light"),
    (5, "5 — steady"),
    (7, "7 — brisk"),
    (10, "10 — intense"),
)


def _multiselect_buttons(
    options: tuple[tuple[str, str], ...],
    selected: set[str],
    *,
    prefix: str,
    done_data: str,
    per_row: int = 2,
) -> list[list[InlineButton]]:
    rows: list[list[InlineButton]] = []
    current: list[InlineButton] = []
    for slug, label in options:
        text = f"✅ {label}" if slug in selected else label
        current.append(_button(text, f"{prefix}{slug}"))
        if len(current) == per_row:
            rows.append(current)
            current = []
    if current:
        rows.append(current)
    rows.append([_button("Done ▶", done_data)])
    return rows


def _onboarding_state(session: Session, chat_id: int, user: User):
    return StateStore(session).get(chat_id, user.telegram_user_id)


def _save_onboarding(session: Session, chat_id: int, user: User, payload: dict) -> None:
    StateStore(session).set(chat_id, user.telegram_user_id, ONBOARDING_STATE, payload)


def _topics_reply(payload: dict, *, edit: bool = False) -> BotReply:
    return BotReply(
        "❤️ Pick a few topics you enjoy — your example sentences will be about "
        "them.\n\nTap to toggle, then Done.",
        buttons=_multiselect_buttons(
            TOPIC_CHOICES,
            set(payload.get("topics", [])),
            prefix="onb:topic:",
            done_data="onb:done:topics",
        ),
        edit_message=edit,
    )


def _kinds_reply(payload: dict, *, edit: bool = False) -> BotReply:
    selected = set(payload.get("kinds", [])) | set(payload.get("sets", []))
    return BotReply(
        "📦 What kind of vocabulary do you want to build?\n\n"
        "🎪 The bottom rows are fun sets — optional, but they make practice a "
        "lot more entertaining.\n\nPick as many as you like, then Done.",
        buttons=_multiselect_buttons(
            (*KIND_CHOICES, *SET_CHOICES),
            selected,
            prefix="onb:kind:",
            done_data="onb:done:kinds",
        ),
        edit_message=edit,
    )


def _size_reply(*, edit: bool = False) -> BotReply:
    return BotReply(
        "📊 How many words should I put in your starter list?\n"
        "You can always add more of your own later.",
        buttons=[[_button(str(size), f"onb:size:{size}") for size in SIZE_CHOICES]],
        edit_message=edit,
    )


def _per_day_reply(*, edit: bool = False) -> BotReply:
    return BotReply(
        "🐢 How many words per day do you want to practice?",
        buttons=[
            [_button(label, f"onb:perday:{value}")] for value, label in PER_DAY_CHOICES
        ],
        edit_message=edit,
    )


def handle_onboarding_start(session: Session, user: User, *, chat_id: int) -> BotReply:
    payload = {
        "step": "topics",
        "topics": [],
        "kinds": [],
        "sets": [],
        "size": 200,
        "per_day": 5,
    }
    _save_onboarding(session, chat_id, user, payload)
    return _topics_reply(payload)


def handle_onboarding_callback(
    session: Session, user: User, action: str, value: str, *, chat_id: int
) -> BotReply:
    state = _onboarding_state(session, chat_id, user)
    if state is None or state.name != ONBOARDING_STATE:
        return handle_onboarding_start(session, user, chat_id=chat_id)
    payload = dict(state.payload or {})

    if action == "cancel":
        StateStore(session).clear(chat_id, user.telegram_user_id)
        return BotReply("Setup cancelled. Run /setup any time.")

    if action == "topic":
        payload["topics"] = _toggle(payload.get("topics", []), value)
        _save_onboarding(session, chat_id, user, payload)
        return _topics_reply(payload, edit=True)

    if action == "kind":
        known_sets = {slug for slug, _ in SET_CHOICES}
        key = "sets" if value in known_sets else "kinds"
        payload[key] = _toggle(payload.get(key, []), value)
        _save_onboarding(session, chat_id, user, payload)
        return _kinds_reply(payload, edit=True)

    if action == "done":
        if value == "topics":
            payload["step"] = "kinds"
            _save_onboarding(session, chat_id, user, payload)
            return _kinds_reply(payload, edit=True)
        payload["step"] = "size"
        _save_onboarding(session, chat_id, user, payload)
        return _size_reply(edit=True)

    if action == "size":
        payload["size"] = int(value) if value.isdigit() else 200
        payload["step"] = "per_day"
        _save_onboarding(session, chat_id, user, payload)
        return _per_day_reply(edit=True)

    if action == "perday":
        payload["per_day"] = int(value) if value.isdigit() else 5
        return _finish_onboarding(session, user, payload, chat_id=chat_id)

    return BotReply("Unknown setup step. Run /setup to start over.")


def _toggle(values: list[str], value: str) -> list[str]:
    current = list(values)
    if value in current:
        current.remove(value)
    else:
        current.append(value)
    return current


def _finish_onboarding(
    session: Session, user: User, payload: dict, *, chat_id: int
) -> BotReply:
    from dataclasses import replace as replace_dataclass

    from fluentloop.db.models import utc_now
    from fluentloop.vocab_prefs import get_prefs, set_prefs
    from fluentloop.wordbank import seed_starter_list

    topics = list(payload.get("topics", []))
    kinds = list(payload.get("kinds", []))
    sets = list(payload.get("sets", []))
    size = int(payload.get("size", 200))
    per_day = int(payload.get("per_day", 5))

    prefs = replace_dataclass(
        get_prefs(user),
        topics=topics,
        kinds=kinds,
        sets=sets,
        starter_size=size,
        words_per_day=per_day,
        onboarded_at=utc_now().isoformat(),
    )
    set_prefs(session, user, prefs)
    StateStore(session).clear(chat_id, user.telegram_user_id)

    created, _skipped = seed_starter_list(
        session, user, topics=topics, kinds=kinds, sets=sets, size=size
    )
    morning = prefs.slots["morning"]
    lines = [f"✅ {created} words added."]
    if created < size:
        lines.append(
            f"That is everything the bank has for your picks; the target was "
            f"{size}. Send me your own words any time to top it up."
        )
    lines.append(f"First cards tomorrow at {morning}.")
    lines.append(f"Try /today {per_day} for a preview right now.")
    # Replaces the wizard rather than leaving a dead keyboard behind.
    return BotReply("\n".join(lines), edit_message=True)


def set_drill_state(
    session: Session,
    user: User,
    delivery_id: int,
    *,
    chat_id: int | None = None,
) -> None:
    """Arm the free-text capture for a midday drill.

    The daily loop always delivers to the private chat, where chat_id equals
    the Telegram user id, so that is the default.
    """

    StateStore(session).set(
        chat_id if chat_id is not None else user.telegram_user_id,
        user.telegram_user_id,
        DRILL_STATE,
        {"delivery_id": delivery_id},
    )


def quiz_buttons(delivery_id: int, options: list[str]) -> list[list[InlineButton]]:
    return [
        [_button(option, f"vocab:ans:{delivery_id}:{index}")]
        for index, option in enumerate(options)
    ]


def render_daily_slot(
    session: Session,
    user: User,
    slot: str,
    delivery,
    *,
    now=None,
    settings: Settings | None = None,
) -> BotReply | None:
    """Build the message for one daily slot, or None when there is nothing.

    The evening slot is not rendered here: it is a multi-question quiz, so
    the scheduler delivers it through ``_deliver_evening_quiz`` instead.
    """

    from fluentloop.vocab_loop import build_drill, render_cards, render_drill
    from fluentloop.vocab_prefs import get_prefs

    if slot == "morning":
        from fluentloop.vocab_loop import select_cards

        items = select_cards(
            session, user, count=get_prefs(user).words_per_day, now=now
        )
        if not items:
            return None
        delivery.learning_item_ids = [item.id for item in items]
        return BotReply(
            render_cards(items),
            user.telegram_user_id,
            parse_mode=HTML_PARSE_MODE,
        )

    if slot == "midday":
        built = build_drill(session, user, now=now)
        if built is None:
            return None
        item, exercise = built
        delivery.learning_item_ids = [item.id]
        delivery.payload_json = {"exercise": exercise.as_dict()}
        return BotReply(
            render_drill(exercise),
            user.telegram_user_id,
            buttons=[
                [
                    _button("✍️ Answer", f"vocab:drill:{delivery.id}"),
                    _button("Skip", f"vocab:skip:{delivery.id}"),
                ]
            ],
            parse_mode=HTML_PARSE_MODE,
        )

    return None


def _load_delivery(session: Session, user: User, delivery_id: int):
    from fluentloop.db.models import VocabDelivery

    delivery = session.get(VocabDelivery, delivery_id)
    if delivery is None or delivery.user_id != user.id:
        return None
    return delivery


def handle_quiz_answer(
    session: Session, user: User, delivery_id: int, choice: int
) -> BotReply:
    from fluentloop.srs import apply_review

    delivery = _load_delivery(session, user, delivery_id)
    if delivery is None:
        return BotReply("That quiz is no longer available.")
    if delivery.status == "answered":
        return BotReply("You already answered this one.")
    payload = delivery.payload_json or {}
    options = payload.get("options") or []
    correct_index = int(payload.get("correct_index", -1))
    if not options or not 0 <= choice < len(options):
        return BotReply("That answer is no longer available.")

    item_ids = delivery.learning_item_ids or []
    item = session.get(LearningItem, item_ids[0]) if item_ids else None
    correct = choice == correct_index
    graduated = False
    if item is not None:
        _, graduated = apply_review(session, item, "Good" if correct else "Again")
    delivery.status = "answered"
    delivery.payload_json = {**payload, "chosen_index": choice}
    session.add(delivery)
    session.flush()

    answer = options[correct_index] if 0 <= correct_index < len(options) else ""
    verdict = f"✅ Right — {bold(answer)}" if correct else f"❌ It was {bold(answer)}"
    lines = [verdict]
    solution = str(payload.get("solution") or "").strip()
    if solution:
        lines.append(italic(solution))
    lines.extend(_answer_gloss_lines(item))
    if graduated:
        lines.append("🎓 Graduated!")
    lines.extend(_glossary_lines(session, user, options, correct_index))
    followup, lines = _quiz_followup(session, delivery, lines)
    return BotReply(
        "\n".join(lines),
        parse_mode=HTML_PARSE_MODE,
        quiz_question_delivery_id=followup,
    )


def _answer_gloss_lines(item: LearningItem | None) -> list[str]:
    """Russian translation of the answer, shown only once it is revealed."""

    if item is None:
        return []
    from fluentloop.vocab_loop import russian_definition

    russian = russian_definition(item)
    return [italic(russian)] if russian else []


def _glossary_lines(
    session: Session, user: User, options: list[str], correct_index: int
) -> list[str]:
    """Explain the options the learner did not pick, so they stick too."""

    from fluentloop.quiz import option_glossary

    notes = option_glossary(session, user, list(options), correct_index)
    if not notes:
        return []
    lines = ["", bold("The others were:")]
    for note in notes:
        if note.english:
            lines.append(f"• {bold(note.text)} — {html_escape(note.english)}")
        else:
            lines.append(f"• {bold(note.text)}")
        # Russian only ever appears after the learner has answered.
        if note.russian:
            lines.append(f"   {italic(note.russian)}")
    return lines


def handle_poll_vote(
    session: Session, poll_id: int, options: list[bytes]
) -> BotReply | None:
    """Turn an incoming native poll vote into a reply, or None to stay silent."""

    from fluentloop.bot.polls import resolve_vote

    outcome = resolve_vote(session, poll_id, options)
    if outcome is None:
        return None
    if outcome.correct:
        lines = [f"✅ Right — {bold(outcome.item_text)}"]
    else:
        lines = [f"❌ It was {bold(outcome.item_text)}"]
    if outcome.solution:
        lines.append(italic(outcome.solution))
    lines.extend(_answer_gloss_lines(outcome.item))
    if outcome.graduated:
        lines.append("🎓 Graduated!")
    voter = session.get(User, outcome.user_id) if outcome.user_id else None
    if voter is not None:
        lines.extend(
            _glossary_lines(
                session, voter, list(outcome.options), outcome.correct_index
            )
        )
    delivery = session.get(VocabDelivery, outcome.delivery_id)
    followup, lines = _quiz_followup(session, delivery, lines)
    return BotReply(
        "\n".join(lines),
        outcome.telegram_user_id or None,
        parse_mode=HTML_PARSE_MODE,
        quiz_question_delivery_id=followup,
    )


def _quiz_followup(
    session: Session, delivery, lines: list[str]
) -> tuple[int | None, list[str]]:
    """Chain the next quiz question, or wrap the quiz up when it ended."""

    from fluentloop.bot.polls import next_quiz_delivery, quiz_summary_line

    if delivery is None:
        return None, lines
    nxt = next_quiz_delivery(session, delivery)
    if nxt is not None:
        return nxt.id, lines
    summary = quiz_summary_line(session, delivery)
    if summary:
        lines = [*lines, "", summary]
    return None, lines


def handle_quiz_start(
    session: Session,
    user: User,
    *,
    now=None,
    settings: Settings | None = None,
) -> BotReply:
    """Start or resume today's on-demand quiz.

    One on-demand quiz per local day: a second /quiz while questions remain
    picks up where the learner stopped, and once everything is answered the
    summary is shown again instead of building a fresh set.
    """

    from fluentloop.bot.polls import quiz_intro, quiz_summary_line
    from fluentloop.quiz import evening_quiz_set
    from fluentloop.vocab_loop import local_date
    from fluentloop.vocab_prefs import get_prefs

    day = local_date(user, now=now)
    rows = list(
        session.scalars(
            select(VocabDelivery)
            .where(
                VocabDelivery.user_id == user.id,
                VocabDelivery.local_date == day,
                VocabDelivery.slot == "quiz",
            )
            .order_by(VocabDelivery.seq)
        ).all()
    )
    claimed = [row for row in rows if row.status == "claimed"]
    if rows and not claimed:
        text = quiz_summary_line(session, rows[0]) or "You finished today's quiz."
        return BotReply(text, parse_mode=HTML_PARSE_MODE)
    if claimed:
        first = claimed[0]
        intro = quiz_intro(len(rows), resume_at=first.seq + 1)
    else:
        specs = evening_quiz_set(
            session,
            user,
            count=get_prefs(user).quiz_size,
            now=now,
            settings=settings,
        )
        if not specs:
            return BotReply("No words to quiz yet. Send me a few words first.")
        rows = []
        for seq, spec in enumerate(specs):
            row = VocabDelivery(
                user_id=user.id,
                local_date=day,
                slot="quiz",
                seq=seq,
                status="claimed",
            )
            row.learning_item_ids = [spec.item_id]
            row.payload_json = {
                "question": spec.question,
                "options": list(spec.options),
                "correct_index": spec.correct_index,
                "solution": spec.solution,
                "mode": "buttons",
            }
            session.add(row)
            rows.append(row)
        session.flush()
        first = rows[0]
        intro = quiz_intro(len(rows))
    return BotReply(
        intro,
        user.telegram_user_id,
        parse_mode=HTML_PARSE_MODE,
        quiz_question_delivery_id=first.id,
    )


def handle_stop(
    session: Session,
    user: User,
    *,
    chat_id: int,
    channel_id: str | None = None,
    message_thread_id: int | None = None,
) -> BotReply:
    """Cancel whatever is waiting for input and close the active session."""

    from fluentloop.bot.polls import QUIZ_SLOTS
    from fluentloop.practice import get_in_progress_session
    from fluentloop.vocab_loop import local_date

    StateStore(session).clear(chat_id, user.telegram_user_id)
    lines = ["⏹ Stopped. Nothing is waiting for your input."]
    from fluentloop.simple_learning import (
        get_active_bonus,
        get_active_stream,
        skip_bonus,
    )

    bonus = get_active_bonus(session, user)
    if bonus is not None:
        skip_bonus(session, user, bonus.id)
        lines.append("Optional writing was skipped; it is not counted as a mistake.")
    simple = get_active_stream(session, user)
    if simple is not None:
        summary = handle_simple_stop(session, user, simple.id)
        lines.append(summary.text)
        lines.append("/study starts a new stream.")
    current = get_in_progress_session(session, user)
    if current is not None:
        current.status = "abandoned"
        session.add(current)
        lines.append("Today's practice session is closed — /today starts a fresh one.")
    # Quiz questions are paused rather than discarded: the learner asked the
    # bot to stop talking, not to throw away their progress. Saying nothing
    # about them would make the line above untrue.
    pending = session.scalar(
        select(func.count())
        .select_from(VocabDelivery)
        .where(
            VocabDelivery.user_id == user.id,
            VocabDelivery.local_date == local_date(user),
            VocabDelivery.slot.in_(QUIZ_SLOTS),
            VocabDelivery.status == "claimed",
        )
    )
    if pending:
        lines.append(
            f"{pending} quiz question(s) are paused — /quiz picks up where "
            "you left off."
        )
    return BotReply("\n".join(lines), channel_id, message_thread_id=message_thread_id)


def handle_drill_start(
    session: Session, user: User, delivery_id: int, *, chat_id: int | None = None
) -> BotReply:
    delivery = _load_delivery(session, user, delivery_id)
    if delivery is None:
        return BotReply("That drill is no longer available.")
    if delivery.status == "answered":
        return BotReply("You already answered this one.")
    set_drill_state(session, user, delivery_id, chat_id=chat_id)
    # The prompt is already on screen in the message above; repeating it just
    # adds noise.
    return BotReply("Go ahead — send your answer as a message.")


def handle_drill_skip(
    session: Session, user: User, delivery_id: int, *, chat_id: int | None = None
) -> BotReply:
    from fluentloop.srs import apply_review

    delivery = _load_delivery(session, user, delivery_id)
    if delivery is None:
        return BotReply("That drill is no longer available.")
    delivery.status = "skipped"
    session.add(delivery)
    exercise = (delivery.payload_json or {}).get("exercise", {})
    item_ids = delivery.learning_item_ids or []
    if item_ids:
        item = session.get(LearningItem, item_ids[0])
        if item is not None:
            apply_review(session, item, "Hard")
    StateStore(session).clear(
        chat_id if chat_id is not None else user.telegram_user_id,
        user.telegram_user_id,
    )
    expected = str(exercise.get("expected_answer") or "").strip()
    if expected:
        return BotReply(
            f"Skipped. The answer was {bold(expected)}.",
            parse_mode=HTML_PARSE_MODE,
        )
    return BotReply("Skipped.")


def handle_drill_answer(
    session: Session,
    user: User,
    provider: AIProvider,
    delivery_id: int,
    answer: str,
    *,
    chat_id: int | None = None,
) -> BotReply:
    from fluentloop.feedback import srs_result_from_feedback
    from fluentloop.srs import apply_review

    delivery = _load_delivery(session, user, delivery_id)
    if delivery is None:
        return BotReply("That drill is no longer available.")
    payload = delivery.payload_json or {}
    exercise = payload.get("exercise") or {}
    # check_answer takes the stored exercise dict directly.
    feedback = check_answer(provider, exercise, answer)
    item_ids = delivery.learning_item_ids or []
    graduated = False
    if item_ids:
        item = session.get(LearningItem, item_ids[0])
        if item is not None:
            _, graduated = apply_review(
                session, item, srs_result_from_feedback(feedback)
            )
    delivery.status = "answered"
    delivery.payload_json = {**payload, "user_answer": answer}
    session.add(delivery)
    session.flush()
    StateStore(session).clear(
        chat_id if chat_id is not None else user.telegram_user_id,
        user.telegram_user_id,
    )

    lines = [labeled("Verdict", f"{feedback.status.title()}.")]
    better = feedback.natural_answer or feedback.corrected_answer
    if better:
        lines.append(f"{bold('Better:')} {code(better)}")
    if feedback.explanation:
        lines.append(html_escape(feedback.explanation))
    if graduated:
        lines.append("🎓 Graduated!")
    return BotReply("\n".join(lines), parse_mode=HTML_PARSE_MODE)


def handle_vocab_undo(session: Session, user: User, raw_ids: str) -> BotReply:
    removed = 0
    for chunk in raw_ids.split(","):
        chunk = chunk.strip()
        if not chunk.isdigit():
            continue
        item = session.get(LearningItem, int(chunk))
        if item is not None and item.user_id == user.id:
            set_item_status(session, item, "archived")
            removed += 1
    if not removed:
        return BotReply("Nothing to undo.")
    return BotReply(f"Removed {removed} item(s).")


def handle_rules(session: Session) -> BotReply:
    from sqlalchemy import func, select

    from fluentloop.db.models import GrammarConcept, LearningItem, MistakePattern

    seed_concepts(session)
    concepts = session.scalars(
        select(GrammarConcept).order_by(GrammarConcept.title)
    ).all()
    lines = ["Grammar rules"]
    for concept in concepts:
        pattern_count = session.scalar(
            select(func.count())
            .select_from(MistakePattern)
            .where(
                MistakePattern.linked_grammar_concept_id == concept.id,
                MistakePattern.status == "active",
            )
        )
        item_count = session.scalar(
            select(func.count())
            .select_from(LearningItem)
            .where(
                LearningItem.linked_grammar_concept_id == concept.id,
                LearningItem.status == "active",
            )
        )
        suffix = ""
        if pattern_count or item_count:
            suffix = f" ({item_count or 0} items, {pattern_count or 0} patterns)"
        lines.append(f"- {concept.title}{suffix}")
    return BotReply("Grammar rules\n" + "\n".join(lines[1:]))


def command_catalog() -> list[str]:
    return [
        "/start",
        "/setup",
        "/today",
        "/study",
        "/progress",
        "/plan",
        "/cards",
        "/review",
        "/practice",
        "/baseline",
        "/outcomes",
        "/library",
        "/subscribe",
        "/topics",
        "/lessons",
        "/lesson",
        "/add",
        "/approve",
        "/candidates",
        "/candidate",
        "/upload",
        "/feedback",
        "/dispute",
        "/mistakes",
        "/rules",
        "/stats",
        "/favorites",
        "/favorite",
        "/items",
        "/item",
        "/words",
        "/more",
        "/learned",
        "/delete",
        "/quiz",
        "/stop",
        "/keyboard",
        "/pause",
        "/resume",
        "/settings",
        "/help",
        "/howto",
    ]


def exercise_type_count() -> int:
    return len(EXERCISE_TYPES)


def state_store(session: Session) -> StateStore:
    return StateStore(session)
