from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.types import JSON


def utc_now() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    telegram_user_id: Mapped[int] = mapped_column(Integer, unique=True, index=True)
    level: Mapped[str] = mapped_column(String(16), default="B2+/C1-")
    focus_areas: Mapped[list[str]] = mapped_column(JSON, default=list)
    timezone: Mapped[str] = mapped_column(String(64), default="Europe/Moscow")
    reminder_time: Mapped[str] = mapped_column(String(5), default="20:00")
    explanation_language: Mapped[str] = mapped_column(String(16), default="mixed")
    practice_duration_minutes: Mapped[int] = mapped_column(Integer, default=15)


class BotState(Base, TimestampMixin):
    __tablename__ = "bot_states"
    __table_args__ = (
        UniqueConstraint("chat_id", "user_id", name="uq_bot_state_chat_user"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    chat_id: Mapped[int] = mapped_column(Integer, index=True)
    user_id: Mapped[int] = mapped_column(Integer, index=True)
    name: Mapped[str] = mapped_column(String(64))
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class SourceMaterial(Base, TimestampMixin):
    __tablename__ = "source_materials"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    type: Mapped[str] = mapped_column(String(32), default="other")
    raw_text: Mapped[str] = mapped_column(Text)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)


class ExtractedCandidate(Base, TimestampMixin):
    __tablename__ = "extracted_candidates"
    __table_args__ = (
        UniqueConstraint(
            "source_material_id",
            "type",
            "text",
            name="uq_candidate_source_type_text",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_material_id: Mapped[int] = mapped_column(
        ForeignKey("source_materials.id"), index=True
    )
    type: Mapped[str] = mapped_column(String(32))
    text: Mapped[str] = mapped_column(String(512))
    meaning: Mapped[str] = mapped_column(Text, default="")
    explanation: Mapped[str] = mapped_column(Text, default="")
    examples: Mapped[list[str]] = mapped_column(JSON, default=list)
    tags: Mapped[list[str]] = mapped_column(JSON, default=list)
    confidence: Mapped[float] = mapped_column(Float, default=0.5)
    status: Mapped[str] = mapped_column(String(16), default="pending")
    terminal_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class LearningItem(Base, TimestampMixin):
    __tablename__ = "learning_items"
    __table_args__ = (
        UniqueConstraint("user_id", "type", "text", name="uq_item_user_type_text"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    type: Mapped[str] = mapped_column(String(32), index=True)
    text: Mapped[str] = mapped_column(String(512), index=True)
    meaning: Mapped[str] = mapped_column(Text, default="")
    explanation: Mapped[str] = mapped_column(Text, default="")
    examples: Mapped[list[str]] = mapped_column(JSON, default=list)
    tags: Mapped[list[str]] = mapped_column(JSON, default=list)
    level: Mapped[str] = mapped_column(String(16), default="B2+/C1-")
    source_material_id: Mapped[int | None] = mapped_column(
        ForeignKey("source_materials.id"), nullable=True
    )
    linked_grammar_concept_id: Mapped[int | None] = mapped_column(
        ForeignKey("grammar_concepts.id"), nullable=True
    )
    is_favorite: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String(16), default="active")
    review_state: Mapped[ReviewState] = relationship(
        back_populates="learning_item", uselist=False
    )


class ReviewState(Base, TimestampMixin):
    __tablename__ = "review_states"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    learning_item_id: Mapped[int] = mapped_column(
        ForeignKey("learning_items.id"), unique=True, index=True
    )
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    last_reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    review_count: Mapped[int] = mapped_column(Integer, default=0)
    success_count: Mapped[int] = mapped_column(Integer, default=0)
    fail_count: Mapped[int] = mapped_column(Integer, default=0)
    difficulty: Mapped[float] = mapped_column(Float, default=1.0)
    stability: Mapped[float] = mapped_column(Float, default=1.0)
    last_result: Mapped[str | None] = mapped_column(String(16), nullable=True)
    last_interval_days: Mapped[float] = mapped_column(Float, default=0.0)
    learning_item: Mapped[LearningItem] = relationship(back_populates="review_state")


class PracticeSession(Base, TimestampMixin):
    __tablename__ = "practice_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    target_date_local: Mapped[date] = mapped_column(Date, index=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    status: Mapped[str] = mapped_column(String(16), default="in_progress")
    exercises: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)


class PracticeAttempt(Base, TimestampMixin):
    __tablename__ = "practice_attempts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    practice_session_id: Mapped[int] = mapped_column(
        ForeignKey("practice_sessions.id"), index=True
    )
    exercise_index: Mapped[int] = mapped_column(Integer)
    exercise_type: Mapped[str] = mapped_column(String(32))
    target_learning_item_ids: Mapped[list[int]] = mapped_column(JSON, default=list)
    prompt: Mapped[str] = mapped_column(Text)
    user_answer: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(24), default="unchecked")
    feedback: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class PracticeSessionCached(Base, TimestampMixin):
    __tablename__ = "practice_session_cached"
    __table_args__ = (
        UniqueConstraint(
            "user_id", "target_date_local", name="uq_cached_session_user_date"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    target_date_local: Mapped[date] = mapped_column(Date, index=True)
    exercises: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(16), default="ready")


class LessonPlan(Base, TimestampMixin):
    __tablename__ = "lesson_plans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    source_material_id: Mapped[int | None] = mapped_column(
        ForeignKey("source_materials.id"), nullable=True, index=True
    )
    title: Mapped[str] = mapped_column(String(256))
    topic: Mapped[str] = mapped_column(String(256), default="Business/IT communication")
    goal: Mapped[str] = mapped_column(Text, default="")
    level: Mapped[str] = mapped_column(String(16), default="B2+/C1-")
    language_focus_json: Mapped[list[str]] = mapped_column(JSON, default=list)
    tags_json: Mapped[list[str]] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(16), default="active", index=True)


