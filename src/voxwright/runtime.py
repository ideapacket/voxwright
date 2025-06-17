"""Logical-clock streaming runtime and application latency accounting."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class LatencyStage(str, Enum):
    PERCEPTION = "perception"
    DECISION = "decision"
    TOOL = "tool"
    RESPONSE = "response"


@dataclass(frozen=True, slots=True)
class LatencyBudget:
    perception_ms: int
    decision_ms: int
    tool_ms: int
    response_ms: int

    def __post_init__(self) -> None:
        if any(value < 0 for value in self.values()):
            raise ValueError("latency budgets cannot be negative")

    def values(self) -> tuple[int, int, int, int]:
        return self.perception_ms, self.decision_ms, self.tool_ms, self.response_ms

    @property
    def total_ms(self) -> int:
        return sum(self.values())

    def for_stage(self, stage: LatencyStage) -> int:
        return dict(zip(LatencyStage, self.values(), strict=True))[stage]
