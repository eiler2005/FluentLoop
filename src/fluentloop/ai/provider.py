from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterable
from itertools import count
from pathlib import Path
from typing import Any

from fluentloop.ai.cost import append_usage, estimate_cost
from fluentloop.ai.schemas import (
    AnswerFeedback,
    ExtractedItem,
    ExtractionResult,
    GenerationResult,
    LessonPlanDraft,
    LessonPlanItemDraft,
    LessonStepDraft,
    Validated,
)
from fluentloop.lesson_overview import infer_lesson_overview
from fluentloop.llm.gateway import DeepSeekGateway, LLMGatewayError
from fluentloop.llm.router import task_profile
from fluentloop.llm.tasks import LLMTask


class AIProvider(ABC):
    @abstractmethod
    def light_call(self, task: str, payload: dict[str, Any]) -> Validated:
        raise NotImplementedError

    @abstractmethod
    def heavy_call(self, task: str, payload: dict[str, Any]) -> Validated:
        raise NotImplementedError


def _deterministic_extract(raw: str, material_type: str) -> list[ExtractedItem]:
    lower = raw.lower()
    if _looks_like_reported_speech_lesson(lower):
        return _reported_speech_candidates()

    candidates = _simple_phrase_candidates(lower)
    if material_type == "lesson_notes" or len(raw) > 500:
        candidates.extend(_business_candidates(lower))
    if not candidates:
        candidates.extend(_generic_candidates(raw))
    return _unique_items(candidates)


def _looks_like_reported_speech_lesson(text: str) -> bool:
    signals = (
        "introvert",
        "extrovert",
        "reported sentences",
        "direct speech",
        "suggested having",
        "boasted about",
        "accused",
        "verb-pattern",
    )
    return any(signal in text for signal in signals)


