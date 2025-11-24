"""Optional CPU PyTorch model for synthetic slot tagging and tool selection."""

from __future__ import annotations

import importlib
import importlib.util
from dataclasses import dataclass
from typing import Any

from voxwright.model_data import (
    ClassInventory,
    ModelExample,
    TokenVocabulary,
    encode_batch,
    split_examples,
    tokenize,
)


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


@dataclass(frozen=True, slots=True)
class PredictedSlot:
    name: str
    value: str
    confidence: float

    def __post_init__(self) -> None:
        if not self.name or not self.value:
            raise ValueError("predicted slot name and value cannot be empty")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("predicted slot confidence must be between zero and one")


def prediction_slots(prediction: ModelPrediction) -> tuple[PredictedSlot, ...]:
    """Convert valid BIO runs to grounded slot spans, discarding orphan I-tags."""
    result: list[PredictedSlot] = []
    current_name: str | None = None
    current_tokens: list[str] = []
    current_confidences: list[float] = []

    def flush() -> None:
        nonlocal current_name, current_tokens, current_confidences
        if current_name is not None:
            result.append(
                PredictedSlot(
                    current_name,
                    " ".join(current_tokens),
                    round(sum(current_confidences) / len(current_confidences), 6),
                )
            )
        current_name = None
        current_tokens = []
        current_confidences = []

    for token, tag, confidence in zip(
        prediction.tokens,
        prediction.slot_tags,
        prediction.slot_confidences,
        strict=True,
    ):
        if tag == "O":
            flush()
        elif tag.startswith("B-") and len(tag) > 2:
            flush()
            current_name = tag[2:]
            current_tokens = [token]
            current_confidences = [confidence]
        elif tag.startswith("I-") and len(tag) > 2:
            if current_name == tag[2:]:
                current_tokens.append(token)
                current_confidences.append(confidence)
            else:
                flush()
        else:
            raise ValueError(f"invalid prediction slot tag: {tag}")
    flush()
    return tuple(result)


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


@dataclass(frozen=True, slots=True)
class TrainingConfig:
    epochs: int = 60
    learning_rate: float = 0.03
    seed: int = 0

    def __post_init__(self) -> None:
        if isinstance(self.epochs, bool) or self.epochs < 1:
            raise ValueError("training epochs must be positive")
        if not 0.0 < self.learning_rate <= 1.0:
            raise ValueError("training learning rate must be between zero and one")
        if isinstance(self.seed, bool) or self.seed < 0:
            raise ValueError("training seed must be non-negative")


@dataclass(frozen=True, slots=True)
class TrainingHistory:
    losses: tuple[float, ...]

    def __post_init__(self) -> None:
        if not self.losses or any(value < 0.0 for value in self.losses):
            raise ValueError("training history requires non-negative losses")


def train_model(
    model: TorchJointModel,
    examples: tuple[ModelExample, ...],
    config: TrainingConfig | None = None,
) -> TrainingHistory:
    """Optimize both heads on planted synthetic labels using CPU tensors."""
    settings = TrainingConfig() if config is None else config
    torch = require_torch()
    torch.manual_seed(settings.seed)
    batch = encode_batch(examples, model.vocabulary, model.slot_classes, model.tool_classes)
    token_ids = torch.tensor(batch.token_ids, dtype=torch.long)
    slot_ids = torch.tensor(batch.slot_ids, dtype=torch.long)
    mask = torch.tensor(batch.mask, dtype=torch.bool)
    tool_ids = torch.tensor(batch.tool_ids, dtype=torch.long)
    optimizer = torch.optim.Adam(model.parameters(), lr=settings.learning_rate)
    losses: list[float] = []
    for _ in range(settings.epochs):
        optimizer.zero_grad()
        slot_logits, tool_logits = model.forward(token_ids, mask)
        slot_loss = torch.nn.functional.cross_entropy(slot_logits[mask], slot_ids[mask])
        tool_loss = torch.nn.functional.cross_entropy(tool_logits, tool_ids)
        loss = slot_loss + tool_loss
        loss.backward()
        optimizer.step()
        losses.append(round(float(loss.detach().item()), 6))
    return TrainingHistory(tuple(losses))


@dataclass(frozen=True, slots=True)
class ModelQuality:
    token_count: int
    correct_tokens: int
    slot_accuracy: float
    example_count: int
    correct_tools: int
    tool_accuracy: float

    def __post_init__(self) -> None:
        if self.token_count < 1 or self.example_count < 1:
            raise ValueError("model quality requires observed examples and tokens")
        if not 0 <= self.correct_tokens <= self.token_count:
            raise ValueError("model quality token count is inconsistent")
        if not 0 <= self.correct_tools <= self.example_count:
            raise ValueError("model quality tool count is inconsistent")
        if not 0.0 <= self.slot_accuracy <= 1.0 or not 0.0 <= self.tool_accuracy <= 1.0:
            raise ValueError("model quality accuracy must be between zero and one")


def evaluate_model(model: TorchJointModel, examples: tuple[ModelExample, ...]) -> ModelQuality:
    """Measure exact planted-label accuracy without claiming real-model quality."""
    if not examples:
        raise ValueError("model evaluation requires examples")
    predictions = tuple(predict(model, example.transcript) for example in examples)
    token_count = sum(len(example.slot_tags) for example in examples)
    correct_tokens = sum(
        expected == predicted
        for example, prediction in zip(examples, predictions, strict=True)
        for expected, predicted in zip(example.slot_tags, prediction.slot_tags, strict=True)
    )
    correct_tools = sum(
        example.tool_label == prediction.tool_label
        for example, prediction in zip(examples, predictions, strict=True)
    )
    return ModelQuality(
        token_count,
        correct_tokens,
        round(correct_tokens / token_count, 6),
        len(examples),
        correct_tools,
        round(correct_tools / len(examples), 6),
    )


@dataclass(frozen=True, slots=True)
class FitResult:
    """Artifacts and measured synthetic validation facts from one seeded fit."""

    model: TorchJointModel
    history: TrainingHistory
    validation: ModelQuality
    train_count: int
    validation_count: int


def fit_synthetic_model(
    examples: tuple[ModelExample, ...],
    *,
    config: TrainingConfig | None = None,
    embedding_size: int = 16,
) -> FitResult:
    """Fit from a seeded train split and score only its held-out synthetic partition."""
    settings = TrainingConfig() if config is None else config
    split = split_examples(examples, seed=settings.seed)
    vocabulary = TokenVocabulary.build(split.train)
    slots = ClassInventory.for_slot_tags(examples)
    tools = ClassInventory.for_tools(examples)
    model = TorchJointModel(
        vocabulary, slots, tools, embedding_size=embedding_size, seed=settings.seed
    )
    history = train_model(model, split.train, settings)
    return FitResult(
        model,
        history,
        evaluate_model(model, split.validation),
        len(split.train),
        len(split.validation),
    )
