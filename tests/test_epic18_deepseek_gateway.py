from __future__ import annotations

import json
from types import SimpleNamespace

from fluentloop.ai.factory import make_provider
from fluentloop.ai.provider import DeepSeekProvider
from fluentloop.ai.schemas import AnswerFeedback, ExtractionResult
from fluentloop.llm.gateway import DeepSeekGateway
from fluentloop.llm.tasks import LLMTask


class FakeCompletions:
    def __init__(self, responses: list[object]) -> None:
        self.responses = responses
        self.calls: list[dict] = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return SimpleNamespace(
            choices=[
                SimpleNamespace(message=SimpleNamespace(content=json.dumps(response)))
            ],
            usage=SimpleNamespace(prompt_tokens=3, completion_tokens=5),
        )


class FakeClient:
    def __init__(self, responses: list[object]) -> None:
        self.completions = FakeCompletions(responses)
        self.chat = SimpleNamespace(completions=self.completions)


def test_deepseek_gateway_validates_json_and_uses_configured_model(tmp_path) -> None:
    client = FakeClient(
        [
            {
                "status": "correct",
                "corrected_answer": "align on",
                "explanation": "Good.",
            }
        ]
    )
    gateway = DeepSeekGateway(
        api_key="test-key",
        model="deepseek-v4-flash",
        client=client,
        usage_path=tmp_path / "usage.jsonl",
    )

    result = gateway.run_json(
        LLMTask.ANSWER_CHECK,
        {"answer": "align on"},
        AnswerFeedback,
    )

    assert result.status == "correct"
    assert client.completions.calls[0]["model"] == "deepseek-v4-flash"
    assert client.completions.calls[0]["response_format"] == {"type": "json_object"}


def test_deepseek_gateway_retries_transient_failure(tmp_path) -> None:
    client = FakeClient(
        [
            RuntimeError("temporary"),
            {"candidates": []},
        ]
    )
    gateway = DeepSeekGateway(
        api_key="test-key",
        client=client,
        max_retries=1,
        usage_path=tmp_path / "usage.jsonl",
    )

    result = gateway.run_json(
        LLMTask.MATERIAL_EXTRACTION,
        {"raw_text": "hello"},
        ExtractionResult,
    )

    assert result.candidates == []
    assert len(client.completions.calls) == 2


def test_deepseek_gateway_uses_fallback_for_invalid_json(tmp_path) -> None:
    client = FakeClient([{"not_status": "bad"}])
    gateway = DeepSeekGateway(
        api_key="test-key",
        client=client,
        max_retries=0,
        usage_path=tmp_path / "usage.jsonl",
    )

    result = gateway.run_json(
        LLMTask.ANSWER_CHECK,
        {},
        AnswerFeedback,
        fallback=AnswerFeedback(status="partial", explanation="fallback"),
    )

    assert result.status == "partial"
    assert "fallback" in result.explanation


def test_deepseek_gateway_missing_key_uses_fallback_without_call(tmp_path) -> None:
    client = FakeClient([{"status": "correct"}])
    gateway = DeepSeekGateway(
        api_key="",
        client=client,
        usage_path=tmp_path / "usage.jsonl",
    )

    result = gateway.run_json(
        LLMTask.ANSWER_CHECK,
        {},
        AnswerFeedback,
        fallback=AnswerFeedback(status="partial"),
    )

    assert result.status == "partial"
    assert client.completions.calls == []


def test_factory_can_select_deepseek_provider(settings) -> None:
    cfg = settings.__class__(
        **{
            **settings.__dict__,
            "ai_provider": "deepseek",
            "deepseek_api_key": "",
        }
    )

    provider = make_provider(cfg)

    assert isinstance(provider, DeepSeekProvider)

