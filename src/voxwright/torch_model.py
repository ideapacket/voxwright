"""Optional CPU PyTorch model for synthetic slot tagging and tool selection."""

from __future__ import annotations

import importlib
import importlib.util
from dataclasses import dataclass
from typing import Any

from voxwright.model_data import ClassInventory, TokenVocabulary, tokenize


def torch_available() -> bool:
    """Report whether the optional framework can be imported."""
    return importlib.util.find_spec("torch") is not None


def require_torch() -> Any:
    """Import the optional dependency with an actionable local-only error."""
    try:
        module: Any = importlib.import_module("torch")
    except ModuleNotFoundError as error:
        raise RuntimeError("install voxwright[torch] to use the trainable adapter") from error
    return module


class TorchJointModel:
    """A small embedding model with token-tag and pooled tool heads."""

    embedding: Any
    slot_head: Any
    tool_head: Any

    def __init__(
        self,
        vocabulary: TokenVocabulary,
        slot_classes: ClassInventory,
        tool_classes: ClassInventory,
        *,
        embedding_size: int = 16,
        seed: int = 0,
    ) -> None:
        if isinstance(embedding_size, bool) or embedding_size < 1:
            raise ValueError("model embedding size must be positive")
        if isinstance(seed, bool) or seed < 0:
            raise ValueError("model seed must be non-negative")
        torch = require_torch()
        torch.manual_seed(seed)
        self.vocabulary = vocabulary
        self.slot_classes = slot_classes
        self.tool_classes = tool_classes
        self.embedding_size = embedding_size
        self.seed = seed
        self.embedding = torch.nn.Embedding(len(vocabulary.tokens), embedding_size)
        self.slot_head = torch.nn.Linear(embedding_size, len(slot_classes.names))
        self.tool_head = torch.nn.Linear(embedding_size, len(tool_classes.names))

    def parameters(self) -> list[Any]:
        return [
            *self.embedding.parameters(),
            *self.slot_head.parameters(),
            *self.tool_head.parameters(),
        ]

    def forward(self, token_ids: Any, mask: Any) -> tuple[Any, Any]:
        embedded = self.embedding(token_ids)
        slot_logits = self.slot_head(embedded)
        weights = mask.unsqueeze(-1).to(dtype=embedded.dtype)
        pooled = (embedded * weights).sum(dim=1) / weights.sum(dim=1).clamp(min=1)
        return slot_logits, self.tool_head(pooled)


@dataclass(frozen=True, slots=True)
class ModelPrediction:
    tokens: tuple[str, ...]
    slot_tags: tuple[str, ...]
    slot_confidences: tuple[float, ...]
    tool_label: str
    tool_confidence: float

    def __post_init__(self) -> None:
        if not self.tokens or len(self.tokens) != len(self.slot_tags):
            raise ValueError("prediction tokens and slot tags must be nonempty and aligned")
        if len(self.slot_confidences) != len(self.tokens):
            raise ValueError("prediction slot confidences must align with tokens")
        if any(not 0.0 <= value <= 1.0 for value in self.slot_confidences):
            raise ValueError("prediction slot confidences must be between zero and one")
        if not self.tool_label or not 0.0 <= self.tool_confidence <= 1.0:
            raise ValueError("prediction tool output is invalid")


def predict(model: TorchJointModel, text: str) -> ModelPrediction:
    """Run deterministic CPU inference and quantize public confidences."""
    torch = require_torch()
    tokens = tokenize(text)
    if not tokens:
        raise ValueError("model prediction requires transcript tokens")
    token_ids = torch.tensor([model.vocabulary.encode(tokens)], dtype=torch.long)
    mask = torch.ones_like(token_ids, dtype=torch.bool)
    with torch.no_grad():
        slot_logits, tool_logits = model.forward(token_ids, mask)
        slot_probabilities = torch.softmax(slot_logits, dim=-1)
        tool_probabilities = torch.softmax(tool_logits, dim=-1)
    slot_indices = slot_probabilities.argmax(dim=-1)[0].tolist()
    slot_confidences = slot_probabilities.max(dim=-1).values[0].tolist()
    tool_index = int(tool_probabilities.argmax(dim=-1)[0].item())
    tool_confidence = float(tool_probabilities[0, tool_index].item())
    return ModelPrediction(
        tokens,
        tuple(model.slot_classes.label(int(index)) for index in slot_indices),
        tuple(round(float(value), 6) for value in slot_confidences),
        model.tool_classes.label(tool_index),
        round(tool_confidence, 6),
    )
