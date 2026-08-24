import hashlib
import io
import json
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from sqlalchemy import select

from app.models import Event
from app.schemas import NormalizedInput
from app.services.content_detector import ContentSignal, ReplyContextSignal
from app.services.ingestion import IngestionService
from app.services.retention import purge_expired
from app.services.semantic_context import event_reference


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


def test_thread_semantic_context_is_aggregated_and_reference_free(client, db, settings):
    started = datetime.now(timezone.utc)
    right_ref = event_reference("semantic-right")
    service = IngestionService(db, settings)
    left, _, _ = service.ingest(
        NormalizedInput(
            source="offline",
            source_event_id="semantic-left",
            post_id="semantic-post",
            comment_id="semantic-left-comment",
            raw_author_identifier="semantic-left-author",
            occurred_at=started,
            received_at=started,
            text="A harmless planning suggestion.",
            metadata={
                "semantic_context": {
                    "source": "experimental_local_semantic_model",
                    "status": "evaluated",
                    "model_id": "safe-test-model",
                    "model_revision": "safe-test-revision",
                    "threshold": 0.78,
                    "time_window_seconds": 60,
                    "neighbor_count": 1,
                    "neighbors": [
                        {
                            "event_ref": right_ref,
                            "similarity": 0.84,
                            "seconds_apart": 5,
                            "shared_parent": False,
                            "private_debug": "MUST_NOT_LEAK",
                        }
                    ],
                }
            },
        )
    )
    service.ingest(
        NormalizedInput(
            source="offline",
            source_event_id="semantic-right",
            post_id="semantic-post",
            comment_id="semantic-right-comment",
            raw_author_identifier="semantic-right-author",
            occurred_at=started + timedelta(seconds=5),
            received_at=started,
            text="A differently worded harmless planning suggestion.",
        )
    )

    payload = client.get(f"/api/v1/posts/{left.post_id}/threads").json()
    context = payload["threads"][0]["semantic_context"]

    assert context["neighbor_count"] == 1
    assert context["strongest_similarity"] == 0.84
    assert context["closest_timing_seconds"] == 5
    serialized = json.dumps(payload)
    assert right_ref not in serialized
    assert "MUST_NOT_LEAK" not in serialized
    assert "planning suggestion" not in serialized


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
    reply_context = threads["threads"][0]["replies"][0]["reply_context"]
    assert reply_context["parent_available"] is True
    assert reply_context["sibling_count"] == 11
    assert reply_context["current"]["relation"] == "repeated_with_siblings"
    assert "PATTERN_ALPHA" not in json.dumps(reply_context)
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
        assert len(report["coordination_graph"]["nodes"]) == 13
        assert report["coordination_graph"]["summary"]["cluster_count"] == 1
        assert "automation" in report["coordination_graph"]["method"]["safety_statement"]
        exported_contexts = [
            event["reply_context"] for event in report["events"] if event["reply_context"]
        ]
        assert exported_contexts[0]["current"]["relation"] == "repeated_with_siblings"
        assert "PATTERN_ALPHA" not in json.dumps(exported_contexts)
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
    assert after["content_review_evidence"]["current"]["source"] == "human_review"


class StubContentDetector:
    def analyze(self, _text):
        return ContentSignal(
            score=0.76,
            category="direct_insult",
            requires_review=True,
            context_score=0.2,
            label_scores={"direct_insult": 0.76},
            model_id="local-test-model",
            model_revision="test-revision",
            threshold=0.65,
        )


class StubContextDetector:
    def analyze(self, _text):
        return None

    def analyze_context(self, _parent_text, _reply_text):
        return ReplyContextSignal(
            relation="opposes_parent",
            score=0.74,
            relation_scores={"opposes_parent": 0.74, "ambiguous_context": 0.26},
            model_id="local-context-test-model",
            model_revision="context-test-revision",
        )


def test_parent_reply_model_context_is_separate_private_metadata(db, settings):
    event, created, _ = IngestionService(db, settings, StubContextDetector()).ingest(
        NormalizedInput(
            source="offline",
            source_event_id="context-event",
            post_id="context-post",
            comment_id="context-reply",
            parent_id="context-parent",
            raw_author_identifier="context-author",
            occurred_at=datetime.now(timezone.utc),
            received_at=datetime.now(timezone.utc),
            text="I disagree; the library should remain open.",
            context_parent_text="The library should close.",
            metadata={
                "reply_context": {
                    "current": {
                        "source": "deterministic_structure",
                        "relation": "parent_context_available",
                    }
                }
            },
        )
    )

    assert created
    context = event.event_metadata["reply_context"]
    assert context["current"]["source"] == "experimental_local_context_model"
    assert context["current"]["relation"] == "opposes_parent"
    assert context["semantic_model"]["requires_human_review"] is True
    assert "library" not in str(context).lower()


