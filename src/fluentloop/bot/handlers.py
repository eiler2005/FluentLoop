from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from fluentloop.ai.provider import AIProvider
from fluentloop.bot.formatting import HTML_PARSE_MODE, bold, code, html_escape, labeled
from fluentloop.bot.messages import (
    HELP,
    candidate_summary,
    mistake_patterns,
    start_message,
)
from fluentloop.bot.state import StateStore
from fluentloop.coach_journal import write_coach_journal
from fluentloop.config import Settings
from fluentloop.db.models import User
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
    lesson_topic_groups,
    random_lesson_plan,
)
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

ITEM_STATUS_USAGE = (
    "Use /item archive <id>, /item suspend <id>, or /item restore <id>."
)


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


def _button(text: str, data: str) -> InlineButton:
    return InlineButton(text=text, data=data)


def _settings_buttons(user: User) -> list[list[InlineButton]]:
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
        [_button("Refresh", "settings:refresh:now")],
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
        "1. Start with /today for the automatic 15-minute lesson, or choose a "
        "lesson with /lessons and /lesson.\n"
        "2. Browse shared seed lessons with /library, then copy one into your "
        "own lesson base with /subscribe <template_id>.\n"
        "3. Answer in text. Use /skip or Skip / show answer when you want the "
        "model answer first.\n"
        "4. Read compact teacher feedback. Use /feedback explain <attempt_id> "
        "for the full breakdown.\n"
        "5. Upload lesson notes in Materials Upload with /upload; approve "
        "candidates before they become active learning items.\n\n"
        "Workspace map:\n"
        "- Practice Flow: current lesson and answers\n"
        "- Materials Upload: lesson notes, word lists, homework, feedback\n"
        "- Feedback: corrections and explanations\n"
        "- Next Prompts: follow-up prompts\n"
        "- Mistakes, Summaries, Stats: weak points and progress\n\n"
        "Useful commands: /today, /library, /subscribe, /practice, /topics, "
        "/lessons, /lesson random, /lesson topic <query>, /upload, /skip, "
        "/help, /howto.",
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
    session: Session, settings: Settings, telegram_user_id: int
) -> BotReply:
    user = ensure_user(session, telegram_user_id, settings)
    seed_concepts(session)
    return BotReply(
        start_message(
            bool(settings.telegram_forum_group_id or settings.telegram_channel_id)
        ),
        user.telegram_user_id,
    )


def handle_help() -> BotReply:
    return BotReply(HELP)


def handle_settings(session: Session, user: User) -> BotReply:
    return BotReply(format_settings(user), buttons=_settings_buttons(user))


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
    return handle_add(
        session, user, type_=type_, text=text, meaning=meaning, tags=tags
    )


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
            f"- #{candidate.id} [{candidate.status}] "
            f"{candidate.type}: {candidate.text}"
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
        pool_size = lesson_pool_size(session, template)
        lines.append(
            f"#{template.id} {html_escape(template.title)} - "
            f"{html_escape(template.topic)} - pool {pool_size}"
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
    return BotReply(
        "\n".join(
            [
                f"Subscribed to template #{template_id}.",
                f"LessonPlan #{result.plan.id}: {result.plan.title}",
                f"Topic: {result.plan.topic}",
                f"Created items: {result.created_items}",
                f"Reused items: {result.reused_items}",
                "Open it with /lesson "
                f"{result.plan.id}, or let /today rotate it in.",
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
        f"Published template #{plan.id}: {plan.title}. "
        "It is now visible in /library."
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
    groups = lesson_topic_groups(session, user)
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
        pool_size = lesson_pool_size(session, plan)
        lines.append(
            f"#{plan.id} {html_escape(plan.title)} - "
            f"{html_escape(plan.topic)} - pool {pool_size}"
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
        return BotReply(
            "Use /lesson <id>, /lesson random, or /lesson topic <query>."
        )
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
    chunks = [item.text for item in items if item.type in {"word", "expression"}][:8]
    grammar = [item.text for item in items if item.type == "grammar_rule"][:6]
    mistakes = [item.text for item in items if item.type == "mistake_pattern"][:5]
    lines = [
        f"{bold('Lesson')} #{plan.id}",
        labeled("Title", plan.title),
        labeled("Topic", plan.topic),
        labeled("Goal", plan.goal),
        labeled("Format", getattr(plan, "format", "lesson")),
    ]
    if plan.language_focus_json:
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
    chunks = [item.text for item in items if item.type in {"word", "expression"}][:8]
    grammar = [item.text for item in items if item.type == "grammar_rule"][:6]
    mistakes = [item.text for item in items if item.type == "mistake_pattern"][:5]
    lines = [
        f"{bold('Shared library lesson')} #{template.id}",
        labeled("Title", template.title),
        labeled("Topic", template.topic),
        labeled("Goal", template.goal),
    ]
    if template.language_focus_json:
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


def handle_feedback_explain(session: Session, user: User, attempt_id: int) -> BotReply:
    from fluentloop.db.models import PracticeAttempt, PracticeSession

    attempt = session.get(PracticeAttempt, attempt_id)
    if attempt is None:
        return BotReply("Attempt not found.")
    practice_session = session.get(PracticeSession, attempt.practice_session_id)
    if practice_session is None or practice_session.user_id != user.id:
        return BotReply("Attempt not found.")
    return BotReply(
        render_detailed_teacher_feedback(attempt.feedback),
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


def handle_article(payload: str) -> BotReply:
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
        "Use /mistakes focus <id>, /mistakes ignore <id>, "
        "or /mistakes examples <id>."
    )


def handle_favorites(session: Session, user: User) -> BotReply:
    items = favorite_items(session, user.id)
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
    if item is None or item.user_id != user.id:
        return BotReply("Learning item not found.")
    toggle_favorite(session, item)
    marker = "favorite" if item.is_favorite else "not favorite"
    return BotReply(
        f"Marked #{item.id} as {marker}: {item.text}",
        buttons=[[_favorite_button(item.id, item.is_favorite)]],
    )


def handle_items(session: Session, user: User, status: str = "active") -> BotReply:
    try:
        items = list_items(session, user.id, status=status, limit=20)
    except ValueError as exc:
        return BotReply(f"Could not list items: {exc}")
    if not items:
        return BotReply(f"No {status} learning items.")
    lines = [f"Learning items ({status})"]
    for item in items:
        favorite = " *" if item.is_favorite else ""
        lines.append(f"- #{item.id} [{item.type}] {item.text}{favorite}")
    buttons = [
        _item_buttons(item.id, item.status, item.is_favorite) for item in items
    ]
    return BotReply("\n".join(lines), buttons=buttons)


def handle_item_status(
    session: Session, user: User, item_id: int, action: str
) -> BotReply:
    from fluentloop.db.models import LearningItem

    item = session.get(LearningItem, item_id)
    if item is None or item.user_id != user.id:
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
        "/today",
        "/review",
        "/practice",
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
        "/settings",
        "/help",
        "/howto",
    ]


def exercise_type_count() -> int:
    return len(EXERCISE_TYPES)


def state_store(session: Session) -> StateStore:
    return StateStore(session)
