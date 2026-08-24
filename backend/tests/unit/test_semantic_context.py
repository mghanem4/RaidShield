from datetime import datetime, timedelta, timezone

from app.schemas import NormalizedInput
from app.services import semantic_context
from app.services.semantic_context import (
    enrich_semantic_context,
    event_reference,
    prepare_semantic_context,
)


class HarmlessEncoder:
    model_id = "local-harmless-semantic-test"
    revision = "semantic-test-revision"

    def encode(self, texts: list[str]) -> list[list[float]]:
        assert all("Parent message:" in text or "Top-level comment:" in text for text in texts)
        return [
            [0.0, 1.0],
            [1.0, 0.0],
            [0.99, 0.1],
            [0.0, 1.0],
        ]


def item(
    event_id: str,
    participant: str,
    seconds: int,
    text: str,
    parent_id: str | None = "parent",
    parent_text: str | None = "Should the library extend its opening hours?",
) -> NormalizedInput:
    started = datetime(2026, 8, 24, tzinfo=timezone.utc)
    return NormalizedInput(
        source="offline",
        source_event_id=event_id,
        post_id="post",
        comment_id=event_id,
        parent_id=parent_id,
        raw_author_identifier=participant,
        occurred_at=started + timedelta(seconds=seconds),
        received_at=started,
        text=text,
        context_parent_text=parent_text,
    )


def test_semantic_context_links_different_wording_with_timing_and_shared_parent():
    events = [
        item("root", "root-author", 0, "A neutral library-hours question.", None, None),
        item("reply-a", "author-a", 3, "Please keep the library open later."),
        item("reply-b", "author-b", 7, "Could the building remain available longer?"),
        item("reply-c", "author-c", 9, "The workshop recording is online."),
    ]

    enriched = enrich_semantic_context(events, HarmlessEncoder(), 0.78, 60)
    left = enriched[1].metadata["semantic_context"]
    right = enriched[2].metadata["semantic_context"]
    unrelated = enriched[3].metadata["semantic_context"]

    assert left["neighbor_count"] == 1
    assert left["neighbors"][0]["event_ref"] == event_reference("reply-b")
    assert left["neighbors"][0]["shared_parent"] is True
    assert right["neighbor_count"] == 1
    assert unrelated["neighbor_count"] == 0
    metadata = str([event.metadata for event in enriched]).lower()
    assert "library open" not in metadata
    assert "building remain" not in metadata


def test_semantic_context_requires_matching_role_and_time_window():
    events = [
        item("top", "author-a", 0, "Neutral planning note.", None, None),
        item("reply", "author-b", 2, "Neutral planning response."),
        item("late-reply", "author-c", 180, "Another neutral planning response."),
        item("other-reply", "author-d", 181, "Different neutral note."),
    ]
    encoder = HarmlessEncoder()
    enriched = enrich_semantic_context(events, encoder, 0.78, 60)

    assert enriched[0].metadata["semantic_context"]["neighbor_count"] == 0
    assert enriched[1].metadata["semantic_context"]["neighbor_count"] == 0


class FailingEncoder:
    model_id = "failing-safe-test"
    revision = "failing-safe-revision"

    def encode(self, _texts: list[str]) -> list[list[float]]:
        raise RuntimeError("PRIVATE_INPUT_DETAIL_MUST_NOT_PERSIST")


def test_semantic_model_failure_is_sanitized_and_non_blocking(monkeypatch, settings):
    settings.semantic_context_enabled = True
    monkeypatch.setattr(semantic_context, "_cached_encoder", lambda *_args: FailingEncoder())

    result = prepare_semantic_context(
        [item("safe-event", "safe-author", 0, "A harmless local planning note.")],
        settings,
    )

    context = result[0].metadata["semantic_context"]
    assert context == {
        "source": "experimental_local_semantic_model",
        "status": "unavailable",
        "reason": "local_semantic_context_inference_failed",
    }
    assert "PRIVATE_INPUT_DETAIL" not in str(context)
