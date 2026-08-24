"""Offline semantic-context readiness check using harmless paraphrases."""

import json
import os

os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

from app.config import get_settings  # noqa: E402
from app.services.semantic_context import LocalSemanticEncoder  # noqa: E402

SAFE_SAMPLES = [
    "Parent: When should the library close? Reply: Please keep it open later.",
    "Parent: What time should the library shut? Reply: Extend the opening hours.",
    "Parent: Is the recording ready? Reply: The workshop video is online.",
]


def dot(left: list[float], right: list[float]) -> float:
    return sum(a * b for a, b in zip(left, right, strict=False))


def main() -> None:
    settings = get_settings()
    encoder = LocalSemanticEncoder(
        settings.semantic_context_model,
        settings.semantic_context_revision,
        settings.semantic_context_device,
        True,
    )
    vectors = encoder.encode(SAFE_SAMPLES)
    print(
        json.dumps(
            {
                "paraphrase_ranking": round(dot(vectors[0], vectors[1]), 4),
                "unrelated_ranking": round(dot(vectors[0], vectors[2]), 4),
            },
            indent=2,
            sort_keys=True,
        )
    )
    print("Readiness only: harmless samples do not validate coordination detection accuracy.")


if __name__ == "__main__":
    main()
