from __future__ import annotations

from pathlib import Path

import pytest

from voxwright.checkpoints import WorkflowCheckpoint, checkpoint_to_dict
from voxwright.core import canonical_json
from voxwright.identifiers import Identifier
from voxwright.sandbox import SideEffectLedger
from voxwright.sandbox_audit import audit_to_dict
from voxwright.schemas import ARTIFACT_SCHEMAS, ArtifactSchema, artifact_schema, schema_catalog
from voxwright.workflow import StepKind, WorkflowDefinition, WorkflowStep
from voxwright.workflow_codec import workflow_to_dict


def test_schema_catalog_has_unique_sorted_public_names() -> None:
    names = [item.name for item in ARTIFACT_SCHEMAS]
    assert names == sorted(names)
    assert len(names) == len(set(names)) == 13
    assert all(item.version == 1 for item in ARTIFACT_SCHEMAS)
    assert schema_catalog() == [item.to_dict() for item in ARTIFACT_SCHEMAS]


def test_schema_lookup_and_descriptor_boundaries() -> None:
    for item in ARTIFACT_SCHEMAS:
        assert artifact_schema(item.name) is item
    with pytest.raises(ValueError, match="unknown artifact schema"):
        artifact_schema("missing")
    with pytest.raises(ValueError, match="positive version"):
        ArtifactSchema("event", 0, "application/json", ("id",), False)
    with pytest.raises(ValueError, match="application type"):
        ArtifactSchema("event", 1, "text/json", ("id",), False)
    with pytest.raises(ValueError, match="nonempty and unique"):
        ArtifactSchema("event", 1, "application/json", ("id", "id"), False)


def test_schema_catalog_matches_reviewed_golden_bytes() -> None:
    golden = Path(__file__).parent / "golden" / "schema_catalog.json"
    assert canonical_json(schema_catalog()) + "\n" == golden.read_text(encoding="utf-8")


def test_workflow_schema_fields_match_the_actual_public_envelope() -> None:
    definition = WorkflowDefinition(
        Identifier("catalog-check"),
        1,
        Identifier("done"),
        (WorkflowStep(Identifier("done"), StepKind.END),),
    )
    schema = artifact_schema("workflow-definition")
    assert tuple(workflow_to_dict(definition)) == schema.required_fields
    assert schema.media_type == "application/json" and not schema.checksummed


def test_checkpoint_schema_fields_match_the_typed_codec() -> None:
    checkpoint = WorkflowCheckpoint((), {})
    schema = artifact_schema("workflow-checkpoint")
    assert tuple(checkpoint_to_dict(checkpoint)) == schema.required_fields
    assert schema.media_type == "application/json" and schema.checksummed


def test_side_effect_schema_matches_the_verified_audit_codec() -> None:
    schema = artifact_schema("side-effect-ledger")
    assert tuple(audit_to_dict(SideEffectLedger())) == schema.required_fields
    assert schema.media_type == "application/json" and schema.checksummed


@pytest.mark.parametrize("schema", ARTIFACT_SCHEMAS, ids=lambda item: item.name)
def test_checksummed_schemas_declare_integrity_fields(schema: ArtifactSchema) -> None:
    integrity = {"checksum", "digest", "links"}.intersection(schema.required_fields)
    assert bool(integrity) is schema.checksummed
