from __future__ import annotations

from pathlib import Path

import pytest

from voxwright.core import canonical_json
from voxwright.schemas import ARTIFACT_SCHEMAS, ArtifactSchema, artifact_schema, schema_catalog


def test_schema_catalog_has_unique_sorted_public_names() -> None:
    names = [item.name for item in ARTIFACT_SCHEMAS]
    assert names == sorted(names)
    assert len(names) == len(set(names)) == 11
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


@pytest.mark.parametrize("schema", ARTIFACT_SCHEMAS, ids=lambda item: item.name)
def test_checksummed_schemas_declare_integrity_fields(schema: ArtifactSchema) -> None:
    integrity = {"checksum", "digest"}.intersection(schema.required_fields)
    assert bool(integrity) is schema.checksummed
