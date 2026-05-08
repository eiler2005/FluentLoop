from __future__ import annotations

import json
from types import SimpleNamespace

from fluentloop.ai.factory import make_provider
from fluentloop.ai.provider import DeepSeekProvider
from fluentloop.ai.schemas import AnswerFeedback, ExtractedItem, ExtractionResult
from fluentloop.llm.gateway import DeepSeekGateway, LLMGatewayError
from fluentloop.llm.router import task_profile
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


class FakeProviderGateway:
    def __init__(self) -> None:
        self.models: list[str] = []

    def run_json(self, task, payload, schema, *, model=None, fallback=None, **kwargs):
        self.models.append(model)
        if len(self.models) == 1:
            raise LLMGatewayError("timeout")
        return ExtractionResult(
            candidates=[
                ExtractedItem(
                    type="expression",
                    text="suggest having",
                    meaning="suggest + gerund",
                )
            ]
        )


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


def test_deepseek_gateway_accepts_per_call_model_profile(tmp_path) -> None:
    client = FakeClient([{"candidates": []}])
    gateway = DeepSeekGateway(
        api_key="test-key",
        model="deepseek-v4-flash",
        client=client,
        usage_path=tmp_path / "usage.jsonl",
    )

    gateway.run_json(
        LLMTask.SEED_LESSON_PLAN,
        {},
        ExtractionResult,
        model="deepseek-v4-pro",
        thinking=True,
        reasoning_effort="high",
    )

    call = client.completions.calls[0]
    assert call["model"] == "deepseek-v4-pro"
    assert call["reasoning_effort"] == "high"
    assert call["extra_body"] == {"thinking": {"type": "enabled"}}


def test_task_profiles_route_planning_to_pro_and_answers_to_flash(settings) -> None:
    planning = task_profile(LLMTask.SEED_LESSON_PLAN, settings)
    answer = task_profile(LLMTask.ANSWER_CHECK, settings)
    simple_extract = task_profile(
        LLMTask.MATERIAL_EXTRACTION, settings, material_type="word_list"
    )
    lesson_extract = task_profile(
        LLMTask.MATERIAL_EXTRACTION, settings, material_type="lesson_notes"
    )

    assert planning.model == "deepseek-v4-pro"
    assert planning.thinking is True
    assert planning.reasoning_effort == "high"
    assert answer.model == "deepseek-v4-flash"
    assert simple_extract.model == "deepseek-v4-flash"
    assert lesson_extract.model == "deepseek-v4-pro"


def test_material_extraction_falls_back_from_pro_to_flash(tmp_path) -> None:
    provider = DeepSeekProvider(
        api_key="test-key",
        base_url="https://api.deepseek.com",
        model="deepseek-v4-flash",
        fast_model="deepseek-v4-flash",
        planner_model="deepseek-v4-pro",
        extractor_model="deepseek-v4-pro",
        timeout_seconds=10,
        max_retries=0,
        usage_path=tmp_path / "usage.jsonl",
    )
    gateway = FakeProviderGateway()
    provider.gateway = gateway

    result = provider.heavy_call(
        "epic_04_extract", {"type": "lesson_notes", "raw_text": "reported speech"}
    )

    assert [item.text for item in result.candidates] == ["suggest having"]
    assert gateway.models == ["deepseek-v4-pro", "deepseek-v4-flash"]


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
