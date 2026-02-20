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


def test_step_decoder_reports_missing_fields_at_the_supplied_path() -> None:
    encoded = step_to_dict(sample_step())
    encoded.pop("effects")
    with pytest.raises(ValueError, match=r"\$\.steps\[4\].*missing=\['effects'\]"):
        step_from_dict(encoded, "$.steps[4]")


def test_step_decoder_does_not_coerce_scalar_types() -> None:
    encoded = step_to_dict(sample_step())
    encoded["next"] = "done"
    with pytest.raises(TypeError, match=r"\$\.step\.next: expected string array"):
        step_from_dict(encoded)
    encoded = step_to_dict(sample_step())
    encoded["max_iterations"] = True
    with pytest.raises(TypeError, match="expected integer"):
        step_from_dict(encoded)


def test_step_decoder_requires_nullable_maps_to_be_objects() -> None:
    for field in ("preconditions", "effects", "compensation"):
        encoded = step_to_dict(sample_step())
        encoded[field] = ["not", "an", "object"]
        with pytest.raises(TypeError, match=rf"{field}: expected object or null"):
            step_from_dict(encoded)
