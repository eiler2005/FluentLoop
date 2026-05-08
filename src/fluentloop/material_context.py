from __future__ import annotations

import re
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from fluentloop.db.models import MaterialChunk, SourceMaterial, User

TOKEN_RE = re.compile(r"[a-zA-Z][a-zA-Z0-9_+-]{2,}")


@dataclass(frozen=True)
class MaterialContext:
    chunk_id: int
    source_material_id: int
    chunk_index: int
    text: str
    score: int


def split_material_into_chunks(
    text: str, *, max_chars: int = 900, overlap_chars: int = 120
) -> list[str]:
    paragraphs = [part.strip() for part in re.split(r"\n\s*\n", text) if part.strip()]
    chunks: list[str] = []
    current = ""
    for paragraph in paragraphs or [text.strip()]:
        if not current:
            current = paragraph
        elif len(current) + len(paragraph) + 2 <= max_chars:
            current = f"{current}\n\n{paragraph}"
        else:
            chunks.extend(_split_long_text(current, max_chars=max_chars))
            tail = current[-overlap_chars:] if overlap_chars and current else ""
            current = f"{tail}\n\n{paragraph}" if tail else paragraph
    if current:
        chunks.extend(_split_long_text(current, max_chars=max_chars))
    return [chunk.strip() for chunk in chunks if chunk.strip()]


def index_source_material(
    session: Session,
    material: SourceMaterial,
    *,
    tags: list[str] | None = None,
) -> list[MaterialChunk]:
    existing = list(
        session.scalars(
            select(MaterialChunk)
            .where(MaterialChunk.source_material_id == material.id)
            .order_by(MaterialChunk.chunk_index)
        )
    )
    if existing:
        return existing
    chunks: list[MaterialChunk] = []
    for index, text in enumerate(split_material_into_chunks(material.raw_text)):
        chunk = MaterialChunk(
            source_material_id=material.id,
            chunk_index=index,
            text=text,
            tags_json=tags or [],
        )
        session.add(chunk)
        chunks.append(chunk)
    session.flush()
    return chunks


def search_material_chunks(
    session: Session,
    user: User,
    query: str,
    *,
    source_material_id: int | None = None,
    limit: int = 5,
) -> list[MaterialContext]:
    terms = _tokens(query)
    if not terms:
        return []
    stmt = (
        select(MaterialChunk)
        .join(SourceMaterial, SourceMaterial.id == MaterialChunk.source_material_id)
        .where(SourceMaterial.user_id == user.id)
        .order_by(MaterialChunk.created_at.desc())
    )
    if source_material_id is not None:
        stmt = stmt.where(MaterialChunk.source_material_id == source_material_id)
    results: list[MaterialContext] = []
    for chunk in session.scalars(stmt):
        haystack = " ".join([chunk.text, " ".join(chunk.tags_json or [])]).lower()
        score = sum(1 for term in terms if term in haystack)
        if score:
            results.append(
                MaterialContext(
                    chunk_id=chunk.id,
                    source_material_id=chunk.source_material_id,
                    chunk_index=chunk.chunk_index,
                    text=chunk.text,
                    score=score,
                )
            )
    return sorted(results, key=lambda item: item.score, reverse=True)[:limit]


def build_material_context(
    session: Session,
    user: User,
    query: str,
    *,
    source_material_id: int | None = None,
    limit: int = 3,
) -> list[dict]:
    return [
        {
            "chunk_id": item.chunk_id,
            "source_material_id": item.source_material_id,
            "chunk_index": item.chunk_index,
            "text": item.text[:900],
            "score": item.score,
        }
        for item in search_material_chunks(
            session,
            user,
            query,
            source_material_id=source_material_id,
            limit=limit,
        )
    ]


def _split_long_text(text: str, *, max_chars: int) -> list[str]:
    if len(text) <= max_chars:
        return [text]
    chunks: list[str] = []
    start = 0
    while start < len(text):
        chunks.append(text[start : start + max_chars])
        start += max_chars
    return chunks


def _tokens(query: str) -> set[str]:
    return {token.lower() for token in TOKEN_RE.findall(query)}

