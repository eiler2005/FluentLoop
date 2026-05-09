from __future__ import annotations

import logging
from pathlib import Path

from sqlalchemy.orm import sessionmaker

from fluentloop.ai.factory import make_provider
from fluentloop.bot.handlers import (
    BotReply,
    handle_add_text,
    handle_answer,
    handle_approve_all,
    handle_attempt_ack,
    handle_attempt_hard,
    handle_candidate_action,
    handle_candidate_edit_menu,
    handle_candidate_edit_prompt,
    handle_candidate_edit_value,
    handle_candidates,
    handle_channel_help,
    handle_channel_hub,
    handle_dispute,
    handle_favorite_toggle,
    handle_favorites,
    handle_feedback_explain,
    handle_help,
    handle_item_status,
    handle_items,
    handle_lesson,
    handle_lesson_callback,
    handle_lessons,
    handle_materials_channel_hub,
    handle_mistake_action,
    handle_mistakes,
    handle_practice,
    handle_rules,
    handle_setting_update,
    handle_settings,
    handle_skip_all,
    handle_skip_current,
    handle_start,
    handle_stats,
    handle_today,
    handle_topics,
    handle_upload,
    handle_upload_prompt,
    handle_upload_start,
    handle_upload_type_choice,
)
from fluentloop.bot.state import StateStore
from fluentloop.channel import record_channel_discovery
from fluentloop.config import Settings
from fluentloop.db.models import User
from fluentloop.db.session import session_scope
from fluentloop.materials import MAX_UPLOAD_CHARS
from fluentloop.scheduler import build_scheduler
from fluentloop.telegram_bot_api import pin_bot_api_message, send_bot_api_reply
from fluentloop.telegram_workspace import workspace_destination, workspace_enabled
from fluentloop.users import ensure_user

LOG = logging.getLogger(__name__)
ITEM_STATUS_USAGE = (
    "Use /item archive <id>, /item suspend <id>, or /item restore <id>."
)
CANDIDATE_USAGE = "Use /candidate add <id> or /candidate skip <id>."
CHANNEL_DISCOVERY_PATH = Path("data/channel_discovery.json")


def _is_forum_chat(chat_id: int | str | None, settings: Settings) -> bool:
    return (
        chat_id is not None
        and settings.telegram_forum_group_id is not None
        and str(chat_id) == str(settings.telegram_forum_group_id)
    )


def _effective_user_id(
    telegram_user_id: int, chat_id: int | str | None, settings: Settings
) -> int:
    if _is_forum_chat(chat_id, settings) and settings.telegram_allowed_user_id:
        return settings.telegram_allowed_user_id
    return telegram_user_id


async def _reject_or_ignore(event, settings: Settings) -> None:  # type: ignore[no-untyped-def]
    if _is_forum_chat(event.chat_id, settings):
        return
    await event.reply("This is a personal FluentLoop bot.")


def _telethon_buttons(reply: BotReply):  # type: ignore[no-untyped-def]
    if not reply.buttons:
        return None
    from telethon import Button

    return [
        [
            Button.inline(button.text, button.data.encode("utf-8"))
            for button in row
        ]
        for row in reply.buttons
    ]


async def send_reply(  # type: ignore[no-untyped-def]
    client,
    fallback_chat_id,
    reply: BotReply,
    settings: Settings | None = None,
):
    if reply.message_thread_id is not None:
        if settings is None:
            raise RuntimeError("Forum topic replies need Settings for Bot API")
        message = await send_bot_api_reply(settings.telegram_bot_token, reply)
    else:
        message = await client.send_message(
            reply.target_chat_id or fallback_chat_id,
            reply.text,
            buttons=_telethon_buttons(reply),
            parse_mode=reply.parse_mode,
        )
    for extra in reply.extra_replies:
        await send_reply(client, fallback_chat_id, extra, settings)
    return message


async def answer_callback(event, text: str) -> None:  # type: ignore[no-untyped-def]
    try:
        await event.answer(text)
    except Exception as exc:  # noqa: BLE001 - Telegram may expire callback ids.
        LOG.warning("Could not answer callback query: %s", type(exc).__name__)


