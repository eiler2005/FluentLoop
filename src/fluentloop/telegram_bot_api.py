from __future__ import annotations

import asyncio
import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

from fluentloop.bot.handlers import BotReply


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
    if reply.message_thread_id is not None:
        payload["message_thread_id"] = reply.message_thread_id
    markup = inline_keyboard(reply)
    if markup is not None:
        payload["reply_markup"] = markup
    parsed = await asyncio.to_thread(call_bot_api, token, "sendMessage", payload)
    message_id = int(parsed["result"]["message_id"])
    return SentBotApiMessage(message_id=message_id, raw=parsed)


async def pin_bot_api_message(token: str, chat_id: int | str, message_id: int) -> None:
    await asyncio.to_thread(
        call_bot_api,
        token,
        "pinChatMessage",
        {"chat_id": chat_id, "message_id": message_id, "disable_notification": True},
    )
