from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from html import escape
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from fluentloop.curriculum_b2 import CURRICULUM_TAG
from fluentloop.db.models import LessonPlan
from fluentloop.lesson_formats import scenario_cards
from fluentloop.lesson_plans import lesson_items, lesson_steps
from fluentloop.lesson_types import (
    LESSON_TYPES,
    LessonType,
    format_target_mix,
    lesson_type_by_key,
    lesson_type_for_plan,
)

GENERATED_NOTICE = (
    "Generated from FluentLoop DB/code. Do not hand-edit; regenerate with "
    "`scripts/export_lesson_catalog.py`."
)
LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")


@dataclass(frozen=True)
class CatalogLesson:
    source: str
    public_id: str
    title: str
    series_key: str
    series_title: str
    lesson_type: LessonType
    topic: str
    goal: str
    focus: tuple[str, ...]
    target_mix: str
    commands: tuple[str, ...]
    typical_steps: tuple[str, ...]
    target_examples: tuple[str, ...]
    tags: tuple[str, ...] = ()


def build_public_catalog(
    session: Session, *, include_scenarios: bool = True
) -> list[CatalogLesson]:
    lessons = [
        _template_to_catalog(session, plan) for plan in _public_templates(session)
    ]
    if include_scenarios:
        lessons.extend(_scenario_catalog())
    return sorted(
        lessons,
        key=lambda lesson: (
            _series_sort_key(lesson.series_key),
            lesson.lesson_type.title.casefold(),
            lesson.title.casefold(),
        ),
    )


def render_catalog_files(
    lessons: Iterable[CatalogLesson], *, html: bool = True
) -> dict[str, str]:
    catalog = list(lessons)
    files = {
        "index.md": _render_index_md(catalog),
        "lesson-types.md": _render_lesson_types_md(),
        "b2-b2plus-seed.md": _render_series_md(
            catalog, "b2-b2plus-seed", "B2/B2+ Seed Lessons"
        ),
        "english-for-tech.md": _render_series_md(
            catalog, "english-for-tech", "English for Tech"
        ),
        "scenarios.md": _render_series_md(
            catalog, "scenarios", "Business/IT Scenarios"
        ),
    }
    if html:
        for name, content in list(files.items()):
            html_name = name.removesuffix(".md") + ".html"
            files[html_name] = _render_html(content, title=_title_for_file(name))
    return files


