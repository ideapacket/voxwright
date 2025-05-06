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


def test_cycle_validation_rejects_unbounded_action_cycle() -> None:
    definition = workflow.WorkflowDefinition(
        Identifier("cycle"),
        1,
        Identifier("a"),
        (step("a", workflow.StepKind.ACTION, "b"), step("b", workflow.StepKind.ACTION, "a")),
    )
    with pytest.raises(ValueError, match="unbounded workflow cycle"):
        workflow.validate_acyclic(definition)


def test_bounded_loop_back_edge_is_allowed() -> None:
    loop = workflow.WorkflowStep(
        Identifier("loop"),
        workflow.StepKind.LOOP,
        (Identifier("loop"), Identifier("done")),
        max_iterations=2,
    )
    definition = workflow.WorkflowDefinition(
        Identifier("bounded"), 1, Identifier("loop"), (loop, step("done", workflow.StepKind.END))
    )
    workflow.validate_acyclic(definition)


def test_preconditions_compare_types_exactly() -> None:
    item = workflow.WorkflowStep(
        Identifier("check"), workflow.StepKind.ACTION, preconditions={"ready": True}
    )
    assert workflow.preconditions_met(item, {"ready": True})
    assert not workflow.preconditions_met(item, {"ready": 1})
    assert not workflow.preconditions_met(item, {})


def test_effect_application_does_not_mutate_caller_state() -> None:
    state = {"status": "old"}
    item = workflow.WorkflowStep(
        Identifier("set"), workflow.StepKind.ACTION, effects={"status": "new", "count": 1}
    )
    assert workflow.apply_effects(item, state) == {"status": "new", "count": 1}
    assert state == {"status": "old"}


def test_linear_engine_applies_steps_in_graph_order() -> None:
    start = workflow.WorkflowStep(
        Identifier("start"), workflow.StepKind.ACTION, (Identifier("done"),), effects={"count": 1}
    )
    definition = workflow.WorkflowDefinition(
        Identifier("linear"), 1, start.step_id, (start, step("done", workflow.StepKind.END))
    )
    result = workflow.run_linear(definition)
    assert result.state == {"count": 1}
    assert result.visited == (Identifier("start"), Identifier("done"))


def test_linear_engine_stops_before_failed_precondition_effect() -> None:
    guarded = workflow.WorkflowStep(
        Identifier("guard"),
        workflow.StepKind.ACTION,
        preconditions={"allowed": True},
        effects={"executed": True},
    )
    definition = workflow.WorkflowDefinition(Identifier("guarded"), 1, guarded.step_id, (guarded,))
    with pytest.raises(RuntimeError, match="precondition failed"):
        workflow.run_linear(definition, {"allowed": False})


def test_branch_target_uses_true_then_false_successor_order() -> None:
    branch = workflow.WorkflowStep(
        Identifier("choose"),
        workflow.StepKind.BRANCH,
        (Identifier("yes"), Identifier("no")),
        preconditions={"confirmed": True},
    )
    assert workflow.branch_target(branch, {"confirmed": True}) == Identifier("yes")
    assert workflow.branch_target(branch, {"confirmed": False}) == Identifier("no")


def test_branch_target_rejects_non_branch_step() -> None:
    with pytest.raises(ValueError, match="two-way branch"):
        workflow.branch_target(step("action"), {})


def test_loop_target_runs_exactly_bounded_iterations() -> None:
    loop = workflow.WorkflowStep(
        Identifier("loop"),
        workflow.StepKind.LOOP,
        (Identifier("body"), Identifier("done")),
        max_iterations=2,
    )
    assert [workflow.loop_target(loop, index) for index in range(3)] == [
        Identifier("body"),
        Identifier("body"),
        Identifier("done"),
    ]


def test_loop_target_rejects_negative_iteration() -> None:
    loop = workflow.WorkflowStep(
        Identifier("loop"),
        workflow.StepKind.LOOP,
        (Identifier("body"), Identifier("done")),
        max_iterations=1,
    )
    with pytest.raises(ValueError, match="cannot be negative"):
        workflow.loop_target(loop, -1)


def test_parallel_fanout_preserves_declared_order() -> None:
    fanout = step("fanout", workflow.StepKind.PARALLEL, "calendar", "music", "home")
    assert workflow.parallel_order(fanout) == (
        Identifier("calendar"),
        Identifier("music"),
        Identifier("home"),
    )


def test_parallel_fanout_rejects_duplicate_targets() -> None:
    duplicate = step("fanout", workflow.StepKind.PARALLEL, "same", "same")
    with pytest.raises(ValueError, match="must be unique"):
        workflow.parallel_order(duplicate)
