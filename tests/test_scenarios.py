"""Tests for reproducible synthetic scenario generation."""

from __future__ import annotations

import pytest

import voxwright.scenarios as scenarios
from voxwright.identifiers import Identifier


def expected_call(name: str = "calendar.create") -> scenarios.ExpectedToolCall:
    return scenarios.ExpectedToolCall(Identifier(name), {"title": "review"})


def test_task_families_are_public_and_stable() -> None:
    assert [item.value for item in scenarios.TaskType] == [
        "schedule",
        "music",
        "smart-home",
        "notes",
        "multi-task",
        "nested",
    ]


def test_goal_preserves_planted_slots_and_call_order() -> None:
    calls = (expected_call(), expected_call("timer.start"))
    goal = scenarios.TaskGoal(
        Identifier("goal-1"), scenarios.TaskType.SCHEDULE, {"hour": 19}, calls
    )
    assert goal.slots == {"hour": 19}
    assert goal.tool_calls == calls


def test_goal_requires_safe_slot_names_and_ground_truth_calls() -> None:
    with pytest.raises(ValueError, match="invalid identifier"):
        scenarios.TaskGoal(
            Identifier("goal-1"), scenarios.TaskType.NOTES, {"bad slot": "x"}, (expected_call(),)
        )
    with pytest.raises(ValueError, match="at least one"):
        scenarios.TaskGoal(Identifier("goal-1"), scenarios.TaskType.NOTES, {}, ())
