from __future__ import annotations

import json
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from fluentloop.ai.provider import DeepSeekProvider
from fluentloop.ai.schemas import AnswerFeedback, NativeRewriteFeedback
from fluentloop.llm.gateway import LLMGateway
from fluentloop.llm.prompts import user_prompt
from fluentloop.llm.tasks import LLMTask


@pytest.mark.parametrize(
    "verdict,expected",
    [
        ("correct", "correct"),
        ("partial", "partial"),
        ("incorrect", "incorrect"),
        ("pass", "correct"),
        ("passed", "correct"),
        ("fail", "incorrect"),
        ("failed", "incorrect"),
        (" PASSED ", "correct"),
    ],
)
def test_verdict_contract_accepts_only_canonical_and_conservative_aliases(
    verdict, expected
):
    feedback = AnswerFeedback.model_validate({"status": verdict})
    assert feedback.status == expected
    assert feedback.genuine_evaluation is False
    assert feedback.model_dump()["status"] == expected


@pytest.mark.parametrize(
    "verdict", ["success", "uncertain", "unchecked", "", None, True, 1]
)
def test_unknown_verdict_cannot_become_a_passing_answer(verdict):
    with pytest.raises(ValidationError):
        AnswerFeedback.model_validate({"status": verdict, "genuine_evaluation": True})


def test_status_is_required_and_optional_feedback_defaults_are_valid():
    with pytest.raises(ValidationError):
        AnswerFeedback.model_validate({"explanation": "Looks good."})
    feedback = AnswerFeedback.model_validate({"status": "incorrect"})
    assert feedback.corrected_answer == ""
    assert feedback.better_variants == []
    assert feedback.format_feedback == {}
    assert feedback.confidence_rating is None
    assert AnswerFeedback.model_json_schema()["properties"]["status"]["enum"] == [
        "correct",
        "partial",
        "incorrect",
    ]
    with pytest.raises(ValidationError):
        AnswerFeedback.model_validate({"status": "correct", "better_variants": None})


class FakeClient:
    def __init__(self, result):
        self.result = result
        self.calls = []
        self.chat = SimpleNamespace(completions=self)

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(content=json.dumps(self.result))
                )
            ],
            usage=SimpleNamespace(prompt_tokens=3, completion_tokens=5),
        )


@pytest.mark.parametrize(
    "verdict,model_provenance,expected,genuine",
    [
        ("pass", False, "correct", True),
        ("passed", True, "correct", True),
        ("failed", True, "incorrect", True),
        ("success", True, None, False),
        ("uncertain", True, None, False),
    ],
)
def test_provider_and_real_gateway_validate_verdict_and_own_provenance(
    tmp_path, verdict, model_provenance, expected, genuine
):
    client = FakeClient({"status": verdict, "genuine_evaluation": model_provenance})
    provider = DeepSeekProvider(
        api_key="",
        base_url="https://example.invalid",
        model="test-model",
        timeout_seconds=1,
        max_retries=0,
        usage_path=tmp_path / "usage.jsonl",
    )
    provider.gateway = LLMGateway(
        api_key="test-key",
        client=client,
        max_retries=0,
        usage_path=tmp_path / "usage.jsonl",
    )
    result = provider.light_call(
        "epic_10_check_answer",
        {
            "stage": "b2",
            "prompt": "Suggest a new arrival time to a friend.",
            "expected_answer": "suggest + gerund",
            "answer": "I suggest arriving a little earlier so we can enjoy the sunset.",
        },
    )
    assert result.genuine_evaluation is genuine
    if expected is not None:
        assert result.status == expected
    else:
        assert result.status in {"correct", "partial", "incorrect"}
    entries = [
        json.loads(line) for line in (tmp_path / "usage.jsonl").read_text().splitlines()
    ]
    assert entries[0]["status"] == ("success" if genuine else "fallback")
    assert len(client.calls) == 1


def test_answer_prompt_has_verdict_completion_context_and_optional_field_contract():
    prompt = user_prompt(
        LLMTask.ANSWER_CHECK,
        {
            "stage": "b2",
            "prompt": "Suggest a new arrival time to a friend.",
            "expected_answer": "suggest + gerund",
        },
        AnswerFeedback,
    )
    assert "exactly correct, partial or incorrect" in prompt
    assert "fluent but unrelated answer is incorrect" in prompt
    assert "construction or rubric rather than a literal sentence" in prompt
    assert "Do not require a workplace setting or C1 wording" in prompt
    assert "Optional style upgrades" in prompt
    assert "omitted optional fields use their defaults" in prompt
    assert 'text fields must be "", lists [], objects {}' in prompt
    assert "Only confidence_rating may be null" in prompt
    assert "Do not return genuine_evaluation" in prompt
    assert "  genuine_evaluation:" not in prompt
    assert '"properties"' not in prompt
    assert "$defs" not in prompt


def test_other_task_prompt_retains_its_existing_required_fields_and_instruction():
    prompt = user_prompt(
        LLMTask.TONE_FEEDBACK, {"answer": "Thanks."}, NativeRewriteFeedback
    )
    assert "Return only a C1-level native rewrite" in prompt
    assert "exactly these keys" in prompt
    assert "  native_rewrite: str\n  reason: str\n  has_upgrade: bool" in prompt
    assert "omitted optional" not in prompt
    assert "required key is status" not in prompt
