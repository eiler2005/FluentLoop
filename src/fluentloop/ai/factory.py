from __future__ import annotations

from fluentloop.ai.provider import AIProvider, OpenAIProvider, StubProvider
from fluentloop.config import Settings, get_settings


def make_provider(settings: Settings | None = None) -> AIProvider:
    cfg = settings or get_settings()
    if cfg.ai_provider == "stub":
        return StubProvider()
    if cfg.ai_provider == "openai":
        return OpenAIProvider(
            api_key=cfg.openai_api_key,
            light_model=cfg.openai_model_light,
            heavy_model=cfg.openai_model_heavy,
        )
    raise ValueError(f"unknown AI_PROVIDER: {cfg.ai_provider}")