def _reported_speech_candidates() -> list[ExtractedItem]:
    return [
        _item(
            "expression",
            "suggest having",
            "suggest + gerund",
            "Use suggest + -ing to report an idea or proposal.",
            "She suggested having just one meeting a week.",
            ["reported_speech", "verb_patterns"],
        ),
        _item(
            "expression",
            "suggest that",
            "suggest + that-clause",
            "Use suggest that + clause to report a recommendation.",
            "They suggested that I stayed with them.",
            ["reported_speech", "that_clause"],
        ),
        _item(
            "expression",
            "refuse to",
            "refuse + infinitive",
            "Use refuse to + verb when someone says no to an action.",
            "People refused to take the idea seriously.",
            ["reported_speech", "infinitive"],
        ),
        _item(
            "expression",
            "take the idea seriously",
            "воспринимать идею всерьез",
            "A useful workplace collocation for evaluating a proposal.",
            "At first people refused to take the idea seriously.",
            ["workplace_opinions", "collocation"],
        ),
        _item(
            "expression",
            "insist on giving it a try",
            "insist on + gerund",
            "Use insist on + -ing when someone strongly pushes for an action.",
            "I insisted on giving it a try.",
            ["reported_speech", "preposition_gerund"],
        ),
        _item(
            "expression",
            "threaten to stop coming",
            "threaten + infinitive",
            "Use threaten to + verb for a warning about a future action.",
            "I threatened to stop coming to meetings.",
            ["reported_speech", "infinitive"],
        ),
        _item(
            "expression",
            "boast about having",
            "boast about + gerund",
            "Use boast about + -ing to report someone showing off.",
            "He boasted about having a lot of achievements.",
            ["reported_speech", "preposition_gerund"],
        ),
        _item(
            "expression",
            "boast that",
            "boast + that-clause",
            "Boast can also introduce a that-clause.",
            "He boasted that he had many achievements.",
            ["reported_speech", "that_clause"],
        ),
        _item(
            "expression",
            "claim that",
            "claim + that-clause",
            "Use claim that when reporting something presented as true.",
            "He claimed that he worked as the manager of a restaurant.",
            ["reported_speech", "that_clause"],
        ),
        _item(
            "expression",
            "question someone about",
            "question + object + about",
            "Use question someone about + noun/gerund for asking for details.",
            "I questioned him about the details.",
            ["reported_speech", "object_preposition"],
        ),
        _item(
            "expression",
            "admit that",
            "admit + that-clause",
            "Use admit that when someone accepts something is true.",
            "He admitted that it wasn't true.",
            ["reported_speech", "that_clause"],
        ),
        _item(
            "expression",
            "accuse someone of eating",
            "accuse + object + of + gerund",
            "Use accuse someone of + -ing for blame.",
            "He accused his younger sister of eating his ice-cream.",
            ["reported_speech", "object_preposition_gerund"],
        ),
        _item(
            "expression",
            "apologize for waking",
            "apologize for + gerund",
            "Use apologize for + -ing to say what caused the apology.",
            "She apologized for waking me up.",
            ["reported_speech", "preposition_gerund"],
        ),
        _item(
            "expression",
            "doubt that",
            "doubt + that-clause",
            "Use doubt that to report uncertainty about a result.",
            "She doubted that anyone would notice.",
            ["reported_speech", "that_clause"],
        ),
        _item(
            "expression",
            "recommend bringing",
            "recommend + gerund",
            "Use recommend + -ing for practical advice.",
            "He recommended bringing my laptop.",
            ["reported_speech", "verb_patterns"],
        ),
        _item(
            "expression",
            "recommend that",
            "recommend + that-clause",
            "Use recommend that + clause as an alternative to recommend + -ing.",
            "He recommended that I bring my laptop.",
            ["reported_speech", "that_clause"],
        ),
        _item(
            "expression",
            "propose + gerund",
            "propose doing something",
            "Use propose + -ing to suggest a plan.",
            "I proposed reducing the number of meetings.",
            ["reported_speech", "verb_patterns"],
        ),
        _item(
            "expression",
            "deny + gerund",
            "deny doing something",
            "Use deny + -ing to report rejecting an accusation.",
            "He denied lying about the job.",
            ["reported_speech", "verb_patterns"],
        ),
        _item(
            "expression",
            "regret + gerund",
            "regret doing something",
            "Use regret + -ing to talk about a past action you feel bad about.",
            "She regretted arriving late.",
            ["reported_speech", "verb_patterns"],
        ),
        _item(
            "expression",
            "criticise someone for",
            "criticise + object + for + gerund",
            "Use criticise someone for + -ing to report criticism.",
            "They criticised him for boasting.",
            ["reported_speech", "object_preposition_gerund"],
        ),
        _item(
            "grammar_rule",
            "Reported speech for opinions and claims",
            "reporting opinions and claims",
            "Choose a reporting verb that matches the speaker's intention.",
            "He claimed that he had worked there.",
            ["reported_speech", "grammar"],
        ),
        _item(
            "grammar_rule",
            "Verb + gerund patterns",
            "verb + -ing",
            "Some reporting verbs are followed by a gerund.",
            "She suggested having fewer meetings.",
            ["verb_patterns", "grammar"],
        ),
        _item(
            "grammar_rule",
            "Verb + preposition + gerund patterns",
            "preposition + -ing",
            "After a preposition, use a gerund, not an infinitive.",
            "He apologized for waking me up.",
            ["verb_patterns", "grammar"],
        ),
        _item(
            "grammar_rule",
            "Verb + that-clause patterns",
            "that-clause after reporting verbs",
            "Some reporting verbs can introduce a full clause.",
            "She doubted that anyone would notice.",
            ["that_clause", "grammar"],
        ),
        _item(
            "grammar_rule",
            "Verb + infinitive patterns",
            "verb + to + infinitive",
            "Some reporting verbs are followed by to + infinitive.",
            "My boss threatened to fire me.",
            ["infinitive", "grammar"],
        ),
        _item(
            "grammar_rule",
            "Verb + object + preposition + gerund",
            "object + preposition + -ing",
            "Use this pattern for blame, questions, and criticism.",
            "He accused his sister of eating the ice-cream.",
            ["object_preposition_gerund", "grammar"],
        ),
        _item(
            "grammar_rule",
            "Reporting verbs by communicative function",
            "meaning-driven reporting verbs",
            "Pick the verb by function: suggest, insist, threaten, boast, claim.",
            "He boasted about having three sports cars.",
            ["reported_speech", "meaning"],
        ),
    ]


