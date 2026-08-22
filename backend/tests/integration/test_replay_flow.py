import hashlib
import io
import json
import zipfile
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.models import Event
from app.schemas import NormalizedInput
from app.services.ingestion import IngestionService
from app.services.retention import purge_expired


@pytest.mark.parametrize(
    "fixture,alert_expected,priority",
    [
        ("normal_discussion", False, None),
        ("coordinated_benign_burst", True, "medium"),
        ("coordinated_review_burst", True, "high"),
        ("single_review_comment", False, None),
        ("reply_thread_burst", True, "medium"),
    ],
)
def test_fixture_expected_outcomes(client, auth, fixture, alert_expected, priority):
    response = client.post(
        "/api/v1/replay",
        headers=auth,
        json={"fixture": fixture, "speed": 0, "reset_before_replay": True},
    )
    assert response.status_code == 200, response.text
    run = response.json()
    assert run["status"] == "completed"
    assert bool(run["result_alert_id"]) is alert_expected
    if alert_expected:
        alert = client.get(f"/api/v1/alerts/{run['result_alert_id']}").json()
        assert alert["priority"] == priority
        assert alert["coordination_score"] >= 0.7
        assert "human review" in " ".join(alert["explanations"]).lower()


def test_idempotency_pseudonym_and_no_raw_storage(db, settings):
    item = NormalizedInput(
        source="replay",
        source_event_id="same-id",
        post_id="p",
        comment_id="c",
        raw_author_identifier="raw-user-name",
        occurred_at=datetime.now(timezone.utc),
        received_at=datetime.now(timezone.utc),
        text="Raw comment text",
    )
    service = IngestionService(db, settings)
    first, created, _ = service.ingest(item)
    second, duplicate, _ = service.ingest(item)
    assert created and not duplicate and first.id == second.id
    row = db.scalar(select(Event))
    assert row and row.encrypted_text is None
    assert row.author_pseudonym != "raw-user-name"
    assert "raw-user-name" not in str(row.__dict__)
    assert "Raw comment text" not in str(row.__dict__)


def test_reply_thread_review_export_and_manifest(client, auth):
    run = client.post(
        "/api/v1/replay",
        headers=auth,
        json={"fixture": "reply_thread_burst", "speed": 0, "reset_before_replay": True},
    ).json()
    alert_id, post_id = run["result_alert_id"], run["result_post_id"]
    threads = client.get(f"/api/v1/posts/{post_id}/threads").json()
    assert len(threads["threads"][0]["replies"]) == 12
    assert all(
        x["participant"].startswith("Participant ") for x in threads["threads"][0]["replies"]
    )
    reviewed = client.patch(
        f"/api/v1/alerts/{alert_id}",
        headers=auth,
        json={
            "status": "resolved",
            "resolution": "benign_coordination",
            "reviewer_note": "Safe campaign context",
        },
    )
    assert reviewed.json()["resolution"] == "benign_coordination"
    exported = client.post(f"/api/v1/alerts/{alert_id}/export", headers=auth)
    assert exported.status_code == 200
    with zipfile.ZipFile(io.BytesIO(exported.content)) as archive:
        names = set(archive.namelist())
        assert names == {
            "incident_report.html",
            "incident_report.json",
            "integrity_manifest.json",
            "README.txt",
        }
        report = json.loads(archive.read("incident_report.json"))
        assert "username" not in json.dumps(report).lower()
        manifest = json.loads(archive.read("integrity_manifest.json"))
        for name, digest in manifest["files"].items():
            assert hashlib.sha256(archive.read(name)).hexdigest() == digest


def test_content_review_stays_separate(client, auth):
    run = client.post(
        "/api/v1/replay",
        headers=auth,
        json={"fixture": "coordinated_benign_burst", "speed": 0, "reset_before_replay": True},
    ).json()
    before = client.get(f"/api/v1/alerts/{run['result_alert_id']}").json()
    after = client.post(
        f"/api/v1/alerts/{run['result_alert_id']}/content-review",
        headers=auth,
        json={"score": 0.8, "category": "needs_review"},
    ).json()
    assert after["coordination_score"] == before["coordination_score"]
    assert after["content_review_score"] == 0.8 and after["priority"] == "high"


def test_retention_clears_expired_text_and_rows(db, settings):
    settings.store_raw_text = True
    old = datetime.now(timezone.utc) - timedelta(days=40)
    item = NormalizedInput(
        source="replay",
        source_event_id="old",
        post_id="old-post",
        comment_id="old-comment",
        raw_author_identifier="old-user",
        occurred_at=old,
        received_at=old,
        text="Encrypted old text",
    )
    IngestionService(db, settings).ingest(item)
    assert db.scalar(select(Event)).encrypted_text is not None
    counts = purge_expired(db, 24, 30)
    assert counts["raw_text_cleared"] == 1 and counts["events_deleted"] == 1
    settings.store_raw_text = False


def test_auth_validation_health_and_delete(client, auth):
    assert client.get("/api/v1/health").json()["database_ready"]
    assert (
        client.post("/api/v1/replay", json={"fixture": "single_review_comment"}).status_code == 401
    )
    assert client.put("/api/v1/settings/detection", headers=auth, json={}).status_code == 422
    assert client.delete("/api/v1/admin/data?confirmation=wrong", headers=auth).status_code == 422
