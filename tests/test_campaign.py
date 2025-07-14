"""Tests for synthetic campaign slicing and artifacts."""

from __future__ import annotations

import pytest

from voxwright.campaign import SliceDimension, slice_campaign
from voxwright.evaluation import EvaluationRun


def run(run_id: str, *, task: str = "schedule", difficulty: str = "easy") -> EvaluationRun:
    return EvaluationRun(
        run_id=run_id,
        task_type=task,
        difficulty=difficulty,
        noise_rate=0.1,
        expected_slots={"value": run_id},
        predicted_slots={"value": run_id},
        expected_tools=(f"{task}.tool",),
        selected_tools=(f"{task}.tool",),
        goal_satisfied=True,
        turns=1,
        repairs=0,
        false_executes=0,
        latency_ms=10,
        latency_budget_ms=20,
    )


def test_campaign_slices_task_type_with_independent_metrics() -> None:
    runs = (run("b", task="music"), run("a"), run("c", task="music"))
    slices = slice_campaign(runs, SliceDimension.TASK_TYPE)
    assert [(item.label, item.run_ids) for item in slices] == [
        ("music", ("b", "c")),
        ("schedule", ("a",)),
    ]
    assert [item.metrics.run_count for item in slices] == [2, 1]


def test_campaign_slices_difficulty_without_losing_runs() -> None:
    runs = (run("a", difficulty="hard"), run("b", difficulty="easy"))
    slices = slice_campaign(runs, SliceDimension.DIFFICULTY)
    assert sum(item.metrics.run_count for item in slices) == len(runs)
    assert {item.label for item in slices} == {"easy", "hard"}


def test_campaign_slice_order_is_independent_of_input_order() -> None:
    forward = (run("a", task="schedule"), run("b", task="music"))
    reverse = tuple(reversed(forward))
    assert [item.label for item in slice_campaign(forward, SliceDimension.TASK_TYPE)] == [
        item.label for item in slice_campaign(reverse, SliceDimension.TASK_TYPE)
    ]


def test_campaign_slicing_rejects_no_observations() -> None:
    with pytest.raises(ValueError, match="at least one run"):
        slice_campaign((), SliceDimension.TASK_TYPE)


def test_campaign_slice_retains_original_order_within_label() -> None:
    runs = (run("z", task="music"), run("a", task="music"))
    [music] = slice_campaign(runs, SliceDimension.TASK_TYPE)
    assert music.run_ids == ("z", "a")
