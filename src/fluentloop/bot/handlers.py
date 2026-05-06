from __future__ import annotations

from dataclasses import dataclass

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
from fluentloop.feedback import apply_feedback, check_answer
from fluentloop.grammar import seed_concepts
from fluentloop.learning import create_learning_item, favorite_items
from fluentloop.materials import approve_all, extract_candidates, store_material
from fluentloop.mistakes import active_patterns
from fluentloop.practice import next_exercise, record_attempt, start_or_resume_session
from fluentloop.stats import collect_stats, render_stats
from fluentloop.users import ensure_user, format_settings, update_setting


@dataclass(frozen=True)
class BotReply:
    text: str
    target_chat_id: int | str | None = None


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
    return BotReply(format_settings(user))


def handle_setting_update(
    session: Session, user: User, field: str, value: str
) -> BotReply:
    try:
        update_setting(session, user, field, value)
    except ValueError as exc:
        return BotReply(f"Could not update setting: {exc}")
    return BotReply("Updated.\n" + format_settings(user))


def handle_add(
    session: Session,
    user: User,
    *,
    type_: str,
    text: str,
    meaning: str = "",
    tags: list[str] | None = None,
) -> BotReply:
    item = create_learning_item(
        session,
        user,
        type_=type_,
        text=text,
        meaning=meaning,
        tags=tags or [],
    )
    return BotReply(f"Added {item.type}: {item.text}")


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
    material = store_material(session, user, raw_text, type_=type_)
    candidates = extract_candidates(session, material, provider)
    return BotReply(candidate_summary(candidates))


def handle_approve_all(session: Session, user: User, material_id: int) -> BotReply:
    from fluentloop.db.models import SourceMaterial

    source = session.get(SourceMaterial, material_id)
    if source is None:
        return BotReply("Material not found.")
    count = approve_all(session, user, source)
    return BotReply(f"Added {count} learning items.")


def handle_today(
    session: Session,
    user: User,
    *,
    channel_id: str | None = None,
) -> BotReply:
    practice_session = start_or_resume_session(session, user)
    current = next_exercise(session, practice_session)
    if current is None:
        return BotReply(
            "Today's practice is complete.", channel_id or user.telegram_user_id
        )
    index, exercise = current
    text = f"Today's English practice\n\nExercise {index + 1}/7\n{exercise['prompt']}"
    return BotReply(text, channel_id or user.telegram_user_id)


def handle_answer(
    session: Session,
    user: User,
    provider: AIProvider,
    answer: str,
) -> BotReply:
    practice_session = start_or_resume_session(session, user)
    current = next_exercise(session, practice_session)
    if current is None:
        return BotReply("No active exercise. Send /today.")
    index, exercise = current
    feedback = check_answer(provider, exercise, answer)
    apply_feedback(session, user, exercise, answer, feedback)
    record_attempt(
        session, practice_session, index, exercise, answer, feedback.model_dump()
    )
    follow_up = next_exercise(session, practice_session)
    message = (
        f"{feedback.status.title()}.\n"
        f"Better: {feedback.natural_answer or feedback.corrected_answer}\n"
        f"Why: {feedback.explanation}"
    )
    if follow_up is not None:
        next_index, next_item = follow_up
        message += f"\n\nExercise {next_index + 1}/7\n{next_item['prompt']}"
    else:
        message += "\n\nSession complete."
    return BotReply(message)


def handle_stats(session: Session, user: User) -> BotReply:
    return BotReply(render_stats(collect_stats(session, user)))


def handle_mistakes(session: Session, user: User) -> BotReply:
    return BotReply(mistake_patterns(active_patterns(session, user.id)))


def handle_favorites(session: Session, user: User) -> BotReply:
    items = favorite_items(session, user.id)
    if not items:
        return BotReply("No favorites yet.")
    return BotReply("Favorites\n" + "\n".join(f"- {item.text}" for item in items))


def handle_rules(session: Session) -> BotReply:
    from sqlalchemy import select

    from fluentloop.db.models import GrammarConcept

    seed_concepts(session)
    concepts = session.scalars(
        select(GrammarConcept).order_by(GrammarConcept.title)
    ).all()
    return BotReply(
        "Grammar rules\n" + "\n".join(f"- {concept.title}" for concept in concepts)
    )


def command_catalog() -> list[str]:
    return [
        "/start",
        "/today",
        "/review",
        "/add",
        "/approve",
        "/upload",
        "/mistakes",
        "/rules",
        "/stats",
        "/favorites",
        "/settings",
        "/help",
    ]


def exercise_type_count() -> int:
    return len(EXERCISE_TYPES)


def state_store(session: Session) -> StateStore:
    return StateStore(session)
