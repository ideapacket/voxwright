"""Workflow checkpoint artifact tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from voxwright.checkpoints import (
    WorkflowCheckpoint,
    checkpoint_from_dict,
    checkpoint_to_dict,
    decode_checkpoint,
    encode_checkpoint,
)
from voxwright.hashing import EMPTY_DIGEST
from voxwright.identifiers import Identifier

GOLDEN = Path(__file__).parent / "golden" / "workflow_checkpoint.json"


def sample_checkpoint() -> WorkflowCheckpoint:
    return WorkflowCheckpoint(
        (Identifier("prepare"), Identifier("commit")),
        {"count": 2, "ready": True},
        "sha256:" + "1" * 64,
    )


def test_checkpoint_accepts_strict_state_and_stable_identity() -> None:
    checkpoint = sample_checkpoint()
    assert checkpoint.schema_version == 1
    assert checkpoint.completed == (Identifier("prepare"), Identifier("commit"))
    assert checkpoint.state == {"count": 2, "ready": True}


def test_empty_checkpoint_uses_empty_content_digest() -> None:
    checkpoint = WorkflowCheckpoint((), {})
    assert checkpoint.digest == EMPTY_DIGEST


def test_checkpoint_rejects_duplicate_steps_bad_state_and_digest() -> None:
    with pytest.raises(ValueError, match="must be unique"):
        WorkflowCheckpoint((Identifier("same"), Identifier("same")), {})
    with pytest.raises(TypeError, match="unsupported JSON"):
        WorkflowCheckpoint((), {"bad": object()})  # type: ignore[dict-item]
    with pytest.raises(ValueError, match="algorithm-qualified"):
        WorkflowCheckpoint((), {}, "not-a-digest")


def test_checkpoint_object_codec_roundtrips_every_field() -> None:
    original = sample_checkpoint()
    assert checkpoint_from_dict(checkpoint_to_dict(original)) == original
    assert tuple(checkpoint_to_dict(original)) == (
        "schema_version",
        "completed",
        "state",
        "digest",
    )


def test_checkpoint_decoder_rejects_field_and_version_drift() -> None:
    encoded = checkpoint_to_dict(sample_checkpoint())
    encoded["extra"] = True
    with pytest.raises(ValueError, match=r"unknown=\['extra'\]"):
        checkpoint_from_dict(encoded)
    encoded.pop("extra")
    encoded["schema_version"] = 2
    with pytest.raises(ValueError, match="unsupported checkpoint schema version"):
        checkpoint_from_dict(encoded)


def test_checkpoint_decoder_reports_completed_item_paths() -> None:
    encoded = checkpoint_to_dict(sample_checkpoint())
    encoded["completed"] = ["prepare", 4]
    with pytest.raises(TypeError, match=r"completed\[1\]: expected string"):
        checkpoint_from_dict(encoded)
    encoded["completed"] = "prepare"
    with pytest.raises(TypeError, match="expected string array"):
        checkpoint_from_dict(encoded)


def test_checkpoint_text_codec_is_canonical_and_reversible() -> None:
    encoded = encode_checkpoint(sample_checkpoint())
    assert encoded.endswith("\n") and " " not in encoded
    assert decode_checkpoint(encoded) == sample_checkpoint()
    assert encode_checkpoint(decode_checkpoint(encoded)).encode() == encoded.encode()


def test_checkpoint_text_decoder_rejects_empty_and_trailing_documents() -> None:
    with pytest.raises(ValueError, match="document is empty"):
        decode_checkpoint("\n")
    with pytest.raises(ValueError):
        decode_checkpoint(encode_checkpoint(sample_checkpoint()) + "{}")


def test_checkpoint_bytes_match_reviewed_golden() -> None:
    assert encode_checkpoint(sample_checkpoint()).encode() == GOLDEN.read_bytes()
    assert decode_checkpoint(GOLDEN.read_text(encoding="utf-8")) == sample_checkpoint()
