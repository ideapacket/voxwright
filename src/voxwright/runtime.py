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


@dataclass(frozen=True, slots=True)
class LatencySample:
    """One measured stage duration on the logical clock."""

    stage: LatencyStage
    started_ms: int
    ended_ms: int

    def __post_init__(self) -> None:
        if self.started_ms < 0 or self.ended_ms < self.started_ms:
            raise ValueError("latency sample has invalid logical interval")

    @property
    def duration_ms(self) -> int:
        return self.ended_ms - self.started_ms

    def within(self, budget: LatencyBudget) -> bool:
        return self.duration_ms <= budget.for_stage(self.stage)


@dataclass(frozen=True, slots=True)
class LatencyTrace:
    """An immutable, stage-ordered latency trace for one application turn."""

    samples: tuple[LatencySample, ...] = ()

    def __post_init__(self) -> None:
        expected = tuple(LatencyStage)
        for index, sample in enumerate(self.samples):
            if index >= len(expected) or sample.stage is not expected[index]:
                raise ValueError("latency samples must follow stage order without duplicates")
            if index and sample.started_ms < self.samples[index - 1].ended_ms:
                raise ValueError("latency samples cannot overlap")

    def append(self, sample: LatencySample) -> LatencyTrace:
        """Return a new trace containing the next ordered sample."""
        return LatencyTrace((*self.samples, sample))

    @property
    def active_ms(self) -> int:
        return sum(sample.duration_ms for sample in self.samples)

    @property
    def elapsed_ms(self) -> int:
        if not self.samples:
            return 0
        return self.samples[-1].ended_ms - self.samples[0].started_ms

    @property
    def complete(self) -> bool:
        return len(self.samples) == len(LatencyStage)
