from __future__ import annotations

from typing import Any


def make_openai_compatible_client(
    *, api_key: str, base_url: str, timeout: float
) -> Any:
    from openai import OpenAI

    return OpenAI(
        api_key=api_key,
        base_url=base_url,
        timeout=timeout,
        max_retries=0,
    )
