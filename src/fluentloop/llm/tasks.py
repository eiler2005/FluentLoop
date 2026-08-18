from __future__ import annotations

from enum import StrEnum


class LLMTask(StrEnum):
    MATERIAL_EXTRACTION = "material_extraction"
    SEED_LESSON_PLAN = "seed_lesson_plan"
    EXERCISE_GENERATION = "exercise_generation"
    ANSWER_CHECK = "answer_check"
    GRAMMAR_EXPLANATION = "grammar_explanation"
    TONE_FEEDBACK = "tone_feedback"
    QUIZ_DISTRACTORS = "quiz_distractors"
    WORD_CARD = "word_card"

