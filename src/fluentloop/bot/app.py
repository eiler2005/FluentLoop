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
    handle_candidate_action,
    handle_candidates,
    handle_dispute,
    handle_favorite_toggle,
    handle_favorites,
    handle_help,
    handle_item_status,
    handle_items,
    handle_mistake_action,
    handle_mistakes,
    handle_rules,
    handle_setting_update,
    handle_settings,
    handle_start,
    handle_stats,
    handle_today,
    handle_upload,
)
from fluentloop.bot.state import StateStore
from fluentloop.channel import record_channel_discovery
from fluentloop.config import Settings
from fluentloop.db.models import User
from fluentloop.db.session import session_scope
from fluentloop.scheduler import build_scheduler
from fluentloop.users import ensure_user

LOG = logging.getLogger(__name__)
ITEM_STATUS_USAGE = (
    "Use /item archive <id>, /item suspend <id>, or /item restore <id>."
)
CANDIDATE_USAGE = "Use /candidate add <id> or /candidate skip <id>."
CHANNEL_DISCOVERY_PATH = Path("data/channel_discovery.json")


async def maybe_record_channel(event, settings: Settings) -> bool:  # type: ignore[no-untyped-def]
    chat = await event.get_chat()
    title = getattr(chat, "title", None)
    if title != settings.telegram_channel_title:
        return False
    chat_id = event.chat_id
    if chat_id is None:
        return False
    record_channel_discovery(
        CHANNEL_DISCOVERY_PATH,
        title=title,
        channel_id=int(chat_id),
    )
    LOG.info("Discovered Telegram channel %r from incoming channel event", title)
    return True


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
        telegram_user_id = int(sender.id)
        with session_scope(session_factory) as session:
            if (
                settings.telegram_allowed_user_id is not None
                and settings.telegram_allowed_user_id != telegram_user_id
            ):
                await event.reply("This is a personal FluentLoop bot.")
                return
            user = ensure_user(session, telegram_user_id, settings)
            parts = event.raw_text.split(maxsplit=2)
            command = parts[0]
            if command == "/start":
                reply = handle_start(session, settings, telegram_user_id)
            elif command == "/help":
                reply = handle_help()
            elif command in {"/today", "/review"}:
                reply = handle_today(
                    session, user, channel_id=settings.telegram_channel_id
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
                StateStore(session).set(event.chat_id, telegram_user_id, "upload", {})
                reply = BotReply("Paste the lesson material in the next message.")
            elif command == "/approve":
                if len(parts) < 2:
                    reply = BotReply("Use /approve <material_id>.")
                else:
                    try:
                        material_id = int(parts[1])
                    except ValueError:
                        reply = BotReply("Use /approve <material_id>.")
                    else:
                        reply = handle_approve_all(session, user, material_id)
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
                            session, user, parts[1], candidate_id
                        )
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
            elif command == "/mistakes":
                if len(parts) >= 3 and parts[1] in {"focus", "ignore"}:
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
            await client.send_message(reply.target_chat_id or event.chat_id, reply.text)

    @client.on(events.CallbackQuery(data=b"start_today"))
    async def on_start_today(event) -> None:  # type: ignore[no-untyped-def]
        sender = await event.get_sender()
        telegram_user_id = int(sender.id)
        with session_scope(session_factory) as session:
            if (
                settings.telegram_allowed_user_id is not None
                and settings.telegram_allowed_user_id != telegram_user_id
            ):
                await event.answer("This is a personal FluentLoop bot.")
                return
            user = ensure_user(session, telegram_user_id, settings)
            reply = handle_today(
                session, user, channel_id=settings.telegram_channel_id
            )
            await event.answer("Starting practice")
            await client.send_message(reply.target_chat_id or event.chat_id, reply.text)

    @client.on(events.NewMessage)
    async def on_free_text(event) -> None:  # type: ignore[no-untyped-def]
        if str(event.raw_text).startswith("/"):
            return
        if await maybe_record_channel(event, settings):
            return
        sender = await event.get_sender()
        telegram_user_id = int(sender.id)
        with session_scope(session_factory) as session:
            if (
                settings.telegram_allowed_user_id is not None
                and settings.telegram_allowed_user_id != telegram_user_id
            ):
                await event.reply("This is a personal FluentLoop bot.")
                return
            user: User = ensure_user(session, telegram_user_id, settings)
            state_store = StateStore(session)
            state = state_store.get(event.chat_id, telegram_user_id)
            if state is not None and state.name == "upload":
                reply = handle_upload(session, user, provider, event.raw_text)
                state_store.clear(event.chat_id, telegram_user_id)
            elif state is not None and state.name == "add":
                reply = handle_add_text(session, user, event.raw_text)
                state_store.clear(event.chat_id, telegram_user_id)
            else:
                reply = handle_answer(
                    session,
                    user,
                    provider,
                    event.raw_text,
                    channel_id=settings.telegram_channel_id,
                )
            await client.send_message(reply.target_chat_id or event.chat_id, reply.text)

    await client.start(bot_token=settings.telegram_bot_token)
    me = await client.get_me()
    LOG.info("Telethon bot connected as @%s", getattr(me, "username", "<unknown>"))
    scheduler = build_scheduler(settings, session_factory, client=client)
    scheduler.start()
    try:
        await client.run_until_disconnected()
    finally:
        scheduler.shutdown(wait=False)
