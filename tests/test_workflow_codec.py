"""Versioned workflow DSL serialization tests."""

from __future__ import annotations

from voxwright.identifiers import Identifier
from voxwright.workflow import StepKind, WorkflowStep
from voxwright.workflow_codec import step_to_dict


def sample_step() -> WorkflowStep:
    return WorkflowStep(
        Identifier("reserve"),
        StepKind.ACTION,
        (Identifier("done"),),
        preconditions={"allowed": True},
        effects={"status": "held"},
        compensation={"status": "released"},
    )


def test_step_encoding_exposes_defaults_and_ordered_successors() -> None:
    assert step_to_dict(sample_step()) == {
        "id": "reserve",
        "kind": "action",
        "next": ["done"],
        "preconditions": {"allowed": True},
        "effects": {"status": "held"},
        "compensation": {"status": "released"},
        "max_iterations": 0,
    }
    assert step_to_dict(WorkflowStep(Identifier("done"), StepKind.END))["next"] == []
