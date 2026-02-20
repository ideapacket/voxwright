"""Versioned workflow DSL serialization tests."""

from __future__ import annotations

import pytest

from voxwright.identifiers import Identifier
from voxwright.workflow import StepKind, WorkflowStep
from voxwright.workflow_codec import step_from_dict, step_to_dict


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


def test_step_codec_roundtrips_nested_json_effects() -> None:
    original = WorkflowStep(
        Identifier("apply"),
        StepKind.ACTION,
        effects={"nested": {"items": [1, True, None]}},
    )
    assert step_from_dict(step_to_dict(original)) == original


def test_step_decoder_rejects_unknown_fields_and_kinds() -> None:
    encoded = step_to_dict(sample_step())
    encoded["surprise"] = True
    with pytest.raises(ValueError, match=r"unknown=\['surprise'\]"):
        step_from_dict(encoded)
    encoded.pop("surprise")
    encoded["kind"] = "fork"
    with pytest.raises(ValueError, match="unknown step kind 'fork'"):
        step_from_dict(encoded)
