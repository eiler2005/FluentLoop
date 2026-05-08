from __future__ import annotations

import time
from collections.abc import Callable
from pathlib import Path
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError

from fluentloop.ai.cost import append_usage
from fluentloop.llm.clients import make_openai_compatible_client
from fluentloop.llm.prompts import system_prompt, user_prompt
from fluentloop.llm.tasks import LLMTask

T = TypeVar("T", bound=BaseModel)


class LLMGatewayError(RuntimeError):
    pass


class DeepSeekGateway:
    def __init__(
        self,
        *,
        api_key: str,
        base_url: str = "https://api.deepseek.com",
        model: str = "deepseek-v4-flash",
        timeout_seconds: float = 30,
        max_retries: int = 2,
        client: Any | None = None,
        usage_path: Path | str = "data/usage_log.jsonl",
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url
        self.model = model
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self.client = client
        if self.client is None and api_key:
            self.client = make_openai_compatible_client(
                api_key=api_key,
                base_url=base_url,
                timeout=timeout_seconds,
            )
        self.usage_path = Path(usage_path)

    def run_json(
        self,
        task: LLMTask,
        payload: dict[str, Any],
        schema: type[T],
        *,
        fallback: T | Callable[[], T] | None = None,
    ) -> T:
        if not self.api_key and fallback is not None:
            return self._fallback(task, fallback, "missing_api_key")
        if self.client is None:
            raise LLMGatewayError("DeepSeek API key is required")
        last_error: Exception | None = None
        for attempt in range(self.max_retries + 1):
            started = time.monotonic()
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system_prompt()},
                        {"role": "user", "content": user_prompt(task, payload, schema)},
                    ],
                    response_format={"type": "json_object"},
                    temperature=0.2,
                )
                content = response.choices[0].message.content or "{}"
                result = schema.model_validate_json(content)
                self._log(task, response, "success", started)
                return result
            except (ValidationError, ValueError, TypeError, RuntimeError) as exc:
                last_error = exc
                if attempt >= self.max_retries:
                    break
            except Exception as exc:
                last_error = exc
                if attempt >= self.max_retries:
                    break
        if fallback is not None:
            return self._fallback(task, fallback, type(last_error).__name__)
        raise LLMGatewayError(f"DeepSeek task failed: {task.value}") from last_error

    def _fallback(
        self, task: LLMTask, fallback: T | Callable[[], T], reason: str
    ) -> T:
        append_usage(
            self.usage_path,
            provider="deepseek",
            model=self.model,
            task=task.value,
            prompt_tokens=0,
            completion_tokens=0,
            cost_usd=0.0,
            status="fallback",
            error=reason,
        )
        return fallback() if callable(fallback) else fallback

    def _log(self, task: LLMTask, response: Any, status: str, started: float) -> None:
        usage = getattr(response, "usage", None)
        prompt_tokens = getattr(usage, "prompt_tokens", 0) if usage else 0
        completion_tokens = getattr(usage, "completion_tokens", 0) if usage else 0
        append_usage(
            self.usage_path,
            provider="deepseek",
            model=self.model,
            task=task.value,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            cost_usd=0.0,
            status=status,
            latency_ms=int((time.monotonic() - started) * 1000),
        )
