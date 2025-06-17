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
