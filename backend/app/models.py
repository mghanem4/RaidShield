from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def uuid_str() -> str:
    return str(uuid.uuid4())


class Post(Base):
    __tablename__ = "posts"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    source: Mapped[str] = mapped_column(String(20), nullable=False)
    source_post_id: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    display_label: Mapped[str | None] = mapped_column(String(120))
    first_observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_event_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    comment_count: Mapped[int] = mapped_column(Integer, default=0)
    reply_count: Mapped[int] = mapped_column(Integer, default=0)
    monitoring_status: Mapped[str] = mapped_column(String(20), default="active")
    events: Mapped[list[Event]] = relationship(back_populates="post", cascade="all, delete-orphan")


class Event(Base):
    __tablename__ = "events"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    source: Mapped[str] = mapped_column(String(20), nullable=False)
    source_event_id: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    post_id: Mapped[str] = mapped_column(ForeignKey("posts.id", ondelete="CASCADE"), index=True)
    comment_id: Mapped[str] = mapped_column(String(255), index=True)
    parent_id: Mapped[str | None] = mapped_column(String(255), index=True)
    author_pseudonym: Mapped[str] = mapped_column(String(64), index=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    encrypted_text: Mapped[str | None] = mapped_column(Text)
    text_fingerprint: Mapped[str] = mapped_column(String(64))
    manual_content_review_score: Mapped[float | None] = mapped_column(Float)
    event_metadata: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    post: Mapped[Post] = relationship(back_populates="events")

    __table_args__ = (Index("ix_events_post_time", "post_id", "occurred_at"),)


class Alert(Base):
    __tablename__ = "alerts"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    post_id: Mapped[str] = mapped_column(ForeignKey("posts.id", ondelete="CASCADE"), index=True)
    parent_thread_id: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    window_start: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    window_end: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    coordination_score: Mapped[float] = mapped_column(Float)
    content_review_score: Mapped[float | None] = mapped_column(Float)
    content_review_evidence: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    priority: Mapped[str] = mapped_column(String(20))
    confidence: Mapped[str] = mapped_column(String(20))
    features: Mapped[dict[str, Any]] = mapped_column(JSON)
    explanations: Mapped[list[str]] = mapped_column(JSON)
    event_ids: Mapped[list[str]] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(20), default="new", index=True)
    resolution: Mapped[str | None] = mapped_column(String(40))
    reviewer_note: Mapped[str | None] = mapped_column(Text)
    reviews: Mapped[list[ContentReview]] = relationship(cascade="all, delete-orphan")
    audits: Mapped[list[AlertAudit]] = relationship(cascade="all, delete-orphan")


class ContentReview(Base):
    __tablename__ = "content_reviews"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    alert_id: Mapped[str] = mapped_column(ForeignKey("alerts.id", ondelete="CASCADE"), index=True)
    score: Mapped[float] = mapped_column(Float)
    category: Mapped[str] = mapped_column(String(80))
    reviewer_note: Mapped[str | None] = mapped_column(Text)
    reviewed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class AlertAudit(Base):
    __tablename__ = "alert_audits"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    alert_id: Mapped[str] = mapped_column(ForeignKey("alerts.id", ondelete="CASCADE"), index=True)
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    change_type: Mapped[str] = mapped_column(String(50))
    details: Mapped[dict[str, Any]] = mapped_column(JSON)


class ReplayRun(Base):
    __tablename__ = "replay_runs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    fixture: Mapped[str] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(20), index=True)
    total_events: Mapped[int] = mapped_column(Integer)
    processed_events: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    result_post_id: Mapped[str | None] = mapped_column(String(36))
    result_alert_id: Mapped[str | None] = mapped_column(String(36))


class DetectionSetting(Base):
    __tablename__ = "detection_settings"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    alert_threshold: Mapped[float] = mapped_column(Float, default=0.70)
    minimum_unique_authors: Mapped[int] = mapped_column(Integer, default=4)
    similarity_threshold: Mapped[float] = mapped_column(Float, default=0.85)
    cold_start_threshold: Mapped[int] = mapped_column(Integer, default=6)
    raw_text_retention_hours: Mapped[int] = mapped_column(Integer, default=24)
    aggregate_retention_days: Mapped[int] = mapped_column(Integer, default=30)
    store_raw_text: Mapped[bool] = mapped_column(Boolean, default=False)
