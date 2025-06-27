"""Deterministic latency statistics for synthetic streaming campaigns."""

from __future__ import annotations

from dataclasses import dataclass

from voxwright.runtime import LatencySample, LatencyStage, LatencyTrace


@dataclass(frozen=True, slots=True)
class LatencyDistribution:
    stage: LatencyStage
    count: int
    minimum_ms: int
    p50_ms: int
    p95_ms: int
    maximum_ms: int
    mean_ms: float


def _nearest_rank(values: tuple[int, ...], percentile: int) -> int:
    index = max(0, (len(values) * percentile + 99) // 100 - 1)
    return values[index]


def latency_distribution(samples: tuple[LatencySample, ...]) -> LatencyDistribution:
    """Summarize same-stage samples with integer nearest-rank percentiles."""
    if not samples:
        raise ValueError("latency distribution requires at least one sample")
    stage = samples[0].stage
    if any(sample.stage is not stage for sample in samples):
        raise ValueError("latency distribution samples must share one stage")
    values = tuple(sorted(sample.duration_ms for sample in samples))
    return LatencyDistribution(
        stage=stage,
        count=len(values),
        minimum_ms=values[0],
        p50_ms=_nearest_rank(values, 50),
        p95_ms=_nearest_rank(values, 95),
        maximum_ms=values[-1],
        mean_ms=round(sum(values) / len(values), 6),
    )


def stage_latency_profile(traces: tuple[LatencyTrace, ...]) -> tuple[LatencyDistribution, ...]:
    """Build one distribution per stage from complete turn traces."""
    if not traces:
        raise ValueError("stage latency profile requires at least one trace")
    if any(not trace.complete for trace in traces):
        raise ValueError("stage latency profile requires complete traces")
    return tuple(
        latency_distribution(
            tuple(sample for trace in traces for sample in trace.samples if sample.stage is stage)
        )
        for stage in LatencyStage
    )


@dataclass(frozen=True, slots=True)
class RunOutcome:
    latency_ms: int
    success: bool

    def __post_init__(self) -> None:
        if isinstance(self.latency_ms, bool) or self.latency_ms < 0:
            raise ValueError("run latency must be a non-negative integer")
        if not isinstance(self.success, bool):
            raise TypeError("run success must be boolean")


@dataclass(frozen=True, slots=True)
class SuccessCurvePoint:
    budget_ms: int
    completed: int
    successes: int
    adherence_rate: float
    success_rate: float


def latency_success_curve(
    outcomes: tuple[RunOutcome, ...], budgets_ms: tuple[int, ...]
) -> tuple[SuccessCurvePoint, ...]:
    """Measure completion and planted-task success under each latency budget."""
    if not outcomes:
        raise ValueError("latency curve requires at least one outcome")
    if not budgets_ms:
        raise ValueError("latency curve requires at least one budget")
    if any(isinstance(value, bool) or value < 0 for value in budgets_ms):
        raise ValueError("latency curve budgets must be non-negative integers")
    if len(set(budgets_ms)) != len(budgets_ms):
        raise ValueError("latency curve budgets must be unique")
    total = len(outcomes)
    points: list[SuccessCurvePoint] = []
    for budget_ms in sorted(budgets_ms):
        eligible = tuple(outcome for outcome in outcomes if outcome.latency_ms <= budget_ms)
        successes = sum(outcome.success for outcome in eligible)
        points.append(
            SuccessCurvePoint(
                budget_ms,
                len(eligible),
                successes,
                round(len(eligible) / total, 6),
                round(successes / total, 6),
            )
        )
    return tuple(points)
