from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from fluentloop.llm.tasks import LLMTask


def system_prompt() -> str:
    return (
        "You are FluentLoop's structured JSON generator for B2+/C1- business "
        "and IT English practice. Return JSON only. Keep Telegram prompts "
        "concise and practical."
    )


def user_prompt(
    task: LLMTask, payload: dict[str, Any], schema: type[BaseModel]
) -> str:
    schema_json = schema.model_json_schema()
    return (
        f"Task: {task.value}\n"
        f"Payload: {payload!r}\n"
        f"Return JSON matching this schema:\n{schema_json!r}"
    )

