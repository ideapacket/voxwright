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


def linear_workflow() -> workflow.WorkflowDefinition:
    return workflow.WorkflowDefinition(
        Identifier("simple"),
        1,
        Identifier("start"),
        (step("start", workflow.StepKind.ACTION, "done"), step("done", workflow.StepKind.END)),
    )


def test_definition_indexes_unique_steps() -> None:
    definition = linear_workflow()
    assert definition.step_map[Identifier("start")].next_steps == (Identifier("done"),)


def test_definition_rejects_missing_start_and_duplicate_ids() -> None:
    with pytest.raises(ValueError, match="start step does not exist"):
        workflow.WorkflowDefinition(Identifier("bad"), 1, Identifier("missing"), (step("done"),))
    with pytest.raises(ValueError, match="must be unique"):
        workflow.WorkflowDefinition(
            Identifier("bad"), 1, Identifier("same"), (step("same"), step("same"))
        )


def test_reference_validation_rejects_dangling_target() -> None:
    definition = workflow.WorkflowDefinition(
        Identifier("bad"),
        1,
        Identifier("start"),
        (step("start", workflow.StepKind.ACTION, "missing"),),
    )
    with pytest.raises(ValueError, match="dangling reference missing"):
        workflow.validate_references(definition)


def test_reference_validation_enforces_branch_and_parallel_arity() -> None:
    branch = workflow.WorkflowDefinition(
        Identifier("bad"), 1, Identifier("branch"), (step("branch", workflow.StepKind.BRANCH),)
    )
    with pytest.raises(ValueError, match="invalid successor count"):
        workflow.validate_references(branch)