def _simple_phrase_candidates(text: str) -> list[ExtractedItem]:
    phrase_bank = [
        (
            "push back on",
            "мягко возражать",
            "A natural collocation for polite disagreement.",
            "I'd like to push back on this proposal a bit.",
            ["meetings", "stakeholders"],
        ),
        (
            "align on",
            "согласовать позицию по",
            "Use align on + topic.",
            "We need to align on priorities before the sprint starts.",
            ["planning"],
        ),
        (
            "circle back",
            "вернуться к теме позже",
            "A common workplace phrase for returning to a topic.",
            "Let's circle back after the client call.",
            ["meetings"],
        ),
        (
            "follow up",
            "продолжить обсуждение / уточнить",
            "Use follow up to mean continue with the next message or action.",
            "I'll follow up with the action items.",
            ["communication"],
        ),
    ]
    return [
        _item("expression", phrase, meaning, explanation, example, tags, 0.88)
        for phrase, meaning, explanation, example, tags in phrase_bank
        if phrase in text
    ]


def _business_candidates(text: str) -> list[ExtractedItem]:
    if not any(
        signal in text
        for signal in (
            "stakeholder",
            "architecture",
            "trade-off",
            "tradeoff",
            "risk",
            "release",
            "incident",
            "reliability",
        )
    ):
        return []
    seeds = [
        ("expression", "frame a recommendation"),
        ("expression", "raise a concern diplomatically"),
        ("expression", "summarize the trade-off"),
        ("expression", "from a reliability perspective"),
        ("expression", "the safest next step is"),
        ("expression", "I would lean towards"),
        ("expression", "mitigate the risk"),
        ("expression", "align on priorities"),
        ("expression", "push back on the timeline"),
        ("expression", "clarify the scope"),
        ("expression", "set expectations"),
        ("expression", "share a concise update"),
        ("expression", "there is a risk that"),
        ("grammar_rule", "we may need to"),
        ("grammar_rule", "it might be worth"),
        ("grammar_rule", "reported suggestions"),
        ("grammar_rule", "summarising opinions"),
        ("grammar_rule", "specific project events"),
        ("grammar_rule", "business collocations with on"),
        ("grammar_rule", "softening direct feedback"),
        ("expression", "explain the impact"),
        ("expression", "recommend a fallback"),
        ("expression", "ask for stakeholder input"),
        ("expression", "confirm the next step"),
    ]
    return [
        _item(
            type_,
            text_,
            "useful workplace English target",
            "High-value B2+/C1 target for business/IT communication practice.",
            f"We can use this to {text_}.",
            ["business", "IT", "teacher_priority"],
            0.78,
        )
        for type_, text_ in seeds
    ]


def _generic_candidates(raw: str) -> list[ExtractedItem]:
    words = [
        part.strip(" -*_`#0123456789.():;\"'")
        for part in raw.splitlines()
        if 3 <= len(part.strip()) <= 80
    ]
    candidates = [
        _item(
            "expression",
            text,
            "candidate from uploaded material",
            "Review this candidate before approving it for practice.",
            text,
            ["uploaded_material"],
            0.55,
        )
        for text in words[:8]
    ]
    return candidates or [
        _item(
            "expression",
            "uploaded material target",
            "candidate from uploaded material",
            "Review this target before approving it.",
            "Use this in a short answer.",
            ["uploaded_material"],
            0.5,
        )
    ]


def _item(
    type_: str,
    text: str,
    meaning: str,
    explanation: str,
    example: str,
    tags: Iterable[str],
    confidence: float = 0.8,
) -> ExtractedItem:
    return ExtractedItem(
        type=type_,
        text=text,
        meaning=meaning,
        explanation=explanation,
        examples=[example],
        tags=list(tags),
        confidence=confidence,
    )


