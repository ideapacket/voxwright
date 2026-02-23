"""Versioned workflow DSL serialization tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from voxwright.identifiers import Identifier
from voxwright.workflow import StepKind, WorkflowDefinition, WorkflowStep
from voxwright.workflow_codec import (
    decode_workflow,
    encode_workflow,
    load_workflow,
    step_from_dict,
    step_to_dict,
    workflow_from_dict,
    workflow_to_dict,
)

GOLDEN = Path(__file__).parent / "golden" / "workflow.json"


def sample_step() -> WorkflowStep:
    return WorkflowStep(
        Identifier("reserve"),
        StepKind.ACTION,
        (Identifier("done"),),
        preconditions={"allowed": True},
        effects={"status": "held"},
        compensation={"status": "released"},
    )


def sample_workflow() -> WorkflowDefinition:
    first = sample_step()
    return WorkflowDefinition(
        Identifier("booking"),
        2,
        first.step_id,
        (first, WorkflowStep(Identifier("done"), StepKind.END)),
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


def test_workflow_encoding_declares_schema_and_graph_identity() -> None:
    encoded = workflow_to_dict(sample_workflow())
    assert encoded["schema_version"] == 1
    assert encoded["name"] == "booking"
    assert encoded["version"] == 2
    assert encoded["start"] == "reserve"
    assert [item["id"] for item in encoded["steps"]] == ["reserve", "done"]  # type: ignore[index]


def test_workflow_definition_roundtrips_after_graph_validation() -> None:
    original = sample_workflow()
    assert workflow_from_dict(workflow_to_dict(original)) == original


def test_workflow_decoder_rejects_future_schema_and_empty_graph() -> None:
    encoded = workflow_to_dict(sample_workflow())
    encoded["schema_version"] = 2
    with pytest.raises(ValueError, match="unsupported version 2"):
        workflow_from_dict(encoded)
    encoded = workflow_to_dict(sample_workflow())
    encoded["steps"] = []
    with pytest.raises(ValueError, match="expected nonempty array"):
        workflow_from_dict(encoded)


def test_workflow_decoder_rejects_dangling_and_cyclic_graphs() -> None:
    encoded = workflow_to_dict(sample_workflow())
    first = encoded["steps"][0]  # type: ignore[index]
    first["next"] = ["missing"]  # type: ignore[index]
    with pytest.raises(ValueError, match="dangling reference missing"):
        workflow_from_dict(encoded)
    encoded = workflow_to_dict(sample_workflow())
    last = encoded["steps"][1]  # type: ignore[index]
    last["kind"] = "action"  # type: ignore[index]
    last["next"] = ["reserve"]  # type: ignore[index]
    with pytest.raises(ValueError, match="unbounded workflow cycle"):
        workflow_from_dict(encoded)


def test_workflow_decoder_rejects_envelope_field_drift() -> None:
    encoded = workflow_to_dict(sample_workflow())
    encoded["description"] = "not in version one"
    with pytest.raises(ValueError, match=r"unknown=\['description'\]"):
        workflow_from_dict(encoded)
    encoded.pop("description")
    encoded.pop("start")
    with pytest.raises(ValueError, match=r"missing=\['start'\]"):
        workflow_from_dict(encoded)


def test_workflow_decoder_preserves_declaration_order() -> None:
    original = sample_workflow()
    decoded = workflow_from_dict(workflow_to_dict(original))
    assert tuple(item.step_id for item in decoded.steps) == (
        Identifier("reserve"),
        Identifier("done"),
    )


def test_workflow_text_codec_is_canonical_and_byte_deterministic() -> None:
    encoded = encode_workflow(sample_workflow())
    assert encoded.endswith("\n") and not encoded.endswith("\n\n")
    assert " " not in encoded
    assert decode_workflow(encoded) == sample_workflow()
    assert encode_workflow(decode_workflow(encoded)).encode() == encoded.encode()


def test_workflow_text_decoder_rejects_empty_and_multiple_documents() -> None:
    with pytest.raises(ValueError, match="document is empty"):
        decode_workflow(" \n")
    with pytest.raises(ValueError):
        decode_workflow(encode_workflow(sample_workflow()) + "{}")


def test_workflow_encoding_matches_reviewed_golden_bytes() -> None:
    assert encode_workflow(sample_workflow()).encode() == GOLDEN.read_bytes()
    assert decode_workflow(GOLDEN.read_text(encoding="utf-8")) == sample_workflow()


def test_workflow_loader_reads_complete_utf8_artifact(tmp_path: Path) -> None:
    artifact = tmp_path / "workflow.json"
    artifact.write_text(encode_workflow(sample_workflow()), encoding="utf-8")
    assert load_workflow(artifact) == sample_workflow()


def test_workflow_loader_rejects_truncated_or_missing_files(tmp_path: Path) -> None:
    artifact = tmp_path / "workflow.json"
    artifact.write_text(encode_workflow(sample_workflow()).rstrip("\n"), encoding="utf-8")
    with pytest.raises(ValueError, match="missing terminal newline"):
        load_workflow(artifact)
    with pytest.raises(FileNotFoundError):
        load_workflow(tmp_path / "missing.json")
