from __future__ import annotations

from typing import Any

from fluentloop.llm.gateway import DeepSeekGateway
from fluentloop.llm.schemas import LLMExerciseResult
from fluentloop.llm.tasks import LLMTask

AI_EXERCISE_STAGES = {
    "free_production",
    "grammar_or_mistake_focus",
}


def enhance_staged_exercises_with_ai(
    gateway: DeepSeekGateway,
    exercises: list[dict[str, Any]],
    *,
    max_generated: int = 2,
) -> list[dict[str, Any]]:
    enhanced: list[dict[str, Any]] = []
    generated_count = 0
    for exercise in exercises:
        if (
            generated_count < max_generated
            and exercise.get("stage") in AI_EXERCISE_STAGES
        ):
            generated = generate_ai_exercise(gateway, exercise)
            if generated.get("ai_generated"):
                generated_count += 1
            enhanced.append(generated)
        else:
            enhanced.append(exercise)
    return enhanced


def generate_ai_exercise(
    gateway: DeepSeekGateway, base_exercise: dict[str, Any]
) -> dict[str, Any]:
    fallback = LLMExerciseResult(exercises=[])
    result = gateway.run_json(
        LLMTask.EXERCISE_GENERATION,
        _payload_for_generation(base_exercise),
        LLMExerciseResult,
        fallback=fallback,
    )
    if not result.exercises:
        return {**base_exercise, "ai_generated": False}
    generated = result.exercises[0]
    target_ids = (
        generated.target_learning_item_ids
        or generated.target_item_ids
        or base_exercise.get("target_learning_item_ids", [])
    )
    metadata = {
        **dict(base_exercise.get("metadata") or {}),
        "stage": generated.stage or base_exercise.get("stage", ""),
        "mode": generated.mode or base_exercise.get("mode", ""),
        "topic": generated.topic or base_exercise.get("topic", ""),
        "lesson_goal": generated.lesson_goal or base_exercise.get("lesson_goal", ""),
        "target_skill": generated.target_skill
        or base_exercise.get("target_skill", ""),
        "target_item_ids": target_ids,
        "ai_generated": True,
    }
    return {
        **base_exercise,
        "exercise_type": generated.exercise_type
        or base_exercise.get("exercise_type", "follow_up"),
        "prompt": generated.prompt,
        "expected_answer": generated.expected_answer
        or base_exercise.get("expected_answer", ""),
        "hint": generated.hint or base_exercise.get("hint", ""),
        "explanation": generated.explanation or base_exercise.get("explanation", ""),
        "target_learning_item_ids": target_ids,
        "target_item_ids": target_ids,
        "target_skill": metadata["target_skill"],
        "stage": metadata["stage"],
        "metadata": metadata,
        "ai_generated": True,
        "ai_tags": generated.tags,
        "difficulty": generated.difficulty,
    }


def _payload_for_generation(base_exercise: dict[str, Any]) -> dict[str, Any]:
    return {
        "stage": base_exercise.get("stage", ""),
        "mode": base_exercise.get("mode", ""),
        "topic": base_exercise.get("topic", ""),
        "lesson_goal": base_exercise.get("lesson_goal", ""),
        "target_skill": base_exercise.get("target_skill", ""),
        "exercise_type": base_exercise.get("exercise_type", ""),
        "prompt": base_exercise.get("prompt", ""),
        "expected_answer": base_exercise.get("expected_answer", ""),
        "target_learning_item_ids": base_exercise.get("target_learning_item_ids", []),
        "material_context": (base_exercise.get("metadata") or {}).get(
            "material_context", []
        ),
        "level": base_exercise.get("difficulty", "B2+/C1-"),
        "style": "concise Telegram-friendly business/IT English",
    }
