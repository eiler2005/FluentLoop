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


def task_profile(
    task: LLMTask,
    settings: Settings | None = None,
    *,
    material_type: str = "",
) -> LLMProfile:
    cfg = settings or get_settings()
    fast = cfg.deepseek_fast_model or cfg.deepseek_chat_model
    planner = cfg.deepseek_planner_model or cfg.deepseek_chat_model
    extractor = cfg.deepseek_extractor_model or planner
    if task == LLMTask.SEED_LESSON_PLAN:
        return LLMProfile(
            planner,
            thinking=True,
            reasoning_effort=cfg.deepseek_planner_reasoning_effort,
        )
    if task == LLMTask.MATERIAL_EXTRACTION:
        simple_material = material_type in {"word_list", "expression_list"}
        return LLMProfile(fast if simple_material else extractor)
    if task == LLMTask.ANSWER_CHECK:
        return LLMProfile(fast)
    if task == LLMTask.EXERCISE_GENERATION:
        return LLMProfile(fast)
    if task == LLMTask.TONE_FEEDBACK:
        return LLMProfile(fast)
    return LLMProfile(fast)


def deepseek_gateway(settings: Settings | None = None) -> DeepSeekGateway:
    cfg = settings or get_settings()
    return DeepSeekGateway(
        api_key=cfg.deepseek_api_key,
        base_url=cfg.deepseek_base_url,
        model=cfg.deepseek_fast_model or cfg.deepseek_chat_model,
        timeout_seconds=cfg.deepseek_timeout_seconds,
        max_retries=cfg.deepseek_max_retries,
    )