async def pin_reply(  # type: ignore[no-untyped-def]
    settings: Settings,
    client,
    fallback_chat_id,
    reply: BotReply,
) -> None:
    message = await send_reply(client, fallback_chat_id, reply, settings)
    try:
        if reply.message_thread_id is not None:
            await pin_bot_api_message(
                settings.telegram_bot_token,
                reply.target_chat_id or fallback_chat_id,
                message.message_id,
            )
        else:
            await client.pin_message(
                reply.target_chat_id or fallback_chat_id,
                message,
                notify=False,
            )
    except Exception:
        LOG.exception("Could not pin Telegram help message")


async def maybe_record_channel(event, settings: Settings) -> bool:  # type: ignore[no-untyped-def]
    chat = await event.get_chat()
    title = getattr(chat, "title", None)
    if title not in {settings.telegram_channel_title, settings.telegram_forum_title}:
        return False
    chat_id = event.chat_id
    if chat_id is None:
        return False
    record_channel_discovery(
        CHANNEL_DISCOVERY_PATH,
        title=title,
        channel_id=int(chat_id),
    )
    LOG.info("Discovered Telegram workspace chat %r from incoming event", title)
    return title == settings.telegram_channel_title


def _reply_in_workspace_topic(
    reply: BotReply, settings: Settings, topic: str
) -> BotReply:
    target = workspace_destination(settings, topic)
    if target.chat_id is None or target.message_thread_id is None:
        return reply
    return BotReply(
        reply.text,
        target.chat_id,
        reply.buttons,
        target.message_thread_id,
        reply.extra_replies,
        reply.parse_mode,
    )


def _material_upload_reply(reply: BotReply, event, settings: Settings) -> BotReply:  # type: ignore[no-untyped-def]
    if _is_forum_chat(event.chat_id, settings):
        return _reply_in_workspace_topic(reply, settings, "materials_upload")
    return reply


async def _material_text_from_event(event) -> str:  # type: ignore[no-untyped-def]
    raw_text = str(event.raw_text or "").strip()
    file = getattr(event.message, "file", None)
    if file is None:
        return raw_text
    size = getattr(file, "size", None)
    if size is not None and size > MAX_UPLOAD_CHARS:
        raise ValueError("Material is too large; paste it in chunks")
    blob = await event.download_media(file=bytes)
    if not isinstance(blob, bytes) or not blob:
        raise ValueError("Could not read the attached file")
    if len(blob) > MAX_UPLOAD_CHARS:
        raise ValueError("Material is too large; paste it in chunks")
    try:
        file_text = blob.decode("utf-8").strip()
    except UnicodeDecodeError as exc:
        raise ValueError("Only UTF-8 text, .txt, or .md files are supported") from exc
    if raw_text and not raw_text.startswith("/"):
        return f"{raw_text}\n\n{file_text}".strip()
    return file_text


