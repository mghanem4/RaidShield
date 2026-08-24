from __future__ import annotations

from dataclasses import asdict, dataclass
from functools import lru_cache
from typing import Any, Protocol

from app.config import Settings

# These labels describe observable content-review needs. They deliberately do
# not identify a protected target or claim hate, intent, or a policy violation.
REVIEW_LABELS = {
    "targeted_hostility": "targeted hostility toward a protected community",
    "direct_insult": "a direct insult or demeaning statement aimed at people",
    "threat_or_harm": "a threat or advocacy of harm against people",
}
CONTEXT_LABEL = "context that requires human interpretation such as quotation or counterspeech"
REPLY_RELATION_LABELS = {
    "supports_parent": "a reply that agrees with or supports the parent message",
    "opposes_parent": "a reply that disagrees with or challenges the parent message",
    "restates_parent": "a reply that quotes or restates the parent message",
    "asks_clarification": "a reply that asks the parent for clarification",
    "unrelated_to_parent": "a reply that is unrelated to the parent message",
    "ambiguous_context": "a reply whose relationship to the parent is ambiguous",
}


@dataclass(frozen=True)
class ContentSignal:
    score: float
    category: str
    requires_review: bool
    context_score: float
    label_scores: dict[str, float]
    model_id: str
    model_revision: str
    threshold: float
    status: str = "experimental"
    source: str = "experimental_local_model"

    def metadata(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ReplyContextSignal:
    relation: str
    score: float
    relation_scores: dict[str, float]
    model_id: str
    model_revision: str
    status: str = "experimental"
    source: str = "experimental_local_context_model"
    requires_human_review: bool = True

    def metadata(self) -> dict[str, Any]:
        return asdict(self)


class ContentDetector(Protocol):
    def analyze(self, text: str) -> ContentSignal | None: ...


class LocalZeroShotDetector:
    """Optional local NLI triage model; never logs or persists its input text."""

    def __init__(
        self,
        model_id: str,
        revision: str,
        threshold: float,
        device: str,
        local_files_only: bool,
    ):
        self.model_id = model_id
        self.revision = revision
        self.threshold = threshold
        self.device = device
        self.local_files_only = local_files_only
        self._classifier: Any | None = None

    def _load(self) -> Any:
        if self._classifier is not None:
            return self._classifier
        try:
            import torch
            from transformers import (
                AutoModelForSequenceClassification,
                AutoTokenizer,
                pipeline,
            )
        except ImportError as exc:
            raise RuntimeError("optional_content_detector_dependencies_missing") from exc

        selected_device = self.device
        if selected_device == "auto":
            selected_device = "mps" if torch.backends.mps.is_available() else "cpu"
        tokenizer = AutoTokenizer.from_pretrained(
            self.model_id,
            revision=self.revision,
            local_files_only=self.local_files_only,
        )
        model = AutoModelForSequenceClassification.from_pretrained(
            self.model_id,
            revision=self.revision,
            local_files_only=self.local_files_only,
            use_safetensors=True,
        )
        self._classifier = pipeline(
            "zero-shot-classification",
            model=model,
            tokenizer=tokenizer,
            device=selected_device,
        )
        return self._classifier

    def analyze(self, text: str) -> ContentSignal | None:
        if not text.strip():
            return None
        labels = [*REVIEW_LABELS.values(), CONTEXT_LABEL]
        result = self._load()(
            text,
            candidate_labels=labels,
            hypothesis_template="This text contains {}.",
            multi_label=True,
            truncation=True,
        )
        raw_scores = dict(zip(result["labels"], result["scores"], strict=False))
        label_scores = {
            key: round(float(raw_scores.get(label, 0.0)), 4) for key, label in REVIEW_LABELS.items()
        }
        category = max(label_scores, key=label_scores.get)  # type: ignore[arg-type]
        score = label_scores[category]
        return ContentSignal(
            score=score,
            category=category,
            requires_review=score >= self.threshold,
            context_score=round(float(raw_scores.get(CONTEXT_LABEL, 0.0)), 4),
            label_scores=label_scores,
            model_id=self.model_id,
            model_revision=self.revision,
            threshold=self.threshold,
        )

    def analyze_context(self, parent_text: str, reply_text: str) -> ReplyContextSignal | None:
        if not parent_text.strip() or not reply_text.strip():
            return None
        labels = list(REPLY_RELATION_LABELS.values())
        combined = f"Parent message: {parent_text}\nReply message: {reply_text}"
        result = self._load()(
            combined,
            candidate_labels=labels,
            hypothesis_template="The relationship is {}.",
            multi_label=False,
            truncation=True,
        )
        raw_scores = dict(zip(result["labels"], result["scores"], strict=False))
        relation_scores = {
            key: round(float(raw_scores.get(label, 0.0)), 4)
            for key, label in REPLY_RELATION_LABELS.items()
        }
        relation = max(relation_scores, key=relation_scores.get)  # type: ignore[arg-type]
        return ReplyContextSignal(
            relation=relation,
            score=relation_scores[relation],
            relation_scores=relation_scores,
            model_id=self.model_id,
            model_revision=self.revision,
        )


@lru_cache(maxsize=4)
def _cached_detector(
    model_id: str,
    revision: str,
    threshold: float,
    device: str,
    local_files_only: bool,
) -> LocalZeroShotDetector:
    return LocalZeroShotDetector(model_id, revision, threshold, device, local_files_only)


def configured_detector(settings: Settings) -> ContentDetector | None:
    if not settings.content_detector_enabled:
        return None
    return _cached_detector(
        settings.content_detector_model,
        settings.content_detector_revision,
        settings.content_detector_threshold,
        settings.content_detector_device,
        settings.content_detector_local_files_only,
    )
