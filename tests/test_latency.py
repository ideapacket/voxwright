"""Tests for deterministic synthetic latency analytics."""

from __future__ import annotations

import pytest

from voxwright.latency import (
    RunOutcome,
    latency_distribution,
    latency_success_curve,
    stage_latency_profile,
)
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


def test_latency_success_curve_counts_outcomes_against_all_runs() -> None:
    outcomes = (
        RunOutcome(100, True),
        RunOutcome(200, False),
        RunOutcome(300, True),
        RunOutcome(400, True),
    )
    points = latency_success_curve(outcomes, (400, 100, 250))
    assert [point.budget_ms for point in points] == [100, 250, 400]
    assert [(point.completed, point.successes) for point in points] == [(1, 1), (2, 1), (4, 3)]
    assert [(point.adherence_rate, point.success_rate) for point in points] == [
        (0.25, 0.25),
        (0.5, 0.25),
        (1.0, 0.75),
    ]


def test_latency_curve_includes_exact_budget_boundary() -> None:
    point = latency_success_curve((RunOutcome(0, True), RunOutcome(1, False)), (0,))[0]
    assert (point.completed, point.successes) == (1, 1)
    assert (point.adherence_rate, point.success_rate) == (0.5, 0.5)


def test_latency_curve_rejects_ambiguous_inputs() -> None:
    with pytest.raises(ValueError, match="at least one outcome"):
        latency_success_curve((), (100,))
    with pytest.raises(ValueError, match="at least one budget"):
        latency_success_curve((RunOutcome(1, True),), ())
    with pytest.raises(ValueError, match="non-negative integers"):
        latency_success_curve((RunOutcome(1, True),), (-1,))
    with pytest.raises(ValueError, match="must be unique"):
        latency_success_curve((RunOutcome(1, True),), (10, 10))


def test_run_outcome_rejects_invalid_latency_and_success_type() -> None:
    with pytest.raises(ValueError, match="non-negative integer"):
        RunOutcome(-1, True)
    with pytest.raises(TypeError, match="must be boolean"):
        RunOutcome(1, 1)  # type: ignore[arg-type]