class FailingContextDetector:
    def analyze(self, _text):
        return None

    def analyze_context(self, _parent_text, _reply_text):
        raise RuntimeError("private parent and reply detail must not be persisted")


def test_parent_reply_model_failure_is_sanitized_and_non_blocking(db, settings):
    event, created, _ = IngestionService(db, settings, FailingContextDetector()).ingest(
        NormalizedInput(
            source="offline",
            source_event_id="failed-context-event",
            post_id="failed-context-post",
            comment_id="failed-context-reply",
            parent_id="failed-context-parent",
            raw_author_identifier="failed-context-author",
            occurred_at=datetime.now(timezone.utc),
            received_at=datetime.now(timezone.utc),
            text="I would like a later closing time.",
            context_parent_text="The library should close at eight.",
            metadata={
                "reply_context": {
                    "current": {
                        "source": "deterministic_structure",
                        "relation": "parent_context_available",
                    }
                }
            },
        )
    )

    assert created
    context = event.event_metadata["reply_context"]
    assert context["current"]["relation"] == "parent_context_available"
    assert context["semantic_model"] == {
        "source": "experimental_local_context_model",
        "status": "unavailable",
        "reason": "local_context_inference_failed",
    }
    assert "private parent" not in str(context).lower()
    assert "library" not in str(context).lower()


def test_experimental_content_signal_prioritizes_but_does_not_change_coordination(
    client, db, settings
):
    service = IngestionService(db, settings, StubContentDetector())
    start = datetime.now(timezone.utc)
    alert = None
    for index in range(4):
        _, _, alert = service.ingest(
            NormalizedInput(
                source="replay",
                source_event_id=f"model-event-{index}",
                post_id="model-post",
                comment_id=f"model-comment-{index}",
                parent_id="safe-parent",
                raw_author_identifier=f"safe-author-{index}",
                occurred_at=start + timedelta(seconds=index * 2),
                received_at=start + timedelta(seconds=index * 2),
                text="PATTERN_REDACTED_REVIEW",
                metadata={"content_detector_eligible": True},
            )
        )

    assert alert is not None
    assert alert.coordination_score >= settings.alert_threshold
    assert alert.content_review_score == 0.76
    assert alert.priority == "high"
    assert alert.content_review_evidence["current"]["source"] == "experimental_local_model"
    event = db.scalar(select(Event).where(Event.source_event_id == "model-event-0"))
    assert event is not None
    assert "PATTERN_REDACTED_REVIEW" not in str(event.event_metadata)
    signal = dict(event.event_metadata["experimental_content_signal"])
    signal["raw_explanation"] = "PRIVATE_MODEL_DETAIL"
    event.event_metadata = {**event.event_metadata, "experimental_content_signal": signal}
    db.commit()
    threads = client.get(f"/api/v1/posts/{event.post_id}/threads").json()
    public_signal = threads["unknown_parent_replies"][0]["content_signal"]
    assert public_signal["category"] == "direct_insult"
    assert public_signal["label_scores"] == {"direct_insult": 0.76}
    assert public_signal["threshold"] == 0.65
    assert "raw_explanation" not in public_signal
    assert "PRIVATE_MODEL_DETAIL" not in json.dumps(threads)


class FailingContentDetector:
    def analyze(self, _text):
        raise RuntimeError("sensitive upstream detail must not be persisted")


def test_optional_detector_failure_is_sanitized_and_does_not_block_ingestion(db, settings):
    event, created, _ = IngestionService(db, settings, FailingContentDetector()).ingest(
        NormalizedInput(
            source="replay",
            source_event_id="failed-model-event",
            post_id="failed-model-post",
            comment_id="failed-model-comment",
            raw_author_identifier="failed-model-author",
            occurred_at=datetime.now(timezone.utc),
            received_at=datetime.now(timezone.utc),
            text="SAFE_INPUT",
            metadata={"content_detector_eligible": True},
        )
    )
    assert created
    assert event.event_metadata["experimental_content_signal"] == {
        "source": "experimental_local_model",
        "status": "unavailable",
        "reason": "local_detector_inference_failed",
    }
    assert "sensitive upstream detail" not in str(event.event_metadata)


def test_export_includes_decrypted_text_only_when_enabled(client, auth, settings):
    settings.store_raw_text = True
    try:
        run = client.post(
            "/api/v1/replay",
            headers=auth,
            json={
                "fixture": "coordinated_benign_burst",
                "speed": 0,
                "reset_before_replay": True,
            },
        ).json()
        exported = client.post(f"/api/v1/alerts/{run['result_alert_id']}/export", headers=auth)
        with zipfile.ZipFile(io.BytesIO(exported.content)) as archive:
            report = json.loads(archive.read("incident_report.json"))
            report_html = archive.read("incident_report.html").decode()
        assert report["events"][0]["content"].startswith("PATTERN_ALPHA")
        assert "PATTERN_ALPHA" in report_html
        assert "benign-a01" not in json.dumps(report)
    finally:
        settings.store_raw_text = False


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


