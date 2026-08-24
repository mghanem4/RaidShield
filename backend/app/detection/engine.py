from __future__ import annotations

import hashlib
import math
import statistics
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Protocol

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


class DetectionEvent(Protocol):
    source_event_id: str
    author_pseudonym: str
    occurred_at: datetime
    parent_id: str | None
    event_metadata: dict[str, Any]


@dataclass(frozen=True)
class FeatureResult:
    burst: float
    similarity: float
    semantic_context: float | None
    synchronization: float
    novelty: float
    concentration: float
    unique_authors: int
    event_count: int
    largest_similarity_cluster: int
    largest_semantic_cluster: int
    largest_parent_thread: int

    def dict(self) -> dict[str, float | int | None]:
        return asdict(self)


def burst_score(unique_authors: int, threshold: int = 6, history: list[int] | None = None) -> float:
    if not history or len(history) < 3:
        return min(1.0, unique_authors / threshold)
    baseline = statistics.median(history)
    mad = statistics.median(abs(item - baseline) for item in history)
    robust_z = (unique_authors - baseline) / max(1.0, 1.4826 * mad)
    return 1 / (1 + math.exp(-(robust_z - 2)))


def similarity_score(texts: list[str], threshold: float = 0.85) -> tuple[float, int]:
    if len(texts) < 3 or not any(text.strip() for text in texts):
        return 0.0, 0
    try:
        vectors = TfidfVectorizer(analyzer="char", ngram_range=(3, 5)).fit_transform(texts)
    except ValueError:
        return 0.0, 0
    matrix = cosine_similarity(vectors)
    visited: set[int] = set()
    clustered: set[int] = set()
    largest = 0
    for i in range(len(texts)):
        if i in visited:
            continue
        cluster = {j for j, value in enumerate(matrix[i]) if value >= threshold}
        visited |= cluster
        if len(cluster) >= 3:
            clustered |= cluster
            largest = max(largest, len(cluster))
    return len(clustered) / len(texts), largest


def semantic_context_score(events: Sequence[DetectionEvent]) -> tuple[float | None, int]:
    contexts = [
        event.event_metadata.get("semantic_context")
        if isinstance(event.event_metadata, dict)
        else None
        for event in events
    ]
    if not any(
        isinstance(context, dict) and context.get("status") == "evaluated" for context in contexts
    ):
        return None, 0

    refs = {
        hashlib.sha256(f"semantic-event:{event.source_event_id}".encode()).hexdigest(): index
        for index, event in enumerate(events)
    }
    neighbors: dict[int, set[int]] = {index: set() for index in range(len(events))}
    clustered: set[int] = set()
    for index, context in enumerate(contexts):
        if not isinstance(context, dict):
            continue
        matches = context.get("neighbors")
        if not isinstance(matches, list):
            continue
        for match in matches:
            if not isinstance(match, dict):
                continue
            other = refs.get(str(match.get("event_ref", "")))
            if other is None or events[index].author_pseudonym == events[other].author_pseudonym:
                continue
            neighbors[index].add(other)
            neighbors[other].add(index)
            clustered.update((index, other))

    largest = 0
    unseen = set(clustered)
    while unseen:
        stack = [unseen.pop()]
        size = 0
        while stack:
            current = stack.pop()
            size += 1
            discovered = neighbors[current] & unseen
            unseen -= discovered
            stack.extend(discovered)
        largest = max(largest, size)
    return len(clustered) / len(events) if events else 0.0, largest


def synchronization_score(events: Sequence[DetectionEvent], reference_seconds: float = 30) -> float:
    first_by_author: dict[str, datetime] = {}
    for event in events:
        occurred_at = event.occurred_at
        if occurred_at.tzinfo is None:
            occurred_at = occurred_at.replace(tzinfo=timezone.utc)
        previous = first_by_author.get(event.author_pseudonym)
        if previous is None or occurred_at < previous:
            first_by_author[event.author_pseudonym] = occurred_at
    times = sorted(first_by_author.values())
    if len(times) < 2:
        return 0.0
    gaps = [(b - a).total_seconds() for a, b in zip(times, times[1:], strict=False)]
    return 1 - min(1.0, statistics.median(gaps) / reference_seconds)


def novelty_score(authors: set[str], previously_seen: set[str]) -> float:
    return len(authors - previously_seen) / len(authors) if authors else 0.0


def concentration_score(events: Sequence[DetectionEvent]) -> tuple[float, int]:
    if not events:
        return 0.0, 0
    counts: dict[str, int] = {}
    for event in events:
        group = event.parent_id or event.author_pseudonym + ":top"
        counts[group] = counts.get(group, 0) + 1
    largest = max(counts.values())
    return largest / len(events), largest


def calculate_features(
    events: Sequence[DetectionEvent],
    texts: list[str],
    previously_seen: set[str],
    cold_start_threshold: int = 6,
    similarity_threshold: float = 0.85,
) -> FeatureResult:
    authors = {event.author_pseudonym for event in events}
    similarity, largest_cluster = similarity_score(texts, similarity_threshold)
    semantic_context, largest_semantic_cluster = semantic_context_score(events)
    concentration, largest_thread = concentration_score(events)
    return FeatureResult(
        burst=burst_score(len(authors), cold_start_threshold),
        similarity=similarity,
        semantic_context=semantic_context,
        synchronization=synchronization_score(events),
        novelty=novelty_score(authors, previously_seen),
        concentration=concentration,
        unique_authors=len(authors),
        event_count=len(events),
        largest_similarity_cluster=largest_cluster,
        largest_semantic_cluster=largest_semantic_cluster,
        largest_parent_thread=largest_thread,
    )


def score(features: FeatureResult) -> float:
    if features.semantic_context is not None:
        return round(
            0.25 * features.burst
            + 0.15 * features.similarity
            + 0.20 * features.semantic_context
            + 0.18 * features.synchronization
            + 0.12 * features.novelty
            + 0.10 * features.concentration,
            4,
        )
    return round(
        0.30 * features.burst
        + 0.25 * features.similarity
        + 0.20 * features.synchronization
        + 0.15 * features.novelty
        + 0.10 * features.concentration,
        4,
    )


def confidence(features: FeatureResult, parent_information_available: bool = True) -> str:
    if features.unique_authors < 6 or not parent_information_available:
        return "low"
    if features.unique_authors >= 10 and all(
        value > 0
        for value in (
            features.burst,
            features.similarity,
            features.synchronization,
            features.novelty,
            features.concentration,
        )
    ):
        return "high"
    return "medium"


def explanations(features: FeatureResult, seconds: int = 120) -> list[str]:
    reasons = [
        f"{features.unique_authors} unique participants engaged within {seconds // 60} minutes."
    ]
    if features.similarity > 0:
        reasons.append(f"{features.similarity:.0%} of events belonged to near-duplicate clusters.")
    if features.semantic_context is not None and features.semantic_context > 0:
        reasons.append(
            f"{features.semantic_context:.0%} of events had similar meaning and "
            "conversation context "
            "within the configured timing window."
        )
    if features.novelty > 0:
        reasons.append(
            f"{features.novelty:.0%} of participants were first observed during the window."
        )
    if features.concentration >= 0.5:
        reasons.append(f"{features.concentration:.0%} of activity was concentrated in one thread.")
    reasons.append("These observable indicators require human review and do not prove intent.")
    return reasons
