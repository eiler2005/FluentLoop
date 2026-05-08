from __future__ import annotations

from fluentloop.ai_exercises import (
    enhance_staged_exercises_with_ai,
    generate_ai_exercise,
)
from fluentloop.learning import create_learning_item
from fluentloop.learning_engine import compose_learning_session
from fluentloop.llm.schemas import LLMExercise, LLMExerciseResult
from fluentloop.users import ensure_user


class FakeGateway:
    def __init__(self, result: LLMExerciseResult) -> None:
        self.result = result
        self.calls: list[dict] = []

    def run_json(self, task, payload, schema, *, fallback=None):
        self.calls.append(payload)
        return self.result


def test_ai_exercise_generation_success_preserves_metadata() -> None:
    base = {
        "exercise_type": "follow_up",
        "stage": "free_production",
        "mode": "mixed",
        "topic": "Architecture trade-offs",
        "lesson_goal": "Explain risks diplomatically.",
        "target_skill": "free_production",
        "target_learning_item_ids": [1, 2],
        "target_item_ids": [1, 2],
        "prompt": "Write about trade-offs.",
        "expected_answer": "trade-off",
        "metadata": {
            "stage": "free_production",
            "mode": "mixed",
            "topic": "Architecture trade-offs",
            "lesson_goal": "Explain risks diplomatically.",
            "target_skill": "free_production",
            "target_item_ids": [1, 2],
        },
    }
    gateway = FakeGateway(
        LLMExerciseResult(
            exercises=[
                LLMExercise(
                    exercise_type="free_production",
                    stage="free_production",
                    prompt=(
                        "Write a stakeholder update explaining the release "
                        "trade-off."
                    ),
                    expected_answer="trade-off",
                    target_skill="stakeholder_update",
                    tags=["business", "architecture"],
                )
            ]
        )
    )

    generated = generate_ai_exercise(gateway, base)

    assert generated["ai_generated"] is True
    assert generated["stage"] == "free_production"
    assert generated["target_learning_item_ids"] == [1, 2]
    assert generated["metadata"]["ai_generated"] is True
    assert "stakeholder update" in generated["prompt"]


def test_ai_exercise_generation_falls_back_when_empty() -> None:
    base = {
        "exercise_type": "grammar_rewrite",
        "stage": "grammar_or_mistake_focus",
        "prompt": "Rewrite this.",
        "expected_answer": "A softer rewrite.",
        "target_learning_item_ids": [],
    }
    gateway = FakeGateway(LLMExerciseResult(exercises=[]))

    generated = generate_ai_exercise(gateway, base)

    assert generated["ai_generated"] is False
    assert generated["prompt"] == "Rewrite this."


def test_learning_engine_can_enhance_high_value_stages(db_session, settings) -> None:
    user = ensure_user(db_session, 123456789, settings)
    create_learning_item(
        db_session,
        user,
        type_="expression",
        text="I would lean towards",
        tags=["architecture"],
    )
    gateway = FakeGateway(
        LLMExerciseResult(
            exercises=[
                LLMExercise(
                    exercise_type="free_production",
                    stage="free_production",
                    prompt="AI generated business prompt.",
                    expected_answer="I would lean towards",
                )
            ]
        )
    )

    exercises = compose_learning_session(db_session, user, ai_gateway=gateway)

    assert gateway.calls
    assert any(exercise.get("ai_generated") for exercise in exercises)


def test_enhancer_only_generates_for_high_value_stages() -> None:
    exercises = [
        {"stage": "warmup", "prompt": "Warm up."},
        {"stage": "free_production", "prompt": "Produce."},
    ]
    gateway = FakeGateway(
        LLMExerciseResult(
            exercises=[
                LLMExercise(
                    exercise_type="free_production",
                    stage="free_production",
                    prompt="AI produce.",
                )
            ]
        )
    )

    enhanced = enhance_staged_exercises_with_ai(gateway, exercises)

    assert enhanced[0]["prompt"] == "Warm up."
    assert enhanced[1]["prompt"] == "AI produce."