def _unique_items(items: Iterable[ExtractedItem]) -> list[ExtractedItem]:
    seen: set[tuple[str, str]] = set()
    unique: list[ExtractedItem] = []
    for item in items:
        key = (item.type, item.text.strip().lower())
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)
    return unique


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
                mistake_summary=(
                    ""
                    if correct
                    else "The core meaning is clear, but the chunk is incomplete."
                ),
                why_wrong=(
                    ""
                    if correct
                    else "This phrase works as a collocation: align on + topic."
                ),
                rule="Use the full business collocation, not only one part of it.",
                better_variants=[payload.get("expected_answer", "")],
                micro_drill="Write one more sentence using the full chunk.",
                teacher_note="Keep the meaning, tighten the form.",
                detected_mistake_type="collocation" if not correct else "",
                should_create_mistake_event=not correct,
                should_create_or_update_mistake_pattern=not correct,
            )
        return self.heavy_call(task, payload)

    def heavy_call(self, task: str, payload: dict[str, Any]) -> Validated:
        self._log(task)
        if task == "epic_04_extract":
            raw = str(payload.get("raw_text", ""))
            candidates = _deterministic_extract(raw, str(payload.get("type", "")))
            if "article" in raw.lower():
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
            return ExtractionResult(candidates=_unique_items(candidates))
        if task == "epic_17_seed_lesson_plan":
            raw = str(payload.get("source_material", {}).get("raw_text", ""))
            item_texts = [
                str(item.get("text", "")) for item in payload.get("items", [])
            ]
            tags = [
                str(tag)
                for item in payload.get("items", [])
                for tag in item.get("tags", [])
            ]
            overview = infer_lesson_overview(raw, item_texts=item_texts, tags=tags)
            return LessonPlanDraft(
                title=overview.title,
                topic=overview.topic,
                goal=overview.goal,
                language_focus=[
                    *overview.knowledge_areas[:4],
                    *overview.grammar_rules[:4],
                ],
                tags=[*overview.knowledge_areas[:6], "micro-drills"],
                item_priorities=[
                    LessonPlanItemDraft(
                        text=item.get("text", ""),
                        role=item.get("role", "target"),
                        priority=index,
                        rationale="Useful, reusable workplace target.",
                    )
                    for index, item in enumerate(payload.get("items", []), start=1)
                ],
                steps=[
                    LessonStepDraft(
                        step_type="warmup",
                        title="Warm-up",
                        instruction="Activate the topic with one short answer.",
                        estimated_minutes=1,
                        target_skill="activation",
                    ),
                    LessonStepDraft(
                        step_type="input",
                        title="Input",
                        instruction="Notice reusable chunks from the material.",
                        estimated_minutes=2,
                        target_skill="noticing",
                    ),
                    LessonStepDraft(
                        step_type="controlled_practice",
                        title="Controlled practice",
                        instruction="Practice target chunks quickly and accurately.",
                        estimated_minutes=7,
                        target_skill="accuracy",
                    ),
                    LessonStepDraft(
                        step_type="grammar_or_mistake_focus",
                        title="Grammar / mistake focus",
                        instruction="Repair grammar or recurring weak spots.",
                        estimated_minutes=3,
                        target_skill="repair",
                    ),
                    LessonStepDraft(
                        step_type="free_production",
                        title="Free production",
                        instruction="Write a concise realistic work message.",
                        estimated_minutes=1,
                        target_skill="production",
                    ),
                    LessonStepDraft(
                        step_type="recap",
                        title="Recap",
                        instruction="Recall key language without looking back.",
                        estimated_minutes=1,
                        target_skill="active_recall",
                    ),
                ],
                teacher_rationale=(
                    "Targets are ranked for reuse in business/IT contexts and "
                    "rotated through short micro-drills."
                ),
            )
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


