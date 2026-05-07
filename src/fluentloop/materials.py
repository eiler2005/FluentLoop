from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from fluentloop.ai.provider import AIProvider
from fluentloop.db.models import ExtractedCandidate, SourceMaterial, User, utc_now
from fluentloop.learning import promote_candidate

MAX_UPLOAD_CHARS = 10_000
MATERIAL_TYPES = {
    "lesson_notes",
    "word_list",
    "expression_list",
    "homework",
    "exercise",
    "teacher_feedback",
    "other",
}


def store_material(
    session: Session,
    user: User,
    raw_text: str,
    *,
    type_: str = "other",
) -> SourceMaterial:
    if type_ not in MATERIAL_TYPES:
        raise ValueError("Unsupported material type")
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
    try:
        result = provider.heavy_call(
            "epic_04_extract",
            {"raw_text": material.raw_text, "type": material.type},
        )
    except Exception as exc:
        raise ValueError("couldn't extract candidates; try again or rephrase") from exc
    if not hasattr(result, "candidates"):
        raise ValueError("couldn't extract candidates; try again or rephrase")
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
            ExtractedCandidate.status.in_(("pending", "edited")),
        )
    )
    count = 0
    for candidate in candidates:
        promote_candidate(session, user, candidate)
        count += 1
    return count


def approve_candidate(
    session: Session, user: User, candidate: ExtractedCandidate
) -> int:
    if candidate.status not in {"pending", "edited"}:
        return 0
    source = session.get(SourceMaterial, candidate.source_material_id)
    if source is None or source.user_id != user.id:
        raise ValueError("Candidate not found")
    promote_candidate(session, user, candidate)
    return 1


def skip_candidate(
    session: Session, user: User, candidate: ExtractedCandidate
) -> int:
    source = session.get(SourceMaterial, candidate.source_material_id)
    if source is None or source.user_id != user.id:
        raise ValueError("Candidate not found")
    if candidate.status not in {"pending", "edited"}:
        return 0
    candidate.status = "skipped"
    candidate.terminal_at = utc_now()
    session.add(candidate)
    session.flush()
    return 1


def skip_all(session: Session, material: SourceMaterial) -> int:
    candidates = session.scalars(
        select(ExtractedCandidate).where(
            ExtractedCandidate.source_material_id == material.id,
            ExtractedCandidate.status.in_(("pending", "edited")),
        )
    )
    count = 0
    for candidate in candidates:
        candidate.status = "skipped"
        candidate.terminal_at = utc_now()
        session.add(candidate)
        count += 1
    return count


def edit_candidate(
    session: Session,
    user: User,
    candidate: ExtractedCandidate,
    field: str,
    value: str,
) -> ExtractedCandidate:
    source = session.get(SourceMaterial, candidate.source_material_id)
    if source is None or source.user_id != user.id:
        raise ValueError("Candidate not found")
    if candidate.status not in {"pending", "edited"}:
        raise ValueError("Candidate already handled")
    if field == "text":
        normalized = value.strip()
        if not normalized:
            raise ValueError("Text is required")
        duplicate = session.scalar(
            select(ExtractedCandidate).where(
                ExtractedCandidate.source_material_id
                == candidate.source_material_id,
                ExtractedCandidate.type == candidate.type,
                ExtractedCandidate.text == normalized,
                ExtractedCandidate.id != candidate.id,
            )
        )
        if duplicate is not None:
            raise ValueError("Duplicate candidate text")
        candidate.text = normalized
    elif field == "meaning":
        candidate.meaning = value.strip()
    elif field == "tags":
        candidate.tags = [tag.strip() for tag in value.split(",") if tag.strip()]
    else:
        raise ValueError("Use text, meaning, or tags")
    candidate.status = "edited"
    session.add(candidate)
    session.flush()
    return candidate
