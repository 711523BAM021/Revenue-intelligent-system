from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def new_id() -> str:
    return uuid.uuid4().hex


class Base(DeclarativeBase):
    pass


class SourceRecord(Base):
    """One logical source record, identified by (source_type, source_id)."""

    __tablename__ = "source_records"
    __table_args__ = (UniqueConstraint("source_type", "source_id", name="uq_source_identity"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_type: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    source_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    record_ref: Mapped[str] = mapped_column(String(32), nullable=False, index=True)

    # Revision bookkeeping
    applied_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    first_revision: Mapped[int] = mapped_column(Integer, nullable=False)

    # Source fields (replaced wholesale by a newer revision)
    title: Mapped[str | None] = mapped_column(String(512))
    started_at_utc: Mapped[str | None] = mapped_column(String(40), index=True)
    activity_date: Mapped[str | None] = mapped_column(String(10), index=True)
    started_at_local: Mapped[str | None] = mapped_column(String(40))
    owner_name: Mapped[str | None] = mapped_column(String(160), index=True)
    owner_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    owner_email: Mapped[str | None] = mapped_column(String(200))
    direction: Mapped[str | None] = mapped_column(String(32))
    duration_seconds: Mapped[int | None] = mapped_column(Integer)
    source_outcome: Mapped[str | None] = mapped_column(String(120))
    is_connected: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    is_conversation: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    recording_status: Mapped[str | None] = mapped_column(String(64))
    has_transcript_flag: Mapped[bool | None] = mapped_column(Boolean, nullable=True)

    # Conversation text (also replaced wholesale)
    transcript_text: Mapped[str | None] = mapped_column(Text)
    turns: Mapped[list | None] = mapped_column(JSON)
    unavailable_reason: Mapped[str | None] = mapped_column(Text)
    has_usable_text: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    text_hash: Mapped[str | None] = mapped_column(String(64))

    raw_payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    raw_transcript_payload: Mapped[dict | None] = mapped_column(JSON)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_batch_id: Mapped[str | None] = mapped_column(String(64))
    last_revision_changed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    analysis: Mapped["Analysis | None"] = relationship(
        back_populates="record", uselist=False, cascade="all, delete-orphan"
    )
    routing: Mapped["RoutingDecision | None"] = relationship(
        back_populates="record", uselist=False, cascade="all, delete-orphan"
    )
    review: Mapped["ReviewState | None"] = relationship(
        back_populates="record", uselist=False, cascade="all, delete-orphan"
    )
    override: Mapped["RouteOverride | None"] = relationship(
        back_populates="record", uselist=False, cascade="all, delete-orphan"
    )


class Analysis(Base):
    """Current analysis for a record. Superseded versions kept in AnalysisHistory."""

    __tablename__ = "analyses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    record_id: Mapped[int] = mapped_column(ForeignKey("source_records.id"), unique=True)
    content: Mapped[dict] = mapped_column(JSON, nullable=False)
    origin: Mapped[str] = mapped_column(String(32), nullable=False)  # pre_generated | rules_derived | human_assisted
    author: Mapped[str | None] = mapped_column(String(120))
    freshness: Mapped[str] = mapped_column(String(24), nullable=False)  # current | stale | pending_review | unavailable | missing
    source_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    text_hash: Mapped[str | None] = mapped_column(String(64))
    engine_version: Mapped[str] = mapped_column(String(24), nullable=False, default="1.0")
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    record: Mapped[SourceRecord] = relationship(back_populates="analysis")


class AnalysisHistory(Base):
    __tablename__ = "analysis_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    record_id: Mapped[int] = mapped_column(ForeignKey("source_records.id"), index=True)
    content: Mapped[dict] = mapped_column(JSON, nullable=False)
    origin: Mapped[str] = mapped_column(String(32), nullable=False)
    freshness: Mapped[str] = mapped_column(String(24), nullable=False)
    source_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    text_hash: Mapped[str | None] = mapped_column(String(64))
    archived_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    archive_reason: Mapped[str | None] = mapped_column(String(255))


class RoutingDecision(Base):
    """Automated suggestion, recomputed from the current source revision."""

    __tablename__ = "routing_decisions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    record_id: Mapped[int] = mapped_column(ForeignKey("source_records.id"), unique=True)
    suggested_routes: Mapped[list] = mapped_column(JSON, nullable=False)
    method: Mapped[str] = mapped_column(String(40), nullable=False)
    rationale: Mapped[str | None] = mapped_column(Text)
    trace: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    text_hash: Mapped[str | None] = mapped_column(String(64))
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    record: Mapped[SourceRecord] = relationship(back_populates="routing")


class RouteOverride(Base):
    __tablename__ = "route_overrides"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    record_id: Mapped[int] = mapped_column(ForeignKey("source_records.id"), unique=True)
    effective_routes: Mapped[list] = mapped_column(JSON, nullable=False)
    reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    record: Mapped[SourceRecord] = relationship(back_populates="override")


class ReviewState(Base):
    __tablename__ = "review_states"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    record_id: Mapped[int] = mapped_column(ForeignKey("source_records.id"), unique=True)
    state: Mapped[str] = mapped_column(String(32), nullable=False)  # unreviewed | in_review | reviewed | awaiting_text | needs_review
    note: Mapped[str | None] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    record: Mapped[SourceRecord] = relationship(back_populates="review")


class ImportBatch(Base):
    __tablename__ = "import_batches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    batch_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    delivery_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False)  # applied | failed
    imported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    inserted: Mapped[int] = mapped_column(Integer, default=0)
    updated: Mapped[int] = mapped_column(Integer, default=0)
    ignored: Mapped[int] = mapped_column(Integer, default=0)
    unchanged: Mapped[int] = mapped_column(Integer, default=0)
    errors: Mapped[list] = mapped_column(JSON, default=list)
    details: Mapped[dict] = mapped_column(JSON, default=dict)


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    record_id: Mapped[int | None] = mapped_column(ForeignKey("source_records.id"), index=True)
    kind: Mapped[str] = mapped_column(String(48), nullable=False)
    detail: Mapped[dict] = mapped_column(JSON, default=dict)
    actor: Mapped[str] = mapped_column(String(80), default="manager")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ExportRun(Base):
    __tablename__ = "export_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    state_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    archive_path: Mapped[str] = mapped_column(String(512), nullable=False)
    manifest: Mapped[dict] = mapped_column(JSON, nullable=False)
    record_count: Mapped[int] = mapped_column(Integer, default=0)
    superseded: Mapped[bool] = mapped_column(Boolean, default=False)
