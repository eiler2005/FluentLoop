from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from fluentloop.db.models import LessonPlan, LessonStep, SourceMaterial, User
from fluentloop.learning import create_learning_item
from fluentloop.lesson_formats import GENRE_SPECS
from fluentloop.lesson_plans import create_lesson_plan_from_source, link_lesson_items
from fluentloop.materials import store_material


@dataclass(frozen=True)
class GenreLessonSeed:
    name: str
    title: str
    schema: str
    target: str
    chunks: tuple[str, ...]


def genre_lesson_seeds() -> tuple[GenreLessonSeed, ...]:
    seeds: list[GenreLessonSeed] = []
    for spec in GENRE_SPECS:
        name = spec["name"]
        readable = name.replace("_", " ").title()
        schema = spec["schema"]
        target = spec["target"]
        chunks = tuple(_chunks_for_schema(schema, name))
        seeds.append(
            GenreLessonSeed(
                name=name,
                title=f"Genre: {readable}",
                schema=schema,
                target=target,
                chunks=chunks,
            )
        )
    return tuple(seeds)


def seed_genre_curriculum(session: Session, user: User) -> dict[str, int]:
    plans = 0
    items = 0
    for seed in genre_lesson_seeds():
        material = _material_for_seed(session, user, seed)
        lesson_items = [
            create_learning_item(
                session,
                user,
                type_="chunk",
                text=chunk,
                meaning="genre scaffold phrase",
                explanation=f"Use in {seed.title}.",
                examples=[f"{chunk.capitalize()} this section should be concise."],
                tags=["genre_curriculum", seed.name],
                source_material_id=material.id,
                metadata={
                    "field": "GENRE",
                    "register": "professional",
                    "function": seed.name,
                },
            )
            for chunk in seed.chunks
        ]
        lesson_items.append(
            create_learning_item(
                session,
                user,
                type_="grammar_rule",
                text=f"{seed.title} target: {seed.target}",
                meaning=seed.target,
                explanation=f"Language target for {seed.title}.",
                examples=[seed.schema],
                tags=["genre_curriculum", seed.name, "grammar"],
                source_material_id=material.id,
            )
        )
        items += len(lesson_items)
        plan = create_lesson_plan_from_source(
            session,
            user,
            material,
            items=lesson_items,
            status="active",
            provider=None,
        )
        _apply_genre_metadata(session, plan, seed)
        link_lesson_items(session, plan, lesson_items)
        plans += 1
    session.flush()
    return {"lessons": plans, "items": items}


def render_genre_curriculum_markdown() -> str:
    lines = [
        "# EPIC-22 Genre Curriculum",
        "",
        "Deterministic 10-genre curriculum for C1 business/IT writing.",
        "",
    ]
    for index, seed in enumerate(genre_lesson_seeds(), start=1):
        lines.extend(
            [
                f"## {index}. {seed.title}",
                "",
                f"- Slug: `{seed.name}`",
                f"- Schema: {seed.schema}",
                f"- Target: {seed.target}",
                f"- Chunks: {', '.join(seed.chunks)}",
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def _material_for_seed(
    session: Session, user: User, seed: GenreLessonSeed
) -> SourceMaterial:
    raw_text = (
        f"{seed.title}\n"
        f"Schema: {seed.schema}\n"
        f"Target: {seed.target}\n"
        f"Chunks: {', '.join(seed.chunks)}"
    )
    existing = session.scalar(
        select(SourceMaterial).where(
            SourceMaterial.user_id == user.id,
            SourceMaterial.raw_text == raw_text,
        )
    )
    if existing is not None:
        return existing
    material = store_material(session, user, raw_text, type_="lesson_notes")
    material.summary = seed.title
    session.add(material)
    session.flush()
    return material


def _apply_genre_metadata(
    session: Session, plan: LessonPlan, seed: GenreLessonSeed
) -> None:
    plan.title = seed.title
    plan.topic = seed.name.replace("_", " ")
    plan.goal = f"Produce a clear {plan.topic} using the expected genre schema."
    plan.language_focus_json = [seed.target]
    plan.tags_json = ["genre_curriculum", seed.name]
    plan.format = "genre"
    session.add(plan)
    steps = list(
        session.scalars(
            select(LessonStep)
            .where(LessonStep.lesson_plan_id == plan.id)
            .order_by(LessonStep.order_index)
        )
    )
    for step in steps:
        if step.order_index == 1:
            step.title = "Schema noticing"
            step.instruction = f"Identify the stages: {seed.schema}."
        elif step.order_index == 2:
            step.title = "Chunk placement"
            step.instruction = "Place each scaffold chunk into the right stage."
        elif step.order_index == 6:
            step.title = "Genre production"
            step.instruction = f"Draft a compact {plan.topic} artifact."
        step.metadata_json = {**(step.metadata_json or {}), "genre": seed.name}
        session.add(step)


def _chunks_for_schema(schema: str, genre_name: str) -> list[str]:
    parts = [part.strip().lower() for part in schema.split("->") if part.strip()]
    readable = genre_name.replace("_", " ")
    return [f"{part} section for {readable}" for part in parts[:5]]
