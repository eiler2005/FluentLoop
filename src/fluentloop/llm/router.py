from __future__ import annotations

from fluentloop.config import Settings, get_settings
from fluentloop.llm.gateway import DeepSeekGateway


def deepseek_gateway(settings: Settings | None = None) -> DeepSeekGateway:
    cfg = settings or get_settings()
    return DeepSeekGateway(
        api_key=cfg.deepseek_api_key,
        base_url=cfg.deepseek_base_url,
        model=cfg.deepseek_chat_model,
        timeout_seconds=cfg.deepseek_timeout_seconds,
        max_retries=cfg.deepseek_max_retries,
    )