class DeepSeekProvider(AIProvider):
    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        model: str,
        fast_model: str | None = None,
        planner_model: str | None = None,
        extractor_model: str | None = None,
        planner_reasoning_effort: str = "high",
        timeout_seconds: float,
        max_retries: int,
        usage_path: Path | str = "data/usage_log.jsonl",
    ) -> None:
        self.gateway = DeepSeekGateway(
            api_key=api_key,
            base_url=base_url,
            model=model,
            timeout_seconds=timeout_seconds,
            max_retries=max_retries,
            usage_path=usage_path,
        )
        self.stub = StubProvider(usage_path)
        self.fast_model = fast_model or model
        self.planner_model = planner_model or model
        self.extractor_model = extractor_model or self.planner_model
        self.planner_reasoning_effort = planner_reasoning_effort

    def light_call(self, task: str, payload: dict[str, Any]) -> Validated:
        return self._call(task, payload)

    def heavy_call(self, task: str, payload: dict[str, Any]) -> Validated:
        return self._call(task, payload)

    def _call(self, task: str, payload: dict[str, Any]) -> Validated:
        if task == "epic_04_extract":
            profile = task_profile(
                LLMTask.MATERIAL_EXTRACTION,
                _settings_for_models(
                    self.fast_model,
                    self.planner_model,
                    self.extractor_model,
                    self.planner_reasoning_effort,
                ),
                material_type=str(payload.get("type", "")),
            )
            if profile.model != self.fast_model:
                try:
                    return self.gateway.run_json(
                        LLMTask.MATERIAL_EXTRACTION,
                        payload,
                        ExtractionResult,
                        model=profile.model,
                    )
                except LLMGatewayError:
                    pass
            return self.gateway.run_json(
                LLMTask.MATERIAL_EXTRACTION,
                payload,
                ExtractionResult,
                model=self.fast_model,
                fallback=lambda: self.stub.heavy_call(task, payload),
            )
        if task == "epic_17_seed_lesson_plan":
            profile = task_profile(
                LLMTask.SEED_LESSON_PLAN,
                _settings_for_models(
                    self.fast_model,
                    self.planner_model,
                    self.extractor_model,
                    self.planner_reasoning_effort,
                ),
            )
            return self.gateway.run_json(
                LLMTask.SEED_LESSON_PLAN,
                payload,
                LessonPlanDraft,
                model=profile.model,
                thinking=profile.thinking,
                reasoning_effort=profile.reasoning_effort,
                fallback=lambda: self.stub.heavy_call(task, payload),
            )
        if task == "epic_07_generate_exercise":
            profile = task_profile(
                LLMTask.EXERCISE_GENERATION,
                _settings_for_models(
                    self.fast_model,
                    self.planner_model,
                    self.extractor_model,
                    self.planner_reasoning_effort,
                ),
            )
            return self.gateway.run_json(
                LLMTask.EXERCISE_GENERATION,
                payload,
                GenerationResult,
                model=profile.model,
                fallback=GenerationResult(),
            )
        if task == "epic_10_check_answer":
            profile = task_profile(
                LLMTask.ANSWER_CHECK,
                _settings_for_models(
                    self.fast_model,
                    self.planner_model,
                    self.extractor_model,
                    self.planner_reasoning_effort,
                ),
            )
            return self.gateway.run_json(
                LLMTask.ANSWER_CHECK,
                payload,
                AnswerFeedback,
                model=profile.model,
                fallback=lambda: self.stub.light_call(task, payload),
            )
        return self.stub.heavy_call(task, payload)


def _settings_for_models(
    fast_model: str,
    planner_model: str,
    extractor_model: str,
    planner_reasoning_effort: str,
):
    from types import SimpleNamespace

    return SimpleNamespace(
        deepseek_chat_model=fast_model,
        deepseek_fast_model=fast_model,
        deepseek_planner_model=planner_model,
        deepseek_extractor_model=extractor_model,
        deepseek_planner_reasoning_effort=planner_reasoning_effort,
    )
