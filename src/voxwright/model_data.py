"""Framework-neutral synthetic data for the optional trainable adapter."""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass

from voxwright.scenarios import SyntheticScenario

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
