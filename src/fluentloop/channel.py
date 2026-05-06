from __future__ import annotations

from typing import Any


def find_channel_from_updates(updates: list[dict[str, Any]], title: str) -> int | None:
    for update in updates:
        for key in ("channel_post", "edited_channel_post", "message", "edited_message"):
            obj = update.get(key) or {}
            chat = obj.get("chat") or {}
            if chat.get("type") == "channel" and chat.get("title") == title:
                return int(chat["id"])
        member = update.get("my_chat_member") or {}
        chat = member.get("chat") or {}
        if chat.get("type") == "channel" and chat.get("title") == title:
            return int(chat["id"])
    return None


def channel_or_private(
    settings_channel_id: str | None, private_chat_id: int
) -> int | str:
    return settings_channel_id or private_chat_id
