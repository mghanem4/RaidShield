import hashlib
import hmac
import json

from app.adapters.instagram import InstagramWebhookAdapter, verify_signature

PAYLOAD = {
    "entry": [
        {
            "time": 1787328000,
            "changes": [
                {
                    "field": "comments",
                    "value": {
                        "id": "comment-1",
                        "media_id": "media-1",
                        "text": "Safe sample",
                        "from": {"id": "user-1"},
                        "parent_id": "parent-1",
                        "timestamp": "2026-08-21T16:00:00Z",
                    },
                }
            ],
        }
    ]
}


def test_signature_valid_invalid_missing_and_modified():
    body = json.dumps(PAYLOAD).encode()
    signature = "sha256=" + hmac.new(b"secret", body, hashlib.sha256).hexdigest()
    assert verify_signature(body, signature, "secret")
    assert not verify_signature(body + b" ", signature, "secret")
    assert not verify_signature(body, "sha256=bad", "secret")
    assert not verify_signature(body, None, "secret")


def test_supported_reply_normalizes_parent():
    event = InstagramWebhookAdapter().normalize(PAYLOAD)[0]
    assert event.source_event_id == "instagram:comment-1"
    assert event.parent_id == "parent-1"
    assert event.raw_author_identifier == "user-1"


def test_unsupported_or_incomplete_payload_is_ignored():
    assert (
        InstagramWebhookAdapter().normalize(
            {"entry": [{"changes": [{"field": "messages", "value": {}}]}]}
        )
        == []
    )


def test_webhook_verification_and_signature_endpoints(client):
    ok = client.get(
        "/webhooks/instagram",
        params={"hub.mode": "subscribe", "hub.verify_token": "verify-me", "hub.challenge": "123"},
    )
    assert ok.status_code == 200 and ok.text == "123"
    assert (
        client.get(
            "/webhooks/instagram", params={"hub.mode": "subscribe", "hub.verify_token": "wrong"}
        ).status_code
        == 403
    )
    body = json.dumps(PAYLOAD, separators=(",", ":")).encode()
    signature = "sha256=" + hmac.new(b"meta-test-secret", body, hashlib.sha256).hexdigest()
    assert (
        client.post(
            "/webhooks/instagram",
            content=body,
            headers={"X-Hub-Signature-256": signature, "Content-Type": "application/json"},
        ).status_code
        == 200
    )
    assert client.post("/webhooks/instagram", content=body).status_code == 401
    assert (
        client.post(
            "/webhooks/instagram", content=body, headers={"X-Hub-Signature-256": "sha256=bad"}
        ).status_code
        == 401
    )
