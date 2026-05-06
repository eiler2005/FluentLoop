from __future__ import annotations

import logging

from sqlalchemy.orm import sessionmaker

from fluentloop.ai.factory import make_provider
from fluentloop.bot.handlers import (
    handle_answer,
    handle_help,
    handle_mistakes,
    handle_rules,
    handle_settings,
    handle_start,
    handle_stats,
    handle_today,
)
from fluentloop.config import Settings
from fluentloop.db.models import User
from fluentloop.db.session import session_scope
from fluentloop.users import ensure_user

LOG = logging.getLogger(__name__)


async def run_bot(settings: Settings, session_factory: sessionmaker) -> None:
    from telethon import TelegramClient, events

    provider = make_provider(settings)
    client = TelegramClient(
        "data/sessions/fluentloop-bot",
        settings.telegram_api_id,
        settings.telegram_api_hash,
    )

    @client.on(
        events.NewMessage(
            pattern=r"^/(start|help|today|review|settings|stats|mistakes|rules)$"
        )
    )
    async def on_command(event) -> None:  # type: ignore[no-untyped-def]
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
            text = event.raw_text.split()[0]
            if text == "/start":
                reply = handle_start(session, settings, telegram_user_id)
            elif text == "/help":
                reply = handle_help()
            elif text in {"/today", "/review"}:
                reply = handle_today(
                    session, user, channel_id=settings.telegram_channel_id
                )
            elif text == "/settings":
                reply = handle_settings(session, user)
            elif text == "/stats":
                reply = handle_stats(session, user)
            elif text == "/mistakes":
                reply = handle_mistakes(session, user)
            else:
                reply = handle_rules(session)
            await client.send_message(reply.target_chat_id or event.chat_id, reply.text)

    @client.on(events.NewMessage)
    async def on_free_text(event) -> None:  # type: ignore[no-untyped-def]
        if str(event.raw_text).startswith("/"):
            return
        sender = await event.get_sender()
        telegram_user_id = int(sender.id)
        with session_scope(session_factory) as session:
            user: User = ensure_user(session, telegram_user_id, settings)
            reply = handle_answer(session, user, provider, event.raw_text)
            await event.reply(reply.text)

    await client.start(bot_token=settings.telegram_bot_token)
    me = await client.get_me()
    LOG.info("Telethon bot connected as @%s", getattr(me, "username", "<unknown>"))
    await client.run_until_disconnected()
