from __future__ import annotations

import pytest

from voxwright.context import AttachmentKind, ContextAttachment
from voxwright.context_artifacts import attachment_from_dict, attachment_to_dict
from voxwright.identifiers import Identifier


def sample_attachment() -> ContextAttachment:
    return ContextAttachment(
        Identifier("screen-1"),
        AttachmentKind.SCREEN_STATE,
        {"page": "calendar", "selection": 2},
        version=3,
        token_cost=4,
        priority=2,
    )


def test_attachment_artifact_exposes_version_and_budget_fields() -> None:
    assert attachment_to_dict(sample_attachment()) == {
        "context_id": "screen-1",
        "kind": "screen-state",
        "content": {"page": "calendar", "selection": 2},
        "version": 3,
        "token_cost": 4,
        "priority": 2,
    }


def test_attachment_codec_roundtrips_structured_content() -> None:
    original = sample_attachment()
    assert attachment_from_dict(attachment_to_dict(original)) == original


def test_attachment_decoder_rejects_unknown_kind_and_scalar_coercion() -> None:
    encoded = attachment_to_dict(sample_attachment())
    encoded["kind"] = "camera"
    with pytest.raises(ValueError, match="unknown attachment kind"):
        attachment_from_dict(encoded)
    encoded = attachment_to_dict(sample_attachment())
    encoded["token_cost"] = True
    with pytest.raises(TypeError, match="token_cost: expected integer"):
        attachment_from_dict(encoded)
