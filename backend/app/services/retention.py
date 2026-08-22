from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, update
from sqlalchemy.orm import Session

from app.models import Alert, Event, Post


def purge_expired(db: Session, raw_hours: int, aggregate_days: int) -> dict[str, int]:
    now = datetime.now(timezone.utc)
    raw_result = db.execute(
        update(Event)
        .where(
            Event.occurred_at < now - timedelta(hours=raw_hours), Event.encrypted_text.is_not(None)
        )
        .values(encrypted_text=None)
    )
    old_alerts = db.execute(
        delete(Alert).where(Alert.created_at < now - timedelta(days=aggregate_days))
    )
    old_events = db.execute(
        delete(Event).where(Event.occurred_at < now - timedelta(days=aggregate_days))
    )
    old_posts = db.execute(delete(Post).where(~Post.events.any()))
    db.commit()
    return {
        "raw_text_cleared": int(getattr(raw_result, "rowcount", 0)),
        "alerts_deleted": int(getattr(old_alerts, "rowcount", 0)),
        "events_deleted": int(getattr(old_events, "rowcount", 0)),
        "posts_deleted": int(getattr(old_posts, "rowcount", 0)),
    }
