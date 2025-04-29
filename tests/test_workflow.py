"""Tests for deterministic versioned workflows."""

from __future__ import annotations

import pytest

import voxwright.workflow as workflow
from voxwright.identifiers import Identifier


def step(
    name: str, kind: workflow.StepKind = workflow.StepKind.ACTION, *next_names: str
) -> workflow.WorkflowStep:
    return workflow.WorkflowStep(
        Identifier(name), kind, tuple(Identifier(item) for item in next_names)
    )


def test_step_kinds_have_stable_dsl_values() -> None:
    assert [item.value for item in workflow.StepKind] == [
        "action",
        "branch",
        "loop",
        "parallel",
        "end",
    ]


def test_step_validates_loop_bound_and_end_successors() -> None:
    with pytest.raises(ValueError, match="positive iteration"):
        step("loop", workflow.StepKind.LOOP, "again")
    with pytest.raises(ValueError, match="end step cannot"):
        step("done", workflow.StepKind.END, "extra")


def test_step_preserves_strict_json_effects() -> None:
    item = workflow.WorkflowStep(
        Identifier("set"), workflow.StepKind.ACTION, effects={"status": "ready"}
    )
    assert item.effects == {"status": "ready"}
