"""Deterministic, public views of the reviewed lexical bank; no learner state."""

from __future__ import annotations

from collections import Counter
from html import escape
from pathlib import Path

STAGES = {"b2": "B2", "b2_plus": "B2+", "c1_intro": "C1 intro"}


def markdown_bank(bank: dict) -> str:
    counts = Counter(entry["strand"] for entry in bank["entries"])
    lines = [
        "# Слова и выражения FluentLoop",
        "",
        f"{len(bank['entries'])} значений · {len(bank['functions'])} функций · "
        f"работа: {counts['work']} · общий английский: {counts['general']}.",
        "",
        "Это отдельные **30% учебных вопросов**: новые значения и интервальное "
        "повторение. Ещё 30% — общий английский, "
        "40% — рабочие темы и языковая практика.",
        "",
        "[Учебный план](lexical-programme.md) · "
        "[Поиск и фильтры в HTML](lexical-bank.html) · "
        "[Исследование](../research/workplace-lexical-learning.md) · "
        "[Как обновить банк](../runbooks/lexical-learning.md)",
        "",
        "Редактируй [исходный JSON]"
        "(../../src/fluentloop/seeds/workplace_lexicon_v1.json). "
        "Этот каталог генерируется командой `uv run python scripts/lexical_bank.py "
        "--render docs/curriculum`. В JSON также лежат два вопроса на узнавание "
        "и две ситуации для письма на каждое значение.",
        "",
        "B2/B2+/C1 intro обозначают сложность учебной задачи. Одно выражение не "
        "подтверждает уровень CEFR. Ссылки помогают проверить употребление; "
        "примеры и упражнения написаны для FluentLoop.",
    ]
    for function in bank["functions"]:
        entries = [e for e in bank["entries"] if e["function_id"] == function["id"]]
        lines.extend(["", f"## {function['title_ru']}", ""])
        for entry in entries:
            lines.extend(
                [
                    f"### {entry['headword']} · {STAGES[entry['stage']]}",
                    "",
                    f"`{entry['id']}` · модули: {', '.join(entry['module_ids'])}",
                    "",
                    f"**Значение:** {entry['meaning_ru']}. {entry['meaning_en']}",
                    "",
                    f"**Пример:** {entry['example']}",
                    "",
                    f"**Форма:** {entry['grammar']}",
                    "",
                    f"**Регистр:** {entry['register']}",
                    "",
                    f"**Простая альтернатива:** {entry['plain_alternative']}",
                    "",
                    "**Применить самостоятельно:** "
                    + " / ".join(p["prompt"] for p in entry["production_prompts"]),
                    "",
                    "**Источники:** "
                    + ", ".join(
                        f"[словарь {i + 1}]({url})"
                        for i, url in enumerate(entry["source_urls"])
                    ),
                    "",
                ]
            )
    return "\n".join(lines).rstrip() + "\n"


def html_bank(bank: dict) -> str:
    functions = {f["id"]: f for f in bank["functions"]}
    cards = []
    for entry in bank["entries"]:
        fields = "".join(
            f"<dt>{label}</dt><dd>{escape(entry[field])}</dd>"
            for field, label in (
                ("meaning_en", "English meaning"),
                ("example", "Пример"),
                ("grammar", "Форма"),
                ("register", "Регистр"),
                ("plain_alternative", "Проще"),
            )
        )
        production = "".join(
            f"<li>{escape(p['prompt'])}</li>" for p in entry["production_prompts"]
        )
        sources = " · ".join(
            f'<a href="{escape(url, quote=True)}" target="_blank" '
            f'rel="noopener noreferrer">Словарь {i + 1}</a>'
            for i, url in enumerate(entry["source_urls"])
        )
        cards.append(
            f'<details class="card" data-strand="{entry["strand"]}" '
            f'data-stage="{entry["stage"]}">'
            f"<summary><strong>{escape(entry['headword'])}</strong>"
            f"<span>{escape(entry['meaning_ru'])}</span>"
            f"<small>{STAGES[entry['stage']]} · "
            f"{escape(functions[entry['function_id']]['title_ru'])}</small></summary>"
            f"<dl>{fields}</dl><h3>Применить в своём письме</h3><ol>{production}</ol>"
            f'<p>{sources}</p><p class="muted">ID: {entry["id"]} · '
            f"{', '.join(entry['module_ids'])}</p></details>"
        )
    template = Path(__file__).parent / "templates" / "lexical_bank.html"
    return template.read_text(encoding="utf-8").replace(
        "__LEXICAL_CARDS__", "\n".join(cards)
    )


def public_views(bank: dict) -> dict[str, str]:
    return {
        "lexical-bank.md": markdown_bank(bank),
        "lexical-bank.html": html_bank(bank),
    }
