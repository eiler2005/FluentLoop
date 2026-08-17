from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def load_env(path: Path | None = None) -> None:
    env_path = path or Path(".env")
    if not env_path.exists():
        return
    for raw in env_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip())


@dataclass(frozen=True)
class Settings:
    telegram_api_id: int
    telegram_api_hash: str
    telegram_bot_token: str
    telegram_allowed_user_id: int | None
    telegram_channel_id: str | None
    telegram_forum_group_id: str | None
    db_url: str
    timezone: str
    reminder_time_default: str
    practice_duration_minutes: int
    ai_provider: str
    openai_api_key: str
    openai_model_light: str
    openai_model_heavy: str
    deepseek_api_key: str
    deepseek_base_url: str
    deepseek_chat_model: str
    deepseek_fast_model: str
    deepseek_planner_model: str
    deepseek_extractor_model: str
    deepseek_planner_reasoning_effort: str
    deepseek_timeout_seconds: float
    deepseek_max_retries: int
    log_level: str
    pre_gen_hour: int
    pre_gen_minute: int
    backup_hour: int
    backup_minute: int
    backup_retention_days: int
    telegram_channel_title: str
    telegram_forum_title: str
    telegram_topic_help_id: int | None
    telegram_topic_practice_flow_id: int | None
    telegram_topic_materials_upload_id: int | None
    telegram_topic_feedback_id: int | None
    telegram_topic_next_prompt_id: int | None
    telegram_topic_summary_id: int | None
    telegram_topic_mistakes_id: int | None
    telegram_topic_stats_id: int | None
    # Fields below carry defaults so existing Settings(...) call sites keep
    # working. Any new field must also have one, and must be added at the end.
    vocab_quiz_polls: bool = True
    qwen_api_key: str = ""
    qwen_base_url: str = "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"
    qwen_chat_model: str = "qwen3.7-flash"
    qwen_fast_model: str = "qwen3.7-flash"
    qwen_planner_model: str = "qwen3.7-flash"
    qwen_extractor_model: str = "qwen3.7-flash"
    qwen_timeout_seconds: float = 30.0
    qwen_max_retries: int = 2


def _optional_int(name: str) -> int | None:
    raw = os.environ.get(name, "").strip()
    return int(raw) if raw else None


