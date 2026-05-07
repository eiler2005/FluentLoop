from __future__ import annotations

from dataclasses import dataclass

from fluentloop.config import Settings


@dataclass(frozen=True)
class TelegramDestination:
    chat_id: int | str | None
    message_thread_id: int | None = None


TOPIC_NAMES: dict[str, str] = {
    "help": "Help",
    "practice_flow": "Practice Flow",
    "materials_upload": "Materials Upload",
    "feedback": "Feedback",
    "next_prompt": "Next Prompts",
    "summary": "Summaries",
    "mistakes": "Mistakes",
    "stats": "Stats",
}

TOPIC_ENV_VARS: dict[str, str] = {
    "help": "TELEGRAM_TOPIC_HELP_ID",
    "practice_flow": "TELEGRAM_TOPIC_PRACTICE_FLOW_ID",
    "materials_upload": "TELEGRAM_TOPIC_MATERIALS_UPLOAD_ID",
    "feedback": "TELEGRAM_TOPIC_FEEDBACK_ID",
    "next_prompt": "TELEGRAM_TOPIC_NEXT_PROMPT_ID",
    "summary": "TELEGRAM_TOPIC_SUMMARY_ID",
    "mistakes": "TELEGRAM_TOPIC_MISTAKES_ID",
    "stats": "TELEGRAM_TOPIC_STATS_ID",
}


def workspace_enabled(settings: Settings) -> bool:
    return bool(settings.telegram_forum_group_id or settings.telegram_channel_id)


def _topic_id(settings: Settings, topic: str) -> int | None:
    return {
        "help": settings.telegram_topic_help_id,
        "practice_flow": settings.telegram_topic_practice_flow_id,
        "materials_upload": settings.telegram_topic_materials_upload_id,
        "feedback": settings.telegram_topic_feedback_id,
        "next_prompt": settings.telegram_topic_next_prompt_id,
        "summary": settings.telegram_topic_summary_id,
        "mistakes": settings.telegram_topic_mistakes_id,
        "stats": settings.telegram_topic_stats_id,
    }.get(topic)


def workspace_destination(settings: Settings, topic: str) -> TelegramDestination:
    if settings.telegram_forum_group_id:
        return TelegramDestination(
            settings.telegram_forum_group_id,
            _topic_id(settings, topic),
        )
    return TelegramDestination(settings.telegram_channel_id)
