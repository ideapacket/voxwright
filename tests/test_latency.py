"""Tests for deterministic synthetic latency analytics."""

from __future__ import annotations

import pytest

from voxwright.latency import latency_distribution
from voxwright.runtime import LatencySample, LatencyStage


def sample(stage: LatencyStage, duration_ms: int) -> LatencySample:
    return LatencySample(stage, 10, 10 + duration_ms)


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
