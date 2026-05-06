from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from fluentloop.db.models import LearningItem


@dataclass(frozen=True)
class Exercise:
    exercise_type: str
    prompt: str
    expected_answer: str
    hint: str
    explanation: str
    target_learning_item_ids: list[int]

    def as_dict(self) -> dict:
        return {
            "exercise_type": self.exercise_type,
            "prompt": self.prompt,
            "expected_answer": self.expected_answer,
            "hint": self.hint,
            "explanation": self.explanation,
            "target_learning_item_ids": self.target_learning_item_ids,
        }


class ExerciseType(Protocol):
    key: str
    pretty_name: str
    target_item_kinds: tuple[str, ...]

    def render(self, item: LearningItem) -> Exercise: ...


@dataclass(frozen=True)
class GuessExercise:
    key: str = "guess"
    pretty_name: str = "Guess word/expression"
    target_item_kinds: tuple[str, ...] = ("word", "expression")

    def render(self, item: LearningItem) -> Exercise:
        definition = item.meaning or item.explanation or "the target expression"
        return Exercise(
            self.key,
            f'Guess the expression:\n"{definition}"',
            item.text,
            item.examples[0] if item.examples else "Think of a business context.",
            item.explanation,
            [item.id],
        )


@dataclass(frozen=True)
class TranslateExercise:
    key: str = "translate"
    pretty_name: str = "Translate phrase"
    target_item_kinds: tuple[str, ...] = ("word", "expression")

    def render(self, item: LearningItem) -> Exercise:
        source = item.meaning or item.text
        return Exercise(
            self.key,
            f'Translate into English:\n"{source}"',
            item.text,
            "Use natural business English.",
            item.explanation,
            [item.id],
        )


@dataclass(frozen=True)
class ClozeExercise:
    key: str = "cloze"
    pretty_name: str = "Cloze"
    target_item_kinds: tuple[str, ...] = ("word", "expression")

    def render(self, item: LearningItem) -> Exercise:
        example = (
            item.examples[0] if item.examples else f"We need to {item.text} this risk."
        )
        prompt = example.replace(item.text, "____", 1)
        if prompt == example:
            prompt = (
                "Fill the gap:\nWe need to ____ this in the next planning meeting."
            )
        return Exercise(
            self.key,
            prompt,
            item.text,
            "One gap, one answer.",
            item.explanation,
            [item.id],
        )


@dataclass(frozen=True)
class GrammarRewriteExercise:
    key: str = "grammar_rewrite"
    pretty_name: str = "Grammar rewrite"
    target_item_kinds: tuple[str, ...] = ("grammar_rule", "mistake_pattern")

    def render(self, item: LearningItem) -> Exercise:
        return Exercise(
            self.key,
            (
                "Rewrite this in a more diplomatic business style:\n"
                '"We must change the architecture immediately."'
            ),
            "We might need to reconsider the architecture soon.",
            item.text,
            item.explanation or "Use hedging to soften recommendations.",
            [item.id],
        )


@dataclass(frozen=True)
class ErrorCorrectionExercise:
    key: str = "error_correction"
    pretty_name: str = "Error correction"
    target_item_kinds: tuple[str, ...] = ("grammar_rule", "mistake_pattern")

    def render(self, item: LearningItem) -> Exercise:
        return Exercise(
            self.key,
            (
                "Find and fix the issue:\n"
                '"We need to align priorities before sprint starts."'
            ),
            "We need to align on priorities before the sprint starts.",
            item.text,
            item.explanation,
            [item.id],
        )


@dataclass(frozen=True)
class FollowUpExercise:
    key: str = "follow_up"
    pretty_name: str = "Business/IT follow-up"
    target_item_kinds: tuple[str, ...] = ("word", "expression", "grammar_rule")

    def render(self, item: LearningItem) -> Exercise:
        return Exercise(
            self.key,
            (
                "Reply in 2-3 sentences to a stakeholder who questions the "
                f"timeline. Use: {item.text}"
            ),
            item.text,
            "Acknowledge the concern, then propose a next step.",
            item.explanation,
            [item.id],
        )


EXERCISE_TYPES: dict[str, ExerciseType] = {
    "guess": GuessExercise(),
    "translate": TranslateExercise(),
    "cloze": ClozeExercise(),
    "grammar_rewrite": GrammarRewriteExercise(),
    "error_correction": ErrorCorrectionExercise(),
    "follow_up": FollowUpExercise(),
}


def render_for_item(item: LearningItem, preferred_type: str | None = None) -> Exercise:
    if preferred_type:
        return EXERCISE_TYPES[preferred_type].render(item)
    for exercise_type in EXERCISE_TYPES.values():
        if item.type in exercise_type.target_item_kinds:
            return exercise_type.render(item)
    return EXERCISE_TYPES["follow_up"].render(item)
