"""Tests for logical streaming runtime and latency accounting."""

from __future__ import annotations

import pytest

import voxwright.runtime as runtime


def budget() -> runtime.LatencyBudget:
    return runtime.LatencyBudget(100, 200, 300, 150)


def test_latency_budget_maps_every_stage() -> None:
    expected = {"perception": 100, "decision": 200, "tool": 300, "response": 150}
    assert {stage.value: budget().for_stage(stage) for stage in runtime.LatencyStage} == expected
    assert budget().total_ms == 750


def test_latency_budget_allows_zero_but_not_negative() -> None:
    assert runtime.LatencyBudget(0, 0, 0, 0).total_ms == 0
    with pytest.raises(ValueError, match="cannot be negative"):
        runtime.LatencyBudget(-1, 0, 0, 0)


def test_latency_sample_uses_inclusive_budget_boundary() -> None:
    exact = runtime.LatencySample(runtime.LatencyStage.DECISION, 10, 210)
    over = runtime.LatencySample(runtime.LatencyStage.DECISION, 10, 211)
    assert exact.duration_ms == 200 and exact.within(budget())
    assert not over.within(budget())


@pytest.mark.parametrize(("start", "end"), [(-1, 0), (10, 9)])
def test_latency_sample_rejects_invalid_interval(start: int, end: int) -> None:
    with pytest.raises(ValueError, match="invalid logical interval"):
        runtime.LatencySample(runtime.LatencyStage.TOOL, start, end)


def test_latency_trace_accumulates_ordered_samples_immutably() -> None:
    first = runtime.LatencySample(runtime.LatencyStage.PERCEPTION, 10, 30)
    second = runtime.LatencySample(runtime.LatencyStage.DECISION, 35, 55)
    empty = runtime.LatencyTrace()
    trace = empty.append(first).append(second)
    assert empty.samples == ()
    assert trace.samples == (first, second)
    assert trace.active_ms == 40
    assert trace.elapsed_ms == 45
    assert not trace.complete