class LessonStep(Base, TimestampMixin):
    __tablename__ = "lesson_steps"
    __table_args__ = (
        UniqueConstraint(
            "lesson_plan_id", "order_index", name="uq_lesson_step_plan_order"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    lesson_plan_id: Mapped[int] = mapped_column(
        ForeignKey("lesson_plans.id"), index=True
    )
    order_index: Mapped[int] = mapped_column(Integer)
    step_type: Mapped[str] = mapped_column(String(64), index=True)
    title: Mapped[str] = mapped_column(String(256))
    instruction: Mapped[str] = mapped_column(Text, default="")
    exercise_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    estimated_minutes: Mapped[int] = mapped_column(Integer, default=2)
    target_skill: Mapped[str | None] = mapped_column(String(64), nullable=True)
    prompt_template: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class LessonPlanItem(Base, TimestampMixin):
    __tablename__ = "lesson_plan_items"
    __table_args__ = (
        UniqueConstraint(
            "lesson_plan_id",
            "learning_item_id",
            "role",
            name="uq_lesson_plan_item_role",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    lesson_plan_id: Mapped[int] = mapped_column(
        ForeignKey("lesson_plans.id"), index=True
    )
    learning_item_id: Mapped[int] = mapped_column(
        ForeignKey("learning_items.id"), index=True
    )
    role: Mapped[str] = mapped_column(String(32), default="target")
    priority: Mapped[int] = mapped_column(Integer, default=0)


class MistakeEvent(Base, TimestampMixin):
    __tablename__ = "mistake_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    wrong_answer: Mapped[str] = mapped_column(Text)
    corrected_answer: Mapped[str] = mapped_column(Text, default="")
    explanation: Mapped[str] = mapped_column(Text, default="")
    mistake_type: Mapped[str] = mapped_column(String(64), index=True)
    linked_learning_item_id: Mapped[int | None] = mapped_column(
        ForeignKey("learning_items.id"), nullable=True
    )
    linked_grammar_concept_id: Mapped[int | None] = mapped_column(
        ForeignKey("grammar_concepts.id"), nullable=True
    )


class MistakePattern(Base, TimestampMixin):
    __tablename__ = "mistake_patterns"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    description: Mapped[str] = mapped_column(Text)
    mistake_type: Mapped[str] = mapped_column(String(64), index=True)
    linked_learning_item_id: Mapped[int | None] = mapped_column(
        ForeignKey("learning_items.id"), nullable=True
    )
    linked_grammar_concept_id: Mapped[int | None] = mapped_column(
        ForeignKey("grammar_concepts.id"), nullable=True
    )
    confidence: Mapped[str] = mapped_column(String(16), default="low")
    status: Mapped[str] = mapped_column(String(16), default="active")
    wrong_examples: Mapped[list[str]] = mapped_column(JSON, default=list)
    correct_examples: Mapped[list[str]] = mapped_column(JSON, default=list)
    event_count: Mapped[int] = mapped_column(Integer, default=0)


class GrammarConcept(Base, TimestampMixin):
    __tablename__ = "grammar_concepts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(256), unique=True)
    description: Mapped[str] = mapped_column(Text, default="")
    parent_ids: Mapped[list[int]] = mapped_column(JSON, default=list)
    child_ids: Mapped[list[int]] = mapped_column(JSON, default=list)
    examples: Mapped[list[str]] = mapped_column(JSON, default=list)


class UsageLog(Base, TimestampMixin):
    __tablename__ = "usage_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    provider: Mapped[str] = mapped_column(String(32), default="stub")
    model: Mapped[str] = mapped_column(String(64), default="stub")
    task: Mapped[str] = mapped_column(String(64), index=True)
    prompt_tokens: Mapped[int] = mapped_column(Integer, default=0)
    completion_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