def write_public_catalog(
    session: Session, out_dir: Path, *, html: bool = True
) -> dict[str, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    files = render_catalog_files(build_public_catalog(session), html=html)
    written: dict[str, Path] = {}
    for relative_path, content in files.items():
        path = out_dir / relative_path
        path.write_text(content, encoding="utf-8")
        written[relative_path] = path
    return written


def _public_templates(session: Session) -> list[LessonPlan]:
    return list(
        session.scalars(
            select(LessonPlan)
            .where(
                LessonPlan.is_template.is_(True),
                LessonPlan.status.in_(("active", "draft")),
            )
            .order_by(LessonPlan.title.asc(), LessonPlan.id.asc())
        )
    )


def _template_to_catalog(session: Session, plan: LessonPlan) -> CatalogLesson:
    items = lesson_items(session, plan)
    steps = lesson_steps(session, plan)
    lesson_type = lesson_type_for_plan(plan, items)
    series_key, series_title = _series_for_plan(plan)
    return CatalogLesson(
        source="template",
        public_id=str(plan.id),
        title=plan.title,
        series_key=series_key,
        series_title=series_title,
        lesson_type=lesson_type,
        topic=plan.topic,
        goal=plan.goal,
        focus=tuple((plan.language_focus_json or [])[:8]),
        target_mix=format_target_mix(items),
        commands=(f"/subscribe {plan.id}", "/lesson <id>", "/today"),
        typical_steps=tuple(step.title for step in steps[:8]),
        target_examples=tuple(item.text for item in items[:10]),
        tags=tuple(plan.tags_json or ()),
    )


def _scenario_catalog() -> list[CatalogLesson]:
    lesson_type = lesson_type_by_key("scenario")
    lessons: list[CatalogLesson] = []
    for index, card in enumerate(scenario_cards(), start=1):
        lessons.append(
            CatalogLesson(
                source="scenario",
                public_id=card["id"],
                title=card["setting"],
                series_key="scenarios",
                series_title="Business/IT Scenarios",
                lesson_type=lesson_type,
                topic="Scenario rehearsal",
                goal="Rehearse a high-stakes workplace conversation.",
                focus=tuple(card["tasks"]),
                target_mix="scenario card",
                commands=(f"/scene {index}", "/practice diplomatic", "/brief <agenda>"),
                typical_steps=("set roles", "state constraints", "land next step"),
                target_examples=tuple(card["target_chunks"]),
                tags=("scenario", "business-it"),
            )
        )
    return lessons


def _series_for_plan(plan: LessonPlan) -> tuple[str, str]:
    tags = tuple(plan.tags_json or ())
    if "series:english-for-tech" in tags:
        return "english-for-tech", "English for Tech"
    if CURRICULUM_TAG in tags:
        return "b2-b2plus-seed", "B2/B2+ Seed Lessons"
    for tag in tags:
        if tag.startswith("series:"):
            slug = tag.removeprefix("series:").strip() or "shared-library"
            return slug, slug.replace("-", " ").title()
    return "shared-library", "Shared Lesson Library"


def _render_index_md(lessons: list[CatalogLesson]) -> str:
    by_series = _group_by_series(lessons)
    lines = [
        "# FluentLoop Public Lesson Catalog",
        "",
        f"> {GENERATED_NOTICE}",
        "",
        "This catalog shows public learning surfaces only: shared lesson "
        "templates and code-defined scenario cards. Private uploads, raw source "
        "texts, user answers, reflections, and PDFs are not exported.",
        "",
        "## Browse",
        "",
        "- [Lesson types](lesson-types.md)",
        "- [B2/B2+ seed lessons](b2-b2plus-seed.md)",
        "- [English for Tech](english-for-tech.md)",
        "- [Business/IT scenarios](scenarios.md)",
        "",
        "## Public surfaces",
        "",
    ]
    for _series_key, series_lessons in by_series.items():
        series_title = series_lessons[0].series_title
        lines.append(f"### {series_title}")
        lines.append("")
        for lesson in series_lessons:
            command = lesson.commands[0] if lesson.commands else "-"
            lines.append(
                f"- **{lesson.title}** ({lesson.lesson_type.title}) - "
                f"`{command}` - {lesson.goal}"
            )
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _render_lesson_types_md() -> str:
    lines = [
        "# FluentLoop Lesson Types",
        "",
        f"> {GENERATED_NOTICE}",
        "",
        "Lesson Type is the learner-facing layer that connects material, "
        "practice mode, exercises, feedback, SRS, and outcomes.",
        "",
        "| Type | Goal | When to use | Commands | Metrics | Next modes |",
        "|---|---|---|---|---|---|",
    ]
    for lesson_type in LESSON_TYPES:
        commands = ", ".join(f"`{command}`" for command in lesson_type.commands)
        next_modes = ", ".join(
            f"`{mode}`" for mode in lesson_type.recommended_next_modes
        )
        lines.append(
            "| "
            f"{lesson_type.title} | "
            f"{lesson_type.goal} | "
            f"{lesson_type.when_to_use} | "
            f"{commands or '-'} | "
            f"{', '.join(lesson_type.metrics) or '-'} | "
            f"{next_modes or '-'} |"
        )
    return "\n".join(lines).rstrip() + "\n"


def _render_series_md(
    lessons: list[CatalogLesson], series_key: str, title: str
) -> str:
    selected = [lesson for lesson in lessons if lesson.series_key == series_key]
    lines = [
        f"# {title}",
        "",
        f"> {GENERATED_NOTICE}",
        "",
    ]
    if not selected:
        lines.append("No public lessons in this series yet.")
        return "\n".join(lines).rstrip() + "\n"

    grouped = _group_by_type(selected)
    for type_title, type_lessons in grouped.items():
        lines.append(f"## {type_title}")
        lines.append("")
        for lesson in type_lessons:
            lines.extend(_render_lesson_md(lesson))
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _render_lesson_md(lesson: CatalogLesson) -> list[str]:
    lines = [
        f"### {lesson.title}",
        "",
        f"- Public id: `{lesson.public_id}`",
        f"- Lesson type: {lesson.lesson_type.title}",
        f"- Topic: {lesson.topic}",
        f"- Goal: {lesson.goal}",
        f"- Target mix: {lesson.target_mix}",
        f"- Commands: {', '.join(f'`{command}`' for command in lesson.commands)}",
    ]
    if lesson.focus:
        lines.append(f"- Focus: {', '.join(lesson.focus)}")
    if lesson.typical_steps:
        lines.append(f"- Typical steps: {', '.join(lesson.typical_steps)}")
    if lesson.target_examples:
        lines.append(f"- Sample targets: {', '.join(lesson.target_examples)}")
    return lines


def _render_html(markdown: str, *, title: str) -> str:
    body_lines = []
    in_list = False
    for raw_line in markdown.splitlines():
        line = raw_line.rstrip()
        if not line:
            if in_list:
                body_lines.append("</ul>")
                in_list = False
            continue
        if line.startswith("# "):
            if in_list:
                body_lines.append("</ul>")
                in_list = False
            body_lines.append(f"<h1>{_inline_md(line[2:])}</h1>")
        elif line.startswith("## "):
            if in_list:
                body_lines.append("</ul>")
                in_list = False
            body_lines.append(f"<h2>{_inline_md(line[3:])}</h2>")
        elif line.startswith("### "):
            if in_list:
                body_lines.append("</ul>")
                in_list = False
            body_lines.append(f"<h3>{_inline_md(line[4:])}</h3>")
        elif line.startswith("- "):
            if not in_list:
                body_lines.append("<ul>")
                in_list = True
            body_lines.append(f"<li>{_inline_md(line[2:])}</li>")
        elif line.startswith("> "):
            if in_list:
                body_lines.append("</ul>")
                in_list = False
            body_lines.append(f"<blockquote>{_inline_md(line[2:])}</blockquote>")
        elif line.startswith("|"):
            if in_list:
                body_lines.append("</ul>")
                in_list = False
            body_lines.append(f"<pre>{escape(line)}</pre>")
        else:
            if in_list:
                body_lines.append("</ul>")
                in_list = False
            body_lines.append(f"<p>{_inline_md(line)}</p>")
    if in_list:
        body_lines.append("</ul>")
    return _html_shell(title, "\n".join(body_lines))


def _html_shell(title: str, body: str) -> str:
    nav = (
        '<nav><a href="index.html">Catalog</a><a href="lesson-types.html">'
        'Lesson types</a><a href="b2-b2plus-seed.html">B2/B2+</a>'
        '<a href="english-for-tech.html">English for Tech</a>'
        '<a href="scenarios.html">Scenarios</a></nav>'
    )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape(title)}</title>
  <style>
    :root {{ color-scheme: light; --blue:#1559c7; --green:#187533; }}
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      margin: 0; color: #121826; background: #fff; line-height: 1.55; }}
    main {{ max-width: 980px; margin: 0 auto; padding: 32px 20px 56px; }}
    nav {{ display: flex; flex-wrap: wrap; gap: 12px; padding: 16px 20px;
      border-bottom: 1px solid #d7e1ef; background: #f7fbff; }}
    nav a {{ color: var(--blue); text-decoration: none; font-weight: 650; }}
    h1 {{ font-size: clamp(2rem, 4vw, 3.4rem); margin: 18px 0 12px; }}
    h2 {{ margin-top: 36px; color: var(--blue); }}
    h3 {{ margin-top: 24px; color: var(--green); }}
    blockquote {{ border-left: 4px solid var(--blue); margin: 18px 0;
      padding: 8px 14px; background: #f7fbff; }}
    code {{ background: #eef4ff; padding: 2px 6px; border-radius: 5px; }}
    li {{ margin: 7px 0; }}
    pre {{ white-space: pre-wrap; overflow-x: auto; background: #f7fbff;
      border: 1px solid #d7e1ef; padding: 10px; border-radius: 8px; }}
  </style>
</head>
<body>
{nav}
<main>
{body}
</main>
</body>
</html>
"""


def _inline_md(text: str) -> str:
    escaped = _replace_links(text)
    escaped = _replace_inline_code(escaped)
    return _replace_bold(escaped)


def _replace_links(text: str) -> str:
    rendered: list[str] = []
    cursor = 0
    for match in LINK_RE.finditer(text):
        rendered.append(escape(text[cursor : match.start()]))
        label, href = match.groups()
        rendered.append(
            f'<a href="{escape(href, quote=True)}">{escape(label)}</a>'
        )
        cursor = match.end()
    rendered.append(escape(text[cursor:]))
    return "".join(rendered)


def _replace_inline_code(text: str) -> str:
    parts = text.split("`")
    if len(parts) == 1:
        return text
    rendered: list[str] = []
    for index, part in enumerate(parts):
        rendered.append(f"<code>{part}</code>" if index % 2 else part)
    return "".join(rendered)


def _replace_bold(text: str) -> str:
    parts = text.split("**")
    if len(parts) == 1:
        return text
    rendered: list[str] = []
    for index, part in enumerate(parts):
        rendered.append(f"<strong>{part}</strong>" if index % 2 else part)
    return "".join(rendered)


def _group_by_series(lessons: list[CatalogLesson]) -> dict[str, list[CatalogLesson]]:
    grouped: dict[str, list[CatalogLesson]] = {}
    for lesson in lessons:
        grouped.setdefault(lesson.series_key, []).append(lesson)
    return grouped


def _group_by_type(lessons: list[CatalogLesson]) -> dict[str, list[CatalogLesson]]:
    grouped: dict[str, list[CatalogLesson]] = {}
    for lesson in lessons:
        grouped.setdefault(lesson.lesson_type.title, []).append(lesson)
    return grouped


def _series_sort_key(series_key: str) -> tuple[int, str]:
    order = {
        "b2-b2plus-seed": 0,
        "english-for-tech": 1,
        "scenarios": 2,
        "shared-library": 3,
    }
    return order.get(series_key, 99), series_key


def _title_for_file(name: str) -> str:
    return {
        "index.md": "FluentLoop Public Lesson Catalog",
        "lesson-types.md": "FluentLoop Lesson Types",
        "b2-b2plus-seed.md": "B2/B2+ Seed Lessons",
        "english-for-tech.md": "English for Tech",
        "scenarios.md": "Business/IT Scenarios",
    }.get(name, "FluentLoop Catalog")
