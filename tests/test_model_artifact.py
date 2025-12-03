"""Framework-independent model artifact schema checks."""

from __future__ import annotations

import json

import pytest

from voxwright.model_artifact import (
    ModelArtifact,
    decode_model_artifact,
    encode_model_artifact,
    model_artifact_from_dict,
)


def tiny_artifact() -> ModelArtifact:
    return ModelArtifact(
        ("<unk>", "play"),
        ("O", "B-track"),
        ("music.play",),
        2,
        7,
        {
            "embedding.weight": [[0.0, 0.1], [0.2, 0.3]],
            "slot_head.weight": [[0.4, 0.5], [0.6, 0.7]],
            "slot_head.bias": [0.0, 0.1],
            "tool_head.weight": [[0.8, 0.9]],
            "tool_head.bias": [0.2],
        },
    )


def test_model_artifact_roundtrips_canonical_json() -> None:
    artifact = tiny_artifact()
    encoded = encode_model_artifact(artifact)
    assert encoded.endswith("\n") and encoded.count("\n") == 1
    assert '"schema_version":1' in encoded
    assert '"checksum":"sha256:' in encoded
    assert decode_model_artifact(encoded) == artifact
    assert model_artifact_from_dict(artifact.to_dict()) == artifact


def test_model_artifact_rejects_envelope_drift_and_tampering() -> None:
    encoded = encode_model_artifact(tiny_artifact())
    value = json.loads(encoded)
    value["model"]["seed"] = 8
    with pytest.raises(ValueError, match="checksum mismatch"):
        decode_model_artifact(json.dumps(value) + "\n")
    with pytest.raises(ValueError, match="one complete JSON line"):
        decode_model_artifact(encoded.rstrip("\n"))
    value = json.loads(encoded)
    value["schema_version"] = 2
    with pytest.raises(ValueError, match="unsupported"):
        decode_model_artifact(json.dumps(value) + "\n")


def test_model_artifact_validates_names_shapes_and_types() -> None:
    artifact = tiny_artifact()
    value = artifact.to_dict()
    value["extra"] = True
    with pytest.raises(ValueError, match="invalid model artifact shape"):
        model_artifact_from_dict(value)
    parameters = dict(artifact.parameters)
    parameters["embedding.weight"] = [[0.0]]
    with pytest.raises(ValueError, match=r"shape .* expected"):
        ModelArtifact(
            artifact.vocabulary,
            artifact.slot_classes,
            artifact.tool_classes,
            artifact.embedding_size,
            artifact.seed,
            parameters,
        )
    value = artifact.to_dict()
    value["vocabulary"] = [1]
    with pytest.raises(TypeError, match="string array"):
        model_artifact_from_dict(value)


def test_model_artifact_rejects_nonfinite_and_missing_parameters() -> None:
    artifact = tiny_artifact()
    parameters = dict(artifact.parameters)
    parameters["slot_head.bias"] = [float("inf"), 0.0]
    with pytest.raises(ValueError, match="non-finite number"):
        ModelArtifact(
            artifact.vocabulary,
            artifact.slot_classes,
            artifact.tool_classes,
            artifact.embedding_size,
            artifact.seed,
            parameters,
        )
    parameters = dict(artifact.parameters)
    parameters.pop("tool_head.bias")
    with pytest.raises(ValueError, match="parameter names are invalid"):
        ModelArtifact(
            artifact.vocabulary,
            artifact.slot_classes,
            artifact.tool_classes,
            artifact.embedding_size,
            artifact.seed,
            parameters,
        )
    parameters = dict(artifact.parameters)
    parameters["tool_head.bias"] = ["not-a-number"]
    with pytest.raises(ValueError, match="must be numeric"):
        ModelArtifact(
            artifact.vocabulary,
            artifact.slot_classes,
            artifact.tool_classes,
            artifact.embedding_size,
            artifact.seed,
            parameters,
        )
