from __future__ import annotations

import asyncio
import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

from fluentloop.bot.handlers import BotReply

BOT_COMMANDS: tuple[tuple[str, str], ...] = (
    ("start", "Create or load your FluentLoop profile"),
    ("today", "Start today's 15-minute practice"),
    ("review", "Review due items"),
    ("practice", "Start focused and EPIC-22 breakthrough practice modes"),
    ("baseline", "Show or record monthly learning baseline"),
    ("outcomes", "Show 30-day learning outcome metrics"),
    ("library", "Browse shared seed lessons"),
    ("subscribe", "Copy a shared lesson into your lesson base"),
    ("topics", "Browse lesson topics and knowledge areas"),
    ("lessons", "List active lessons, optionally filtered"),
    ("lesson", "Show or start a lesson by id, random, or topic"),
    ("skip", "Skip the current prompt and show the answer"),
    ("feedback", "Show detailed teacher feedback for an attempt"),
    ("reflect", "Save a reflective practice note"),
    ("scene", "Build a business roleplay scene"),
    ("brief", "Prepare just-in-time meeting language"),
    ("mentor", "Weekly Socratic English prompt"),
    ("article", "Start text-first Article Lab"),
    ("debate", "Start Debate Mode"),
    ("translate_lab", "Practice RU-to-EN transfer"),
    ("fluency432", "Practice 4-3-2 fluency"),
    ("upload", "Upload lesson material"),
    ("approve", "Approve pending extracted candidates"),
    ("mistakes", "Show recurring mistake patterns"),
    ("rules", "Show grammar concepts"),
    ("stats", "Show progress stats"),
    ("help", "Show the FluentLoop guide"),
    ("howto", "Show how to use FluentLoop"),
)


class TelegramBotApiError(RuntimeError):
    pass


@dataclass(frozen=True)
class SentBotApiMessage:
    message_id: int
    raw: dict[str, Any]


def inline_keyboard(reply: BotReply) -> dict[str, Any] | None:
    if not reply.buttons:
        return None
    return {
        "inline_keyboard": [
            [{"text": button.text, "callback_data": button.data} for button in row]
            for row in reply.buttons
        ]
    }


def bot_commands_payload() -> list[dict[str, str]]:
    return [
        {"command": command, "description": description}
        for command, description in BOT_COMMANDS
    ]


def call_bot_api(token: str, method: str, payload: dict[str, Any]) -> dict[str, Any]:
    url = f"https://api.telegram.org/bot{token}/{method}"
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            parsed = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="ignore")
        raise TelegramBotApiError(f"HTTP {exc.code}: {body}") from exc
    if not parsed.get("ok"):
        raise TelegramBotApiError(str(parsed))
    return parsed


async def send_bot_api_reply(token: str, reply: BotReply) -> SentBotApiMessage:
    if reply.target_chat_id is None:
        raise TelegramBotApiError("Bot API replies need target_chat_id")
    payload: dict[str, Any] = {
        "chat_id": reply.target_chat_id,
        "text": reply.text,
    }
    if reply.parse_mode:
        payload["parse_mode"] = (
            "HTML" if reply.parse_mode.lower() == "html" else reply.parse_mode
        )
    if reply.message_thread_id is not None:
        payload["message_thread_id"] = reply.message_thread_id
    markup = inline_keyboard(reply)
    if markup is not None:
        payload["reply_markup"] = markup
    parsed = await asyncio.to_thread(call_bot_api, token, "sendMessage", payload)
    message_id = int(parsed["result"]["message_id"])
    return SentBotApiMessage(message_id=message_id, raw=parsed)


def set_bot_commands(token: str) -> dict[str, Any]:
    return call_bot_api(token, "setMyCommands", {"commands": bot_commands_payload()})


def delete_bot_api_message(token: str, chat_id: int | str, message_id: int) -> None:
    call_bot_api(token, "deleteMessage", {"chat_id": chat_id, "message_id": message_id})


def unpin_all_forum_topic_messages(
    token: str, chat_id: int | str, message_thread_id: int
) -> None:
    call_bot_api(
        token,
        "unpinAllForumTopicMessages",
        {"chat_id": chat_id, "message_thread_id": message_thread_id},
    )


async def pin_bot_api_message(token: str, chat_id: int | str, message_id: int) -> None:
    await asyncio.to_thread(
        call_bot_api,
        token,
        "pinChatMessage",
        {"chat_id": chat_id, "message_id": message_id, "disable_notification": True},
    )
