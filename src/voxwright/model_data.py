"""Framework-neutral synthetic data for the optional trainable adapter."""

from __future__ import annotations

import re
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
