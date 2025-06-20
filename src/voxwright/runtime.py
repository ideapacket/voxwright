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


@dataclass(frozen=True, slots=True)
class BudgetViolation:
    stage: LatencyStage
    actual_ms: int
    budget_ms: int

    @property
    def overrun_ms(self) -> int:
        return self.actual_ms - self.budget_ms


@dataclass(frozen=True, slots=True)
class BudgetAssessment:
    """Budget result derived exclusively from logical stage durations."""

    complete: bool
    violations: tuple[BudgetViolation, ...]
    total_budget_ms: int
    active_ms: int

    @property
    def within_budget(self) -> bool:
        return self.complete and not self.violations and self.active_ms <= self.total_budget_ms


def assess_latency(trace: LatencyTrace, budget: LatencyBudget) -> BudgetAssessment:
    """Compare every observed stage to its configured inclusive budget."""
    violations = tuple(
        BudgetViolation(sample.stage, sample.duration_ms, budget.for_stage(sample.stage))
        for sample in trace.samples
        if not sample.within(budget)
    )
    return BudgetAssessment(trace.complete, violations, budget.total_ms, trace.active_ms)


@dataclass(frozen=True, slots=True)
class StreamBlock:
    """Transport-neutral input block scheduled on a logical clock."""

    sequence: int
    received_at_ms: int
    duration_ms: int
    final: bool = False

    def __post_init__(self) -> None:
        if isinstance(self.sequence, bool) or self.sequence < 0:
            raise ValueError("stream block sequence must be a non-negative integer")
        if isinstance(self.received_at_ms, bool) or self.received_at_ms < 0:
            raise ValueError("stream block arrival must be a non-negative integer")
        if isinstance(self.duration_ms, bool) or self.duration_ms <= 0:
            raise ValueError("stream block duration must be a positive integer")
        if not isinstance(self.final, bool):
            raise TypeError("stream block final flag must be boolean")
