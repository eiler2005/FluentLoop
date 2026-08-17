from __future__ import annotations

from dataclasses import dataclass

from fluentloop.config import Settings, get_settings
from fluentloop.llm.gateway import DeepSeekGateway
from fluentloop.llm.tasks import LLMTask


@dataclass(frozen=True)
class LLMProfile:
    model: str
    thinking: bool = False
    reasoning_effort: str | None = None


@dataclass(frozen=True)
class ProviderConfig:
    """Which OpenAI-compatible endpoint and models to use (ADR-0010)."""

    name: str
    api_key: str
    base_url: str
    fast: str
    planner: str
    extractor: str
    reasoning_effort: str | None
    timeout_seconds: float
    max_retries: int


def provider_config(settings: Settings | None = None) -> ProviderConfig:
    cfg = settings or get_settings()
    if cfg.ai_provider == "qwen":
        fast = cfg.qwen_fast_model or cfg.qwen_chat_model
        planner = cfg.qwen_planner_model or cfg.qwen_chat_model
        return ProviderConfig(
            name="qwen",
            api_key=cfg.qwen_api_key,
            base_url=cfg.qwen_base_url,
            fast=fast,
            planner=planner,
            extractor=cfg.qwen_extractor_model or planner,
            # Qwen's compatible endpoint ignores reasoning_effort.
            reasoning_effort=None,
            timeout_seconds=cfg.qwen_timeout_seconds,
            max_retries=cfg.qwen_max_retries,
        )
    fast = cfg.deepseek_fast_model or cfg.deepseek_chat_model
    planner = cfg.deepseek_planner_model or cfg.deepseek_chat_model
    return ProviderConfig(
        name="deepseek",
        api_key=cfg.deepseek_api_key,
        base_url=cfg.deepseek_base_url,
        fast=fast,
        planner=planner,
        extractor=cfg.deepseek_extractor_model or planner,
        reasoning_effort=cfg.deepseek_planner_reasoning_effort,
        timeout_seconds=cfg.deepseek_timeout_seconds,
        max_retries=cfg.deepseek_max_retries,
    )


def task_profile(
    task: LLMTask,
    settings: Settings | None = None,
    *,
    material_type: str = "",
) -> LLMProfile:
    provider = provider_config(settings)
    if task == LLMTask.SEED_LESSON_PLAN:
        return LLMProfile(
            provider.planner,
            thinking=provider.reasoning_effort is not None,
            reasoning_effort=provider.reasoning_effort,
        )
    if task == LLMTask.MATERIAL_EXTRACTION:
        simple_material = material_type in {"word_list", "expression_list"}
        return LLMProfile(provider.fast if simple_material else provider.extractor)
    return LLMProfile(provider.fast)


def llm_gateway(settings: Settings | None = None) -> DeepSeekGateway:
    provider = provider_config(settings)
    return DeepSeekGateway(
        api_key=provider.api_key,
        base_url=provider.base_url,
        model=provider.fast,
        timeout_seconds=provider.timeout_seconds,
        max_retries=provider.max_retries,
        provider_name=provider.name,
    )


# Kept for backward compatibility; prefer llm_gateway.
deepseek_gateway = llm_gateway
