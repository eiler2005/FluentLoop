from __future__ import annotations

from abc import ABC, abstractmethod
from itertools import count
from pathlib import Path
from typing import Any

from fluentloop.ai.cost import append_usage, estimate_cost
from fluentloop.ai.schemas import (
    AnswerFeedback,
    ExtractedItem,
    ExtractionResult,
    GenerationResult,
    Validated,
)


class AIProvider(ABC):
    @abstractmethod
    def light_call(self, task: str, payload: dict[str, Any]) -> Validated:
        raise NotImplementedError

    @abstractmethod
    def heavy_call(self, task: str, payload: dict[str, Any]) -> Validated:
        raise NotImplementedError


class StubProvider(AIProvider):
    def __init__(self, usage_path: Path | str = "data/usage_log.jsonl") -> None:
        self.usage_path = Path(usage_path)
        self._counter = count(1)

    def _log(self, task: str) -> None:
        append_usage(
            self.usage_path,
            provider="stub",
            model="stub",
            task=task,
            prompt_tokens=0,
            completion_tokens=0,
            cost_usd=0.0,
        )

    def light_call(self, task: str, payload: dict[str, Any]) -> Validated:
        self._log(task)
        if task == "epic_10_check_answer":
            answer = str(payload.get("answer", "")).strip().lower()
            expected = str(payload.get("expected_answer", "")).strip().lower()
            correct = bool(expected and expected in answer)
            return AnswerFeedback(
                status="correct" if correct else "partial",
                corrected_answer=payload.get("expected_answer", ""),
                natural_answer=payload.get("expected_answer", ""),
                explanation="Good meaning; tighten the collocation if needed.",
                related_rule="Natural business collocation",
                detected_mistake_type="collocation" if not correct else "",
                should_create_mistake_event=not correct,
                should_create_or_update_mistake_pattern=not correct,
            )
        return self.heavy_call(task, payload)

    def heavy_call(self, task: str, payload: dict[str, Any]) -> Validated:
        self._log(task)
        n = next(self._counter)
        if task == "epic_04_extract":
            raw = str(payload.get("raw_text", ""))
            candidates = [
                ExtractedItem(
                    type="expression",
                    text="push back on",
                    meaning="мягко возражать",
                    explanation="A natural collocation for polite disagreement.",
                    examples=["I'd like to push back on this proposal a bit."],
                    tags=["meetings", "stakeholders"],
                    confidence=0.91,
                ),
                ExtractedItem(
                    type="expression",
                    text="align on",
                    meaning="согласовать позицию по",
                    explanation="Use align on + topic.",
                    examples=[
                        "We need to align on priorities before the sprint starts."
                    ],
                    tags=["planning"],
                    confidence=0.88,
                ),
                ExtractedItem(
                    type="grammar_rule",
                    text="Hedging recommendations",
                    meaning="смягчение рекомендаций",
                    explanation="Use might need to / could / it may be worth.",
                    examples=["We might need to reconsider the architecture soon."],
                    tags=["hedging"],
                    confidence=0.84,
                ),
            ]
            if "article" in raw.lower() or n % 2 == 0:
                candidates.append(
                    ExtractedItem(
                        type="mistake_pattern",
                        text="Articles with specific project events",
                        meaning="артикли для конкретных событий проекта",
                        explanation=(
                            "Use the sprint when referring to a specific sprint."
                        ),
                        examples=["before the sprint starts"],
                        tags=["articles"],
                        confidence=0.7,
                    )
                )
            return ExtractionResult(candidates=candidates)
        if task == "epic_07_generate_exercise":
            return GenerationResult(exercises=[])
        if task == "epic_10_check_answer":
            return self.light_call(task, payload)
        return ExtractionResult(candidates=[])


class OpenAIProvider(AIProvider):
    def __init__(
        self,
        *,
        api_key: str,
        light_model: str,
        heavy_model: str,
        usage_path: Path | str = "data/usage_log.jsonl",
    ) -> None:
        from openai import OpenAI

        self.client = OpenAI(api_key=api_key)
        self.light_model = light_model
        self.heavy_model = heavy_model
        self.usage_path = Path(usage_path)

    def light_call(self, task: str, payload: dict[str, Any]) -> Validated:
        return self._call(self.light_model, task, payload)

    def heavy_call(self, task: str, payload: dict[str, Any]) -> Validated:
        return self._call(self.heavy_model, task, payload)

    def _call(self, model: str, task: str, payload: dict[str, Any]) -> Validated:
        response = self.client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "Return compact JSON for FluentLoop."},
                {"role": "user", "content": f"task={task}\npayload={payload!r}"},
            ],
            response_format={"type": "json_object"},
            temperature=0.2,
        )
        usage = response.usage
        prompt_tokens = usage.prompt_tokens if usage else 0
        completion_tokens = usage.completion_tokens if usage else 0
        append_usage(
            self.usage_path,
            provider="openai",
            model=model,
            task=task,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            cost_usd=estimate_cost(model, prompt_tokens, completion_tokens),
        )
        # Real parsing is intentionally conservative for tomorrow's provider flip.
        if task == "epic_10_check_answer":
            return AnswerFeedback.model_validate_json(
                response.choices[0].message.content or "{}"
            )
        if task == "epic_07_generate_exercise":
            return GenerationResult.model_validate_json(
                response.choices[0].message.content or "{}"
            )
        return ExtractionResult.model_validate_json(
            response.choices[0].message.content or "{}"
        )
