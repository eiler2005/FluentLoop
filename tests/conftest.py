from __future__ import annotations

from collections.abc import Iterator

import pytest
from sqlalchemy.orm import Session

from fluentloop.config import Settings
from fluentloop.db.session import make_engine, make_session_factory


@pytest.fixture
def settings() -> Settings:
    return Settings(
        telegram_api_id=1,
        telegram_api_hash="hash",
        telegram_bot_token="token",
        telegram_allowed_user_id=123456789,
        telegram_channel_id=None,
        db_url="sqlite:///:memory:",
        timezone="Europe/Moscow",
        reminder_time_default="20:00",
        practice_duration_minutes=15,
        ai_provider="stub",
        openai_api_key="STUB_OVERNIGHT_BUILD",
        openai_model_light="gpt-4o-mini",
        openai_model_heavy="gpt-4o",
        log_level="INFO",
        pre_gen_hour=3,
        pre_gen_minute=0,
        backup_hour=4,
        backup_minute=0,
        backup_retention_days=14,
        telegram_channel_title="FluentLoop English",
    )


@pytest.fixture
def db_session() -> Iterator[Session]:
    engine = make_engine("sqlite:///:memory:")
    factory = make_session_factory(engine)
    with factory() as session:
        yield session
