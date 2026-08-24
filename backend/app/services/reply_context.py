from __future__ import annotations

from collections import defaultdict
from difflib import SequenceMatcher

from app.schemas import NormalizedInput
from app.services.crypto import normalize_text

NEAR_DUPLICATE_THRESHOLD = 0.82


def enrich_reply_context(events: list[NormalizedInput]) -> list[NormalizedInput]:
    """Attach safe structural context while keeping comparison text transient."""

    by_comment = {event.comment_id: event for event in events}
    by_parent: dict[str, list[NormalizedInput]] = defaultdict(list)
    for event in events:
        if event.parent_id:
            by_parent[event.parent_id].append(event)
    for siblings in by_parent.values():
        siblings.sort(key=lambda item: (item.occurred_at, item.source_event_id))

    enriched: list[NormalizedInput] = []
    for event in events:
        if not event.parent_id:
            enriched.append(event)
            continue
        parent = by_comment.get(event.parent_id)
        siblings = by_parent[event.parent_id]
        other_siblings = [
            sibling for sibling in siblings if sibling.source_event_id != event.source_event_id
        ]
        normalized_reply = normalize_text(event.text)
        normalized_siblings = [normalize_text(sibling.text) for sibling in other_siblings]
        exact_siblings = sum(text == normalized_reply for text in normalized_siblings)
        near_siblings = sum(
            text != normalized_reply
            and SequenceMatcher(None, normalized_reply, text).ratio() >= NEAR_DUPLICATE_THRESHOLD
            for text in normalized_siblings
        )
        repeats_parent = bool(parent and normalize_text(parent.text) == normalized_reply)
        if repeats_parent:
            relation = "repetition_of_parent"
        elif exact_siblings:
            relation = "repeated_with_siblings"
        elif near_siblings:
            relation = "similar_to_siblings"
        elif parent:
            relation = "parent_context_available"
        else:
            relation = "parent_unavailable"

        seconds_after_parent = None
        if parent:
            seconds_after_parent = round(
                (event.occurred_at - parent.occurred_at).total_seconds(), 3
            )
        metadata = dict(event.metadata)
        metadata["reply_context"] = {
            "current": {
                "source": "deterministic_structure",
                "status": "structural_only",
                "relation": relation,
                "score": 1.0 if relation.startswith(("repetition", "repeated")) else None,
            },
            "semantic_model": None,
            "parent_available": parent is not None,
            "reply_position": siblings.index(event) + 1,
            "sibling_count": len(other_siblings),
            "exact_duplicate_sibling_count": exact_siblings,
            "near_duplicate_sibling_count": near_siblings,
            "seconds_after_parent": seconds_after_parent,
            "same_participant_as_parent": (
                event.raw_author_identifier == parent.raw_author_identifier if parent else None
            ),
        }
        enriched.append(
            event.model_copy(
                update={
                    "metadata": metadata,
                    "context_parent_text": parent.text if parent else None,
                }
            )
        )
    return enriched
