"""Golden evaluation checks over synthetic planted truth."""

from __future__ import annotations

import pytest

from voxwright.evaluation import EvaluationRun


def run(**overrides: object) -> EvaluationRun:
    values: dict[str, object] = {
        "run_id": "run-1",
        "task_type": "schedule",
        "difficulty": "easy",
        "noise_rate": 0.1,
        "expected_slots": {"title": "lab"},
        "predicted_slots": {"title": "lab"},
        "expected_tools": ("calendar.create",),
        "selected_tools": ("calendar.create",),
        "goal_satisfied": True,
        "turns": 2,
        "repairs": 0,
        "false_executes": 0,
        "latency_ms": 100,
        "latency_budget_ms": 150,
    }
    values.update(overrides)
    return EvaluationRun(**values)  # type: ignore[arg-type]


def test_evaluation_run_preserves_planted_and_observed_values() -> None:
    item = run()
    assert item.expected_slots == item.predicted_slots
    assert item.expected_tools == item.selected_tools
    assert item.goal_satisfied and item.false_executes == 0


def test_evaluation_run_validates_identity_and_probability_fields() -> None:
    with pytest.raises(ValueError, match="run id cannot be empty"):
        run(run_id=" ")
    with pytest.raises(ValueError, match="noise rate"):
        run(noise_rate=1.01)
    with pytest.raises(TypeError, match="goal_satisfied"):
        run(goal_satisfied=1)


def test_evaluation_run_rejects_malformed_ground_truth() -> None:
    with pytest.raises(ValueError, match="expected slot"):
        run(expected_slots={"title": ""})
    with pytest.raises(ValueError, match="predicted slot"):
        run(predicted_slots={"": "lab"})
    with pytest.raises(ValueError, match="tool names"):
        run(expected_tools=("",))


def test_evaluation_run_enforces_counter_boundaries() -> None:
    with pytest.raises(ValueError, match="turns must be positive"):
        run(turns=0)
    with pytest.raises(ValueError, match="repairs cannot exceed"):
        run(turns=1, repairs=2)
    with pytest.raises(ValueError, match="false executes"):
        run(false_executes=-1)
    with pytest.raises(ValueError, match="latency budget"):
        run(latency_budget_ms=-1)
