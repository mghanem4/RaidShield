"""Cache the pinned semantic-context model without processing user text."""

from transformers import AutoModel, AutoTokenizer

from app.config import get_settings


def main() -> None:
    settings = get_settings()
    common = {
        "revision": settings.semantic_context_revision,
        "local_files_only": False,
    }
    AutoTokenizer.from_pretrained(settings.semantic_context_model, **common)
    AutoModel.from_pretrained(
        settings.semantic_context_model,
        **common,
        use_safetensors=True,
    )
    print(
        "Cached optional semantic-context model "
        f"{settings.semantic_context_model}@{settings.semantic_context_revision[:10]}."
    )


if __name__ == "__main__":
    main()
