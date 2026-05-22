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


class LessonPlanItemDraft(BaseModel):
    text: str
    role: str = "target"
    priority: int = 0
    rationale: str = ""


class LessonStepDraft(BaseModel):
    step_type: str
    title: str = ""
    instruction: str = ""
    estimated_minutes: int = 1
    target_skill: str = ""
    rationale: str = ""


class LessonPlanDraft(BaseModel):
    title: str = ""
    topic: str = ""
    goal: str = ""
    language_focus: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    item_priorities: list[LessonPlanItemDraft] = Field(default_factory=list)
    steps: list[LessonStepDraft] = Field(default_factory=list)
    teacher_rationale: str = ""


class GeneratedExercise(BaseModel):
    exercise_type: str
    prompt: str
    expected_answer: str
    hint: str = ""
    explanation: str = ""
    target_learning_item_ids: list[int] = Field(default_factory=list)
    stage: str = ""
    mode: str = ""
    topic: str = ""
    lesson_goal: str = ""
    target_skill: str = ""
    target_item_ids: list[int] = Field(default_factory=list)
    difficulty: str = "B2+/C1-"
    tags: list[str] = Field(default_factory=list)


class GenerationResult(BaseModel):
    exercises: list[GeneratedExercise] = Field(default_factory=list)


class AnswerFeedback(BaseModel):
    status: str
    corrected_answer: str = ""
    natural_answer: str = ""
    explanation: str = ""
    related_rule: str = ""
    mistake_summary: str = ""
    why_wrong: str = ""
    rule: str = ""
    error_layer: str = ""
    native_rewrite: str = ""
    native_rewrite_reason: str = ""
    why_layer: str = ""
    l1_hits: list[dict[str, str]] = Field(default_factory=list)
    confidence_rating: int | None = None
    better_variants: list[str] = Field(default_factory=list)
    micro_drill: str = ""
    teacher_note: str = ""
    detected_mistake_type: str = ""
    should_create_mistake_event: bool = False
    should_create_or_update_mistake_pattern: bool = False
    suggested_candidates: list[ExtractedItem] = Field(default_factory=list)


class NativeRewriteFeedback(BaseModel):
    native_rewrite: str = ""
    reason: str = ""
    has_upgrade: bool = False


Validated = (
    ExtractionResult
    | GenerationResult
    | AnswerFeedback
    | NativeRewriteFeedback
    | LessonPlanDraft
)
