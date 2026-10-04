"""Portable public syllabus views, with no learner history or reserved questions."""

from __future__ import annotations

import json
from html import escape
from importlib.resources import files
from pathlib import Path

from fluentloop.adaptive_learning import TOPIC_TITLES
from fluentloop.curriculum_b2 import CURRICULUM_LESSONS
from fluentloop.workplace_roadmap import default_plan, load_curriculum

STAGES = {"b2": "B2", "b2_plus": "B2+", "c1_intro": "C1 intro"}
DELIVERY = {
    "mixed": "Вопрос и короткое письмо в боте + самостоятельный сценарий",
    "external": "Вопрос и короткое письмо в боте; аудио и речь — внешняя практика",
    "brief": "Вопрос и короткое письмо в боте + большой самостоятельный сценарий",
}
LESSON_TITLES = {lesson.slug: lesson.title for lesson in CURRICULUM_LESSONS}


def render_roadmap_markdown(catalog: dict) -> str:
    lines = [
        "# " + catalog["title_ru"],
        "",
        "Сгенерировано из `src/fluentloop/seeds/workplace_curriculum_v1.json`.",
        "Правьте источник и запускайте `uv run python scripts/workplace_plan.py "
        "--render docs/curriculum`.",
        "",
        "[Открыть редактор](workplace-planner.html) · "
        "[Как пользоваться](workplace-plan-guide.md) · "
        "[Программа и схемы](learning-programme.md)",
        "",
        "Общий английский — основа; клиентская работа и Big Tech — дополнения. "
        "В новой программе 30% вопросов отведено общей базе, 40% — работе и "
        "поддерживающей языковой практике, 30% — словам и выражениям. "
        "Сохранённый личный план "
        "управляет подбором /study: долей направлений, порядком, фокусом и паузами. "
        "Уже показанный вопрос сохраняется; ступени определяются результатами. "
        "Минуты в неделю — ориентир, а не измеренное время.",
        "",
        "Отдельная часть нового плана отводит 30% вопросов словам, "
        "коллокациям и выражениям: новое значение, контекст и интервальное "
        "повторение. Настройка `lexical_share` уменьшает рабочую долю: "
        "общая + рабочая + лексическая части составляют 100%. "
        "Меняйте через `/roadmap lexical 30` или офлайн-редактор. "
        "Старые экспорты без поля сохраняют лексическую долю 0 до явного изменения. "
        "[Лексическая программа](lexical-programme.md) · "
        "[Банк выражений](lexical-bank.md).",
        "Все 48 модулей имеют короткий вопрос и минимум два письменных варианта "
        "на каждой ступени; шесть рабочих модулей имеют по четыре варианта C1. "
        "Всего 144 вопроса и 300 письменных ситуаций. "
        "Ниже опубликованы большие сценарии самостоятельной практики; "
        "устные навыки текстовый бот не оценивает.",
        "",
        "## Предпосылки",
        "",
        *["- " + value for value in catalog["assumptions_ru"]],
        "",
        "## Карта модулей",
        "",
        "| Модуль | Направление | Навыки | Доступность |",
        "| --- | --- | --- | --- |",
    ]
    for module in catalog["modules"]:
        skills = ", ".join(catalog["skills"][key] for key in module["skills"])
        strand = "Общий английский" if module["strand"] == "general" else "Дополнение"
        title = module["title_ru"].replace("|", "\\|")
        lines.append(
            f"| [{title}](#{module['id']}) | {strand} | {skills} | "
            f"{DELIVERY[module['delivery']]} |"
        )
    source_map = {source["id"]: source for source in catalog["sources"]}
    for module in catalog["modules"]:
        lines.extend(
            [
                "",
                f'<a id="{module["id"]}"></a>',
                "",
                "## " + module["title_ru"],
                "",
                f"ID: `{module['id']}` · {module['area']} · "
                f"{DELIVERY[module['delivery']]}",
                "",
                "Языковой фокус: " + "; ".join(module["language_focus"]) + ".",
            ]
        )
        for stage, title in STAGES.items():
            lines.extend(
                [
                    "",
                    f"### {title}",
                    "",
                    module["outcomes"][stage],
                    "",
                    "**Задание:** " + module["tasks"][stage],
                ]
            )
        lines.extend(["", "**Что проверить в результате:**", ""])
        lines.extend("- " + item for item in module["evidence"])
        lines.extend(
            [
                "",
                "Связанные языковые темы /study: "
                + (
                    ", ".join(TOPIC_TITLES[key] for key in module["adaptive_topics"])
                    or "пока нет прямого соответствия"
                )
                + ". Связь с темой не означает освоения целого модуля.",
                "",
                "Уроки каталога /library: "
                + (
                    ", ".join(LESSON_TITLES[key] for key in module["library_slugs"])
                    or "отдельный урок ещё не опубликован"
                )
                + ". Доступность конкретной подписки проверяется в боте.",
                "",
                "Материалы: "
                + ", ".join(
                    f"[{source_map[key]['title']}]({source_map[key]['url']})"
                    for key in module["source_ids"]
                )
                + ".",
            ]
        )
    lines.extend(["", "## Языковая карта и пробелы", ""])
    for item in catalog["language_map"]:
        lines.extend(
            [
                "### " + item["title_ru"],
                "",
                "- B2: " + item["b2_focus"],
                "- C1 intro: " + item["c1_focus"],
                "- Банк: "
                + (
                    "частичное покрытие"
                    if item["coverage"] == "partial"
                    else "пополнение запланировано"
                ),
                "- Модули: " + ", ".join(f"`{key}`" for key in item["module_ids"]),
                "",
            ]
        )
    lines.extend(["## Источники", ""])
    lines.extend(
        f"- [{source['title']}]({source['url']}) — {source['publisher']}; "
        f"проверено {source['accessed']}."
        for source in catalog["sources"]
    )
    return "\n".join(lines) + "\n"


def _script_json(value: dict) -> str:
    # Keep untrusted text inside the JSON script element, even if it contains HTML.
    return (
        json.dumps(value, ensure_ascii=False)
        .replace("<", "\\u003c")
        .replace("&", "\\u0026")
        .replace("\u2028", "\\u2028")
        .replace("\u2029", "\\u2029")
    )


def render_roadmap_html(catalog: dict) -> str:
    template = (
        files("fluentloop")
        .joinpath("templates/workplace_planner.html")
        .read_text(encoding="utf-8")
    )
    return (
        template.replace("__TITLE__", escape(catalog["title_ru"]))
        .replace("__CATALOG_JSON__", _script_json(catalog))
        .replace("__DEFAULT_PLAN_JSON__", _script_json(default_plan(catalog)))
        .replace("__TOPIC_LABELS_JSON__", _script_json(TOPIC_TITLES))
        .replace("__LESSON_LABELS_JSON__", _script_json(LESSON_TITLES))
    )


def write_roadmap_files(output_dir: str | Path, catalog: dict | None = None) -> dict:
    catalog = catalog or load_curriculum()
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    rendered = {
        "workplace-roadmap.md": render_roadmap_markdown(catalog),
        "workplace-planner.html": render_roadmap_html(catalog),
        "client-work-plan.json": json.dumps(
            default_plan(catalog), ensure_ascii=False, indent=2
        )
        + "\n",
    }
    paths = {}
    for name, content in rendered.items():
        path = output_dir / name
        path.write_text(content, encoding="utf-8")
        paths[name] = path
    return paths
