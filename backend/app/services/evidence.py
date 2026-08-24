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
from app.services.coordination_graph import build_coordination_graph
from app.services.crypto import decrypt_text, display_pseudonym


def _reply_context_relation(reply_context: object) -> str:
    if not isinstance(reply_context, dict):
        return "Not evaluated"
    current = reply_context.get("current")
    if not isinstance(current, dict):
        return "Not evaluated"
    return str(current.get("relation", "Not evaluated")).replace("_", " ")


def build_evidence_zip(db: Session, alert: Alert, encryption_key: str = "") -> bytes:
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
            "content_review_evidence": alert.content_review_evidence,
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
                "content": (
                    decrypt_text(event.encrypted_text, encryption_key)
                    if event.encrypted_text and encryption_key
                    else "content hidden"
                ),
                "reply_context": (
                    event.event_metadata.get("reply_context")
                    if isinstance(event.event_metadata, dict)
                    else None
                ),
            }
            for event in events
        ],
        "coordination_graph": build_coordination_graph(events),
        "limitations": [
            "Observable coordination indicators require human review.",
            "The system cannot observe private messages or infer intent.",
        ],
    }
    json_bytes = json.dumps(record, indent=2, sort_keys=True).encode()
    reasons = "".join(f"<li>{html.escape(reason)}</li>" for reason in alert.explanations)
    current_review = (alert.content_review_evidence or {}).get("current") or {}
    content_summary = (
        "No independent content-review score was provided."
        if alert.content_review_score is None
        else (
            f"Review score: {alert.content_review_score:.0%}; source: "
            f"{str(current_review.get('source', 'unspecified')).replace('_', ' ')}; "
            f"category: {str(current_review.get('category', 'not specified')).replace('_', ' ')}."
        )
    )
    event_rows = "".join(
        "<tr>"
        f"<td>{html.escape(str(event['occurred_at']))}</td>"
        f"<td>{html.escape(str(event['participant']))}</td>"
        f"<td>{html.escape(str(event['parent_id'] or 'Top level'))}</td>"
        "<td>"
        f"{html.escape(_reply_context_relation(event['reply_context']))}"
        "</td>"
        f"<td>{html.escape(str(event['content']))}</td>"
        "</tr>"
        for event in record["events"]
    )
    html_bytes = (
        "<!doctype html><html><head><meta charset='utf-8'><title>RaidShield incident report"
        "</title></head><body><h1>RaidShield incident report</h1>"
        f"<p>{html.escape(record['disclosure'])}</p><h2>Indicators</h2><ul>{reasons}</ul>"
        f"<h2>Independent content review</h2><p>{html.escape(content_summary)}</p>"
        "<p>Experimental model output is a triage signal, not a probability or determination.</p>"
        f"<h2>Coordination graph</h2><p>{len(record['coordination_graph']['nodes'])} "
        f"participants and {len(record['coordination_graph']['edges'])} behavioral connections. "
        "See incident_report.json for the redacted graph data.</p>"
        "<h2>Reply-thread evidence</h2><table><thead><tr>"
        "<th>Timestamp</th><th>Participant</th><th>Parent</th>"
        "<th>Reply context</th><th>Content</th>"
        f"</tr></thead><tbody>{event_rows}</tbody></table>"
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
