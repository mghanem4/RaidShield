from __future__ import annotations

import hashlib
from dataclasses import dataclass
from functools import lru_cache
from itertools import combinations
from typing import Any, Protocol

from app.config import Settings
from app.schemas import NormalizedInput

MAX_NEIGHBORS_PER_EVENT = 20
MAX_TOKENS = 256
INFERENCE_BATCH_SIZE = 32


class SemanticEncoder(Protocol):
    model_id: str
    revision: str

    def encode(self, texts: list[str]) -> list[list[float]]: ...


@dataclass
class LocalSemanticEncoder:
    """Pinned local sentence encoder; inputs and embeddings are never persisted."""

    model_id: str
    revision: str
    device: str
    local_files_only: bool
    _tokenizer: Any | None = None
    _model: Any | None = None
    _selected_device: str | None = None

    def _load(self) -> tuple[Any, Any, str]:
        if self._tokenizer is not None and self._model is not None and self._selected_device:
            return self._tokenizer, self._model, self._selected_device
        try:
            import torch
            from transformers import AutoModel, AutoTokenizer
        except ImportError as exc:
            raise RuntimeError("optional_semantic_context_dependencies_missing") from exc

        selected_device = self.device
        if selected_device == "auto":
            selected_device = "mps" if torch.backends.mps.is_available() else "cpu"
        self._tokenizer = AutoTokenizer.from_pretrained(
            self.model_id,
            revision=self.revision,
            local_files_only=self.local_files_only,
        )
        self._model = AutoModel.from_pretrained(
            self.model_id,
            revision=self.revision,
            local_files_only=self.local_files_only,
            use_safetensors=True,
        ).to(selected_device)
        self._model.eval()
        self._selected_device = selected_device
        return self._tokenizer, self._model, selected_device

    def encode(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        import torch
        import torch.nn.functional as functional

        tokenizer, model, selected_device = self._load()
        result: list[list[float]] = []
        for offset in range(0, len(texts), INFERENCE_BATCH_SIZE):
            batch = texts[offset : offset + INFERENCE_BATCH_SIZE]
            tokens = tokenizer(
                batch,
                padding=True,
                truncation=True,
                max_length=MAX_TOKENS,
                return_tensors="pt",
            )
            tokens = {key: value.to(selected_device) for key, value in tokens.items()}
            with torch.inference_mode():
                output = model(**tokens)
                mask = (
                    tokens["attention_mask"].unsqueeze(-1).expand(output.last_hidden_state.size())
                )
                pooled = (output.last_hidden_state * mask).sum(1) / mask.sum(1).clamp(min=1e-9)
                normalized = functional.normalize(pooled, p=2, dim=1)
            result.extend(normalized.cpu().tolist())
        return result


def event_reference(source_event_id: str) -> str:
    return hashlib.sha256(f"semantic-event:{source_event_id}".encode()).hexdigest()


def _context_document(event: NormalizedInput) -> str:
    if event.context_parent_text:
        return f"Parent message:\n{event.context_parent_text}\nReply message:\n{event.text}"
    return f"Top-level comment:\n{event.text}"


def _dot(left: list[float], right: list[float]) -> float:
    return sum(a * b for a, b in zip(left, right, strict=False))


def enrich_semantic_context(
    events: list[NormalizedInput],
    encoder: SemanticEncoder,
    threshold: float,
    time_window_seconds: float,
) -> list[NormalizedInput]:
    """Persist abstract pair evidence while keeping plaintext and vectors transient."""

    embeddings = encoder.encode([_context_document(event) for event in events])
    if len(embeddings) != len(events):
        raise RuntimeError("semantic_context_embedding_count_mismatch")
    neighbors: list[list[dict[str, Any]]] = [[] for _ in events]
    for left_index, right_index in combinations(range(len(events)), 2):
        left, right = events[left_index], events[right_index]
        if left.post_id != right.post_id:
            continue
        if left.raw_author_identifier == right.raw_author_identifier:
            continue
        left_is_reply, right_is_reply = left.parent_id is not None, right.parent_id is not None
        if left_is_reply != right_is_reply:
            continue
        seconds_apart = abs((left.occurred_at - right.occurred_at).total_seconds())
        if seconds_apart > time_window_seconds:
            continue
        similarity = max(0.0, min(1.0, _dot(embeddings[left_index], embeddings[right_index])))
        if similarity < threshold:
            continue
        shared_parent = bool(left.parent_id and left.parent_id == right.parent_id)
        common = {
            "similarity": round(similarity, 4),
            "seconds_apart": round(seconds_apart, 3),
            "shared_parent": shared_parent,
            "same_reply_role": True,
        }
        neighbors[left_index].append(
            {**common, "event_ref": event_reference(right.source_event_id)}
        )
        neighbors[right_index].append(
            {**common, "event_ref": event_reference(left.source_event_id)}
        )

    enriched: list[NormalizedInput] = []
    for event, matches in zip(events, neighbors, strict=True):
        ranked = sorted(
            matches,
            key=lambda match: (-float(match["similarity"]), float(match["seconds_apart"])),
        )[:MAX_NEIGHBORS_PER_EVENT]
        metadata = dict(event.metadata)
        metadata["semantic_context"] = {
            "source": "experimental_local_semantic_model",
            "status": "evaluated",
            "model_id": encoder.model_id,
            "model_revision": encoder.revision,
            "threshold": threshold,
            "time_window_seconds": time_window_seconds,
            "neighbor_count": len(matches),
            "neighbors": ranked,
        }
        enriched.append(event.model_copy(update={"metadata": metadata}))
    return enriched


def unavailable_semantic_context(events: list[NormalizedInput]) -> list[NormalizedInput]:
    result = []
    for event in events:
        metadata = dict(event.metadata)
        metadata["semantic_context"] = {
            "source": "experimental_local_semantic_model",
            "status": "unavailable",
            "reason": "local_semantic_context_inference_failed",
        }
        result.append(event.model_copy(update={"metadata": metadata}))
    return result


@lru_cache(maxsize=4)
def _cached_encoder(
    model_id: str, revision: str, device: str, local_files_only: bool
) -> LocalSemanticEncoder:
    return LocalSemanticEncoder(model_id, revision, device, local_files_only)


def prepare_semantic_context(
    events: list[NormalizedInput], settings: Settings
) -> list[NormalizedInput]:
    if not settings.semantic_context_enabled or not events:
        return events
    encoder = _cached_encoder(
        settings.semantic_context_model,
        settings.semantic_context_revision,
        settings.semantic_context_device,
        settings.semantic_context_local_files_only,
    )
    try:
        return enrich_semantic_context(
            events,
            encoder,
            settings.semantic_context_threshold,
            settings.semantic_context_time_window_seconds,
        )
    except Exception:
        return unavailable_semantic_context(events)
