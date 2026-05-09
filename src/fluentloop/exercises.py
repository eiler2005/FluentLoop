from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from fluentloop.db.models import LearningItem


def _meaning_hint(item: LearningItem) -> str:
    meaning = (item.meaning or item.explanation or "").strip()
    return f"\n({meaning})" if meaning else ""


@dataclass(frozen=True)
class Exercise:
    exercise_type: str
    prompt: str
    expected_answer: str
    hint: str
    explanation: str
    target_learning_item_ids: list[int]
    metadata: dict[str, object] = field(default_factory=dict)

    def as_dict(self) -> dict:
        payload = {
            "exercise_type": self.exercise_type,
            "prompt": self.prompt,
            "expected_answer": self.expected_answer,
            "hint": self.hint,
            "explanation": self.explanation,
            "target_learning_item_ids": self.target_learning_item_ids,
        }
        if self.metadata:
            payload["metadata"] = self.metadata
            payload.update(self.metadata)
        return payload


class ExerciseType(Protocol):
    key: str
    pretty_name: str
    target_item_kinds: tuple[str, ...]
    mode_tags: tuple[str, ...]
    stage_tags: tuple[str, ...]
    difficulty: str
    writing_weight: int

    def render(self, item: LearningItem) -> Exercise: ...


@dataclass(frozen=True)
class GuessExercise:
    key: str = "guess"
    pretty_name: str = "Guess word/expression"
    target_item_kinds: tuple[str, ...] = ("word", "expression")
    mode_tags: tuple[str, ...] = ("vocab", "review", "mixed")
    stage_tags: tuple[str, ...] = ("controlled_practice", "recap")
    difficulty: str = "B2"
    writing_weight: int = 1

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
    mode_tags: tuple[str, ...] = ("vocab", "review", "mixed")
    stage_tags: tuple[str, ...] = ("controlled_practice",)
    difficulty: str = "B2"
    writing_weight: int = 1

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
    mode_tags: tuple[str, ...] = ("vocab", "grammar", "review", "mixed")
    stage_tags: tuple[str, ...] = ("controlled_practice",)
    difficulty: str = "B2"
    writing_weight: int = 1

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
            prompt + _meaning_hint(item),
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
    mode_tags: tuple[str, ...] = ("grammar", "mistakes", "writing", "mixed")
    stage_tags: tuple[str, ...] = ("grammar_or_mistake_focus", "free_production")
    difficulty: str = "B2+"
    writing_weight: int = 2

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
    mode_tags: tuple[str, ...] = ("grammar", "mistakes", "review", "mixed")
    stage_tags: tuple[str, ...] = ("grammar_or_mistake_focus",)
    difficulty: str = "B2+"
    writing_weight: int = 1

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
    mode_tags: tuple[str, ...] = ("writing", "mixed")
    stage_tags: tuple[str, ...] = ("warmup", "free_production", "recap")
    difficulty: str = "B2+"
    writing_weight: int = 3

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


@dataclass(frozen=True)
class NoticingExercise:
    key: str = "noticing"
    pretty_name: str = "Noticing"
    target_item_kinds: tuple[str, ...] = ("word", "expression", "grammar_rule")
    mode_tags: tuple[str, ...] = ("vocab", "grammar", "mixed")
    stage_tags: tuple[str, ...] = ("input",)
    difficulty: str = "B2"
    writing_weight: int = 1

    def render(self, item: LearningItem) -> Exercise:
        example = item.examples[0] if item.examples else f"We can use {item.text} here."
        return Exercise(
            self.key,
            (
                "Notice the target language:\n"
                f"{item.text}\n"
                f"Example: {example}\n"
                "Write one similar workplace sentence."
            ),
            item.text,
            "Keep the same pattern, but change the situation.",
            item.explanation,
            [item.id],
        )


@dataclass(frozen=True)
class CollocationDrillExercise:
    key: str = "collocation_drill"
    pretty_name: str = "Collocation drill"
    target_item_kinds: tuple[str, ...] = ("word", "expression", "mistake_pattern")
    mode_tags: tuple[str, ...] = ("vocab", "mistakes", "review", "mixed")
    stage_tags: tuple[str, ...] = ("controlled_practice", "grammar_or_mistake_focus")
    difficulty: str = "B2"
    writing_weight: int = 1

    def render(self, item: LearningItem) -> Exercise:
        return Exercise(
            self.key,
            f"Complete the natural business chunk:\nWe need to ____ {item.text}.",
            item.text,
            "Use the full chunk, not a single keyword.",
            item.explanation,
            [item.id],
        )


