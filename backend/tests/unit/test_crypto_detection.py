from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

import pytest

from app.detection.engine import (
    FeatureResult,
    burst_score,
    calculate_features,
    concentration_score,
    novelty_score,
    score,
    semantic_context_score,
    similarity_score,
    synchronization_score,
)
from app.services.crypto import (
    decrypt_text,
    encrypt_text,
    fingerprint,
    normalize_text,
    pseudonymize,
)
from app.services.semantic_context import event_reference


@dataclass
class E:
    author_pseudonym: str
    occurred_at: datetime
    parent_id: str | None = None
    source_event_id: str = "event"
    event_metadata: dict = field(default_factory=dict)


def test_crypto_and_pseudonymization(settings):
    one = pseudonymize("offline", "raw-name", settings.pseudonymization_key)
    assert one == pseudonymize("offline", "raw-name", settings.pseudonymization_key)
    assert one != pseudonymize("offline", "raw-name", "another-key")
    encrypted = encrypt_text("private text", settings.data_encryption_key)
    assert "private text" not in encrypted
    assert decrypt_text(encrypted, settings.data_encryption_key) == "private text"
    assert normalize_text(" A\u200b  TEST ") == "a test"
    assert fingerprint("A TEST") == fingerprint(" a   test ")


def test_burst_cold_start_and_history():
    assert burst_score(3, 6) == 0.5
    assert burst_score(12, 6) == 1
    assert burst_score(20, history=[2, 2, 3, 2, 3]) > 0.9
    assert burst_score(2, history=[2, 2, 2]) < 0.2


def test_similarity_groups_safe_tokens_but_not_diverse_text():
    similar = [
        "pattern alpha support library",
        "pattern alpha support library!",
        "pattern alpha support library.",
        "unrelated sentence",
    ]
    value, largest = similarity_score(similar, 0.80)
    assert value >= 0.75 and largest >= 3
    diverse = ["morning workshop", "transit map", "recording later", "volunteer desk"]
    assert similarity_score(diverse, 0.85) == (0, 0)


def test_sync_ignores_repeat_author_and_novelty_scope():
    start = datetime.now(timezone.utc)
    repeated = [E("same", start), E("same", start + timedelta(seconds=1))]
    assert synchronization_score(repeated) == 0
    unique = [E(f"a{i}", start + timedelta(seconds=i * 5)) for i in range(5)]
    assert synchronization_score(unique) == pytest.approx(5 / 6)
    assert novelty_score({"a", "b"}, {"a", "outside-post"}) == 0.5


def test_concentration_and_formula():
    now = datetime.now(timezone.utc)
    events = [E("a", now, "parent"), E("b", now, "parent"), E("c", now, None)]
    assert concentration_score(events) == (pytest.approx(2 / 3), 2)
    features = FeatureResult(
        burst=0.8,
        similarity=0.7,
        semantic_context=None,
        synchronization=0.6,
        novelty=0.5,
        concentration=0.4,
        unique_authors=8,
        event_count=8,
        largest_similarity_cluster=4,
        largest_semantic_cluster=0,
        largest_parent_thread=5,
    )
    assert score(features) == 0.65


def test_calculate_features_is_reproducible():
    now = datetime.now(timezone.utc)
    events = [E(f"a{i}", now + timedelta(seconds=i), "parent") for i in range(6)]
    texts = ["PATTERN_ALPHA safe token"] * 6
    first = calculate_features(events, texts, set())
    assert first == calculate_features(events, texts, set())
    assert first.unique_authors == 6
    assert first.largest_parent_thread == 6


def test_semantic_context_score_counts_cross_participant_matches():
    now = datetime.now(timezone.utc)
    left = E("a", now, "parent", "left")
    right = E("b", now + timedelta(seconds=4), "parent", "right")
    unrelated = E("c", now + timedelta(seconds=6), "parent", "unrelated")
    left.event_metadata = {
        "semantic_context": {
            "status": "evaluated",
            "neighbors": [{"event_ref": event_reference("right"), "similarity": 0.84}],
        }
    }
    right.event_metadata = {"semantic_context": {"status": "evaluated", "neighbors": []}}
    unrelated.event_metadata = {"semantic_context": {"status": "evaluated", "neighbors": []}}

    value, largest = semantic_context_score([left, right, unrelated])

    assert value == pytest.approx(2 / 3)
    assert largest == 2
