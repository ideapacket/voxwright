"""Tests for deterministic synthetic latency analytics."""

from __future__ import annotations

import pytest

from voxwright.latency import latency_distribution, stage_latency_profile
from voxwright.runtime import LatencySample, LatencyStage, LatencyTrace


def sample(stage: LatencyStage, duration_ms: int) -> LatencySample:
    return LatencySample(stage, 10, 10 + duration_ms)


def trace(durations: tuple[int, int, int, int]) -> LatencyTrace:
    return LatencyTrace(
        tuple(
            LatencySample(stage, sum(durations[:index]), sum(durations[: index + 1]))
            for index, stage in enumerate(LatencyStage)
        )
    )


def test_latency_distribution_uses_nearest_rank_and_quantized_mean() -> None:
    values = (1, 2, 3, 10)
    result = latency_distribution(tuple(sample(LatencyStage.TOOL, value) for value in values))
    assert result.stage is LatencyStage.TOOL
    assert (result.count, result.minimum_ms, result.maximum_ms) == (4, 1, 10)
    assert (result.p50_ms, result.p95_ms, result.mean_ms) == (2, 10, 4.0)


def test_latency_distribution_requires_a_single_nonempty_stage() -> None:
    with pytest.raises(ValueError, match="at least one"):
        latency_distribution(())
    with pytest.raises(ValueError, match="share one stage"):
        latency_distribution((sample(LatencyStage.TOOL, 1), sample(LatencyStage.RESPONSE, 1)))


def test_latency_percentiles_are_stable_for_small_campaigns() -> None:
    single = latency_distribution((sample(LatencyStage.DECISION, 7),))
    assert (single.p50_ms, single.p95_ms, single.mean_ms) == (7, 7, 7.0)

    two = latency_distribution(
        (sample(LatencyStage.DECISION, 100), sample(LatencyStage.DECISION, 0))
    )
    assert (two.p50_ms, two.p95_ms, two.mean_ms) == (0, 100, 50.0)


def test_latency_mean_is_quantized_at_production() -> None:
    result = latency_distribution(
        tuple(sample(LatencyStage.PERCEPTION, value) for value in (0, 0, 2))
    )
    assert result.mean_ms == 0.666667


def test_stage_profile_preserves_canonical_stage_order() -> None:
    profile = stage_latency_profile((trace((10, 20, 30, 40)), trace((20, 30, 40, 50))))
    assert tuple(item.stage for item in profile) == tuple(LatencyStage)
    assert [item.mean_ms for item in profile] == [15.0, 25.0, 35.0, 45.0]


def test_stage_profile_rejects_empty_and_partial_campaigns() -> None:
    with pytest.raises(ValueError, match="at least one trace"):
        stage_latency_profile(())
    partial = LatencyTrace((sample(LatencyStage.PERCEPTION, 10),))
    with pytest.raises(ValueError, match="complete traces"):
        stage_latency_profile((trace((1, 2, 3, 4)), partial))


def test_stage_profile_does_not_mutate_input_traces() -> None:
    traces = (trace((4, 3, 2, 1)), trace((1, 2, 3, 4)))
    before = tuple(item.samples for item in traces)
    stage_latency_profile(traces)
    assert tuple(item.samples for item in traces) == before