@dataclass(frozen=True)
class SentenceTransformExercise:
    key: str = "sentence_transform"
    pretty_name: str = "Sentence transform"
    target_item_kinds: tuple[str, ...] = ("expression", "grammar_rule")
    mode_tags: tuple[str, ...] = ("grammar", "writing", "mixed")
    stage_tags: tuple[str, ...] = ("controlled_practice", "grammar_or_mistake_focus")
    difficulty: str = "B2+"
    writing_weight: int = 2

    def render(self, item: LearningItem) -> Exercise:
        return Exercise(
            self.key,
            (
                "Transform this into a more natural workplace sentence.\n"
                '"We need change it now."\n'
                f"Use or reflect: {item.text}"
            ),
            item.text,
            "Keep the meaning, improve the form.",
            item.explanation,
            [item.id],
        )


@dataclass(frozen=True)
class WordFamilyExercise:
    key: str = "word_family"
    pretty_name: str = "Word family"
    target_item_kinds: tuple[str, ...] = ("word",)
    mode_tags: tuple[str, ...] = ("vocab", "review", "mixed")
    stage_tags: tuple[str, ...] = ("controlled_practice",)
    difficulty: str = "B2+"
    writing_weight: int = 1

    def render(self, item: LearningItem) -> Exercise:
        return Exercise(
            self.key,
            f"Use the word in a different form if possible:\n{item.text}",
            item.text,
            "Think noun / verb / adjective forms.",
            item.explanation,
            [item.id],
        )


@dataclass(frozen=True)
class RegisterChoiceExercise:
    key: str = "register_choice"
    pretty_name: str = "Register choice"
    target_item_kinds: tuple[str, ...] = (
        "expression",
        "grammar_rule",
        "mistake_pattern",
    )
    mode_tags: tuple[str, ...] = ("grammar", "writing", "mixed")
    stage_tags: tuple[str, ...] = ("grammar_or_mistake_focus",)
    difficulty: str = "B2+"
    writing_weight: int = 1

    def render(self, item: LearningItem) -> Exercise:
        return Exercise(
            self.key,
            (
                "Choose the more diplomatic version and improve it if needed:\n"
                "A) We must change this now.\n"
                "B) It may be worth adjusting this soon."
            ),
            "It may be worth adjusting this soon.",
            item.text,
            item.explanation or "Register matters in stakeholder communication.",
            [item.id],
        )


@dataclass(frozen=True)
class ChunkBuilderExercise:
    key: str = "chunk_builder"
    pretty_name: str = "Chunk builder"
    target_item_kinds: tuple[str, ...] = ("word", "expression")
    mode_tags: tuple[str, ...] = ("vocab", "writing", "mixed")
    stage_tags: tuple[str, ...] = ("controlled_practice", "free_production")
    difficulty: str = "B2"
    writing_weight: int = 2

    def render(self, item: LearningItem) -> Exercise:
        return Exercise(
            self.key,
            f"Build a short work sentence around this chunk:\n{item.text}",
            item.text,
            "One sentence is enough; make it realistic.",
            item.explanation,
            [item.id],
        )


@dataclass(frozen=True)
class ActiveRecallExercise:
    key: str = "active_recall"
    pretty_name: str = "Active recall"
    target_item_kinds: tuple[str, ...] = ("word", "expression", "grammar_rule")
    mode_tags: tuple[str, ...] = ("review", "mixed")
    stage_tags: tuple[str, ...] = ("recap",)
    difficulty: str = "B2"
    writing_weight: int = 1

    def render(self, item: LearningItem) -> Exercise:
        return Exercise(
            self.key,
            f"Without looking back, recall and use this target:\n{item.text}",
            item.text,
            "Use active recall before checking.",
            item.explanation,
            [item.id],
        )


@dataclass(frozen=True)
class MiniWritingExercise:
    key: str = "mini_writing"
    pretty_name: str = "Mini writing"
    target_item_kinds: tuple[str, ...] = ("word", "expression", "grammar_rule")
    mode_tags: tuple[str, ...] = ("writing", "mixed")
    stage_tags: tuple[str, ...] = ("free_production",)
    difficulty: str = "B2+"
    writing_weight: int = 3

    def render(self, item: LearningItem) -> Exercise:
        return Exercise(
            self.key,
            (
                "Write a 2-3 sentence workplace update.\n"
                f"Use this target naturally: {item.text}"
            ),
            item.text,
            "Context + point + next step.",
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
    "noticing": NoticingExercise(),
    "collocation_drill": CollocationDrillExercise(),
    "sentence_transform": SentenceTransformExercise(),
    "word_family": WordFamilyExercise(),
    "register_choice": RegisterChoiceExercise(),
    "chunk_builder": ChunkBuilderExercise(),
    "active_recall": ActiveRecallExercise(),
    "mini_writing": MiniWritingExercise(),
}


def render_for_item(item: LearningItem, preferred_type: str | None = None) -> Exercise:
    if preferred_type:
        return EXERCISE_TYPES[preferred_type].render(item)
    for exercise_type in EXERCISE_TYPES.values():
        if item.type in exercise_type.target_item_kinds:
            return exercise_type.render(item)
    return EXERCISE_TYPES["follow_up"].render(item)
