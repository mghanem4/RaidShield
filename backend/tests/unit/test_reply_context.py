from datetime import datetime, timedelta, timezone

from app.schemas import NormalizedInput
from app.services.reply_context import enrich_reply_context


def item(
    event_id: str,
    author: str,
    seconds: int,
    text: str,
    parent_id: str | None = None,
) -> NormalizedInput:
    occurred_at = datetime(2026, 8, 24, tzinfo=timezone.utc) + timedelta(seconds=seconds)
    return NormalizedInput(
        source="replay",
        source_event_id=event_id,
        post_id="safe-post",
        comment_id=event_id,
        parent_id=parent_id,
        raw_author_identifier=author,
        occurred_at=occurred_at,
        received_at=occurred_at,
        text=text,
    )


def test_reply_context_compares_parent_and_all_siblings_without_persisting_text():
    events = enrich_reply_context(
        [
            item("root", "author-root", 0, "The community meeting starts at nine."),
            item("reply-1", "author-a", 2, "Thanks, the meeting starts at nine.", "root"),
            item("reply-2", "author-b", 4, "Thanks, the meeting starts at nine!", "root"),
            item("reply-3", "author-c", 6, "Thanks, the meeting starts at nine.", "root"),
        ]
    )

    reply = events[1]
    context = reply.metadata["reply_context"]
    assert reply.context_parent_text == "The community meeting starts at nine."
    assert context["parent_available"] is True
    assert context["reply_position"] == 1
    assert context["sibling_count"] == 2
    assert context["exact_duplicate_sibling_count"] == 1
    assert context["near_duplicate_sibling_count"] == 1
    assert context["seconds_after_parent"] == 2
    assert context["same_participant_as_parent"] is False
    assert context["current"]["relation"] == "repeated_with_siblings"
    assert "meeting starts" not in str(context)


def test_reply_context_marks_unavailable_parent_without_raw_context():
    reply = enrich_reply_context(
        [item("reply", "author-a", 2, "A harmless standalone reply.", "missing")]
    )[0]

    assert reply.context_parent_text is None
    assert reply.metadata["reply_context"]["parent_available"] is False
    assert reply.metadata["reply_context"]["current"]["relation"] == "parent_unavailable"