async def run_bot(settings: Settings, session_factory: sessionmaker) -> None:
    from telethon import TelegramClient, events

    provider = make_provider(settings)
    client = TelegramClient(
        "data/sessions/fluentloop-bot",
        settings.telegram_api_id,
        settings.telegram_api_hash,
    )

    @client.on(events.NewMessage(pattern=r"^/"))
    async def on_command(event) -> None:  # type: ignore[no-untyped-def]
        if await maybe_record_channel(event, settings):
            return
        sender = await event.get_sender()
        sender_id = int(sender.id)
        telegram_user_id = _effective_user_id(sender_id, event.chat_id, settings)
        with session_scope(session_factory) as session:
            if (
                settings.telegram_allowed_user_id is not None
                and settings.telegram_allowed_user_id != telegram_user_id
            ):
                await _reject_or_ignore(event, settings)
                return
            user = ensure_user(session, telegram_user_id, settings)
            parts = event.raw_text.split(maxsplit=2)
            command = parts[0]
            if command == "/start":
                reply = handle_start(session, settings, telegram_user_id)
                if workspace_enabled(settings):
                    help_target = workspace_destination(settings, "help")
                    practice_target = workspace_destination(settings, "practice_flow")
                    materials_target = workspace_destination(
                        settings, "materials_upload"
                    )
                    await pin_reply(
                        settings,
                        client,
                        event.chat_id,
                        handle_channel_help(
                            str(help_target.chat_id),
                            message_thread_id=help_target.message_thread_id,
                        ),
                    )
                    await send_reply(
                        client,
                        event.chat_id,
                        handle_channel_hub(
                            str(practice_target.chat_id),
                            message_thread_id=practice_target.message_thread_id,
                        ),
                        settings,
                    )
                    await send_reply(
                        client,
                        event.chat_id,
                        handle_materials_channel_hub(
                            str(materials_target.chat_id),
                            message_thread_id=materials_target.message_thread_id,
                        ),
                        settings,
                    )
            elif command in {"/help", "/howto"}:
                reply = handle_help()
                if workspace_enabled(settings):
                    help_target = workspace_destination(settings, "help")
                    await pin_reply(
                        settings,
                        client,
                        event.chat_id,
                        handle_channel_help(
                            str(help_target.chat_id),
                            message_thread_id=help_target.message_thread_id,
                        ),
                    )
            elif command == "/today":
                practice_target = workspace_destination(settings, "practice_flow")
                reply = handle_today(
                    session,
                    user,
                    channel_id=(
                        str(practice_target.chat_id)
                        if practice_target.chat_id is not None
                        else None
                    ),
                    message_thread_id=practice_target.message_thread_id,
                )
            elif command == "/review":
                practice_target = workspace_destination(settings, "practice_flow")
                reply = handle_practice(
                    session,
                    user,
                    "review",
                    channel_id=(
                        str(practice_target.chat_id)
                        if practice_target.chat_id is not None
                        else None
                    ),
                    message_thread_id=practice_target.message_thread_id,
                )
            elif command == "/practice":
                mode = parts[1] if len(parts) >= 2 else ""
                practice_target = workspace_destination(settings, "practice_flow")
                reply = handle_practice(
                    session,
                    user,
                    mode,
                    channel_id=(
                        str(practice_target.chat_id)
                        if practice_target.chat_id is not None
                        else None
                    ),
                    message_thread_id=practice_target.message_thread_id,
                )
            elif command == "/topics":
                reply = handle_topics(session, user)
            elif command == "/lessons":
                query = event.raw_text.removeprefix("/lessons").strip()
                reply = handle_lessons(session, user, query)
            elif command == "/lesson":
                payload = event.raw_text.removeprefix("/lesson").strip()
                practice_target = workspace_destination(settings, "practice_flow")
                reply = handle_lesson(
                    session,
                    user,
                    payload,
                    channel_id=(
                        str(practice_target.chat_id)
                        if practice_target.chat_id is not None
                        else None
                    ),
                    message_thread_id=practice_target.message_thread_id,
                )
            elif command == "/settings":
                if len(parts) == 3 and parts[1] == "set":
                    field, _, value = parts[2].partition(" ")
                    reply = handle_setting_update(session, user, field, value)
                else:
                    reply = handle_settings(session, user)
            elif command == "/add":
                payload = event.raw_text.removeprefix("/add").strip()
                if payload:
                    reply = handle_add_text(session, user, payload)
                else:
                    StateStore(session).set(event.chat_id, telegram_user_id, "add", {})
                    reply = BotReply(
                        "Send one line:\n"
                        "expression | push back on | мягко возражать | meetings"
                    )
            elif command == "/upload":
                upload_type = parts[1] if len(parts) >= 2 else "other"
                if getattr(event.message, "file", None) is not None:
                    try:
                        material_text = await _material_text_from_event(event)
                    except ValueError as exc:
                        reply = BotReply(f"Could not read material: {exc}")
                    else:
                        reply = handle_upload(
                            session, user, provider, material_text, type_=upload_type
                        )
                else:
                    StateStore(session).set(
                        event.chat_id,
                        telegram_user_id,
                        "upload",
                        {"type": upload_type},
                    )
                    reply = (
                        handle_upload_start()
                        if len(parts) < 2
                        else handle_upload_type_choice(upload_type)
                    )
                reply = _material_upload_reply(reply, event, settings)
            elif command == "/approve":
                if len(parts) < 2:
                    reply = BotReply("Use /approve <material_id>.")
                else:
                    try:
                        material_id = int(parts[1])
                    except ValueError:
                        reply = BotReply("Use /approve <material_id>.")
                    else:
                        reply = handle_approve_all(session, user, material_id, provider)
                reply = _material_upload_reply(reply, event, settings)
            elif command == "/candidates":
                if len(parts) < 2:
                    reply = BotReply("Use /candidates <material_id>.")
                else:
                    try:
                        material_id = int(parts[1])
                    except ValueError:
                        reply = BotReply("Use /candidates <material_id>.")
                    else:
                        reply = handle_candidates(session, user, material_id)
                reply = _material_upload_reply(reply, event, settings)
            elif command == "/candidate":
                if len(parts) < 3:
                    reply = BotReply(CANDIDATE_USAGE)
                else:
                    try:
                        candidate_id = int(parts[2])
                    except ValueError:
                        reply = BotReply(CANDIDATE_USAGE)
                    else:
                        reply = handle_candidate_action(
                            session, user, parts[1], candidate_id, provider
                        )
                reply = _material_upload_reply(reply, event, settings)
            elif command == "/stats":
                reply = handle_stats(session, user)
            elif command == "/dispute":
                if len(parts) < 3:
                    reply = BotReply("Use /dispute <attempt_id> <reason>.")
                else:
                    try:
                        attempt_id = int(parts[1])
                    except ValueError:
                        reply = BotReply("Use /dispute <attempt_id> <reason>.")
                    else:
                        reply = handle_dispute(session, user, attempt_id, parts[2])
            elif command == "/feedback":
                if len(parts) < 3 or parts[1] != "explain":
                    reply = BotReply("Use /feedback explain <attempt_id>.")
                else:
                    try:
                        attempt_id = int(parts[2])
                    except ValueError:
                        reply = BotReply("Use /feedback explain <attempt_id>.")
                    else:
                        reply = handle_feedback_explain(session, user, attempt_id)
            elif command == "/skip":
                next_target = workspace_destination(settings, "next_prompt")
                summary_target = workspace_destination(settings, "summary")
                practice_target = workspace_destination(settings, "practice_flow")
                reply = handle_skip_current(
                    session,
                    user,
                    channel_id=(
                        str(practice_target.chat_id)
                        if practice_target.chat_id is not None
                        else None
                    ),
                    message_thread_id=practice_target.message_thread_id,
                    next_channel_id=(
                        str(next_target.chat_id)
                        if next_target.message_thread_id is not None
                        else None
                    ),
                    next_message_thread_id=next_target.message_thread_id,
                    summary_channel_id=(
                        str(summary_target.chat_id)
                        if summary_target.message_thread_id is not None
                        else None
                    ),
                    summary_message_thread_id=summary_target.message_thread_id,
                )
            elif command == "/mistakes":
                if len(parts) >= 3 and parts[1] in {
                    "focus",
                    "ignore",
                    "examples",
                }:
                    try:
                        pattern_id = int(parts[2])
                    except ValueError:
                        reply = BotReply(
                            "Use /mistakes focus <id> or /mistakes ignore <id>."
                        )
                    else:
                        reply = handle_mistake_action(
                            session, user, parts[1], pattern_id
                        )
                else:
                    reply = handle_mistakes(session, user)
            elif command == "/favorites":
                reply = handle_favorites(session, user)
            elif command == "/favorite":
                if len(parts) < 2:
                    reply = BotReply("Use /favorite <item_id>.")
                else:
                    try:
                        item_id = int(parts[1])
                    except ValueError:
                        reply = BotReply("Use /favorite <item_id>.")
                    else:
                        reply = handle_favorite_toggle(session, user, item_id)
            elif command == "/items":
                status = parts[1] if len(parts) >= 2 else "active"
                reply = handle_items(session, user, status)
            elif command == "/item":
                if len(parts) < 3:
                    reply = BotReply(ITEM_STATUS_USAGE)
                else:
                    try:
                        item_id = int(parts[2])
                    except ValueError:
                        reply = BotReply(ITEM_STATUS_USAGE)
                    else:
                        reply = handle_item_status(session, user, item_id, parts[1])
            elif command == "/rules":
                reply = handle_rules(session)
            else:
                reply = handle_help()
            await send_reply(client, event.chat_id, reply, settings)

    @client.on(events.CallbackQuery)
    async def on_callback(event) -> None:  # type: ignore[no-untyped-def]
        sender = await event.get_sender()
        sender_id = int(sender.id)
        telegram_user_id = _effective_user_id(sender_id, event.chat_id, settings)
        raw_data = bytes(event.data or b"").decode("utf-8", errors="replace")
        with session_scope(session_factory) as session:
            if (
                settings.telegram_allowed_user_id is not None
                and settings.telegram_allowed_user_id != telegram_user_id
            ):
                await answer_callback(event, "This is a personal FluentLoop bot.")
                return
            user = ensure_user(session, telegram_user_id, settings)
            parts = raw_data.split(":", 2)
            if raw_data in {"start_today", "today:start"}:
                practice_target = workspace_destination(settings, "practice_flow")
                reply = handle_today(
                    session,
                    user,
                    channel_id=(
                        str(practice_target.chat_id)
                        if practice_target.chat_id is not None
                        else None
                    ),
                    message_thread_id=practice_target.message_thread_id,
                )
                await answer_callback(event, "Starting practice")
            elif raw_data == "topics:list":
                reply = handle_topics(session, user)
                await answer_callback(event, "Topics")
            elif raw_data == "lessons:list":
                reply = handle_lessons(session, user, "")
                await answer_callback(event, "Lessons")
            elif raw_data == "practice:modes":
                reply = BotReply(
                    "Practice modes\n"
                    "/practice vocab - words and expressions\n"
                    "/practice grammar - grammar micro-drills\n"
                    "/practice mistakes - active weak points\n"
                    "/practice writing - mini-writing prompts\n"
                    "/practice review - due SRS items\n"
                    "/practice mixed - balanced practice"
                )
                await answer_callback(event, "Practice modes")
            elif len(parts) == 3 and parts[0] == "lesson":
                practice_target = workspace_destination(settings, "practice_flow")
                reply = handle_lesson_callback(
                    session,
                    user,
                    parts[1],
                    parts[2],
                    channel_id=(
                        str(practice_target.chat_id)
                        if practice_target.chat_id is not None
                        else None
                    ),
                    message_thread_id=practice_target.message_thread_id,
                )
                await answer_callback(event, "Lesson")
            elif raw_data == "materials:start":
                StateStore(session).set(
                    telegram_user_id,
                    telegram_user_id,
                    "upload",
                    {"type": "other"},
                )
                upload_reply = handle_upload_start()
                reply = BotReply(
                    upload_reply.text,
                    telegram_user_id,
                    upload_reply.buttons,
                )
                await answer_callback(event, "Open the bot DM to paste material")
            elif len(parts) == 3 and parts[0] == "settings":
                field, value = parts[1], parts[2]
                if field == "refresh":
                    reply = handle_settings(session, user)
                else:
                    reply = handle_setting_update(session, user, field, value)
                await answer_callback(event, "Settings updated")
            elif len(parts) == 3 and parts[0] == "approve" and parts[1] in {
                "all",
                "skip",
            }:
                try:
                    material_id = int(parts[2])
                except ValueError:
                    reply = BotReply("Use /approve <material_id>.")
                else:
                    if parts[1] == "all":
                        reply = handle_approve_all(
                            session, user, material_id, provider
                        )
                    else:
                        reply = handle_skip_all(session, user, material_id)
                reply = _material_upload_reply(reply, event, settings)
                await answer_callback(event, "Approval updated")
            elif raw_data == "upload:confirm:pending":
                state_store = StateStore(session)
                state = state_store.get(event.chat_id, telegram_user_id)
                if (
                    state is None
                    or state.name != "confirm_upload"
                    or not state.payload.get("raw_text")
                ):
                    reply = BotReply("Nothing pending. Send /upload first.")
                else:
                    reply = handle_upload(
                        session, user, provider, str(state.payload["raw_text"])
                    )
                    state_store.clear(event.chat_id, telegram_user_id)
                reply = _material_upload_reply(reply, event, settings)
                await answer_callback(event, "Material upload")
            elif raw_data == "upload:cancel:pending":
                StateStore(session).clear(event.chat_id, telegram_user_id)
                reply = BotReply("Cancelled.")
                await answer_callback(event, "Cancelled")
            elif raw_data.startswith("upload_type:"):
                upload_type = raw_data.removeprefix("upload_type:")
                StateStore(session).set(
                    event.chat_id,
                    telegram_user_id,
                    "upload",
                    {"type": upload_type},
                )
                reply = handle_upload_type_choice(upload_type)
                reply = _material_upload_reply(reply, event, settings)
                await answer_callback(event, "Upload type")
            elif len(parts) == 3 and parts[0] == "candidates":
                try:
                    material_id = int(parts[2])
                except ValueError:
                    reply = BotReply("Use /candidates <material_id>.")
                else:
                    reply = handle_candidates(session, user, material_id)
                reply = _material_upload_reply(reply, event, settings)
                await answer_callback(event, "Candidate list")
            elif len(parts) == 3 and parts[0] == "candidate":
                try:
                    candidate_id = int(parts[2])
                except ValueError:
                    reply = BotReply(CANDIDATE_USAGE)
                else:
                    if parts[1] == "edit":
                        reply = handle_candidate_edit_menu(
                            session, user, candidate_id
                        )
                    else:
                        reply = handle_candidate_action(
                            session, user, parts[1], candidate_id, provider
                        )
                reply = _material_upload_reply(reply, event, settings)
                await answer_callback(event, "Candidate handled")
            elif raw_data.startswith("candidate_field:"):
                field_parts = raw_data.split(":", 2)
                try:
                    candidate_id = int(field_parts[1])
                except (IndexError, ValueError):
                    reply = BotReply("Candidate not found.")
                else:
                    field = field_parts[2] if len(field_parts) == 3 else ""
                    reply = handle_candidate_edit_prompt(candidate_id, field)
                    if field in {"text", "meaning", "tags"}:
                        StateStore(session).set(
                            telegram_user_id,
                            telegram_user_id,
                            "edit_candidate",
                            {"candidate_id": candidate_id, "field": field},
                        )
                reply = _material_upload_reply(reply, event, settings)
                await answer_callback(event, "Candidate edit")
            elif len(parts) == 3 and parts[0] == "favorite" and parts[1] == "toggle":
                try:
                    item_id = int(parts[2])
                except ValueError:
                    reply = BotReply("Use /favorite <item_id>.")
                else:
                    reply = handle_favorite_toggle(session, user, item_id)
                await answer_callback(event, "Favorite updated")
            elif len(parts) == 3 and parts[0] == "item":
                try:
                    item_id = int(parts[2])
                except ValueError:
                    reply = BotReply(ITEM_STATUS_USAGE)
                else:
                    reply = handle_item_status(session, user, item_id, parts[1])
                await answer_callback(event, "Item updated")
            elif len(parts) == 3 and parts[0] == "mistake":
                try:
                    pattern_id = int(parts[2])
                except ValueError:
                    reply = BotReply(
                        "Use /mistakes focus <id> or /mistakes ignore <id>."
                    )
                else:
                    reply = handle_mistake_action(
                        session, user, parts[1], pattern_id
                    )
                await answer_callback(event, "Mistake pattern updated")
            elif len(parts) == 3 and parts[0] == "dispute":
                try:
                    attempt_id = int(parts[1])
                except ValueError:
                    reply = BotReply("Use /dispute <attempt_id> <reason>.")
                else:
                    reply = handle_dispute(session, user, attempt_id, parts[2])
                await answer_callback(event, "Dispute logged")
            elif len(parts) == 3 and parts[0] == "attempt" and parts[1] == "ack":
                try:
                    attempt_id = int(parts[2])
                except ValueError:
                    reply = BotReply("Attempt not found.")
                else:
                    reply = handle_attempt_ack(session, user, attempt_id)
                await answer_callback(event, "Got it")
            elif len(parts) == 3 and parts[0] == "attempt" and parts[1] == "hard":
                try:
                    attempt_id = int(parts[2])
                except ValueError:
                    reply = BotReply("Attempt not found.")
                else:
                    reply = handle_attempt_hard(session, user, attempt_id)
                await answer_callback(event, "Marked Hard")
            elif len(parts) == 3 and parts[0] == "feedback" and parts[1] == "explain":
                try:
                    attempt_id = int(parts[2])
                except ValueError:
                    reply = BotReply("Attempt not found.")
                else:
                    reply = handle_feedback_explain(session, user, attempt_id)
                await answer_callback(event, "Teacher details")
            elif raw_data == "practice:skip":
                next_target = workspace_destination(settings, "next_prompt")
                summary_target = workspace_destination(settings, "summary")
                practice_target = workspace_destination(settings, "practice_flow")
                reply = handle_skip_current(
                    session,
                    user,
                    channel_id=(
                        str(practice_target.chat_id)
                        if practice_target.chat_id is not None
                        else None
                    ),
                    message_thread_id=practice_target.message_thread_id,
                    next_channel_id=(
                        str(next_target.chat_id)
                        if next_target.message_thread_id is not None
                        else None
                    ),
                    next_message_thread_id=next_target.message_thread_id,
                    summary_channel_id=(
                        str(summary_target.chat_id)
                        if summary_target.message_thread_id is not None
                        else None
                    ),
                    summary_message_thread_id=summary_target.message_thread_id,
                )
                await answer_callback(event, "Skipped")
            else:
                reply = BotReply("Unknown button action. Send /help.")
                await answer_callback(event, "Unknown action")
            await send_reply(client, event.chat_id, reply, settings)

    @client.on(events.NewMessage)
    async def on_free_text(event) -> None:  # type: ignore[no-untyped-def]
        if str(event.raw_text).startswith("/"):
            return
        if await maybe_record_channel(event, settings):
            return
        sender = await event.get_sender()
        if getattr(sender, "bot", False):
            return
        sender_id = int(sender.id)
        telegram_user_id = _effective_user_id(sender_id, event.chat_id, settings)
        with session_scope(session_factory) as session:
            if (
                settings.telegram_allowed_user_id is not None
                and settings.telegram_allowed_user_id != telegram_user_id
            ):
                await _reject_or_ignore(event, settings)
                return
            user: User = ensure_user(session, telegram_user_id, settings)
            state_store = StateStore(session)
            state = state_store.get(event.chat_id, telegram_user_id)
            if state is not None and state.name == "upload":
                try:
                    material_text = await _material_text_from_event(event)
                except ValueError as exc:
                    reply = BotReply(f"Could not read material: {exc}")
                else:
                    if not material_text:
                        reply = BotReply(
                            "Send material as pasted text or a UTF-8 .md/.txt file."
                        )
                    else:
                        reply = handle_upload(
                            session,
                            user,
                            provider,
                            material_text,
                            type_=str(state.payload.get("type", "other")),
                        )
                state_store.clear(event.chat_id, telegram_user_id)
                reply = _material_upload_reply(reply, event, settings)
            elif state is not None and state.name == "add":
                reply = handle_add_text(session, user, event.raw_text)
                state_store.clear(event.chat_id, telegram_user_id)
            elif state is not None and state.name == "edit_candidate":
                reply = handle_candidate_edit_value(
                    session,
                    user,
                    int(state.payload["candidate_id"]),
                    str(state.payload["field"]),
                    event.raw_text,
                )
                state_store.clear(event.chat_id, telegram_user_id)
                reply = _material_upload_reply(reply, event, settings)
            else:
                feedback_target = workspace_destination(settings, "feedback")
                next_target = workspace_destination(settings, "next_prompt")
                summary_target = workspace_destination(settings, "summary")
                practice_target = workspace_destination(settings, "practice_flow")
                reply = handle_answer(
                    session,
                    user,
                    provider,
                    event.raw_text,
                    channel_id=(
                        str(practice_target.chat_id)
                        if practice_target.chat_id is not None
                        else None
                    ),
                    message_thread_id=practice_target.message_thread_id,
                    next_channel_id=(
                        str(next_target.chat_id)
                        if next_target.message_thread_id is not None
                        else None
                    ),
                    next_message_thread_id=next_target.message_thread_id,
                    feedback_copy_channel_id=(
                        str(feedback_target.chat_id)
                        if feedback_target.message_thread_id is not None
                        else None
                    ),
                    feedback_copy_message_thread_id=feedback_target.message_thread_id,
                    summary_channel_id=(
                        str(summary_target.chat_id)
                        if summary_target.message_thread_id is not None
                        else None
                    ),
                    summary_message_thread_id=summary_target.message_thread_id,
                    progress_channel_id=(
                        str(practice_target.chat_id)
                        if practice_target.message_thread_id is not None
                        else None
                    ),
                    progress_message_thread_id=practice_target.message_thread_id,
                )
                if reply.text.startswith("No active exercise."):
                    state_store.set(
                        event.chat_id,
                        telegram_user_id,
                        "confirm_upload",
                        {"raw_text": event.raw_text},
                    )
                    reply = handle_upload_prompt()
            await send_reply(client, event.chat_id, reply, settings)

    await client.start(bot_token=settings.telegram_bot_token)
    me = await client.get_me()
    LOG.info("Telethon bot connected as @%s", getattr(me, "username", "<unknown>"))
    scheduler = build_scheduler(settings, session_factory, client=client)
    scheduler.start()
    try:
        await client.run_until_disconnected()
    finally:
        scheduler.shutdown(wait=False)
