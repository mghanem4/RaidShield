from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class NormalizedInput(BaseModel):
    source: Literal["instagram", "replay"]
    source_event_id: str = Field(min_length=1, max_length=255)
    post_id: str = Field(min_length=1, max_length=255)
    comment_id: str = Field(min_length=1, max_length=255)
    parent_id: str | None = Field(default=None, max_length=255)
    raw_author_identifier: str = Field(min_length=1, max_length=255, exclude=True)
    occurred_at: datetime
    received_at: datetime
    text: str = Field(max_length=10000, exclude=True)
    manual_content_review_score: float | None = Field(default=None, ge=0, le=1)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ReplayRequest(BaseModel):
    fixture: str = Field(pattern=r"^[a-z0-9_]+$")
    speed: float = Field(default=0, ge=0, le=100)
    reset_before_replay: bool = False


class AlertPatch(BaseModel):
    status: Literal["new", "in_review", "resolved", "dismissed"]
    resolution: (
        Literal["confirmed_coordination", "benign_coordination", "uncertain", "false_alert"] | None
    ) = None
    reviewer_note: str | None = Field(default=None, max_length=2000)


class ReviewRequest(BaseModel):
    score: float = Field(ge=0, le=1)
    category: Literal["needs_review", "safety_concern", "context_needed", "no_concern"]
    reviewer_note: str | None = Field(default=None, max_length=2000)


class SettingsUpdate(BaseModel):
    alert_threshold: float = Field(ge=0.1, le=1)
    minimum_unique_authors: int = Field(ge=2, le=100)
    similarity_threshold: float = Field(ge=0.5, le=1)
    cold_start_threshold: int = Field(ge=2, le=100)
    raw_text_retention_hours: int = Field(ge=1, le=168)
    aggregate_retention_days: int = Field(ge=1, le=365)
    store_raw_text: bool
