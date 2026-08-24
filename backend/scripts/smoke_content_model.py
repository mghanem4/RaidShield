"""Offline readiness smoke test using neutral safe samples only."""

import json
import os
import time

os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

from app.config import get_settings  # noqa: E402
from app.services.content_detector import LocalZeroShotDetector  # noqa: E402

SAFE_SAMPLES = {
    "english_neutral": "The community meeting begins at six.",
    "arabic_neutral": "الاجتماع يبدأ الساعة السادسة.",
    "arabizi_neutral": "el egtema3 hayebda el sa3a 6",
}


def main() -> None:
    settings = get_settings()
    detector = LocalZeroShotDetector(
        settings.content_detector_model,
        settings.content_detector_revision,
        settings.content_detector_threshold,
        settings.content_detector_device,
        True,
    )
    results = {}
    for name, text in SAFE_SAMPLES.items():
        started = time.perf_counter()
        signal = detector.analyze(text)
        results[name] = {
            "elapsed_seconds": round(time.perf_counter() - started, 3),
            "requires_review": signal.requires_review if signal else None,
            "score": signal.score if signal else None,
        }
    print(json.dumps(results, indent=2, sort_keys=True))
    print("Readiness only: these neutral samples do not validate detector accuracy.")


if __name__ == "__main__":
    main()
