from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from fluentloop.ai.provider import AIProvider
from fluentloop.db.models import ExtractedCandidate, SourceMaterial, User, utc_now
from fluentloop.learning import promote_candidate

MAX_UPLOAD_CHARS = 10_000


def store_material(
    session: Session,
    user: User,
    raw_text: str,
    *,
    type_: str = "other",
) -> SourceMaterial:
    if len(raw_text.encode("utf-8")) > MAX_UPLOAD_CHARS:
        raise ValueError("Material is too large; paste it in chunks")
    material = SourceMaterial(user_id=user.id, type=type_, raw_text=raw_text)
    session.add(material)
    session.flush()
    return material


def extract_candidates(
    session: Session,
    material: SourceMaterial,
    provider: AIProvider,
) -> list[ExtractedCandidate]:
    result = provider.heavy_call(
        "epic_04_extract",
        {"raw_text": material.raw_text, "type": material.type},
    )
    stored: list[ExtractedCandidate] = []
    for item in result.candidates:
        existing = session.scalar(
            select(ExtractedCandidate).where(
                ExtractedCandidate.source_material_id == material.id,
                ExtractedCandidate.type == item.type,
                ExtractedCandidate.text == item.text,
            )
        )
        if existing is not None:
            stored.append(existing)
            continue
        candidate = ExtractedCandidate(
            source_material_id=material.id,
            type=item.type,
            text=item.text,
            meaning=item.meaning,
            explanation=item.explanation,
            examples=item.examples,
            tags=item.tags,
            confidence=item.confidence,
            status="pending",
        )
        session.add(candidate)
        session.flush()
        stored.append(candidate)
    return stored


def approve_all(session: Session, user: User, material: SourceMaterial) -> int:
    candidates = session.scalars(
        select(ExtractedCandidate).where(
            ExtractedCandidate.source_material_id == material.id,
            ExtractedCandidate.status == "pending",
        )
    )
    count = 0
    for candidate in candidates:
        promote_candidate(session, user, candidate)
        count += 1
    return count


def skip_all(session: Session, material: SourceMaterial) -> int:
    candidates = session.scalars(
        select(ExtractedCandidate).where(
            ExtractedCandidate.source_material_id == material.id,
            ExtractedCandidate.status == "pending",
        )
    )
    count = 0
    for candidate in candidates:
        candidate.status = "skipped"
        candidate.terminal_at = utc_now()
        session.add(candidate)
        count += 1
    return count