def test_offline_json_import_is_private_idempotent_and_generates_alert(client, auth, db):
    start = datetime(2026, 8, 24, 12, 0, tzinfo=timezone.utc)
    payload = {
        "dataset_name": "authorized_safe_batch",
        "description": "Synthetic safe synchronized offline activity.",
        "content_origin": "synthetic-safe-placeholder",
        "events": [
            {
                "source_event_id": f"offline-event-{index}",
                "post_id": "offline-post",
                "comment_id": f"offline-comment-{index}",
                "parent_id": "offline-parent",
                "participant_id": f"raw-participant-{index}",
                "occurred_at": (start + timedelta(seconds=index * 2)).isoformat(),
                "text": "PATTERN_OFFLINE_REVIEW",
            }
            for index in range(4)
        ],
    }
    first = client.post(
        "/api/v1/offline/import",
        headers=auth,
        files={"file": ("safe-batch.json", json.dumps(payload), "application/json")},
    )
    assert first.status_code == 200, first.text
    result = first.json()
    assert result["created_events"] == 4
    assert result["duplicate_events"] == 0
    assert len(result["result_post_ids"]) == 1
    assert len(result["result_alert_ids"]) == 1

    graph_response = client.get(f"/api/v1/posts/{result['result_post_ids'][0]}/coordination-graph")
    assert graph_response.status_code == 200
    graph = graph_response.json()
    assert graph["summary"] == {
        "participant_count_total": 4,
        "participant_count_shown": 4,
        "edge_count": 6,
        "cluster_count": 1,
        "strongest_edge": graph["summary"]["strongest_edge"],
        "truncated": False,
    }
    assert graph["summary"]["strongest_edge"] > 0.9
    assert all(edge["reasons"] for edge in graph["edges"])
    assert "raw-participant" not in graph_response.text
    assert "PATTERN_OFFLINE_REVIEW" not in graph_response.text

    rows = list(db.scalars(select(Event)))
    assert len(rows) == 4
    assert all(row.source == "offline" for row in rows)
    assert all(row.encrypted_text is None for row in rows)
    serialized = str([row.__dict__ for row in rows])
    assert "raw-participant" not in serialized
    assert "PATTERN_OFFLINE_REVIEW" not in serialized
    assert "safe-batch.json" not in serialized

    second = client.post(
        "/api/v1/offline/import",
        headers=auth,
        files={"file": ("safe-batch.json", json.dumps(payload), "application/json")},
    ).json()
    assert second["created_events"] == 0
    assert second["duplicate_events"] == 4


def test_harmless_bot_like_example_builds_coordination_graph(client, auth):
    example_path = (
        Path(__file__).resolve().parents[3] / "examples" / "offline_safe_bot_raid_demo.json"
    )
    payload = json.loads(example_path.read_text())
    assert all(event["text"].startswith("SAFE DEMO:") for event in payload["events"])
    assert all(event["organizer_review_score"] == 0.0 for event in payload["events"])

    imported = client.post(
        "/api/v1/offline/import",
        headers=auth,
        files={"file": (example_path.name, json.dumps(payload), "application/json")},
    )
    assert imported.status_code == 200
    result = imported.json()
    alert = client.get(f"/api/v1/alerts/{result['result_alert_ids'][0]}").json()
    graph = client.get(f"/api/v1/posts/{result['result_post_ids'][0]}/coordination-graph").json()

    assert alert["priority"] == "medium"
    assert alert["content_review_score"] == 0.0
    assert alert["coordination_score"] > 0.9
    assert graph["summary"]["participant_count_total"] == 13
    assert graph["summary"]["cluster_count"] == 1
    assert graph["summary"]["edge_count"] > 40


def test_offline_import_rejects_unauthorized_or_invalid_files(client, auth):
    assert (
        client.post(
            "/api/v1/offline/import",
            files={"file": ("safe.json", "{}", "application/json")},
        ).status_code
        == 401
    )
    wrong_type = client.post(
        "/api/v1/offline/import",
        headers=auth,
        files={"file": ("safe.csv", "value", "text/csv")},
    )
    assert wrong_type.status_code == 415
    invalid = client.post(
        "/api/v1/offline/import",
        headers=auth,
        files={"file": ("safe.json", "{}", "application/json")},
    )
    assert invalid.status_code == 422
    assert "input" not in invalid.text.lower()
    assert client.get("/api/v1/posts/missing/coordination-graph").status_code == 404
