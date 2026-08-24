from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import Settings
from app.detection import calculate_features, confidence, explanations, score
from app.models import Alert, AlertAudit, Event, Post, ReplayRun
from app.schemas import NormalizedInput
from app.services.content_detector import ContentDetector, configured_detector
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
    def __init__(
        self,
        db: Session,
        settings: Settings,
        content_detector: ContentDetector | None = None,
    ):
        self.db = db
        self.settings = settings
        self.content_detector = content_detector or configured_detector(settings)

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
        event_metadata = dict(item.metadata)
        detector_eligible = (
            item.source == "offline" or item.metadata.get("content_detector_eligible") is True
        )
        if self.content_detector and detector_eligible:
            try:
                signal = self.content_detector.analyze(item.text)
                if signal:
                    event_metadata["experimental_content_signal"] = signal.metadata()
            except Exception:  # The optional detector must never block ingestion.
                event_metadata["experimental_content_signal"] = {
                    "source": "experimental_local_model",
                    "status": "unavailable",
                    "reason": "local_detector_inference_failed",
                }
            context_analyzer = getattr(self.content_detector, "analyze_context", None)
            if item.context_parent_text and callable(context_analyzer):
                reply_context = dict(event_metadata.get("reply_context") or {})
                try:
                    context_signal = context_analyzer(item.context_parent_text, item.text)
                    if context_signal:
                        semantic_metadata = context_signal.metadata()
                        reply_context["semantic_model"] = semantic_metadata
                        reply_context["current"] = semantic_metadata
                except Exception:
                    reply_context["semantic_model"] = {
                        "source": "experimental_local_context_model",
                        "status": "unavailable",
                        "reason": "local_context_inference_failed",
                    }
                event_metadata["reply_context"] = reply_context
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
            event_metadata=event_metadata,
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
        manual_scores = [
            e.manual_content_review_score
            for e in events
            if e.manual_content_review_score is not None
        ]
        detector_signals = [
            signal
            for event in events
            if isinstance(event.event_metadata, dict)
            and isinstance(signal := event.event_metadata.get("experimental_content_signal"), dict)
            and isinstance(signal.get("score"), (int, float))
        ]
        strongest_signal = (
            max(detector_signals, key=lambda item: float(item["score"]))
            if detector_signals
            else None
        )
        if manual_scores:
            content_score = max(manual_scores)
            evidence: dict[str, object] | None = {
                "current": {
                    "source": "organizer_annotation",
                    "score": content_score,
                    "status": "review_required" if content_score >= 0.5 else "no_concern",
                },
                "experimental_local_model": strongest_signal,
            }
        elif strongest_signal and strongest_signal.get("requires_review") is True:
            content_score = float(strongest_signal["score"])
            evidence = {
                "current": strongest_signal,
                "experimental_local_model": strongest_signal,
            }
        else:
            content_score = None
            evidence = (
                {
                    "current": None,
                    "experimental_local_model": strongest_signal,
                }
                if strongest_signal
                else None
            )
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
            if existing.reviews:
                latest_review = max(existing.reviews, key=lambda review: review.reviewed_at)
                content_score = latest_review.score
                priority = "high" if content_score >= 0.5 else "medium"
                evidence = {
                    "current": {
                        "source": "human_review",
                        "score": latest_review.score,
                        "category": latest_review.category,
                        "status": (
                            "review_required" if latest_review.score >= 0.5 else "no_concern"
                        ),
                    },
                    "experimental_local_model": strongest_signal,
                }
            old_score = existing.coordination_score
            existing.window_start = min(utc(existing.window_start), window_start)
            existing.window_end = window_end
            existing.coordination_score = coordination
            existing.content_review_score = content_score
            existing.content_review_evidence = evidence
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
            content_review_evidence=evidence,
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
