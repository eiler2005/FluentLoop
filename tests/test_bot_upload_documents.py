from __future__ import annotations

from dataclasses import replace

import pytest

from fluentloop.bot.app import _material_text_from_event, _material_upload_reply
from fluentloop.bot.handlers import BotReply


class _FakeFile:
    def __init__(self, size: int) -> None:
        self.size = size


class _FakeMessage:
    def __init__(self, size: int) -> None:
        self.file = _FakeFile(size)


class _FakeEvent:
    def __init__(self, raw_text: str, payload: bytes, chat_id: str = "-1001") -> None:
        self.raw_text = raw_text
        self._payload = payload
        self.chat_id = chat_id
        self.message = _FakeMessage(len(payload))

    async def download_media(self, *, file: type[bytes]) -> bytes:
        assert file is bytes
        return self._payload


@pytest.mark.asyncio
async def test_material_text_from_markdown_attachment_ignores_upload_caption() -> None:
    event = _FakeEvent("/upload", b"# Lesson\n\nalign on priorities")

    text = await _material_text_from_event(event)

    assert text == "# Lesson\n\nalign on priorities"


@pytest.mark.asyncio
async def test_material_text_from_attachment_keeps_non_command_caption() -> None:
    event = _FakeEvent("Teacher notes", b"push back on the risky release")

    text = await _material_text_from_event(event)

    assert text == "Teacher notes\n\npush back on the risky release"


@pytest.mark.asyncio
async def test_material_text_from_attachment_rejects_binary_payload() -> None:
    event = _FakeEvent("/upload", b"\xff\xfe\x00")

    with pytest.raises(ValueError, match="UTF-8"):
        await _material_text_from_event(event)


def test_material_upload_reply_routes_forum_upload_to_materials_topic(settings) -> None:
    forum_settings = replace(
        settings,
        telegram_forum_group_id="-1001",
        telegram_topic_materials_upload_id=39,
    )
    event = _FakeEvent("", b"", chat_id="-1001")

    reply = _material_upload_reply(BotReply("Upload"), event, forum_settings)

    assert reply.target_chat_id == "-1001"
    assert reply.message_thread_id == 39

