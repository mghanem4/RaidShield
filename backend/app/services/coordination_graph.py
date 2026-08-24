from __future__ import annotations

import hashlib
from collections import defaultdict
from collections.abc import Sequence
from datetime import datetime, timezone
from itertools import combinations
from typing import Any, Protocol

from app.services.crypto import display_pseudonym

TIME_WINDOW_SECONDS = 30.0
MINIMUM_EDGE_STRENGTH = 0.25
TEXT_WEIGHT = 0.45
TIMING_WEIGHT = 0.35
THREAD_WEIGHT = 0.20
SEMANTIC_TEXT_WEIGHT = 0.25
SEMANTIC_CONTEXT_WEIGHT = 0.30
SEMANTIC_TIMING_WEIGHT = 0.30
SEMANTIC_THREAD_WEIGHT = 0.15


class GraphEvent(Protocol):
    source_event_id: str
    author_pseudonym: str
    occurred_at: datetime
    parent_id: str | None
    text_fingerprint: str
    event_metadata: dict[str, Any]


def _utc(value: datetime) -> datetime:
    return (
        value.replace(tzinfo=timezone.utc)
        if value.tzinfo is None
        else value.astimezone(timezone.utc)
    )


def _minimum_gap(left: Sequence[GraphEvent], right: Sequence[GraphEvent]) -> float:
    return min(
        abs((_utc(a.occurred_at) - _utc(b.occurred_at)).total_seconds())
        for a in left
        for b in right
    )


def _event_reference(event: GraphEvent) -> str:
    return hashlib.sha256(f"semantic-event:{event.source_event_id}".encode()).hexdigest()


def _semantic_similarity(left: Sequence[GraphEvent], right: Sequence[GraphEvent]) -> float:
    right_refs = {_event_reference(event) for event in right}
    strongest = 0.0
    for event in left:
        context = (
            event.event_metadata.get("semantic_context")
            if isinstance(event.event_metadata, dict)
            else None
        )
        if not isinstance(context, dict) or not isinstance(context.get("neighbors"), list):
            continue
        for neighbor in context["neighbors"]:
            if not isinstance(neighbor, dict) or neighbor.get("event_ref") not in right_refs:
                continue
            value = neighbor.get("similarity")
            if isinstance(value, (int, float)):
                strongest = max(strongest, float(value))
    return strongest


def _components(node_ids: list[str], edges: list[dict[str, Any]]) -> dict[str, int | None]:
    neighbors: dict[str, set[str]] = {node_id: set() for node_id in node_ids}
    for edge in edges:
        source, target = str(edge["source"]), str(edge["target"])
        neighbors[source].add(target)
        neighbors[target].add(source)

    result: dict[str, int | None] = {node_id: None for node_id in node_ids}
    components: list[list[str]] = []
    unseen = set(node_ids)
    while unseen:
        start = min(unseen)
        stack = [start]
        component: list[str] = []
        unseen.remove(start)
        while stack:
            current = stack.pop()
            component.append(current)
            discovered = neighbors[current] & unseen
            unseen -= discovered
            stack.extend(sorted(discovered, reverse=True))
        if len(component) > 1:
            components.append(sorted(component))

    for cluster_id, component in enumerate(sorted(components), start=1):
        for node_id in component:
            result[node_id] = cluster_id
    return result


