from __future__ import annotations

from fluentloop.ai.provider import (
    AIProvider,
    DeepSeekProvider,
    OpenAIProvider,
    QwenProvider,
    StubProvider,
)
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
    if cfg.ai_provider == "deepseek":
        return DeepSeekProvider(
            api_key=cfg.deepseek_api_key,
            base_url=cfg.deepseek_base_url,
            model=cfg.deepseek_chat_model,
            fast_model=cfg.deepseek_fast_model,
            planner_model=cfg.deepseek_planner_model,
            extractor_model=cfg.deepseek_extractor_model,
            planner_reasoning_effort=cfg.deepseek_planner_reasoning_effort,
            timeout_seconds=cfg.deepseek_timeout_seconds,
            max_retries=cfg.deepseek_max_retries,
        )
    if cfg.ai_provider == "qwen":
        return QwenProvider(
            api_key=cfg.qwen_api_key,
            base_url=cfg.qwen_base_url,
            model=cfg.qwen_chat_model,
            fast_model=cfg.qwen_fast_model,
            planner_model=cfg.qwen_planner_model,
            extractor_model=cfg.qwen_extractor_model,
            timeout_seconds=cfg.qwen_timeout_seconds,
            max_retries=cfg.qwen_max_retries,
        )
    raise ValueError(f"unknown AI_PROVIDER: {cfg.ai_provider}")
