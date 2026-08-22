from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import Settings
from app.detection import calculate_features, confidence, explanations, score
from app.models import Alert, AlertAudit, Event, Post, ReplayRun
from app.schemas import NormalizedInput
from app.services.crypto import (
    decrypt_text,
    encrypt_text,
    fingerprint,
    normalize_text,
    pseudonymize,
)

_transient_text: dict[str, str] = {}


def utc(value: datetime) -> datetime:
    return (
        value.replace(tzinfo=timezone.utc)
        if value.tzinfo is None
        else value.astimezone(timezone.utc)
    )


class IngestionService:
    def __init__(self, db: Session, settings: Settings):
        self.db = db
        self.settings = settings

    def ingest(self, item: NormalizedInput) -> tuple[Event, bool, Alert | None]:
        existing = self.db.scalar(
            select(Event).where(Event.source_event_id == item.source_event_id)
        )
        if existing:
            return existing, False, self._latest_alert(existing.post_id)
        digest = pseudonymize(
            item.source, item.raw_author_identifier, self.settings.pseudonymization_key
        )
        post = self.db.scalar(select(Post).where(Post.source_post_id == item.post_id))
        if post is None:
            post = Post(
                source=item.source,
                source_post_id=item.post_id,
                display_label=f"Protected post {item.post_id[-6:]}",
                first_observed_at=item.occurred_at,
                last_event_at=item.occurred_at,
            )
            self.db.add(post)
            self.db.flush()
        encrypted = None
        if self.settings.store_raw_text:
            if not self.settings.data_encryption_key:
                raise ValueError("Raw text storage is enabled but no encryption key is configured")
            encrypted = encrypt_text(item.text, self.settings.data_encryption_key)
        event = Event(
            source=item.source,
            source_event_id=item.source_event_id,
            post_id=post.id,
            comment_id=item.comment_id,
            parent_id=item.parent_id,
            author_pseudonym=digest,
            occurred_at=utc(item.occurred_at),
            received_at=utc(item.received_at),
            encrypted_text=encrypted,
            text_fingerprint=fingerprint(item.text),
            manual_content_review_score=item.manual_content_review_score,
            event_metadata=item.metadata,
        )
        self.db.add(event)
        post.last_event_at = max(utc(post.last_event_at), utc(item.occurred_at))
        post.reply_count += int(item.parent_id is not None)
        post.comment_count += int(item.parent_id is None)
        try:
            self.db.flush()
        except IntegrityError:
            self.db.rollback()
            duplicate = self.db.scalar(
                select(Event).where(Event.source_event_id == item.source_event_id)
            )
            if duplicate is None:
                raise
            return duplicate, False, self._latest_alert(duplicate.post_id)
        _transient_text[event.id] = normalize_text(item.text)
        alert = self._evaluate(post.id, utc(item.occurred_at))
        self.db.commit()
        return event, True, alert

    def _latest_alert(self, post_id: str) -> Alert | None:
        return self.db.scalar(
            select(Alert).where(Alert.post_id == post_id).order_by(Alert.created_at.desc())
        )

    def _evaluate(self, post_id: str, window_end: datetime) -> Alert | None:
        window_start = window_end - timedelta(minutes=2)
        events = list(
            self.db.scalars(
                select(Event)
                .where(
                    Event.post_id == post_id,
                    Event.occurred_at >= window_start,
                    Event.occurred_at <= window_end,
                )
                .order_by(Event.occurred_at)
            )
        )
        authors = {event.author_pseudonym for event in events}
        if len(authors) < self.settings.minimum_unique_authors:
            return None
        previous = set(
            self.db.scalars(
                select(Event.author_pseudonym).where(
                    Event.post_id == post_id, Event.occurred_at < window_start
                )
            ).all()
        )
        texts: list[str] = []
        for event in events:
            text = _transient_text.get(event.id)
            if text is None and event.encrypted_text and self.settings.data_encryption_key:
                text = normalize_text(
                    decrypt_text(event.encrypted_text, self.settings.data_encryption_key)
                )
            texts.append(text or event.text_fingerprint)
        features = calculate_features(
            events,
            texts,
            previous,
            self.settings.cold_start_unique_author_threshold,
            self.settings.similarity_threshold,
        )
        coordination = score(features)
        if coordination < self.settings.alert_threshold:
            return None
        content_scores = [
            e.manual_content_review_score
            for e in events
            if e.manual_content_review_score is not None
        ]
        content_score = max(content_scores) if content_scores else None
        priority = "high" if content_score is not None and content_score >= 0.5 else "medium"
        existing = self.db.scalar(
            select(Alert)
            .where(
                Alert.post_id == post_id,
                Alert.status.in_(["new", "in_review"]),
                Alert.window_end >= window_start,
            )
            .order_by(Alert.created_at.desc())
        )
        parent_counts: dict[str, int] = {}
        for event in events:
            if event.parent_id:
                parent_counts[event.parent_id] = parent_counts.get(event.parent_id, 0) + 1
        parent = max(parent_counts, key=parent_counts.get) if parent_counts else None  # type: ignore[arg-type]
        values = features.dict()
        reasons = explanations(features)
        event_ids = [event.id for event in events]
        if existing:
            old_score = existing.coordination_score
            existing.window_start = min(utc(existing.window_start), window_start)
            existing.window_end = window_end
            existing.coordination_score = coordination
            existing.content_review_score = content_score
            existing.priority = priority
            existing.confidence = confidence(features)
            existing.features, existing.explanations, existing.event_ids = (
                values,
                reasons,
                event_ids,
            )
            existing.parent_thread_id = parent
            if abs(old_score - coordination) >= 0.05:
                self.db.add(
                    AlertAudit(
                        alert_id=existing.id,
                        changed_at=datetime.now(timezone.utc),
                        change_type="score_update",
                        details={"previous": old_score, "current": coordination},
                    )
                )
            return existing
        alert = Alert(
            post_id=post_id,
            parent_thread_id=parent,
            created_at=datetime.now(timezone.utc),
            window_start=window_start,
            window_end=window_end,
            coordination_score=coordination,
            content_review_score=content_score,
            priority=priority,
            confidence=confidence(features),
            features=values,
            explanations=reasons,
            event_ids=event_ids,
            status="new",
        )
        self.db.add(alert)
        self.db.flush()
        return alert


def purge_all(db: Session) -> None:
    for model in (AlertAudit, Alert, Event, Post, ReplayRun):
        db.execute(delete(model))
    _transient_text.clear()
    db.commit()
