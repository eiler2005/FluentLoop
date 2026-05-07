from __future__ import annotations

import json
from pathlib import Path
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


def record_channel_discovery(
    path: Path,
    *,
    title: str,
    channel_id: int,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {"title": title, "channel_id": channel_id},
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def read_recorded_channel(path: Path, title: str) -> int | None:
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if data.get("title") != title:
        return None
    channel_id = data.get("channel_id")
    return int(channel_id) if channel_id is not None else None