def build_coordination_graph(
    events: Sequence[GraphEvent], max_participants: int = 100
) -> dict[str, Any]:
    """Build an explainable participant graph without exposing stored pseudonym digests."""

    by_author: dict[str, list[GraphEvent]] = defaultdict(list)
    for event in events:
        by_author[event.author_pseudonym].append(event)

    ranked_authors = sorted(by_author, key=lambda author: (-len(by_author[author]), author))
    selected_authors = sorted(ranked_authors[:max_participants])
    graph_ids = {
        author: f"participant-{index:03d}" for index, author in enumerate(selected_authors, 1)
    }
    semantic_available = any(
        isinstance(event.event_metadata, dict)
        and isinstance(context := event.event_metadata.get("semantic_context"), dict)
        and context.get("status") == "evaluated"
        for event in events
    )

    edges: list[dict[str, Any]] = []
    for left_author, right_author in combinations(selected_authors, 2):
        left = by_author[left_author]
        right = by_author[right_author]
        left_fingerprints = {event.text_fingerprint for event in left}
        right_fingerprints = {event.text_fingerprint for event in right}
        exact_text = float(bool(left_fingerprints & right_fingerprints))
        left_threads = {event.parent_id for event in left if event.parent_id}
        right_threads = {event.parent_id for event in right if event.parent_id}
        shared_thread = float(bool(left_threads & right_threads))
        minimum_gap = _minimum_gap(left, right)
        timing = max(0.0, 1 - minimum_gap / TIME_WINDOW_SECONDS)
        semantic_context = _semantic_similarity(left, right) if semantic_available else 0.0
        if semantic_available:
            strength = round(
                SEMANTIC_TEXT_WEIGHT * exact_text
                + SEMANTIC_CONTEXT_WEIGHT * semantic_context
                + SEMANTIC_TIMING_WEIGHT * timing
                + SEMANTIC_THREAD_WEIGHT * shared_thread,
                4,
            )
        else:
            strength = round(
                TEXT_WEIGHT * exact_text + TIMING_WEIGHT * timing + THREAD_WEIGHT * shared_thread,
                4,
            )
        if semantic_context and not (exact_text or timing > 0 or shared_thread):
            continue
        if strength < MINIMUM_EDGE_STRENGTH:
            continue
        reasons = []
        if exact_text:
            reasons.append("exact repeated text")
        if semantic_context:
            reasons.append(
                f"similar meaning in matching conversation context ({semantic_context:.0%} ranking)"
            )
        if timing > 0:
            reasons.append(f"activity within {round(minimum_gap, 1):g} seconds")
        if shared_thread:
            reasons.append("shared reply target")
        edges.append(
            {
                "id": f"edge-{len(edges) + 1:04d}",
                "source": graph_ids[left_author],
                "target": graph_ids[right_author],
                "strength": strength,
                "signals": {
                    "exact_text": exact_text,
                    "semantic_context": round(semantic_context, 4),
                    "timing": round(timing, 4),
                    "shared_thread": shared_thread,
                },
                "minimum_gap_seconds": round(minimum_gap, 3),
                "reasons": reasons,
            }
        )

    node_ids = list(graph_ids.values())
    cluster_by_node = _components(node_ids, edges)
    incident: dict[str, list[float]] = defaultdict(list)
    for edge in edges:
        incident[str(edge["source"])].append(float(edge["strength"]))
        incident[str(edge["target"])].append(float(edge["strength"]))

    nodes = []
    for author in selected_authors:
        participant_events = sorted(by_author[author], key=lambda event: _utc(event.occurred_at))
        node_id = graph_ids[author]
        strengths = incident[node_id]
        context_relations: dict[str, int] = defaultdict(int)
        for event in participant_events:
            reply_context = (
                event.event_metadata.get("reply_context")
                if isinstance(event.event_metadata, dict)
                else None
            )
            if isinstance(reply_context, dict) and isinstance(reply_context.get("current"), dict):
                relation = reply_context["current"].get("relation")
                if isinstance(relation, str):
                    context_relations[relation] += 1
        nodes.append(
            {
                "id": node_id,
                "label": f"{display_pseudonym(author)}-{node_id[-3:]}",
                "cluster_id": cluster_by_node[node_id],
                "event_count": len(participant_events),
                "reply_count": sum(event.parent_id is not None for event in participant_events),
                "connection_count": len(strengths),
                "average_connection_strength": (
                    round(sum(strengths) / len(strengths), 4) if strengths else 0.0
                ),
                "context_relations": dict(sorted(context_relations.items())),
                "first_observed_at": _utc(participant_events[0].occurred_at).isoformat(),
                "last_observed_at": _utc(participant_events[-1].occurred_at).isoformat(),
            }
        )

    cluster_count = len({value for value in cluster_by_node.values() if value is not None})
    return {
        "nodes": nodes,
        "edges": edges,
        "summary": {
            "participant_count_total": len(by_author),
            "participant_count_shown": len(nodes),
            "edge_count": len(edges),
            "cluster_count": cluster_count,
            "strongest_edge": max((float(edge["strength"]) for edge in edges), default=0.0),
            "truncated": len(by_author) > len(nodes),
        },
        "method": {
            "time_window_seconds": TIME_WINDOW_SECONDS,
            "minimum_edge_strength": MINIMUM_EDGE_STRENGTH,
            "weights": {
                "exact_text": SEMANTIC_TEXT_WEIGHT if semantic_available else TEXT_WEIGHT,
                "semantic_context": SEMANTIC_CONTEXT_WEIGHT if semantic_available else 0.0,
                "timing": SEMANTIC_TIMING_WEIGHT if semantic_available else TIMING_WEIGHT,
                "shared_thread": SEMANTIC_THREAD_WEIGHT if semantic_available else THREAD_WEIGHT,
            },
            "semantic_context_available": semantic_available,
            "safety_statement": (
                "Connections are behavioral indicators for human review and do not prove "
                "automation, intent, identity, or a policy violation."
            ),
        },
    }
