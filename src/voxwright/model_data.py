"""Framework-neutral synthetic data for the optional trainable adapter."""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass

import numpy as np
import numpy.typing as npt

from voxwright.scenarios import SyntheticScenario
from voxwright.seeding import SeedStream

TOKEN_PATTERN = re.compile(r"[\w'-]+", re.UNICODE)


def tokenize(text: str) -> tuple[str, ...]:
    """Normalize an offline transcript into stable lowercase word tokens."""
    return tuple(match.group(0).lower() for match in TOKEN_PATTERN.finditer(text))


@dataclass(frozen=True, slots=True)
class ModelExample:
    """One transcript with planted token tags and a planted tool class."""

    transcript: str
    tokens: tuple[str, ...]
    slot_tags: tuple[str, ...]
    tool_label: str

    def __post_init__(self) -> None:
        if not self.transcript.strip() or not self.tokens:
            raise ValueError("model example transcript cannot be empty")
        if len(self.tokens) != len(self.slot_tags):
            raise ValueError("model token and slot-tag counts must match")
        if any(not token for token in self.tokens):
            raise ValueError("model tokens cannot be empty")
        if any(not tag for tag in self.slot_tags) or not self.tool_label.strip():
            raise ValueError("model labels cannot be empty")


def scenario_example(scenario: SyntheticScenario) -> ModelExample:
    """Derive token tags and tool choice exclusively from planted scenario truth."""
    if len(scenario.goals) != 1:
        raise ValueError("model examples require exactly one synthetic task goal")
    goal = scenario.goals[0]
    if len(goal.tool_calls) != 1:
        raise ValueError("model examples require exactly one planted tool call")
    tokens = tokenize(scenario.transcript)
    tags = ["O"] * len(tokens)
    for slot_name, value in sorted(goal.slots.items()):
        planted = tokenize(str(value))
        if not planted:
            raise ValueError(f"planted slot {slot_name} has no tokens")
        start = next(
            (
                index
                for index in range(len(tokens) - len(planted) + 1)
                if tokens[index : index + len(planted)] == planted
            ),
            None,
        )
        if start is None:
            raise ValueError(f"planted slot {slot_name} is absent from transcript")
        for offset in range(len(planted)):
            if tags[start + offset] != "O":
                raise ValueError("planted slot spans cannot overlap")
            prefix = "B" if offset == 0 else "I"
            tags[start + offset] = f"{prefix}-{slot_name}"
    return ModelExample(
        scenario.transcript,
        tokens,
        tuple(tags),
        str(goal.tool_calls[0].tool_name),
    )


@dataclass(frozen=True, slots=True)
class TokenVocabulary:
    """Stable token-to-index map with an explicit unknown token."""

    tokens: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.tokens or self.tokens[0] != "<unk>":
            raise ValueError("token vocabulary must start with <unk>")
        if any(not token for token in self.tokens) or len(set(self.tokens)) != len(self.tokens):
            raise ValueError("token vocabulary entries must be nonempty and unique")

    @classmethod
    def build(
        cls, examples: tuple[ModelExample, ...], *, minimum_count: int = 1
    ) -> TokenVocabulary:
        if not examples:
            raise ValueError("token vocabulary requires examples")
        if isinstance(minimum_count, bool) or minimum_count < 1:
            raise ValueError("minimum token count must be positive")
        counts = Counter(token for example in examples for token in example.tokens)
        retained = tuple(sorted(token for token, count in counts.items() if count >= minimum_count))
        return cls(("<unk>", *retained))

    def encode(self, tokens: tuple[str, ...]) -> tuple[int, ...]:
        positions = {token: index for index, token in enumerate(self.tokens)}
        return tuple(positions.get(token, 0) for token in tokens)

    def decode(self, indices: tuple[int, ...]) -> tuple[str, ...]:
        if any(isinstance(index, bool) or not 0 <= index < len(self.tokens) for index in indices):
            raise ValueError("token index is outside vocabulary")
        return tuple(self.tokens[index] for index in indices)


