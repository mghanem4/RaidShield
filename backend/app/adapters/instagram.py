from __future__ import annotations

import hashlib
import hmac
from datetime import datetime, timezone
from typing import Any

from app.schemas import NormalizedInput


def verify_signature(raw_body: bytes, signature: str | None, secret: str) -> bool:
    if not signature or not secret or not signature.startswith("sha256="):
        return False
    expected = "sha256=" + hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


class InstagramWebhookAdapter:
    """Isolates Meta payload assumptions from the normalized domain."""

    def normalize(self, payload: dict[str, Any]) -> list[NormalizedInput]:
        normalized: list[NormalizedInput] = []
        for entry in payload.get("entry", []):
            for change in entry.get("changes", []):
                if change.get("field") not in {"comments", "live_comments"}:
                    continue
                value = change.get("value", {})
                comment_id = str(value.get("id") or value.get("comment_id") or "")
                post_id = str(value.get("media_id") or value.get("post_id") or "")
                author = (
                    value.get("from", {}).get("id") or value.get("user_id") or value.get("username")
                )
                if not comment_id or not post_id or not author:
                    continue
                occurred = value.get("timestamp") or entry.get("time")
                if isinstance(occurred, (int, float)):
                    occurred_at = datetime.fromtimestamp(occurred, timezone.utc)
                elif occurred:
                    occurred_at = datetime.fromisoformat(str(occurred).replace("Z", "+00:00"))
                else:
                    occurred_at = datetime.now(timezone.utc)
                normalized.append(
                    NormalizedInput(
                        source="instagram",
                        source_event_id=f"instagram:{comment_id}",
                        post_id=post_id,
                        comment_id=comment_id,
                        parent_id=value.get("parent_id"),
                        raw_author_identifier=str(author),
                        occurred_at=occurred_at,
                        received_at=datetime.now(timezone.utc),
                        text=str(value.get("text") or ""),
                        metadata={
                            "is_hidden": bool(value.get("is_hidden", False)),
                            "like_count": int(value.get("like_count", 0)),
                        },
                    )
                )
        return normalized
