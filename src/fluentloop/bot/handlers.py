from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from fluentloop.ai.provider import AIProvider
from fluentloop.bot.messages import (
    HELP,
    candidate_summary,
    mistake_patterns,
    start_message,
)
from fluentloop.bot.state import StateStore
from fluentloop.config import Settings
from fluentloop.db.models import User
from fluentloop.exercises import EXERCISE_TYPES
from fluentloop.feedback import apply_feedback, check_answer, write_dispute
from fluentloop.grammar import seed_concepts
from fluentloop.learning import (
    create_learning_item,
    favorite_items,
    list_items,
    set_item_status,
    toggle_favorite,
)
from fluentloop.materials import (
    approve_all,
    approve_candidate,
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
    start_or_resume_session,
    summarize_session,
)
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
        [_button("Refresh", "settings:refresh:now")],
    ]


def _candidate_buttons(candidate_id: int) -> list[InlineButton]:
    return [
        _button(f"Add #{candidate_id}", f"candidate:add:{candidate_id}"),
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


def _dispute_buttons(attempt_id: int) -> list[list[InlineButton]]:
    return [
        [
            _button("Got it", f"attempt:ack:{attempt_id}"),
            _button("I disagree", f"dispute:{attempt_id}:equally_valid"),
        ],
        [
            _button("AI was wrong", f"dispute:{attempt_id}:ai_wrong"),
            _button("Style issue", f"dispute:{attempt_id}:style_preference"),
        ],
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
        start_message(bool(settings.telegram_channel_id)), user.telegram_user_id
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
    return BotReply(candidate_summary(candidates), buttons=buttons)


def handle_approve_all(session: Session, user: User, material_id: int) -> BotReply:
    from fluentloop.db.models import SourceMaterial

    source = session.get(SourceMaterial, material_id)
    if source is None:
        return BotReply("Material not found.")
    count = approve_all(session, user, source)
    return BotReply(f"Added {count} learning items.")


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
    session: Session, user: User, action: str, candidate_id: int
) -> BotReply:
    from fluentloop.db.models import ExtractedCandidate

    candidate = session.get(ExtractedCandidate, candidate_id)
    if candidate is None:
        return BotReply("Candidate not found.")
    try:
        if action == "add":
            changed = approve_candidate(session, user, candidate)
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


def handle_today(
    session: Session,
    user: User,
    *,
    channel_id: str | None = None,
) -> BotReply:
    practice_session = start_or_resume_session(session, user)
    current = next_exercise(session, practice_session)
    if current is None:
        text = "Today's practice is complete."
        if channel_id:
            text = "#summary\n" + text
        return BotReply(
            text, channel_id or user.telegram_user_id
        )
    index, exercise = current
    title = "Today's English practice"
    if channel_id:
        title = "#practice_flow\n" + title
    text = f"{title}\n\nExercise {index + 1}/7\n{exercise['prompt']}"
    return BotReply(text, channel_id or user.telegram_user_id)


def handle_answer(
    session: Session,
    user: User,
    provider: AIProvider,
    answer: str,
    *,
    channel_id: str | None = None,
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
    pattern = apply_feedback(session, user, exercise, answer, feedback)
    attempt = record_attempt(
        session, practice_session, index, exercise, answer, feedback.model_dump()
    )
    follow_up = next_exercise(session, practice_session)
    heading = "#feedback\n" if channel_id else ""
    message = (
        f"{heading}Attempt #{attempt.id}\n"
        f"{feedback.status.title()}.\n"
        f"Better: {feedback.natural_answer or feedback.corrected_answer}\n"
        f"Why: {feedback.explanation}"
    )
    if feedback.related_rule:
        message += f"\nRule: {feedback.related_rule}"
    if feedback.should_create_mistake_event:
        message += "\nI'll add this as a weak point unless you dispute it."
    if pattern is not None and pattern.confidence == "low":
        message += (
            f"\n#mistakes Recurring pattern #{pattern.id} detected. "
            f"Use /mistakes focus {pattern.id} or /mistakes ignore {pattern.id}."
        )
    message += f"\nDisagree? Use the buttons or send /dispute {attempt.id} <reason>."
    if follow_up is not None:
        next_index, next_item = follow_up
        next_heading = "#next_prompt\n" if channel_id else ""
        message += (
            f"\n\n{next_heading}Exercise {next_index + 1}/7\n"
            f"{next_item['prompt']}"
        )
    else:
        summary_heading = "#summary\n" if channel_id else ""
        message += "\n\n" + summary_heading + summarize_session(
            session, practice_session
        )
    return BotReply(
        message,
        channel_id or user.telegram_user_id,
        buttons=_dispute_buttons(attempt.id),
    )


def handle_attempt_ack(session: Session, user: User, attempt_id: int) -> BotReply:
    from fluentloop.db.models import PracticeAttempt, PracticeSession

    attempt = session.get(PracticeAttempt, attempt_id)
    if attempt is None:
        return BotReply("Attempt not found.")
    practice_session = session.get(PracticeSession, attempt.practice_session_id)
    if practice_session is None or practice_session.user_id != user.id:
        return BotReply("Attempt not found.")
    return BotReply(f"Got it. Keeping attempt #{attempt.id} as-is.")


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
    return BotReply("Use /mistakes focus <id> or /mistakes ignore <id>.")


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
        "/add",
        "/approve",
        "/candidates",
        "/candidate",
        "/upload",
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
    ]


def exercise_type_count() -> int:
    return len(EXERCISE_TYPES)


def state_store(session: Session) -> StateStore:
    return StateStore(session)
