from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from fluentloop.llm.tasks import LLMTask


def system_prompt() -> str:
    return (
        "You are FluentLoop's structured JSON generator and senior B2+/C1- "
        "business/IT English teacher. Return JSON only. Prioritize reusable "
        "chunks, collocations, grammar patterns, realistic workplace contexts, "
        "and concise Telegram-friendly teaching."
    )


def user_prompt(
    task: LLMTask, payload: dict[str, Any], schema: type[BaseModel]
) -> str:
    if task == LLMTask.MATERIAL_EXTRACTION:
        return _material_extraction_prompt(payload)
    instruction = _task_instruction(task, payload)
    # Never hand over the JSON Schema itself. Models mirror its shape and
    # answer with {"description": ..., "properties": {...}} instead of the
    # instance; describing the fields plainly avoids the whole class of bug.
    return (
        f"Task: {task.value}\n"
        f"Instruction: {instruction}\n"
        f"Payload: {payload!r}\n"
        f"Return one flat JSON object with exactly these keys:\n"
        f"{_field_lines(schema)}\n"
        "Return the values themselves. Do not wrap them in another key and "
        "do not describe the format."
    )


def _field_lines(schema: type[BaseModel]) -> str:
    lines = []
    for name, field in schema.model_fields.items():
        annotation = getattr(field.annotation, "__name__", str(field.annotation))
        lines.append(f"  {name}: {annotation}")
    return "\n".join(lines)


def _material_extraction_prompt(payload: dict[str, Any]) -> str:
    raw_text = str(payload.get("raw_text", ""))[:12_000]
    material_type = payload.get("type", "other")
    return (
        "Task: material_extraction\n"
        f"Material type: {material_type}\n"
        "Act as a senior B2+/C1 English teacher. Extract trainable targets "
        "from the submitted material only; do not import targets from other "
        "lessons. Treat explicit sections such as Context, Vocabulary/chunks, "
        "Grammar/patterns, Mistakes/teacher feedback, My examples, Article "
        "notes, Meeting transcript, or Homework as strong signals for what to "
        "extract. If the material is substantial, return 20-30 targets. Prefer "
        "reusable chunks, collocations, reporting/grammar patterns, realistic "
        "learner mistakes, and likely L1 transfer risks. Avoid trivial "
        "standalone words.\n"
        "Return JSON exactly as an object with this shape:\n"
        "{\"candidates\":[{\"type\":\"expression|grammar_rule|mistake_pattern\","
        "\"text\":\"...\",\"meaning\":\"...\",\"explanation\":\"...\","
        "\"examples\":[\"...\"],\"tags\":[\"...\"],\"confidence\":0.8}]}\n"
        "Material:\n"
        f"{raw_text}"
    )


def _task_instruction(task: LLMTask, payload: dict[str, Any]) -> str:
    if task == LLMTask.MATERIAL_EXTRACTION:
        material_type = payload.get("type", "other")
        if material_type in {"word_list", "expression_list"}:
            return (
                "Extract the useful submitted items. Keep only trainable words, "
                "expressions, grammar rules, or mistake patterns."
            )
        return (
            "Extract 20-30 trainable targets when the material is substantial. "
            "Prefer reusable chunks, business/IT collocations, grammar rules, "
            "and likely mistake patterns. Avoid trivial standalone words."
        )
    if task == LLMTask.SEED_LESSON_PLAN:
        return (
            "Act as a senior English teacher. Build a 15-minute micro-drill "
            "lesson pool from approved targets: choose topic, goal, teacher "
            "rationale, priorities, and stage instructions. Rank items by "
            "communicative usefulness, B2+/C1 relevance, grammar/mistake risk, "
            "and suitability for active recall."
        )
    if task == LLMTask.ANSWER_CHECK:
        return (
            "Check the answer as a concise teacher. Return verdict plus corrected "
            "answer, what was wrong, why, one practical rule, better variants, "
            "and a tiny micro-drill if useful."
        )
    if task == LLMTask.TONE_FEEDBACK:
        return (
            "Return only a C1-level native rewrite of the learner answer when it "
            "would materially improve idiom, register, or workplace pragmatics. "
            "Do not repeat grammar-error analysis."
        )
    if task == LLMTask.EXERCISE_GENERATION:
        return (
            "Generate concise business/IT English micro-drills that fit the "
            "provided stage, metadata, and target items."
        )
    if task == LLMTask.WORD_CARD:
        return (
            "Build a learner card for one English word or phrase at B2+/C1 "
            "level, business and IT context. Return: a short English "
            "definition (under 12 words, no articles like 'a word that "
            "means'); a natural Russian translation of the phrase itself, not "
            "a description; one example sentence from a workplace or "
            "engineering setting that uses the exact phrase; up to three "
            "synonyms; up to three common collocations. meaning, russian and "
            "example must always be filled; leave only synonyms or "
            "collocations empty if none are natural."
        )
    if task == LLMTask.QUIZ_DISTRACTORS:
        return (
            "Return exactly three wrong answers for a vocabulary quiz. Each must "
            "be a real English word or phrase of the same kind and register as "
            "the target, plausible enough to require knowing the meaning, but "
            "clearly incorrect for the given definition. Never return the target "
            "itself, a synonym of it, or a variant sharing its stem."
        )
    return "Return compact, validated JSON for the requested FluentLoop task."
