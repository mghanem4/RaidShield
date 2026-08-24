from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any

from pydantic import ValidationError

from app.schemas import NormalizedInput, OfflineDataset
from app.services.reply_context import enrich_reply_context

MAX_OFFLINE_BYTES = 5_000_000


class OfflineDatasetError(ValueError):
    pass


def _scoped_id(kind: str, dataset_name: str, value: str) -> str:
    digest = hashlib.sha256(f"{kind}:{dataset_name}:{value}".encode()).hexdigest()
    return f"offline:{kind}:{digest}"


class OfflineDatasetAdapter:
    """Validates a local JSON batch and emits privacy-minimized normalized events."""

    def load_bytes(self, raw: bytes) -> tuple[dict[str, Any], list[NormalizedInput]]:
        if len(raw) > MAX_OFFLINE_BYTES:
            raise OfflineDatasetError("Offline dataset exceeds the 5 MB limit")
        try:
            payload = json.loads(raw)
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise OfflineDatasetError("Offline dataset must be valid UTF-8 JSON") from exc
        try:
            dataset = OfflineDataset.model_validate(payload)
        except ValidationError as exc:
            # Do not echo Pydantic's input values because they can contain text
            # or raw participant identifiers.
            raise OfflineDatasetError("Offline dataset failed schema validation") from exc

        received_at = datetime.now(timezone.utc)
        events = [
            NormalizedInput(
                source="offline",
                source_event_id=_scoped_id("event", dataset.dataset_name, event.source_event_id),
                post_id=_scoped_id("post", dataset.dataset_name, event.post_id),
                comment_id=_scoped_id("comment", dataset.dataset_name, event.comment_id),
                parent_id=(
                    _scoped_id("comment", dataset.dataset_name, event.parent_id)
                    if event.parent_id
                    else None
                ),
                raw_author_identifier=event.participant_id,
                occurred_at=event.occurred_at,
                received_at=received_at,
                text=event.text,
                manual_content_review_score=event.organizer_review_score,
                metadata={
                    "dataset_label": dataset.dataset_name,
                    "content_origin": dataset.content_origin,
                    "content_detector_eligible": True,
                },
            )
            for event in dataset.events
        ]
        metadata = {
            "dataset_name": dataset.dataset_name,
            "description": dataset.description,
            "content_origin": dataset.content_origin,
            "total_events": len(events),
        }
        return metadata, enrich_reply_context(events)
