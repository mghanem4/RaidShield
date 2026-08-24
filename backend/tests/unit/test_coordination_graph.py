from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from app.services.coordination_graph import build_coordination_graph
from app.services.semantic_context import event_reference


def event(author: str, seconds: int, text: str, parent: str | None = "safe-root"):
    return SimpleNamespace(
        source_event_id=f"event-{author}-{seconds}",
        author_pseudonym=author * 64,
        occurred_at=datetime(2026, 8, 24, tzinfo=timezone.utc) + timedelta(seconds=seconds),
        parent_id=parent,
        text_fingerprint=text,
        event_metadata=(
            {
                "reply_context": {
                    "current": {
                        "relation": "repeated_with_siblings",
                        "source": "deterministic_structure",
                    }
                }
            }
            if parent
            else {}
        ),
    )


def test_graph_connects_repeated_synchronized_shared_thread_activity():
    graph = build_coordination_graph(
        [event("a", 0, "same"), event("b", 2, "same"), event("c", 4, "same")]
    )

    assert len(graph["nodes"]) == 3
    assert len(graph["edges"]) == 3
    assert graph["summary"]["cluster_count"] == 1
    assert graph["summary"]["strongest_edge"] > 0.9
    assert all(edge["signals"]["exact_text"] == 1 for edge in graph["edges"])
    assert all(edge["signals"]["shared_thread"] == 1 for edge in graph["edges"])
    assert graph["nodes"][0]["context_relations"] == {"repeated_with_siblings": 1}
    assert "a" * 64 not in str(graph)


def test_graph_leaves_sparse_unrelated_activity_disconnected():
    graph = build_coordination_graph(
        [
            event("a", 0, "one", None),
            event("b", 120, "two", None),
            event("c", 240, "three", None),
        ]
    )

    assert graph["edges"] == []
    assert graph["summary"]["cluster_count"] == 0
    assert all(node["cluster_id"] is None for node in graph["nodes"])


def test_shared_reply_target_alone_does_not_create_an_edge():
    graph = build_coordination_graph(
        [event("a", 0, "one", "shared-root"), event("b", 120, "two", "shared-root")]
    )

    assert graph["edges"] == []


def test_graph_caps_displayed_participants_and_reports_truncation():
    graph = build_coordination_graph(
        [event(chr(97 + index), index, "same") for index in range(5)], max_participants=3
    )

    assert graph["summary"]["participant_count_total"] == 5
    assert graph["summary"]["participant_count_shown"] == 3
    assert graph["summary"]["truncated"] is True


def test_graph_connects_different_text_with_semantic_context_and_timing():
    left = event("a", 0, "different-one")
    right = event("b", 8, "different-two")
    left.event_metadata["semantic_context"] = {
        "status": "evaluated",
        "neighbors": [
            {
                "event_ref": event_reference(right.source_event_id),
                "similarity": 0.86,
                "seconds_apart": 8,
                "shared_parent": True,
            }
        ],
    }
    right.event_metadata["semantic_context"] = {"status": "evaluated", "neighbors": []}

    graph = build_coordination_graph([left, right])

    assert len(graph["edges"]) == 1
    edge = graph["edges"][0]
    assert edge["signals"]["exact_text"] == 0
    assert edge["signals"]["semantic_context"] == 0.86
    assert "similar meaning" in " ".join(edge["reasons"])
    assert graph["method"]["semantic_context_available"] is True


def test_semantic_similarity_alone_does_not_create_graph_edge():
    left = event("a", 0, "different-one", None)
    right = event("b", 45, "different-two", None)
    left.event_metadata["semantic_context"] = {
        "status": "evaluated",
        "neighbors": [
            {
                "event_ref": event_reference(right.source_event_id),
                "similarity": 1.0,
                "seconds_apart": 45,
                "shared_parent": False,
            }
        ],
    }
    right.event_metadata["semantic_context"] = {"status": "evaluated", "neighbors": []}

    graph = build_coordination_graph([left, right])

    assert graph["edges"] == []
