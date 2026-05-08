from __future__ import annotations

from pydantic import BaseModel, Field


class LLMExercise(BaseModel):
    exercise_type: str
    stage: str = ""
    title: str = ""
    prompt: str
    expected_answer: str = ""
    hint: str = ""
    explanation: str = ""
    target_learning_item_ids: list[int] = Field(default_factory=list)
    target_item_ids: list[int] = Field(default_factory=list)
    target_skill: str = ""
    difficulty: str = "B2+/C1-"
    tags: list[str] = Field(default_factory=list)


class LLMExerciseResult(BaseModel):
    exercises: list[LLMExercise] = Field(default_factory=list)


class LLMTextResult(BaseModel):
    title: str = ""
    text: str = ""
    tags: list[str] = Field(default_factory=list)

