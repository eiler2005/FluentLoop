from __future__ import annotations

import json
from dataclasses import replace

import pytest

from fluentloop.ai.factory import make_provider
from fluentloop.ai.provider import DeepSeekProvider, QwenProvider
from fluentloop.config import get_settings
from fluentloop.llm.gateway import LLMGateway
from fluentloop.llm.router import (
    deepseek_gateway,
    llm_gateway,
    provider_config,
    task_profile,
)
from fluentloop.llm.tasks import LLMTask

QWEN_ENV = {
    "AI_PROVIDER": "qwen",
    "QWEN_API_KEY": "test-key",
    "QWEN_BASE_URL": "https://example.invalid/v1",
    "QWEN_CHAT_MODEL": "qwen3.7-flash",
    "QWEN_FAST_MODEL": "qwen3.7-flash",
    "QWEN_PLANNER_MODEL": "qwen3.8-max",
    "QWEN_EXTRACTOR_MODEL": "qwen3.7-flash",
}
QWEN_KEYS = (
    "QWEN_API_KEY",
    "DASHSCOPE_API_KEY",
    "QWEN_BASE_URL",
    "QWEN_CHAT_MODEL",
    "QWEN_FAST_MODEL",
    "QWEN_PLANNER_MODEL",
    "QWEN_EXTRACTOR_MODEL",
)


@pytest.fixture(autouse=True)
def _isolate_env(monkeypatch):
    """Keep the developer's real .env out of these tests.

    get_settings() calls load_env(), which populates os.environ from .env via
    setdefault. Without this the "defaults" assertions below would silently be
    reading the local machine's configuration instead.
    """

    monkeypatch.setattr("fluentloop.config.load_env", lambda path=None: None)
    for key in QWEN_KEYS:
        monkeypatch.delenv(key, raising=False)


@pytest.fixture
def qwen_settings(monkeypatch):
    for key, value in QWEN_ENV.items():
        monkeypatch.setenv(key, value)
    return get_settings()


@pytest.fixture
def qwen_defaults(monkeypatch):
    """AI_PROVIDER=qwen with nothing else configured."""

    monkeypatch.setenv("AI_PROVIDER", "qwen")
    return get_settings()


# --- configuration ---------------------------------------------------------


def test_settings_default_to_deepseek_without_qwen_env(settings) -> None:
    config = provider_config(settings)

    assert config.name == "deepseek"
    assert config.fast == "deepseek-v4-flash"
    assert config.reasoning_effort == "high"


def test_qwen_env_selects_the_qwen_endpoint(qwen_settings) -> None:
    config = provider_config(qwen_settings)

    assert config.name == "qwen"
    assert config.base_url == "https://example.invalid/v1"
    assert config.fast == "qwen3.7-flash"
    assert config.planner == "qwen3.8-max"
    # Qwen's compatible endpoint has no reasoning_effort knob.
    assert config.reasoning_effort is None


def test_qwen_defaults_to_the_cheapest_flash_everywhere(qwen_defaults) -> None:
    """Every FluentLoop task is bounded JSON, so nothing needs Max."""

    config = provider_config(qwen_defaults)

    assert config.name == "qwen"
    assert config.base_url.startswith("https://dashscope-intl.aliyuncs.com")
    assert config.fast == "qwen3.7-flash"
    assert config.planner == "qwen3.7-flash"
    assert config.extractor == "qwen3.7-flash"


def test_dashscope_api_key_is_accepted_as_a_fallback(monkeypatch) -> None:
    monkeypatch.setenv("AI_PROVIDER", "qwen")
    monkeypatch.setenv("DASHSCOPE_API_KEY", "from-dashscope")

    assert provider_config(get_settings()).api_key == "from-dashscope"


def test_explicit_qwen_key_wins_over_dashscope(monkeypatch) -> None:
    monkeypatch.setenv("AI_PROVIDER", "qwen")
    monkeypatch.setenv("DASHSCOPE_API_KEY", "fallback")
    monkeypatch.setenv("QWEN_API_KEY", "explicit")

    assert provider_config(get_settings()).api_key == "explicit"


def test_task_profile_routes_qwen_models(qwen_settings) -> None:
    fast = task_profile(LLMTask.ANSWER_CHECK, qwen_settings)
    planner = task_profile(LLMTask.SEED_LESSON_PLAN, qwen_settings)
    extractor = task_profile(LLMTask.MATERIAL_EXTRACTION, qwen_settings)

    assert fast.model == "qwen3.7-flash"
    assert planner.model == "qwen3.8-max"
    assert planner.thinking is False
    assert planner.reasoning_effort is None
    assert extractor.model == "qwen3.7-flash"


def test_task_profile_still_routes_deepseek(settings) -> None:
    planner = task_profile(LLMTask.SEED_LESSON_PLAN, settings)
    simple = task_profile(
        LLMTask.MATERIAL_EXTRACTION, settings, material_type="word_list"
    )

    assert planner.model == "deepseek-v4-pro"
    assert planner.thinking is True
    assert planner.reasoning_effort == "high"
    assert simple.model == "deepseek-v4-flash"


