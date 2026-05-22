from __future__ import annotations

from fluentloop.db.models import MistakePattern


def hint_ladder_for_pattern(pattern: MistakePattern) -> list[str]:
    examples = pattern.correct_examples or ["Use the corrected pattern."]
    model = examples[-1]
    return [
        f"1. Notice the error type: {pattern.mistake_type}.",
        f"2. Recall the rule: {pattern.description}",
        f"3. Compare with a model: {model}",
        "4. Rewrite without looking at the model.",
    ]


def render_hint_ladder(pattern: MistakePattern) -> str:
    return "\n".join(hint_ladder_for_pattern(pattern))
