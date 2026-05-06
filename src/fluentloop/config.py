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
    db_url: str
    timezone: str
    reminder_time_default: str
    practice_duration_minutes: int
    ai_provider: str
    openai_api_key: str
    openai_model_light: str
    openai_model_heavy: str
    log_level: str
    pre_gen_hour: int
    pre_gen_minute: int
    backup_hour: int
    backup_minute: int
    backup_retention_days: int


def get_settings() -> Settings:
    load_env()
    allowed_raw = os.environ.get("TELEGRAM_ALLOWED_USER_ID", "").strip()
    channel_id = os.environ.get("TELEGRAM_CHANNEL_ID", "").strip() or None
    db_url = os.environ.get("DB_URL", "sqlite:///data/fluentloop.sqlite")
    if db_url.startswith("sqlite:////app/") and not Path("/app").exists():
        db_url = db_url.replace("sqlite:////app/", "sqlite:///")
    return Settings(
        telegram_api_id=int(os.environ.get("TELEGRAM_API_ID", "0")),
        telegram_api_hash=os.environ.get("TELEGRAM_API_HASH", ""),
        telegram_bot_token=os.environ.get("TELEGRAM_BOT_TOKEN", ""),
        telegram_allowed_user_id=int(allowed_raw) if allowed_raw else None,
        telegram_channel_id=channel_id,
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
        log_level=os.environ.get("LOG_LEVEL", "INFO"),
        pre_gen_hour=int(os.environ.get("PRE_GEN_HOUR", "3")),
        pre_gen_minute=int(os.environ.get("PRE_GEN_MINUTE", "0")),
        backup_hour=int(os.environ.get("BACKUP_HOUR", "4")),
        backup_minute=int(os.environ.get("BACKUP_MINUTE", "0")),
        backup_retention_days=int(os.environ.get("BACKUP_RETENTION_DAYS", "14")),
    )
