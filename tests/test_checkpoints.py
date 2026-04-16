"""Workflow checkpoint artifact tests."""

from __future__ import annotations

import pytest

from voxwright.checkpoints import WorkflowCheckpoint, checkpoint_from_dict, checkpoint_to_dict
from voxwright.hashing import EMPTY_DIGEST
from voxwright.identifiers import Identifier


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
