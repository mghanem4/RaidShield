from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import pytest

from app.detection.engine import (
    FeatureResult,
    burst_score,
    calculate_features,
    concentration_score,
    novelty_score,
    score,
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


@dataclass
class E:
    author_pseudonym: str
    occurred_at: datetime
    parent_id: str | None = None


def test_crypto_and_pseudonymization(settings):
    one = pseudonymize("instagram", "raw-name", settings.pseudonymization_key)
    assert one == pseudonymize("instagram", "raw-name", settings.pseudonymization_key)
    assert one != pseudonymize("instagram", "raw-name", "another-key")
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
    features = FeatureResult(0.8, 0.7, 0.6, 0.5, 0.4, 8, 8, 4, 5)
    assert score(features) == 0.65


def test_calculate_features_is_reproducible():
    now = datetime.now(timezone.utc)
    events = [E(f"a{i}", now + timedelta(seconds=i), "parent") for i in range(6)]
    texts = ["PATTERN_ALPHA safe token"] * 6
    first = calculate_features(events, texts, set())
    assert first == calculate_features(events, texts, set())
    assert first.unique_authors == 6
    assert first.largest_parent_thread == 6
