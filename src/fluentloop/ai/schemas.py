from __future__ import annotations

from pydantic import BaseModel, Field


class ExtractedItem(BaseModel):
    type: str
    text: str
    meaning: str = ""
    explanation: str = ""
    examples: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    confidence: float = 0.75


class ExtractionResult(BaseModel):
    candidates: list[ExtractedItem] = Field(default_factory=list)


class GeneratedExercise(BaseModel):
    exercise_type: str
    prompt: str
    expected_answer: str
    hint: str = ""
    explanation: str = ""
    target_learning_item_ids: list[int] = Field(default_factory=list)


class GenerationResult(BaseModel):
    exercises: list[GeneratedExercise] = Field(default_factory=list)


class AnswerFeedback(BaseModel):
    status: str
    corrected_answer: str = ""
    natural_answer: str = ""
    explanation: str = ""
    related_rule: str = ""
    detected_mistake_type: str = ""
    should_create_mistake_event: bool = False
    should_create_or_update_mistake_pattern: bool = False
    suggested_candidates: list[ExtractedItem] = Field(default_factory=list)


Validated = ExtractionResult | GenerationResult | AnswerFeedback
