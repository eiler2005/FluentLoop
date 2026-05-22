from __future__ import annotations

from typing import Any


def pre_meeting_brief_card(agenda: str) -> dict[str, Any]:
    topic = agenda.strip() or "the meeting"
    return {
        "topic": topic,
        "chunks": [
            "Could we align on the scope?",
            "One constraint we should account for is...",
            "The trade-off, as I see it, is...",
            "It might be worth deciding this today.",
            "Can we close on an owner and next step?",
        ],
        "moves": [
            "open with context",
            "name the risk",
            "soften pushback",
            "close with owner/date",
        ],
        "l1_traps": ["bare imperatives", "too-direct disagreement"],
    }


def article_lab_modules(text: str) -> list[dict[str, str]]:
    source = text.strip() or "paste an article after /article"
    excerpt = source[:500]
    return [
        {
            "name": "Pre-read",
            "task": "Predict the author's position in one sentence.",
        },
        {
            "name": "Vocab pre-teach",
            "task": "Extract 5 reusable chunks and mark their function.",
        },
        {
            "name": "1T cloze",
            "task": "Create 5 cloze prompts where exactly one chunk is missing.",
        },
        {
            "name": "Critical question",
            "task": "Challenge one assumption and support your challenge.",
        },
        {
            "name": "Cold recall",
            "task": f"Summarize without looking back. Source excerpt: {excerpt}",
        },
    ]


def debate_card(topic: str) -> dict[str, Any]:
    subject = topic.strip() or "the current engineering trade-off"
    return {
        "topic": subject,
        "learner_task": "State your position in 2-3 sentences.",
        "bot_role": "argue the opposite position firmly but professionally",
        "score_axes": ["claim clarity", "concession", "counter-argument", "hedging"],
    }


def translation_lab_pack(topic: str) -> dict[str, Any]:
    subject = topic.strip() or "stakeholder communication"
    return {
        "topic": subject,
        "sentences_ru": [
            "Нам нужно согласовать риски до планирования.",
            "Я не уверен, что это выдержит нагрузку в проде.",
            "Давайте зафиксируем владельца и следующий шаг.",
            "Возможно, стоит сначала уменьшить скоуп.",
            "Можем обсудить компромисс по срокам?",
        ],
        "l1_focus": ["articles", "prepositions", "hedging", "word order"],
    }


def fluency432_card(topic: str) -> dict[str, Any]:
    subject = topic.strip() or "a recent project risk"
    return {
        "topic": subject,
        "rounds": [
            {"minutes": 4, "goal": "full version with context"},
            {"minutes": 3, "goal": "same meaning, fewer words"},
            {"minutes": 2, "goal": "crisp executive version"},
        ],
        "success": "meaning preserved while friction and filler go down",
    }
