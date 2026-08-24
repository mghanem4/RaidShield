import json

import pytest

from app.adapters.offline import OfflineDatasetAdapter, OfflineDatasetError


def safe_dataset() -> dict:
    return {
        "dataset_name": "safe_batch",
        "description": "Synthetic neutral offline import used for validation.",
        "content_origin": "synthetic-safe-placeholder",
        "events": [
            {
                "source_event_id": "event-1",
                "post_id": "post-1",
                "comment_id": "comment-1",
                "parent_id": None,
                "participant_id": "participant-1",
                "occurred_at": "2026-08-24T12:00:00Z",
                "text": "PATTERN_ALPHA support the library",
            }
        ],
    }


def test_offline_adapter_hashes_source_ids_and_marks_model_eligible():
    metadata, events = OfflineDatasetAdapter().load_bytes(json.dumps(safe_dataset()).encode())
    event = events[0]
    assert metadata["dataset_name"] == "safe_batch"
    assert event.source == "offline"
    assert event.source_event_id.startswith("offline:event:")
    assert event.post_id.startswith("offline:post:")
    assert event.comment_id.startswith("offline:comment:")
    assert event.raw_author_identifier == "participant-1"
    assert event.metadata["content_detector_eligible"] is True
    assert "participant-1" not in str(event.metadata)


@pytest.mark.parametrize(
    "payload",
    [
        b"not json",
        json.dumps({"dataset_name": "unsafe space", "events": []}).encode(),
        json.dumps({**safe_dataset(), "unexpected": "value"}).encode(),
        json.dumps(
            {
                **safe_dataset(),
                "events": [{**safe_dataset()["events"][0], "occurred_at": "2026-08-24T12:00:00"}],
            }
        ).encode(),
    ],
)
def test_offline_adapter_rejects_invalid_input_without_echoing_it(payload):
    with pytest.raises(OfflineDatasetError) as raised:
        OfflineDatasetAdapter().load_bytes(payload)
    assert "PATTERN_ALPHA" not in str(raised.value)
    assert "participant-1" not in str(raised.value)
