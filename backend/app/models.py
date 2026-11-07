from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    Numeric,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Conversation(Base):
    """Import storage boundary; no imported or seeded customer data at bootstrap."""

    __tablename__ = "conversations"

    group_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    conversation_id: Mapped[str] = mapped_column(String(200), primary_key=True)
    language: Mapped[str] = mapped_column(String(20))
    channel: Mapped[str] = mapped_column(String(40))
    audio_url: Mapped[str | None] = mapped_column(String, nullable=True)
    # Keep source order and timestamp strings; no lossy timestamp coercion.
    transcript: Mapped[list[dict]] = mapped_column(JSON)


def utcnow() -> datetime:
    return datetime.now(UTC)


def new_id() -> str:
    return str(uuid4())


class Rubric(Base):
    __tablename__ = "rubrics"
    rubric_id: Mapped[str] = mapped_column(String(100), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(200))
    latest_version: Mapped[int] = mapped_column(Integer, default=1)


class RubricVersion(Base):
    __tablename__ = "rubric_versions"
    rubric_id: Mapped[str] = mapped_column(ForeignKey("rubrics.rubric_id"), primary_key=True)
    version: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    document: Mapped[dict] = mapped_column(JSON)


class Batch(Base):
    __tablename__ = "batches"
    batch_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    group_id: Mapped[str] = mapped_column(String(100))
    rubric_id: Mapped[str] = mapped_column(String(100))
    rubric_version: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), default="queued")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    __table_args__ = (
        ForeignKeyConstraint(
            ["rubric_id", "rubric_version"],
            ["rubric_versions.rubric_id", "rubric_versions.version"],
        ),
    )


class Evaluation(Base):
    __tablename__ = "evaluations"
    evaluation_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    group_id: Mapped[str] = mapped_column(String(100))
    conversation_id: Mapped[str] = mapped_column(String(200))
    rubric_id: Mapped[str] = mapped_column(String(100))
    rubric_version: Mapped[int] = mapped_column(Integer)
    rubric_snapshot: Mapped[dict] = mapped_column(JSON)
    conversation_snapshot: Mapped[dict] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(20), default="queued", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    original_score: Mapped[Decimal | None] = mapped_column(Numeric(7, 2), nullable=True)
    gross_error: Mapped[bool] = mapped_column(Boolean, default=False)
    needs_human_review: Mapped[bool] = mapped_column(Boolean, default=False)
    results: Mapped[list[dict]] = mapped_column(JSON, default=list)
    usage: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    batch_id: Mapped[str | None] = mapped_column(
        ForeignKey("batches.batch_id"), nullable=True, index=True
    )
    __table_args__ = (
        ForeignKeyConstraint(
            ["group_id", "conversation_id"],
            ["conversations.group_id", "conversations.conversation_id"],
        ),
        ForeignKeyConstraint(
            ["rubric_id", "rubric_version"],
            ["rubric_versions.rubric_id", "rubric_versions.version"],
        ),
    )


class ModelAttempt(Base):
    __tablename__ = "model_attempts"
    attempt_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    evaluation_id: Mapped[str] = mapped_column(ForeignKey("evaluations.evaluation_id"), index=True)
    attempt_number: Mapped[int] = mapped_column(Integer)
    # Private durable record; never included in a public error or console log.
    raw_output: Mapped[dict | str | None] = mapped_column(JSON, nullable=True)
    usage: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    duration_ms: Mapped[int] = mapped_column(Integer)
    error_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Appeal(Base):
    __tablename__ = "appeals"
    appeal_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    evaluation_id: Mapped[str] = mapped_column(ForeignKey("evaluations.evaluation_id"), index=True)
    criterion_id: Mapped[str] = mapped_column(String(100))
    comment: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String(20), default="open")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ReviewDecision(Base):
    __tablename__ = "review_decisions"
    decision_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    appeal_id: Mapped[str] = mapped_column(ForeignKey("appeals.appeal_id"), unique=True)
    evaluation_id: Mapped[str] = mapped_column(ForeignKey("evaluations.evaluation_id"), index=True)
    criterion_id: Mapped[str] = mapped_column(String(100))
    decision: Mapped[str] = mapped_column(String(20))
    new_value: Mapped[str | int | float | None] = mapped_column(JSON, nullable=True)
    reason: Mapped[str] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AuditEvent(Base):
    __tablename__ = "audit_events"
    event_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    evaluation_id: Mapped[str] = mapped_column(ForeignKey("evaluations.evaluation_id"), index=True)
    kind: Mapped[str] = mapped_column(String(40))
    payload: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