def get_settings() -> Settings:
    load_env()
    allowed_raw = os.environ.get("TELEGRAM_ALLOWED_USER_ID", "").strip()
    channel_id = os.environ.get("TELEGRAM_CHANNEL_ID", "").strip() or None
    forum_group_id = os.environ.get("TELEGRAM_FORUM_GROUP_ID", "").strip() or None
    db_url = os.environ.get("DB_URL", "sqlite:///data/fluentloop.sqlite")
    if db_url.startswith("sqlite:////app/") and not Path("/app").exists():
        db_url = db_url.replace("sqlite:////app/", "sqlite:///")
    return Settings(
        telegram_api_id=int(os.environ.get("TELEGRAM_API_ID", "0")),
        telegram_api_hash=os.environ.get("TELEGRAM_API_HASH", ""),
        telegram_bot_token=os.environ.get("TELEGRAM_BOT_TOKEN", ""),
        telegram_allowed_user_id=int(allowed_raw) if allowed_raw else None,
        telegram_channel_id=channel_id,
        telegram_forum_group_id=forum_group_id,
        db_url=db_url,
        timezone=os.environ.get("TIMEZONE", "Europe/Moscow"),
        reminder_time_default=os.environ.get("REMINDER_TIME_DEFAULT", "20:00"),
        practice_duration_minutes=int(
            os.environ.get("PRACTICE_DURATION_MINUTES", "15")
        ),
        ai_provider=os.environ.get("AI_PROVIDER", "stub").lower(),
        openai_api_key=os.environ.get("OPENAI_API_KEY", ""),
        openai_model_light=os.environ.get("OPENAI_MODEL_LIGHT", "gpt-4o-mini"),
        openai_model_heavy=os.environ.get("OPENAI_MODEL_HEAVY", "gpt-4o"),
        deepseek_api_key=os.environ.get("DEEPSEEK_API_KEY", ""),
        deepseek_base_url=os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
        deepseek_chat_model=os.environ.get(
            "DEEPSEEK_CHAT_MODEL", "deepseek-v4-flash"
        ),
        deepseek_fast_model=os.environ.get(
            "DEEPSEEK_FAST_MODEL",
            os.environ.get("DEEPSEEK_CHAT_MODEL", "deepseek-v4-flash"),
        ),
        deepseek_planner_model=os.environ.get(
            "DEEPSEEK_PLANNER_MODEL", "deepseek-v4-pro"
        ),
        deepseek_extractor_model=os.environ.get(
            "DEEPSEEK_EXTRACTOR_MODEL", "deepseek-v4-pro"
        ),
        deepseek_planner_reasoning_effort=os.environ.get(
            "DEEPSEEK_PLANNER_REASONING_EFFORT", "high"
        ),
        deepseek_timeout_seconds=float(
            os.environ.get("DEEPSEEK_TIMEOUT_SECONDS", "30")
        ),
        deepseek_max_retries=int(os.environ.get("DEEPSEEK_MAX_RETRIES", "2")),
        log_level=os.environ.get("LOG_LEVEL", "INFO"),
        pre_gen_hour=int(os.environ.get("PRE_GEN_HOUR", "3")),
        pre_gen_minute=int(os.environ.get("PRE_GEN_MINUTE", "0")),
        backup_hour=int(os.environ.get("BACKUP_HOUR", "4")),
        backup_minute=int(os.environ.get("BACKUP_MINUTE", "0")),
        backup_retention_days=int(os.environ.get("BACKUP_RETENTION_DAYS", "14")),
        telegram_channel_title=os.environ.get(
            "TELEGRAM_CHANNEL_TITLE", "FluentLoop English"
        ),
        telegram_forum_title=os.environ.get(
            "TELEGRAM_FORUM_TITLE", "FluentLoop English Forum"
        ),
        telegram_topic_help_id=_optional_int("TELEGRAM_TOPIC_HELP_ID"),
        telegram_topic_practice_flow_id=_optional_int(
            "TELEGRAM_TOPIC_PRACTICE_FLOW_ID"
        ),
        telegram_topic_materials_upload_id=_optional_int(
            "TELEGRAM_TOPIC_MATERIALS_UPLOAD_ID"
        ),
        telegram_topic_feedback_id=_optional_int("TELEGRAM_TOPIC_FEEDBACK_ID"),
        telegram_topic_next_prompt_id=_optional_int("TELEGRAM_TOPIC_NEXT_PROMPT_ID"),
        telegram_topic_summary_id=_optional_int("TELEGRAM_TOPIC_SUMMARY_ID"),
        telegram_topic_mistakes_id=_optional_int("TELEGRAM_TOPIC_MISTAKES_ID"),
        telegram_topic_stats_id=_optional_int("TELEGRAM_TOPIC_STATS_ID"),
        vocab_quiz_polls=os.environ.get("VOCAB_QUIZ_POLLS", "1").strip().lower()
        not in {"0", "false", "no", "off"},
        # DASHSCOPE_API_KEY is the name Alibaba's own SDK uses, so accept it as
        # a fallback: a pay-as-you-go key copied from another project works
        # unchanged. Never point this at a Token Plan key - that endpoint 404s
        # on the flash models (see docs/adr/0010).
        qwen_api_key=os.environ.get("QWEN_API_KEY", "")
        or os.environ.get("DASHSCOPE_API_KEY", ""),
        qwen_base_url=os.environ.get(
            "QWEN_BASE_URL", "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"
        ),
        qwen_chat_model=os.environ.get("QWEN_CHAT_MODEL", "qwen3.7-flash"),
        qwen_fast_model=os.environ.get(
            "QWEN_FAST_MODEL", os.environ.get("QWEN_CHAT_MODEL", "qwen3.7-flash")
        ),
        qwen_planner_model=os.environ.get("QWEN_PLANNER_MODEL", "qwen3.7-flash"),
        qwen_extractor_model=os.environ.get(
            "QWEN_EXTRACTOR_MODEL", "qwen3.7-flash"
        ),
        qwen_timeout_seconds=float(os.environ.get("QWEN_TIMEOUT_SECONDS", "30")),
        qwen_max_retries=int(os.environ.get("QWEN_MAX_RETRIES", "2")),
    )
