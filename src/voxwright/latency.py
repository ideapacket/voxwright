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