@dataclass(frozen=True, slots=True)
class ClassInventory:
    """Ordered labels for token tags or tool selection."""

    names: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.names or any(not name for name in self.names):
            raise ValueError("class inventory names cannot be empty")
        if len(set(self.names)) != len(self.names):
            raise ValueError("class inventory names must be unique")

    @classmethod
    def for_slot_tags(cls, examples: tuple[ModelExample, ...]) -> ClassInventory:
        if not examples:
            raise ValueError("slot inventory requires examples")
        observed = {tag for example in examples for tag in example.slot_tags}
        return cls(("O", *sorted(observed - {"O"})))

    @classmethod
    def for_tools(cls, examples: tuple[ModelExample, ...]) -> ClassInventory:
        if not examples:
            raise ValueError("tool inventory requires examples")
        return cls(tuple(sorted({example.tool_label for example in examples})))

    def index(self, name: str) -> int:
        try:
            return self.names.index(name)
        except ValueError as error:
            raise ValueError(f"unknown class label: {name}") from error

    def label(self, index: int) -> str:
        if isinstance(index, bool) or not 0 <= index < len(self.names):
            raise ValueError("class index is outside inventory")
        return self.names[index]


@dataclass(frozen=True, slots=True)
class DatasetSplit:
    train: tuple[ModelExample, ...]
    validation: tuple[ModelExample, ...]

    def __post_init__(self) -> None:
        if not self.train or not self.validation:
            raise ValueError("model split partitions cannot be empty")


def split_examples(
    examples: tuple[ModelExample, ...], *, seed: int, validation_fraction: float = 0.25
) -> DatasetSplit:
    """Create a seeded, stable split without consulting global randomness."""
    if len(examples) < 2:
        raise ValueError("model split requires at least two examples")
    if not 0.0 < validation_fraction < 1.0:
        raise ValueError("validation fraction must be between zero and one")
    shuffled = SeedStream(seed, "model-split").shuffled(examples)
    validation_count = min(len(examples) - 1, max(1, round(len(examples) * validation_fraction)))
    return DatasetSplit(tuple(shuffled[validation_count:]), tuple(shuffled[:validation_count]))


@dataclass(frozen=True, slots=True)
class EncodedBatch:
    """Padded arrays consumed by the optional model implementation."""

    token_ids: npt.NDArray[np.int64]
    slot_ids: npt.NDArray[np.int64]
    mask: npt.NDArray[np.bool_]
    tool_ids: npt.NDArray[np.int64]

    def __post_init__(self) -> None:
        if self.token_ids.ndim != 2 or self.slot_ids.shape != self.token_ids.shape:
            raise ValueError("batch token and slot arrays must share a two-dimensional shape")
        if self.mask.shape != self.token_ids.shape:
            raise ValueError("batch mask must match token shape")
        if self.tool_ids.shape != (self.token_ids.shape[0],):
            raise ValueError("batch tool labels must match the example count")


def encode_batch(
    examples: tuple[ModelExample, ...],
    tokens: TokenVocabulary,
    slots: ClassInventory,
    tools: ClassInventory,
) -> EncodedBatch:
    """Pad examples deterministically while keeping padding out of the mask."""
    if not examples:
        raise ValueError("model batch requires examples")
    width = max(len(example.tokens) for example in examples)
    token_ids = np.zeros((len(examples), width), dtype=np.int64)
    slot_ids = np.zeros((len(examples), width), dtype=np.int64)
    mask = np.zeros((len(examples), width), dtype=np.bool_)
    tool_ids = np.zeros((len(examples),), dtype=np.int64)
    for row, example in enumerate(examples):
        length = len(example.tokens)
        token_ids[row, :length] = tokens.encode(example.tokens)
        slot_ids[row, :length] = tuple(slots.index(tag) for tag in example.slot_tags)
        mask[row, :length] = True
        tool_ids[row] = tools.index(example.tool_label)
    return EncodedBatch(token_ids, slot_ids, mask, tool_ids)
