import sys
from types import SimpleNamespace

from app.services.content_detector import ContentSignal, LocalZeroShotDetector


class FakePipeline:
    def __call__(self, _text, **_kwargs):
        return {
            "labels": [
                "a direct insult or demeaning statement aimed at people",
                "targeted hostility toward a protected community",
                "a threat or advocacy of harm against people",
                "context that requires human interpretation such as quotation or counterspeech",
            ],
            "scores": [0.78, 0.61, 0.11, 0.42],
        }


def test_local_detector_maps_only_safe_review_metadata():
    detector = LocalZeroShotDetector("model", "revision", 0.65, "cpu", True)
    detector._classifier = FakePipeline()
    signal = detector.analyze("NEUTRAL_REDACTED_REVIEW_SAMPLE")

    assert signal is not None
    assert signal.requires_review
    assert signal.category == "direct_insult"
    assert signal.score == 0.78
    assert signal.context_score == 0.42
    assert "NEUTRAL_REDACTED_REVIEW_SAMPLE" not in str(signal.metadata())


def test_local_detector_ignores_blank_text():
    detector = LocalZeroShotDetector("model", "revision", 0.65, "cpu", True)
    detector._classifier = FakePipeline()
    assert detector.analyze("   ") is None


class FakeContextPipeline:
    def __call__(self, _text, **_kwargs):
        return {
            "labels": [
                "a reply that disagrees with or challenges the parent message",
                "a reply whose relationship to the parent is ambiguous",
                "a reply that agrees with or supports the parent message",
            ],
            "scores": [0.72, 0.18, 0.1],
        }


def test_local_detector_maps_parent_reply_context_without_retaining_text():
    detector = LocalZeroShotDetector("model", "revision", 0.65, "cpu", True)
    detector._classifier = FakeContextPipeline()
    signal = detector.analyze_context(
        "The library closes at eight.", "I disagree; it should remain open later."
    )

    assert signal is not None
    assert signal.relation == "opposes_parent"
    assert signal.score == 0.72
    assert signal.requires_human_review
    assert "library" not in str(signal.metadata())


def test_content_signal_metadata_is_explicitly_experimental():
    signal = ContentSignal(
        score=0.7,
        category="targeted_hostility",
        requires_review=True,
        context_score=0.2,
        label_scores={"targeted_hostility": 0.7},
        model_id="model",
        model_revision="revision",
        threshold=0.65,
    )
    assert signal.metadata()["source"] == "experimental_local_model"
    assert signal.metadata()["status"] == "experimental"


def test_model_loader_requires_safetensors(monkeypatch):
    model_calls = []

    class FakeLoader:
        @classmethod
        def from_pretrained(cls, *_args, **kwargs):
            model_calls.append(kwargs)
            return object()

    fake_transformers = SimpleNamespace(
        AutoModelForSequenceClassification=FakeLoader,
        AutoTokenizer=FakeLoader,
        pipeline=lambda *_args, **_kwargs: FakePipeline(),
    )
    fake_torch = SimpleNamespace(
        backends=SimpleNamespace(mps=SimpleNamespace(is_available=lambda: False))
    )
    monkeypatch.setitem(sys.modules, "transformers", fake_transformers)
    monkeypatch.setitem(sys.modules, "torch", fake_torch)

    detector = LocalZeroShotDetector("model", "revision", 0.65, "cpu", True)
    detector._load()

    assert model_calls[0]["local_files_only"] is True
    assert "use_safetensors" not in model_calls[0]
    assert model_calls[1]["use_safetensors"] is True
    assert model_calls[1]["local_files_only"] is True
