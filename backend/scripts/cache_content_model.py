"""Cache the pinned optional content-review model without processing user text."""

from transformers import AutoModelForSequenceClassification, AutoTokenizer

from app.config import get_settings


def main() -> None:
    settings = get_settings()
    common = {
        "revision": settings.content_detector_revision,
        "local_files_only": False,
    }
    AutoTokenizer.from_pretrained(settings.content_detector_model, **common)
    AutoModelForSequenceClassification.from_pretrained(
        settings.content_detector_model,
        **common,
        use_safetensors=True,
    )
    print(
        "Cached optional content-review model "
        f"{settings.content_detector_model}@{settings.content_detector_revision[:10]}."
    )


if __name__ == "__main__":
    main()
