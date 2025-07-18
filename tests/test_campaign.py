"""Tests for synthetic campaign slicing and artifacts."""

from __future__ import annotations

from dataclasses import replace

import pytest

from voxwright.campaign import SliceDimension, noise_band, slice_campaign, slot_breakdown
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


def test_campaign_noise_bands_are_machine_readable() -> None:
    assert [noise_band(value) for value in (0.0, 0.19, 0.2, 0.49, 0.5, 1.0)] == [
        "low",
        "low",
        "medium",
        "medium",
        "high",
        "high",
    ]


def test_noise_slice_places_every_boundary_once() -> None:
    runs = tuple(
        replace(run(f"run-{index}"), noise_rate=rate) for index, rate in enumerate((0.0, 0.2, 0.5))
    )
    slices = slice_campaign(runs, SliceDimension.NOISE_BAND)
    assert [(item.label, item.metrics.run_count) for item in slices] == [
        ("high", 1),
        ("low", 1),
        ("medium", 1),
    ]


def test_noise_band_rejects_out_of_range_values() -> None:
    with pytest.raises(ValueError, match="between 0 and 1"):
        noise_band(-0.01)
    with pytest.raises(ValueError, match="between 0 and 1"):
        noise_band(1.01)


def test_slot_breakdown_explains_per_name_accuracy() -> None:
    runs = (
        run("a"),
        replace(
            run("b"),
            expected_slots={"value": "b", "room": "study"},
            predicted_slots={"value": "wrong", "room": "study"},
        ),
    )
    scores = slot_breakdown(runs)
    assert [(score.name, score.correct, score.expected, score.accuracy) for score in scores] == [
        ("room", 1, 1, 1.0),
        ("value", 1, 2, 0.5),
    ]
