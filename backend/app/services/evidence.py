from __future__ import annotations

import hashlib
import html
import io
import json
import zipfile
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Alert, Event, Post
from app.services.crypto import display_pseudonym


def build_evidence_zip(db: Session, alert: Alert) -> bytes:
    post = db.get(Post, alert.post_id)
    events = list(
        db.scalars(select(Event).where(Event.id.in_(alert.event_ids)).order_by(Event.occurred_at))
    )
    record: dict[str, Any] = {
        "application": "RaidShield",
        "version": "0.1.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "disclosure": "Decision-support export; not a forensic certification or proof of intent.",
        "source": post.source if post else "unknown",
        "post_label": post.display_label if post else None,
        "alert": {
            "id": alert.id,
            "window_start": alert.window_start.isoformat(),
            "window_end": alert.window_end.isoformat(),
            "coordination_score": alert.coordination_score,
            "content_review_score": alert.content_review_score,
            "priority": alert.priority,
            "confidence": alert.confidence,
            "features": alert.features,
            "explanations": alert.explanations,
            "status": alert.status,
            "resolution": alert.resolution,
            "reviewer_note": alert.reviewer_note,
        },
        "events": [
            {
                "id": event.id,
                "comment_id": event.comment_id,
                "parent_id": event.parent_id,
                "participant": display_pseudonym(event.author_pseudonym),
                "occurred_at": event.occurred_at.isoformat(),
                "content": "content hidden",
            }
            for event in events
        ],
        "limitations": [
            "Observable coordination indicators require human review.",
            "The system cannot observe private messages or infer intent.",
        ],
    }
    json_bytes = json.dumps(record, indent=2, sort_keys=True).encode()
    reasons = "".join(f"<li>{html.escape(reason)}</li>" for reason in alert.explanations)
    html_bytes = (
        "<!doctype html><html><head><meta charset='utf-8'><title>RaidShield incident report"
        "</title></head><body><h1>RaidShield incident report</h1>"
        f"<p>{html.escape(record['disclosure'])}</p><h2>Indicators</h2><ul>{reasons}</ul>"
        "<p>Signals prioritize human review; they do not prove intent or a policy violation.</p>"
        "</body></html>"
    ).encode()
    readme = (
        b"RaidShield redacted evidence package. Verify file hashes against "
        b"integrity_manifest.json.\n"
    )
    files = {
        "incident_report.json": json_bytes,
        "incident_report.html": html_bytes,
        "README.txt": readme,
    }
    manifest = {
        "algorithm": "SHA-256",
        "files": {
            name: hashlib.sha256(content).hexdigest() for name, content in sorted(files.items())
        },
    }
    files["integrity_manifest.json"] = json.dumps(manifest, indent=2, sort_keys=True).encode()
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, content in sorted(files.items()):
            archive.writestr(name, content)
    return output.getvalue()
