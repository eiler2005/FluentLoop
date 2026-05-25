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


@dataclass(frozen=True)
class LessonTypeExample:
    lesson_type_key: str
    title: str
    source_kind: str
    source_title: str
    why: str
    idea: str
    when: str
    targets: tuple[str, ...]
    practice_sample: tuple[str, ...]
    good_answer: str
    telegram_path: str
    source_href: str = ""


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
        "examples-by-type.md": _render_examples_by_type_md(catalog),
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
            if name == "index.md":
                files[html_name] = _render_index_html(catalog)
            elif name == "lesson-types.md":
                files[html_name] = _render_lesson_types_html()
            elif name == "examples-by-type.md":
                files[html_name] = _render_examples_by_type_html(
                    build_lesson_type_examples(catalog)
                )
            elif name == "b2-b2plus-seed.md":
                files[html_name] = _render_series_html(
                    catalog, "b2-b2plus-seed", "B2/B2+ Seed Lessons"
                )
            elif name == "english-for-tech.md":
                files[html_name] = _render_series_html(
                    catalog, "english-for-tech", "English for Tech"
                )
            elif name == "scenarios.md":
                files[html_name] = _render_series_html(
                    catalog, "scenarios", "Business/IT Scenarios"
                )
            else:
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
        "- [Examples by type](examples-by-type.md)",
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
            lesson_link = f"{lesson.series_key}.md#{_anchor_for(lesson.title)}"
            lines.append(
                f"- **[{lesson.title}]({lesson_link})** "
                f"({lesson.lesson_type.title}) - "
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


def _render_index_html(catalog: list[CatalogLesson]) -> str:
    by_series = _group_by_series(catalog)
    templates = [lesson for lesson in catalog if lesson.source == "template"]
    scenarios = [lesson for lesson in catalog if lesson.source == "scenario"]
    body = [
        '<section class="hero-panel">',
        '<div class="hero-copy">',
        '<p class="kicker">Public catalog</p>',
        "<h1>FluentLoop lesson catalog</h1>",
        "<p>",
        "A browseable view of public learning surfaces: shared templates, "
        "lesson-type examples, and business/IT scenario cards.",
        "</p>",
        "</div>",
        '<div class="hero-aside">',
        "<strong>Privacy boundary</strong>",
        "<span>Private uploads, raw source texts, answers, reflections, and PDFs "
        "are excluded from this export.</span>",
        "</div>",
        "</section>",
        '<section class="metric-row">',
        _metric_card("Public templates", str(len(templates)), "Subscribable lessons"),
        _metric_card("Scenario cards", str(len(scenarios)), "Roleplay surfaces"),
        _metric_card("Lesson types", str(len(LESSON_TYPES)), "Full taxonomy"),
        _metric_card("Guide pages", "5", "Catalog, types, examples, series"),
        "</section>",
        '<section class="section-block">',
        '<div class="section-header">',
        '<p class="kicker">Where to start</p>',
        "<h2>Navigation guide</h2>",
        "<p>Use these pages as an executive map before opening individual lessons.</p>",
        "</div>",
        '<div class="link-grid">',
        _nav_tile(
            "Examples by type",
            "Human-readable examples for every lesson type.",
            "examples-by-type.html",
        ),
        _nav_tile(
            "Lesson types",
            "The training taxonomy: intent, commands, metrics, next modes.",
            "lesson-types.html",
        ),
        _nav_tile(
            "B2/B2+ seed lessons",
            "Core business/IT templates for communication and production.",
            "b2-b2plus-seed.html",
        ),
        _nav_tile(
            "English for Tech",
            "Curated tech-English series with role, workflow, and interview topics.",
            "english-for-tech.html",
        ),
        _nav_tile(
            "Scenarios",
            "Roleplay cards for meetings, escalation, reviews, and negotiation.",
            "scenarios.html",
        ),
        "</div>",
        "</section>",
        '<section class="section-block">',
        '<div class="section-header">',
        '<p class="kicker">Public surfaces</p>',
        "<h2>Library overview</h2>",
        "<p>Each row links to the detailed HTML series page and keeps the "
        "Telegram entry point visible.</p>",
        "</div>",
        '<div class="series-overview">',
    ]
    for series_key, series_lessons in by_series.items():
        series_title = series_lessons[0].series_title
        series_href = f"{series_key}.html"
        body.extend(
            [
                '<article class="overview-card">',
                '<div class="card-heading-row">',
                f'<h3><a href="{escape(series_href, quote=True)}">'
                f"{escape(series_title)}</a></h3>",
                f"<span>{len(series_lessons)} items</span>",
                "</div>",
                '<div class="compact-list">',
            ]
        )
        for lesson in series_lessons:
            body.append(_compact_lesson_row(lesson))
        body.extend(["</div>", "</article>"])
    body.extend(["</div>", "</section>"])
    return _report_html_shell("FluentLoop Public Lesson Catalog", "\n".join(body))


def _render_lesson_types_html() -> str:
    body = [
        '<section class="hero-panel">',
        '<div class="hero-copy">',
        '<p class="kicker">Learning architecture</p>',
        "<h1>FluentLoop lesson types</h1>",
        "<p>",
        "A lesson type is the user-facing contract for what a session trains, "
        "which command starts it, what evidence proves progress, and where the "
        "learner should go next.",
        "</p>",
        "</div>",
        '<div class="hero-aside">',
        "<strong>How to read this</strong>",
        "<span>Think of each type as a training lane: input, practice mode, "
        "exercise shape, feedback, and metric.</span>",
        "</div>",
        "</section>",
        '<section class="metric-row">',
        _metric_card("Types", str(len(LESSON_TYPES)), "Learner-facing lanes"),
        _metric_card("Practice modes", "13", "Mapped from command registry"),
        _metric_card("Evidence", "Metrics", "Retention, production, L1, outcomes"),
        _metric_card("Next step", "Guided", "Every type points to a follow-up loop"),
        "</section>",
        '<section class="section-block">',
        '<div class="section-header">',
        '<p class="kicker">Portfolio view</p>',
        "<h2>Training taxonomy</h2>",
        "<p>Each card answers four questions: what it trains, when it matters, "
        "how to start, and how progress shows up.</p>",
        "</div>",
        '<div class="type-grid">',
    ]
    for lesson_type in LESSON_TYPES:
        body.append(_lesson_type_card(lesson_type))
    body.extend(
        [
            "</div>",
            "</section>",
            '<section class="section-block">',
            '<div class="section-header">',
            '<p class="kicker">Dense reference</p>',
            "<h2>Command and evidence matrix</h2>",
            "<p>A compact table for scanning commands and metrics after the "
            "portfolio view.</p>",
            "</div>",
            _lesson_type_matrix(),
            "</section>",
        ]
    )
    return _report_html_shell("FluentLoop Lesson Types", "\n".join(body))


def _render_series_html(
    catalog: list[CatalogLesson], series_key: str, title: str
) -> str:
    selected = [lesson for lesson in catalog if lesson.series_key == series_key]
    grouped = _group_by_type(selected)
    template_count = len([lesson for lesson in selected if lesson.source == "template"])
    scenario_count = len([lesson for lesson in selected if lesson.source == "scenario"])
    type_count = len(grouped)
    body = [
        '<section class="hero-panel">',
        '<div class="hero-copy">',
        '<p class="kicker">Public series</p>',
        f"<h1>{escape(title)}</h1>",
        "<p>",
        _series_intro(series_key),
        "</p>",
        "</div>",
        '<div class="hero-aside">',
        "<strong>How to use</strong>",
        "<span>Open a card to inspect targets, then use the Telegram command to "
        "subscribe or start a scenario.</span>",
        "</div>",
        "</section>",
        '<section class="metric-row">',
        _metric_card("Items", str(len(selected)), "Public entries"),
        _metric_card("Lesson types", str(type_count), "Training categories"),
        _metric_card("Templates", str(template_count), "Clone-on-subscribe"),
        _metric_card("Scenarios", str(scenario_count), "Roleplay cards"),
        "</section>",
    ]
    if not selected:
        body.append('<p class="empty-state">No public lessons in this series yet.</p>')
        return _report_html_shell(title, "\n".join(body))

    for type_title, type_lessons in grouped.items():
        body.extend(
            [
                '<section class="section-block">',
                '<div class="section-header">',
                '<p class="kicker">Lesson group</p>',
                f"<h2>{escape(type_title)}</h2>",
                f"<p>{len(type_lessons)} public entries in this group.</p>",
                "</div>",
                '<div class="lesson-grid">',
            ]
        )
        for lesson in type_lessons:
            body.append(_lesson_card(lesson))
        body.extend(["</div>", "</section>"])
    return _report_html_shell(title, "\n".join(body))


def _lesson_type_card(lesson_type: LessonType) -> str:
    return (
        '<article class="type-card">'
        f'<div class="card-index">{escape(lesson_type.key)}</div>'
        f"<h3>{escape(lesson_type.title)}</h3>"
        f"<p>{escape(lesson_type.goal)}</p>"
        '<dl class="mini-facts">'
        "<dt>When to use</dt>"
        f"<dd>{escape(lesson_type.when_to_use)}</dd>"
        "<dt>Commands</dt>"
        f"<dd>{_inline_code_list(lesson_type.commands)}</dd>"
        "<dt>Evidence</dt>"
        f"<dd>{escape(', '.join(lesson_type.metrics) or '-')}</dd>"
        "<dt>Next loop</dt>"
        f"<dd>{_inline_code_list(lesson_type.recommended_next_modes)}</dd>"
        "</dl>"
        "</article>"
    )


def _lesson_type_matrix() -> str:
    rows = [
        "<tr>"
        "<th>Type</th>"
        "<th>Training job</th>"
        "<th>Commands</th>"
        "<th>Evidence</th>"
        "<th>Next modes</th>"
        "</tr>"
    ]
    for lesson_type in LESSON_TYPES:
        rows.append(
            "<tr>"
            f"<td><strong>{escape(lesson_type.title)}</strong></td>"
            f"<td>{escape(lesson_type.goal)}</td>"
            f"<td>{_inline_code_list(lesson_type.commands)}</td>"
            f"<td>{escape(', '.join(lesson_type.metrics) or '-')}</td>"
            f"<td>{_inline_code_list(lesson_type.recommended_next_modes)}</td>"
            "</tr>"
        )
    return f'<div class="table-wrap"><table>{"".join(rows)}</table></div>'


def _lesson_card(lesson: CatalogLesson) -> str:
    command = lesson.commands[0] if lesson.commands else "-"
    command_html = _inline_code_list(lesson.commands)
    details = [
        ("Public id", lesson.public_id),
        ("Type", lesson.lesson_type.title),
        ("Topic", lesson.topic),
        ("Target mix", lesson.target_mix),
    ]
    if lesson.focus:
        details.append(("Focus", ", ".join(lesson.focus)))
    return (
        f'<article class="lesson-card" id="{_anchor_for(lesson.title)}">'
        '<div class="card-heading-row">'
        f"<h3>{escape(lesson.title)}</h3>"
        f"<span>{escape(command)}</span>"
        "</div>"
        f"<p>{escape(lesson.goal)}</p>"
        f"{_detail_grid(details)}"
        f"{_chip_section('Practice steps', lesson.typical_steps)}"
        f"{_chip_section('Sample targets', lesson.target_examples)}"
        f'<p class="command-line">Telegram path: {command_html}</p>'
        "</article>"
    )


def _compact_lesson_row(lesson: CatalogLesson) -> str:
    command = lesson.commands[0] if lesson.commands else "-"
    href = f"{lesson.series_key}.html#{_anchor_for(lesson.title)}"
    return (
        '<div class="compact-row">'
        "<div>"
        f'<a href="{escape(href, quote=True)}">{escape(lesson.title)}</a>'
        f"<span>{escape(lesson.lesson_type.title)} · {escape(lesson.goal)}</span>"
        "</div>"
        f"<code>{escape(command)}</code>"
        "</div>"
    )


def _metric_card(label: str, value: str, note: str) -> str:
    return (
        '<div class="metric-card">'
        f"<span>{escape(label)}</span>"
        f"<strong>{escape(value)}</strong>"
        f"<em>{escape(note)}</em>"
        "</div>"
    )


def _nav_tile(title: str, description: str, href: str) -> str:
    return (
        f'<a class="nav-tile" href="{escape(href, quote=True)}">'
        f"<strong>{escape(title)}</strong>"
        f"<span>{escape(description)}</span>"
        "</a>"
    )


def _detail_grid(items: list[tuple[str, str]]) -> str:
    rows = []
    for label, value in items:
        rows.append(
            "<div>"
            f"<dt>{escape(label)}</dt>"
            f"<dd>{escape(value)}</dd>"
            "</div>"
        )
    return f'<dl class="detail-grid">{"".join(rows)}</dl>'


def _chip_section(label: str, items: tuple[str, ...]) -> str:
    if not items:
        return ""
    chips = "".join(f"<li>{escape(item)}</li>" for item in items)
    return (
        '<div class="chip-section">'
        f"<h4>{escape(label)}</h4>"
        f'<ul class="pill-list">{chips}</ul>'
        "</div>"
    )


def _inline_code_list(items: tuple[str, ...]) -> str:
    if not items:
        return "-"
    return ", ".join(f"<code>{escape(item)}</code>" for item in items)


def _series_intro(series_key: str) -> str:
    intros = {
        "b2-b2plus-seed": (
            "Deterministic B2/B2+ business and IT lessons. Use them as the "
            "baseline library for vocabulary, grammar, diplomacy, reading, and "
            "writing practice."
        ),
        "english-for-tech": (
            "Owner-curated English for Tech lessons covering roles, workflows, "
            "tools, interviews, and practical communication in software teams."
        ),
        "scenarios": (
            "Business/IT roleplay cards for meetings, escalations, interviews, "
            "architecture decisions, and difficult workplace conversations."
        ),
    }
    return intros.get(
        series_key,
        "Public shared-library lessons exported from FluentLoop DB/code.",
    )


def build_lesson_type_examples(
    lessons: Iterable[CatalogLesson],
) -> list[LessonTypeExample]:
    catalog_by_title = {lesson.title: lesson for lesson in lessons}
    examples: list[LessonTypeExample] = []
    for spec in _LESSON_TYPE_EXAMPLE_SPECS:
        lesson = catalog_by_title.get(spec.source_title)
        source_title = spec.source_title
        source_href = spec.source_href
        telegram_path = spec.telegram_path
        if lesson is not None and spec.source_kind.startswith("public"):
            source_title = f"{lesson.series_title}: {lesson.title}"
            source_href = f"{lesson.series_key}.md#{_anchor_for(lesson.title)}"
            if lesson.commands:
                telegram_path = lesson.commands[0]
        examples.append(
            LessonTypeExample(
                lesson_type_key=spec.lesson_type_key,
                title=spec.title,
                source_kind=spec.source_kind,
                source_title=source_title,
                why=spec.why,
                idea=spec.idea,
                when=spec.when,
                targets=spec.targets,
                practice_sample=spec.practice_sample,
                good_answer=spec.good_answer,
                telegram_path=telegram_path,
                source_href=source_href,
            )
        )
    return examples


def _render_examples_by_type_md(lessons: list[CatalogLesson]) -> str:
    examples = build_lesson_type_examples(lessons)
    by_type = _group_examples_by_type(examples)
    lines = [
        "# FluentLoop Examples by Lesson Type",
        "",
        f"> {GENERATED_NOTICE}",
        "",
        "Этот guide показывает, как разные Lesson Types выглядят для пользователя: "
        "зачем нужен урок, в чем идея тренировки, какие targets он поднимает и "
        "какой ответ считается сильным.",
        "",
        "## Executive map",
        "",
        "| Type | Examples | What the type proves |",
        "|---|---|---|",
    ]
    for lesson_type in LESSON_TYPES:
        type_examples = by_type[lesson_type.key]
        links = ", ".join(
            f"[{example.title}](#{_anchor_for(example.title)})"
            for example in type_examples
        )
        lines.append(
            f"| {lesson_type.title} | {links} | {lesson_type.goal} |"
        )

    lines.extend(["", "## Compact examples", ""])
    for lesson_type in LESSON_TYPES:
        commands = ", ".join(f"`{command}`" for command in lesson_type.commands)
        lines.extend(
            [
                f"### {lesson_type.title}",
                "",
                f"- What it trains: {lesson_type.goal}",
                f"- When to use: {lesson_type.when_to_use}",
                f"- Commands: {commands or '-'}",
                "",
            ]
        )
        for example in by_type[lesson_type.key]:
            lines.extend(_render_lesson_type_example_md(example))
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _render_lesson_type_example_md(example: LessonTypeExample) -> list[str]:
    return [
        f"#### {example.title}",
        "",
        f"- Source: {_example_source_md(example)}",
        f"- Telegram path: `{example.telegram_path}`",
        f"- Why this lesson exists: {example.why}",
        f"- Core idea: {example.idea}",
        f"- When to use: {example.when}",
        f"- Targets: {', '.join(example.targets)}",
        "- Practice sample:",
        *[f"  - {item}" for item in example.practice_sample],
        "- Good answer:",
        "",
        "```text",
        example.good_answer,
        "```",
    ]


def _example_source_md(example: LessonTypeExample) -> str:
    label = f"{example.source_kind}: {example.source_title}"
    if example.source_href:
        return f"[{label}]({example.source_href})"
    return label


def _render_examples_by_type_html(examples: list[LessonTypeExample]) -> str:
    by_type = _group_examples_by_type(examples)
    demo_count = len(
        [example for example in examples if example.source_kind == "demo card"]
    )
    template_count = len(examples) - demo_count
    body: list[str] = [
        '<section class="hero-panel">',
        '<div class="hero-copy">',
        '<p class="eyebrow">Public learning guide</p>',
        "<h1>Examples by lesson type</h1>",
        "<p>",
        "Короткая карта того, как FluentLoop превращает материал в тренировку: "
        "от цели и targets до задания, сильного ответа и следующей команды.",
        "</p>",
        "</div>",
        '<div class="hero-aside">',
        "<strong>Reading order</strong>",
        "<span>Start with the matrix, open a type, then inspect the compact "
        "cases and Telegram path.</span>",
        "</div>",
        "</section>",
        '<section class="metric-row">',
        _metric_card("Lesson types", str(len(LESSON_TYPES)), "Every type covered"),
        _metric_card("Examples", str(len(examples)), "Two compact cases per type"),
        _metric_card("Public sources", str(template_count), "Templates and scenarios"),
        _metric_card("Demo cards", str(demo_count), "No private data, no DB clone"),
        "</section>",
        '<section class="section-block">',
        '<div class="section-header">',
        '<p class="kicker">Executive map</p>',
        "<h2>Choose a training lane</h2>",
        "<p>Each tile jumps to a pair of examples with rationale, targets, "
        "practice sample, and strong answer.</p>",
        "</div>",
        '<section class="matrix" aria-label="Lesson type map">',
    ]
    for lesson_type in LESSON_TYPES:
        type_examples = by_type[lesson_type.key]
        body.extend(
            [
                f'<a class="matrix-item" href="#{_anchor_for(lesson_type.title)}">',
                f"<span>{escape(lesson_type.title)}</span>",
                f"<strong>{len(type_examples)} examples</strong>",
                "</a>",
            ]
        )
    body.extend(["</section>", "</section>"])

    for lesson_type in LESSON_TYPES:
        type_examples = by_type[lesson_type.key]
        body.extend(
            [
                f'<section class="type-section" id="{_anchor_for(lesson_type.title)}">',
                '<div class="section-kicker">Lesson type</div>',
                f"<h2>{escape(lesson_type.title)}</h2>",
                f"<p>{escape(lesson_type.goal)}</p>",
                f'<p class="muted">{escape(lesson_type.when_to_use)}</p>',
                '<div class="example-grid">',
            ]
        )
        for example in type_examples:
            body.extend(_render_lesson_type_example_card(example))
        body.extend(["</div>", "</section>"])
    return _report_html_shell(
        "FluentLoop Examples by Lesson Type", "\n".join(body), lang="ru"
    )


def _render_lesson_type_example_card(example: LessonTypeExample) -> list[str]:
    source = escape(f"{example.source_kind}: {example.source_title}")
    if example.source_href:
        source = (
            f'<a href="{escape(_html_href(example.source_href), quote=True)}">'
            f"{source}</a>"
        )
    return [
        '<article class="example-card">',
        '<div class="card-topline">',
        f'<span class="badge">{escape(example.source_kind)}</span>',
        f"<span>{source}</span>",
        "</div>",
        f"<h3>{escape(example.title)}</h3>",
        '<dl class="case-notes">',
        "<dt>Why this lesson exists</dt>",
        f"<dd>{escape(example.why)}</dd>",
        "<dt>Core idea</dt>",
        f"<dd>{escape(example.idea)}</dd>",
        "<dt>When to use</dt>",
        f"<dd>{escape(example.when)}</dd>",
        "</dl>",
        "<h4>Targets</h4>",
        _html_pill_list(example.targets),
        "<h4>Practice sample</h4>",
        _html_ordered_list(example.practice_sample),
        "<h4>Good answer</h4>",
        f'<blockquote class="answer-block">{escape(example.good_answer)}</blockquote>',
        '<p class="telegram">Telegram: '
        f"<code>{escape(example.telegram_path)}</code></p>",
        "</article>",
    ]


def _html_pill_list(items: tuple[str, ...]) -> str:
    pills = "".join(f"<li>{escape(item)}</li>" for item in items)
    return f'<ul class="pill-list">{pills}</ul>'


def _html_ordered_list(items: tuple[str, ...]) -> str:
    entries = "".join(f"<li>{escape(item)}</li>" for item in items)
    return f"<ol>{entries}</ol>"


def _report_html_shell(title: str, body: str, *, lang: str = "en") -> str:
    nav = _catalog_nav()
    return f"""<!doctype html>
<html lang="{escape(lang, quote=True)}">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape(title)}</title>
  <style>
    :root {{
      color-scheme: light;
      --ink: #10131a;
      --muted: #606977;
      --line: #d9dee7;
      --paper: #ffffff;
      --soft: #f5f7fa;
      --accent: #184b8f;
      --warm: #b45309;
      --good: #166534;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      color: var(--ink);
      background: #f6f7f9;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      line-height: 1.52;
    }}
    nav {{
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      padding: 14px 28px;
      border-bottom: 1px solid var(--line);
      background: rgba(255, 255, 255, 0.96);
      position: sticky;
      top: 0;
      z-index: 10;
    }}
    nav a {{
      color: var(--ink);
      border: 1px solid transparent;
      border-radius: 999px;
      font-size: 0.9rem;
      font-weight: 700;
      padding: 7px 10px;
      text-decoration: none;
    }}
    nav a:hover {{
      border-color: var(--line);
      background: var(--soft);
    }}
    main {{
      max-width: 1180px;
      margin: 0 auto;
      padding: 34px 24px 72px;
    }}
    .hero-panel {{
      align-items: end;
      background: var(--paper);
      border: 1px solid var(--line);
      border-top: 6px solid var(--ink);
      display: grid;
      gap: 32px;
      grid-template-columns: minmax(0, 1fr) 300px;
      margin-bottom: 18px;
      padding: 34px;
    }}
    .hero-copy {{
      max-width: 850px;
    }}
    .hero-aside {{
      border-left: 3px solid var(--warm);
      color: var(--muted);
      padding-left: 16px;
    }}
    .hero-aside strong {{
      color: var(--ink);
      display: block;
      font-size: 0.92rem;
      margin-bottom: 6px;
      text-transform: uppercase;
    }}
    .hero-aside span {{
      display: block;
      font-size: 0.95rem;
    }}
    .hero {{
      border-bottom: 1px solid var(--line);
      padding: 12px 0 28px;
      max-width: 920px;
    }}
    .kicker, .eyebrow, .section-kicker {{
      color: var(--warm);
      font-size: 0.78rem;
      font-weight: 800;
      letter-spacing: 0;
      margin: 0 0 8px;
      text-transform: uppercase;
    }}
    h1 {{
      font-size: 3.4rem;
      line-height: 1.04;
      margin: 0 0 16px;
      max-width: 780px;
    }}
    h2 {{
      font-size: 1.75rem;
      line-height: 1.16;
      margin: 0 0 8px;
    }}
    h3 {{
      font-size: 1.06rem;
      line-height: 1.25;
      margin: 10px 0 10px;
    }}
    h4 {{
      color: var(--muted);
      font-size: 0.78rem;
      margin: 18px 0 8px;
      text-transform: uppercase;
    }}
    p {{ margin: 0 0 10px; }}
    a {{ color: var(--accent); }}
    code {{
      background: #eef2f7;
      border-radius: 5px;
      padding: 2px 5px;
    }}
    .answer-block {{
      background: #f8fafc;
      border-left: 3px solid var(--accent);
      color: var(--ink);
      font-size: 0.97rem;
      line-height: 1.58;
      margin: 8px 0 0;
      padding: 12px 14px;
      white-space: pre-line;
    }}
    .muted {{ color: var(--muted); }}
    .metric-row {{
      display: grid;
      gap: 12px;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      margin: 18px 0 32px;
    }}
    .metric-card {{
      background: var(--paper);
      border: 1px solid var(--line);
      border-radius: 8px;
      min-height: 118px;
      padding: 16px;
    }}
    .metric-card span {{
      color: var(--muted);
      display: block;
      font-size: 0.78rem;
      font-weight: 800;
      text-transform: uppercase;
    }}
    .metric-card strong {{
      display: block;
      font-size: 1.95rem;
      line-height: 1.05;
      margin: 12px 0 8px;
    }}
    .metric-card em {{
      color: var(--muted);
      font-style: normal;
    }}
    .section-block {{
      margin-top: 34px;
    }}
    .section-header {{
      border-top: 1px solid var(--line);
      display: grid;
      gap: 18px;
      grid-template-columns: 270px minmax(0, 1fr);
      padding: 28px 0 16px;
    }}
    .section-header p:not(.kicker) {{
      color: var(--muted);
      max-width: 760px;
    }}
    .link-grid, .series-overview, .type-grid, .lesson-grid, .example-grid {{
      display: grid;
      gap: 16px;
    }}
    .link-grid {{
      grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
    }}
    .series-overview {{
      grid-template-columns: 1fr;
    }}
    .type-grid {{
      grid-template-columns: repeat(auto-fit, minmax(310px, 1fr));
    }}
    .lesson-grid, .example-grid {{
      grid-template-columns: repeat(auto-fit, minmax(330px, 1fr));
    }}
    .nav-tile, .overview-card, .type-card, .lesson-card, .example-card {{
      background: var(--paper);
      border: 1px solid var(--line);
      border-radius: 8px;
    }}
    .nav-tile {{
      color: var(--ink);
      min-height: 116px;
      padding: 18px;
      text-decoration: none;
    }}
    .nav-tile strong {{
      display: block;
      font-size: 1rem;
      margin-bottom: 10px;
    }}
    .nav-tile span {{
      color: var(--muted);
      display: block;
    }}
    .overview-card, .type-card, .lesson-card, .example-card {{
      padding: 18px;
    }}
    .card-heading-row {{
      align-items: start;
      display: flex;
      gap: 12px;
      justify-content: space-between;
    }}
    .card-heading-row h3 {{
      margin-top: 0;
    }}
    .card-heading-row span {{
      color: var(--muted);
      flex: 0 0 auto;
      font-size: 0.82rem;
      font-weight: 700;
    }}
    .compact-list {{
      border-top: 1px solid var(--line);
      margin-top: 10px;
    }}
    .compact-row {{
      align-items: center;
      border-bottom: 1px solid var(--line);
      display: grid;
      gap: 18px;
      grid-template-columns: minmax(0, 1fr) auto;
      padding: 11px 0;
    }}
    .compact-row a {{
      display: inline-block;
      font-weight: 800;
      text-decoration: none;
    }}
    .compact-row span {{
      color: var(--muted);
      display: block;
      font-size: 0.9rem;
      margin-top: 2px;
    }}
    .card-index {{
      color: var(--warm);
      font-size: 0.78rem;
      font-weight: 800;
      text-transform: uppercase;
    }}
    .mini-facts, .case-notes {{
      margin: 14px 0 0;
    }}
    .mini-facts dt, .case-notes dt, .detail-grid dt {{
      color: var(--muted);
      font-size: 0.76rem;
      font-weight: 800;
      text-transform: uppercase;
    }}
    .mini-facts dd, .case-notes dd, .detail-grid dd {{
      margin: 3px 0 12px;
    }}
    .detail-grid {{
      border-top: 1px solid var(--line);
      display: grid;
      gap: 12px;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      margin: 16px 0 0;
      padding-top: 14px;
    }}
    .chip-section {{
      margin-top: 16px;
    }}
    .command-line, .telegram {{
      color: var(--muted);
      margin-top: 14px;
    }}
    .table-wrap {{
      background: var(--paper);
      border: 1px solid var(--line);
      border-radius: 8px;
      overflow-x: auto;
    }}
    table {{
      border-collapse: collapse;
      min-width: 900px;
      width: 100%;
    }}
    th, td {{
      border-bottom: 1px solid var(--line);
      padding: 13px 14px;
      text-align: left;
      vertical-align: top;
    }}
    th {{
      background: var(--soft);
      color: var(--muted);
      font-size: 0.76rem;
      text-transform: uppercase;
    }}
    tr:last-child td {{
      border-bottom: 0;
    }}
    .matrix {{
      display: grid;
      gap: 10px;
      grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
      margin: 0;
    }}
    .matrix-item {{
      background: var(--paper);
      border: 1px solid var(--line);
      border-radius: 8px;
      color: var(--ink);
      display: flex;
      justify-content: space-between;
      min-height: 56px;
      padding: 14px;
      text-decoration: none;
    }}
    .matrix-item strong {{ color: var(--muted); font-size: 0.82rem; }}
    .type-section {{
      border-top: 1px solid var(--line);
      padding: 32px 0 4px;
    }}
    .card-topline {{
      align-items: center;
      color: var(--muted);
      display: flex;
      flex-wrap: wrap;
      font-size: 0.82rem;
      gap: 8px;
    }}
    .badge {{
      border: 1px solid var(--line);
      border-radius: 999px;
      color: var(--accent-2);
      font-weight: 800;
      padding: 2px 8px;
      text-transform: uppercase;
    }}
    .pill-list {{
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      list-style: none;
      margin: 0;
      padding: 0;
    }}
    .pill-list li {{
      background: var(--soft);
      border: 1px solid var(--line);
      border-radius: 999px;
      padding: 4px 9px;
    }}
    ol {{ margin: 0; padding-left: 20px; }}
    ol li {{ margin: 6px 0; }}
    .empty-state {{
      background: var(--paper);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 18px;
    }}
    @media (max-width: 700px) {{
      nav {{ padding: 12px 14px; }}
      main {{ padding: 24px 14px 48px; }}
      h1 {{ font-size: 2.35rem; }}
      .hero-panel, .section-header {{
        grid-template-columns: 1fr;
      }}
      .hero-panel {{
        padding: 22px;
      }}
      .hero-aside {{
        border-left: 0;
        border-top: 3px solid var(--warm);
        padding: 14px 0 0;
      }}
      .metric-row, .detail-grid {{
        grid-template-columns: 1fr;
      }}
      .lesson-grid, .example-grid, .type-grid {{
        grid-template-columns: 1fr;
      }}
      .compact-row {{
        align-items: start;
        grid-template-columns: 1fr;
      }}
      .matrix-item {{ min-height: 48px; }}
    }}
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


_LESSON_TYPE_EXAMPLE_SPECS: tuple[LessonTypeExample, ...] = (
    LessonTypeExample(
        "vocabulary",
        "Data Trends and Business Reports",
        "public template",
        "Data Trends and Business Reports",
        "Пользователь часто знает слово trend пассивно, но не умеет быстро "
        "сказать, что именно изменилось и почему это важно для бизнеса.",
        "Превратить data vocabulary в короткое business impact statement.",
        "Когда нужно объяснить метрики, отчет или dashboard без длинного "
        "технического описания.",
        ("a slight increase", "a downward trend", "compared with"),
        (
            "Name the direction of the metric.",
            "Add one comparison point.",
            "Finish with the business impact.",
        ),
        "Revenue showed a slight increase compared with last quarter, but "
        "activation is still on a downward trend. The main risk is that growth "
        "looks healthy while the onboarding funnel is getting weaker.",
        "/practice vocab",
    ),
    LessonTypeExample(
        "vocabulary",
        "Performance, Latency, and Reliability",
        "public template",
        "Performance, Latency, and Reliability",
        "Tech terms вроде latency и reliability легко узнавать, но сложнее "
        "использовать в спокойном объяснении trade-off.",
        "Связать performance word с причиной, эффектом и next step.",
        "Когда надо объяснить проблему сервиса менеджеру, команде или клиенту.",
        ("latency spike", "reliability concern", "under load"),
        (
            "Describe the symptom in one sentence.",
            "Explain the likely cause.",
            "Add one mitigation.",
        ),
        "We saw a latency spike under load after the release. It is a reliability "
        "concern because retries can amplify the issue. I suggest we roll back "
        "the cache change first and then test the queue separately.",
        "/practice vocab",
    ),
    LessonTypeExample(
        "chunks",
        "English for Tech 02: How to Build a Startup",
        "public template",
        "English for Tech 02: How to Build a Startup",
        "Startup vocabulary часто звучит как набор buzzwords. Урок делает его "
        "производительным: идея, problem, market, pitch.",
        "Собрать reusable chunks в короткий startup pitch.",
        "Когда нужно объяснить продуктовую идею, MVP или customer pain point.",
        ("customer pain point", "gap in the market", "scalable solution"),
        (
            "State the customer pain point.",
            "Name the market gap.",
            "Pitch the solution in one sentence.",
        ),
        "The main customer pain point is that small teams cannot track compliance "
        "work without extra admin. We see a gap in the market for a lightweight "
        "tool, so our MVP is a scalable solution for recurring checks.",
        "/practice vocab",
    ),
    LessonTypeExample(
        "chunks",
        "English for Tech 03: Trending Technology",
        "public template",
        "English for Tech 03: Trending Technology",
        "Пользователь может читать про trends, но не всегда умеет описать, что "
        "компания планирует делать с новой технологией.",
        "Тренировать chunks для trend explanation and future plans.",
        "Когда обсуждаешь AI, cloud, automation или новую tooling strategy.",
        ("gain traction", "adopt a tool", "roll it out gradually"),
        (
            "Name the technology trend.",
            "Explain why it matters now.",
            "Say how the team should adopt it.",
        ),
        "The new testing tool is gaining traction because it reduces manual QA "
        "work. I would not roll it out to every team yet; we should adopt it in "
        "one pilot project and expand gradually if the signal is strong.",
        "/practice vocab",
    ),
    LessonTypeExample(
        "grammar",
        "Architecture Trade-offs and Recommendations",
        "public template",
        "Architecture Trade-offs and Recommendations",
        "Без точной grammar recommendation легко звучит слишком уверенно или "
        "слишком расплывчато.",
        "Использовать conditionals и comparatives, чтобы честно сравнить options.",
        "Когда надо рекомендовать архитектурное решение без overselling.",
        ("trade-off", "from a reliability perspective", "I would lean towards"),
        (
            "Compare two options.",
            "State the main trade-off.",
            "Recommend one option with a hedge.",
        ),
        "From a reliability perspective, I would lean towards the async workflow. "
        "The main trade-off is higher operational complexity, but if traffic "
        "spikes again, this option gives us a safer failure mode.",
        "/practice grammar",
    ),
    LessonTypeExample(
        "grammar",
        "Risk Mitigation and Conditionals",
        "public template",
        "Risk Mitigation and Conditionals",
        "Risk language needs precise conditions: what happens if we do X, unless "
        "Y, provided that Z.",
        "Make mitigation sound specific instead of vague.",
        "When writing risk updates, launch plans, or technical recommendations.",
        ("mitigate the risk", "provided that", "unless we"),
        (
            "Name one risk.",
            "Add a condition with provided that or unless.",
            "Close with a mitigation.",
        ),
        "We can mitigate the rollout risk provided that we keep the old endpoint "
        "available for one release. Unless we do that, rollback will be slower "
        "and customer support will have fewer options.",
        "/practice grammar",
    ),
    LessonTypeExample(
        "mistakes",
        "Cross-team Dependencies and Ownership",
        "public template",
        "Cross-team Dependencies and Ownership",
        "Repeated preposition errors make dependency updates sound translated "
        "even when the message is understandable.",
        "Repair dependency + preposition patterns in realistic status language.",
        "When blockers, ownership, and follow-ups are spread across teams.",
        ("depend on", "dependency on", "own the follow-up"),
        (
            "Find the wrong preposition.",
            "Rewrite the dependency sentence.",
            "Add who owns the next step.",
        ),
        "The release depends on the data team finishing the migration. We have a "
        "dependency on their validation script, and I will own the follow-up "
        "with their tech lead today.",
        "/practice mistakes",
    ),
    LessonTypeExample(
        "mistakes",
        "Article/preposition cleanup",
        "demo card",
        "Demo: Article/preposition cleanup",
        "Некоторые ошибки не заслуживают отдельного урока, но возвращаются "
        "каждую неделю: missing articles, wrong prepositions, RU transfer.",
        "Показать пользователю один repeat pattern и сразу закрепить correct form.",
        "Когда `/outcomes` или feedback показывает повторяющуюся low-confidence "
        "ошибку.",
        ("in production", "the rollout", "responsible for"),
        (
            "Correct: We found issue on production.",
            "Explain why the article/preposition changes.",
            "Use the corrected pattern in a new sentence.",
        ),
        "We found the issue in production during the rollout. The platform team "
        "is responsible for the fix, and support will update customers after "
        "validation.",
        "/practice mistakes",
    ),
    LessonTypeExample(
        "diplomatic",
        "Deadline Negotiation and Pushback",
        "public template",
        "Deadline Negotiation and Pushback",
        "Deadline pushback часто звучит либо резко, либо слишком извиняюще.",
        "Дать firm but calm structure: risk, option A, option B.",
        "When a deadline is risky and you need to protect quality.",
        ("move the deadline", "protect quality", "reduce scope"),
        (
            "State the delivery risk calmly.",
            "Offer to move the deadline.",
            "Offer to reduce scope if the date is fixed.",
        ),
        "I am concerned that Friday may be too tight because the API schema is "
        "still changing. If the date is fixed, we can reduce scope and ship the "
        "core flow only. Otherwise, I would suggest moving the deadline to "
        "Wednesday so we can protect quality.",
        "/practice diplomatic",
    ),
    LessonTypeExample(
        "diplomatic",
        "Customer Feedback and Feature Prioritisation",
        "public template",
        "Customer Feedback and Feature Prioritisation",
        "Feature discussions need diplomatic prioritisation, not just louder "
        "opinions.",
        "Turn customer feedback into a ranked recommendation with evidence.",
        "When product, support, and engineering disagree about what to build next.",
        ("recurring feedback", "prioritise", "high-impact"),
        (
            "Summarise the feedback pattern.",
            "Rank one feature as high-impact.",
            "Acknowledge one trade-off.",
        ),
        "The recurring feedback is about onboarding friction, so I would "
        "prioritise the checklist flow. It looks high-impact because it affects "
        "new accounts early, although it means delaying lower-volume reporting "
        "requests.",
        "/practice diplomatic",
    ),
    LessonTypeExample(
        "notebook",
        "Technical conversation native diff",
        "demo card",
        "Demo: Technical conversation native diff",
        "Notebook нужен, чтобы получить живой текст пользователя, а не только "
        "ответы на закрытые drills.",
        "Free writing -> native rewrite -> mined chunks -> next practice.",
        "When the system needs fresh production data from a real work situation.",
        ("real stakeholder", "constraint", "native rewrite"),
        (
            "Write 4-5 sentences about a technical conversation.",
            "Mention one stakeholder and one constraint.",
            "Compare your answer with a native rewrite.",
        ),
        "Yesterday I explained the migration risk to our product manager. The "
        "main constraint is that the billing service still depends on the old "
        "schema. I suggested a smaller release first, so we can validate the "
        "flow before moving all customers.",
        "/practice notebook",
    ),
    LessonTypeExample(
        "notebook",
        "Weekly work reflection",
        "demo card",
        "Demo: Weekly work reflection",
        "Reflection превращает рабочие события в language data: что было трудно "
        "сказать, где не хватило chunks, где появился L1 transfer.",
        "Use a short weekly note to feed future lessons.",
        "When you want FluentLoop to learn from your actual work week.",
        ("reflection", "missing chunk", "next focus"),
        (
            "Describe one moment where English slowed you down.",
            "Name the phrase you wished you had.",
            "Pick the next practice focus.",
        ),
        "This week I struggled to push back on a vague request. I wanted to say "
        "that the scope was unclear without sounding negative. Next week I want "
        "to practise diplomatic clarification and requirement questions.",
        "/reflect",
    ),
    LessonTypeExample(
        "reading",
        "Executive Summaries and Concise Recommendations",
        "public template",
        "Executive Summaries and Concise Recommendations",
        "Reading practice should end in a decision-ready output, not only "
        "comprehension.",
        "Extract the bottom line, key risk, and recommended option.",
        "When you need to brief a manager after reading a long article or memo.",
        ("bottom line", "recommended option", "key risk"),
        (
            "Find the main claim.",
            "Name one assumption or risk.",
            "Write a three-sentence executive summary.",
        ),
        "Bottom line: the async option is safer for reliability. The key risk is "
        "additional operational complexity during rollout. My recommended option "
        "is to pilot it with one workflow before expanding.",
        "/practice reading",
    ),
    LessonTypeExample(
        "reading",
        "Incident Updates and ETA Caveats",
        "public template",
        "Incident Updates and ETA Caveats",
        "Incident reading/writing needs uncertainty: what we know, what we do "
        "not know, and what happens next.",
        "Train concise updates with caveats instead of overpromising.",
        "When summarising production issues for stakeholders.",
        ("root cause", "impact window", "ETA caveat"),
        (
            "State the current known impact.",
            "Add one caveat about ETA.",
            "Close with the next update time.",
        ),
        "Current impact is limited to checkout retries between 09:10 and 09:24 "
        "UTC. We have narrowed the root cause down to cache invalidation, but "
        "the ETA has a caveat around validation. We will send the next update "
        "in 30 minutes.",
        "/practice reading",
    ),
    LessonTypeExample(
        "writing",
        "Async Slack and Email Updates",
        "public template",
        "Async Slack and Email Updates",
        "Async updates fail when context, status, and next step are mixed "
        "together.",
        "Use a compact structure: context, current status, next step.",
        "When writing Slack/email updates for distributed teams.",
        ("for context", "current status", "next step"),
        (
            "Write one sentence of context.",
            "Add current status.",
            "Finish with the owner and next step.",
        ),
        "For context, the migration is blocked by one failing validation check. "
        "Current status: backend has a fix ready, but QA needs one more run. "
        "Next step: I will post the result by 16:00 and confirm whether we can "
        "ship today.",
        "/practice writing",
    ),
    LessonTypeExample(
        "writing",
        "English for Tech 12: Job Interview",
        "public template",
        "English for Tech 12: Job Interview",
        "Interview answers need structure and evidence, not memorised phrases.",
        "Turn experience into a concise STAR-style workplace answer.",
        "When preparing for recruiter screens or technical interviews.",
        ("responsible for", "worked on", "resulted in"),
        (
            "Choose one project.",
            "Explain your responsibility.",
            "End with a measurable result.",
        ),
        "I was responsible for improving the billing retry flow. I worked on the "
        "API changes and coordinated testing with QA. The change resulted in "
        "fewer failed renewals and a clearer support playbook.",
        "/practice writing",
    ),
    LessonTypeExample(
        "genre",
        "Incident post-mortem",
        "demo card",
        "Demo: Incident post-mortem",
        "Genre lessons train the shape of a work artifact, not only individual "
        "phrases.",
        "Use the expected sections: timeline, impact, root cause, remediation, "
        "prevention.",
        "When you need to write a post-mortem that is clear and blameless.",
        ("timeline", "root cause", "prevention"),
        (
            "Place each note into the correct section.",
            "Rewrite one blame-heavy sentence neutrally.",
            "Draft the prevention section.",
        ),
        "Prevention: we will add a pre-release cache validation check and a "
        "rollback owner for checkout changes. This should reduce detection time "
        "and make the response path clearer during future incidents.",
        "/practice genre",
    ),
    LessonTypeExample(
        "genre",
        "RFC decision memo",
        "demo card",
        "Demo: RFC decision memo",
        "RFCs become easier to review when the structure separates problem, "
        "constraints, options, trade-offs, and recommendation.",
        "Practice the document schema before writing the full proposal.",
        "When proposing an architecture or process decision.",
        ("problem", "trade-offs", "recommendation"),
        (
            "Draft the five RFC section headings.",
            "Put one note under each heading.",
            "Write the recommendation with a hedge.",
        ),
        "Recommendation: I would lean towards the async option because it gives "
        "us better failure isolation. The trade-off is extra operational "
        "complexity, so I suggest piloting it with one workflow first.",
        "/practice genre",
    ),
    LessonTypeExample(
        "scenario",
        "Design review - defend choice A vs B",
        "public scenario card",
        "Design review - defend choice A vs B",
        "Roleplay is for pressure: you need language while another person is "
        "challenging the decision.",
        "Rehearse defending a design with constraints and trade-offs.",
        "Before architecture reviews, design reviews, or senior stakeholder Q&A.",
        ("constraint", "trade-off", "recommendation"),
        (
            "State your recommendation.",
            "Acknowledge one downside.",
            "Ask for alignment on the next step.",
        ),
        "I recommend option A because it gives us better failure isolation. The "
        "trade-off is a slightly longer migration, but it lowers rollback risk. "
        "If we agree on that priority, I can draft the migration plan today.",
        "/scene 1",
    ),
    LessonTypeExample(
        "scenario",
        "Customer escalation absorb and de-escalate",
        "public scenario card",
        "Customer escalation absorb and de-escalate",
        "Escalations require tone control: acknowledge, clarify, and move toward "
        "a concrete next step.",
        "Practise calm customer language under stress.",
        "Before customer calls, incident follow-ups, or support escalations.",
        ("I understand the concern", "what I can confirm", "next update"),
        (
            "Acknowledge the customer's frustration.",
            "Separate confirmed facts from investigation.",
            "Promise a specific next update.",
        ),
        "I understand the concern, and I agree the delay is frustrating. What I "
        "can confirm is that the fix is deployed and validation is running now. "
        "I will send the next update by 15:30 with either confirmation or a new "
        "ETA.",
        "/scene 12",
    ),
    LessonTypeExample(
        "review",
        "Due chunk recall",
        "demo card",
        "Demo: Due chunk recall",
        "Review lessons protect memory: useful chunks return before they become "
        "passive again.",
        "Cold recall first, explanation second.",
        "When `/today` or `/review` brings back due items.",
        ("active recall", "cloze", "confidence"),
        (
            "Fill the missing chunk without looking.",
            "Rate confidence.",
            "Use the chunk in a new work sentence.",
        ),
        "Could we move the deadline to Wednesday? This would help us protect "
        "quality and still keep the core release on track.",
        "/review",
    ),
    LessonTypeExample(
        "review",
        "Weak mistake return",
        "demo card",
        "Demo: Weak mistake return",
        "Weak items need to reappear in a different form, otherwise the user only "
        "memorises one answer.",
        "Return the same mistake pattern as rewrite, cloze, and production.",
        "When confidence is low or the same error repeats.",
        ("error correction", "same pattern", "new sentence"),
        (
            "Correct the old mistake.",
            "Explain the pattern in one line.",
            "Write a new sentence with the corrected form.",
        ),
        "The system depends on the billing service, not depends from it. We also "
        "have a dependency on the data export before we can finish validation.",
        "/practice review",
    ),
    LessonTypeExample(
        "mixed",
        "Balanced daily lesson",
        "demo card",
        "Demo: Balanced daily lesson",
        "A daily lesson should not overfit one skill; it should mix recall, "
        "accuracy, production, and feedback.",
        "Combine vocabulary, grammar, writing, and SRS in one short loop.",
        "When the user opens `/today` and needs the next best training mix.",
        ("recall", "grammar repair", "mini writing"),
        (
            "Recall one due chunk.",
            "Repair one sentence.",
            "Write a short realistic update.",
        ),
        "For context, the rollout is delayed because validation found one edge "
        "case. If the date is fixed, we can reduce scope; otherwise I recommend "
        "moving the deadline to protect quality.",
        "/today",
    ),
    LessonTypeExample(
        "mixed",
        "Tech textbook mixed loop",
        "demo card",
        "Demo: Tech textbook mixed loop",
        "Textbook-like lessons usually contain vocabulary, grammar, speaking, and "
        "writing together.",
        "Turn broad material into a sequence of small production tasks.",
        "When a public or uploaded lesson covers a whole topic, not one pattern.",
        ("topic vocabulary", "grammar focus", "free production"),
        (
            "Notice the topic vocabulary.",
            "Practise the grammar focus.",
            "Produce a short workplace answer.",
        ),
        "I usually work on backend APIs, but this week I am helping the DevOps "
        "team with deployment checks. It is a good chance to keep up with our "
        "cloud tooling and understand the release process better.",
        "/lesson <id>",
    ),
    LessonTypeExample(
        "outcomes",
        "Monthly baseline",
        "demo card",
        "Demo: Monthly baseline",
        "Outcomes need a stable starting point; otherwise progress is just a "
        "feeling.",
        "Capture a monthly writing sample and reserve held-out items.",
        "When starting a new month or checking whether practice transfers to "
        "production.",
        ("baseline", "held-out items", "writing metrics"),
        (
            "Write 120-180 words about a real work situation.",
            "Include one risk, one trade-off, and one recommendation.",
            "Use the result as the comparison point for the month.",
        ),
        "The main trade-off is speed versus reliability. I recommend delaying "
        "the full rollout by two days, because the current validation gap could "
        "create support load if we ship to all customers at once.",
        "/baseline",
    ),
    LessonTypeExample(
        "outcomes",
        "30-day outcomes report",
        "demo card",
        "Demo: 30-day outcomes report",
        "The user needs evidence: retention, productive chunks, L1 density, and "
        "mistake extinction, not just number of exercises.",
        "Summarise learning quality and choose the next loop.",
        "Weekly or monthly, after enough practice attempts.",
        ("retention", "productive chunks", "L1 density"),
        (
            "Read the sample size first.",
            "Find the weakest metric.",
            "Choose the next practice loop.",
        ),
        "Next best loop: use `/practice notebook` for production volume and "
        "`/practice diplomatic` for L1 transfer. Retention is acceptable, but "
        "productive chunk use is still thin, so the next week should generate "
        "more free writing.",
        "/outcomes full",
    ),
)


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
            heading = line[2:]
            body_lines.append(
                f'<h1 id="{_anchor_for(heading)}">{_inline_md(heading)}</h1>'
            )
        elif line.startswith("## "):
            if in_list:
                body_lines.append("</ul>")
                in_list = False
            heading = line[3:]
            body_lines.append(
                f'<h2 id="{_anchor_for(heading)}">{_inline_md(heading)}</h2>'
            )
        elif line.startswith("### "):
            if in_list:
                body_lines.append("</ul>")
                in_list = False
            heading = line[4:]
            body_lines.append(
                f'<h3 id="{_anchor_for(heading)}">{_inline_md(heading)}</h3>'
            )
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
    nav = _catalog_nav()
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
    h1 {{ font-size: 2.8rem; line-height: 1.08; margin: 18px 0 12px; }}
    h2 {{ margin-top: 36px; color: var(--blue); }}
    h3 {{ margin-top: 24px; color: var(--green); }}
    blockquote {{ border-left: 4px solid var(--blue); margin: 18px 0;
      padding: 8px 14px; background: #f7fbff; }}
    code {{ background: #eef4ff; padding: 2px 6px; border-radius: 5px; }}
    li {{ margin: 7px 0; }}
    pre {{ white-space: pre-wrap; overflow-x: auto; background: #f7fbff;
      border: 1px solid #d7e1ef; padding: 10px; border-radius: 8px; }}
    @media (max-width: 700px) {{ h1 {{ font-size: 2.05rem; }} }}
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


def _catalog_nav() -> str:
    return (
        '<nav><a href="index.html">Catalog</a><a href="lesson-types.html">'
        'Lesson types</a><a href="examples-by-type.html">Examples by type</a>'
        '<a href="b2-b2plus-seed.html">B2/B2+</a>'
        '<a href="english-for-tech.html">English for Tech</a>'
        '<a href="scenarios.html">Scenarios</a></nav>'
    )


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
            f'<a href="{escape(_html_href(href), quote=True)}">{escape(label)}</a>'
        )
        cursor = match.end()
    rendered.append(escape(text[cursor:]))
    return "".join(rendered)


def _html_href(href: str) -> str:
    local_path, separator, fragment = href.partition("#")
    if (
        local_path.endswith(".md")
        and not local_path.startswith(("http://", "https://", "mailto:"))
    ):
        local_path = local_path.removesuffix(".md") + ".html"
    return local_path + (separator + fragment if separator else "")


def _anchor_for(text: str) -> str:
    anchor = re.sub(r"[^a-z0-9 -]", "", text.casefold()).strip()
    anchor = re.sub(r"\s+", "-", anchor)
    anchor = re.sub(r"-+", "-", anchor)
    return anchor or "section"


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


def _group_examples_by_type(
    examples: Iterable[LessonTypeExample],
) -> dict[str, list[LessonTypeExample]]:
    grouped: dict[str, list[LessonTypeExample]] = {
        lesson_type.key: [] for lesson_type in LESSON_TYPES
    }
    for example in examples:
        grouped.setdefault(example.lesson_type_key, []).append(example)
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
        "examples-by-type.md": "FluentLoop Examples by Lesson Type",
        "b2-b2plus-seed.md": "B2/B2+ Seed Lessons",
        "english-for-tech.md": "English for Tech",
        "scenarios.md": "Business/IT Scenarios",
    }.get(name, "FluentLoop Catalog")