def test_quiz_distractor_task_routes_to_the_fast_model(settings) -> None:
    assert task_profile(LLMTask.QUIZ_DISTRACTORS, settings).model == (
        "deepseek-v4-flash"
    )


# --- gateway and providers -------------------------------------------------


def test_llm_gateway_carries_the_provider_name(qwen_settings, settings) -> None:
    assert llm_gateway(qwen_settings).provider_name == "qwen"
    assert llm_gateway(settings).provider_name == "deepseek"


def test_deepseek_gateway_alias_still_works(settings) -> None:
    assert deepseek_gateway(settings).provider_name == "deepseek"


def test_gateway_alias_points_at_the_same_class() -> None:
    from fluentloop.llm.gateway import DeepSeekGateway

    assert LLMGateway is DeepSeekGateway


def test_factory_returns_a_qwen_provider(qwen_settings) -> None:
    provider = make_provider(qwen_settings)

    assert isinstance(provider, QwenProvider)
    assert isinstance(provider, DeepSeekProvider)
    assert provider.provider_name == "qwen"
    assert provider.fast_model == "qwen3.7-flash"


def test_factory_is_unchanged_for_other_providers(settings) -> None:
    from fluentloop.ai.provider import StubProvider

    assert isinstance(make_provider(settings), StubProvider)
    deepseek = make_provider(replace(settings, ai_provider="deepseek"))
    assert isinstance(deepseek, DeepSeekProvider)
    assert deepseek.provider_name == "deepseek"


def test_unknown_provider_still_raises(settings) -> None:
    with pytest.raises(ValueError, match="unknown AI_PROVIDER"):
        make_provider(replace(settings, ai_provider="nope"))


def test_usage_log_attributes_the_qwen_provider(tmp_path, qwen_settings) -> None:
    from fluentloop.llm.gateway import DeepSeekGateway
    from fluentloop.llm.schemas import QuizDistractors

    usage_path = tmp_path / "usage.jsonl"
    gateway = DeepSeekGateway(
        api_key="",  # forces the fallback path, so no network is touched
        base_url=qwen_settings.qwen_base_url,
        model="qwen-flash",
        usage_path=usage_path,
        provider_name="qwen",
    )

    result = gateway.run_json(
        LLMTask.QUIZ_DISTRACTORS,
        {"target": "pipeline"},
        QuizDistractors,
        fallback=lambda: QuizDistractors(options=[]),
    )

    assert result.options == []
    entry = json.loads(usage_path.read_text(encoding="utf-8").splitlines()[0])
    assert entry["provider"] == "qwen"
    assert entry["status"] == "fallback"


def test_quiz_distractors_degrade_to_skipping_the_quiz(db_session, settings) -> None:
    from fluentloop.learning import create_learning_item
    from fluentloop.quiz import llm_distractors
    from fluentloop.users import ensure_user

    user = ensure_user(db_session, 123456789, settings)
    item = create_learning_item(
        db_session, user, type_="word", text="lonely", meaning="no peers"
    )

    # No API key configured: an empty list means "skip tonight's quiz".
    assert llm_distractors(item, settings) == []


# --- reasoning is off for Qwen -------------------------------------------


class _RecordingClient:
    """Captures the request instead of sending it."""

    def __init__(self, payload: str) -> None:
        self.request: dict = {}
        outer = self

        class _Completions:
            def create(self, **kwargs):
                outer.request = kwargs
                message = type("M", (), {"content": payload})()
                choice = type("C", (), {"message": message})()
                return type(
                    "R", (), {"choices": [choice], "usage": None}
                )()

        self.chat = type("Chat", (), {"completions": _Completions()})()


def _gateway(provider_name: str, tmp_path):
    from fluentloop.llm.gateway import DeepSeekGateway

    return DeepSeekGateway(
        api_key="test-key",
        model="test-model",
        client=_RecordingClient('{"options": ["a", "b", "c"]}'),
        usage_path=tmp_path / "usage.jsonl",
        provider_name=provider_name,
    )


def _run(gateway):
    from fluentloop.llm.schemas import QuizDistractors

    return gateway.run_json(
        LLMTask.QUIZ_DISTRACTORS, {"target": "x"}, QuizDistractors
    )


def test_qwen_requests_disable_reasoning(tmp_path) -> None:
    """qwen3.x flash reasons by default; that is billed output we never use."""

    gateway = _gateway("qwen", tmp_path)

    _run(gateway)

    assert gateway.client.request["extra_body"] == {"enable_thinking": False}


def test_deepseek_requests_are_unchanged(tmp_path) -> None:
    gateway = _gateway("deepseek", tmp_path)

    _run(gateway)

    assert "extra_body" not in gateway.client.request


def test_thinking_still_wins_when_requested(tmp_path) -> None:
    from fluentloop.llm.schemas import QuizDistractors

    gateway = _gateway("qwen", tmp_path)

    gateway.run_json(
        LLMTask.SEED_LESSON_PLAN,
        {"x": 1},
        QuizDistractors,
        thinking=True,
    )

    assert gateway.client.request["extra_body"] == {"thinking": {"type": "enabled"}}
