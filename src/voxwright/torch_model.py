"""Optional CPU PyTorch model for synthetic slot tagging and tool selection."""

from __future__ import annotations

import importlib
import importlib.util
from typing import Any

from voxwright.model_data import ClassInventory, TokenVocabulary


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
