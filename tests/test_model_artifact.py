"""Framework-independent model artifact schema checks."""

from __future__ import annotations

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
