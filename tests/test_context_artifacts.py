from __future__ import annotations

import pytest

from voxwright.context import AttachmentKind, ContextAttachment, ContextManager
from voxwright.context_artifacts import (
    attachment_from_dict,
    attachment_to_dict,
    context_from_dict,
    context_to_dict,
    decode_context,
    encode_context,
)
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


def test_attachment_decoder_rejects_field_drift_with_path() -> None:
    encoded = attachment_to_dict(sample_attachment())
    encoded["owner"] = "unversioned"
    with pytest.raises(ValueError, match=r"\$\.items\[2\]: expected exact"):
        attachment_from_dict(encoded, "$.items[2]")
    encoded.pop("owner")
    encoded.pop("content")
    with pytest.raises(ValueError, match="expected exact"):
        attachment_from_dict(encoded)


def test_context_snapshot_roundtrips_order_and_budget() -> None:
    manager = ContextManager(12)
    manager.add(sample_attachment())
    manager.add(
        ContextAttachment(Identifier("doc-1"), AttachmentKind.DOCUMENT, "synthetic", token_cost=2)
    )
    decoded = context_from_dict(context_to_dict(manager))
    assert decoded.token_budget == 12
    assert decoded.attachments == manager.attachments


def test_context_text_codec_is_canonical_and_deterministic() -> None:
    manager = ContextManager(8)
    manager.add(sample_attachment())
    encoded = encode_context(manager)
    assert encoded.endswith("\n") and " " not in encoded
    decoded = decode_context(encoded)
    assert encode_context(decoded).encode() == encoded.encode()


def test_context_text_decoder_rejects_empty_and_trailing_documents() -> None:
    with pytest.raises(ValueError, match="document is empty"):
        decode_context("\n")
    with pytest.raises(ValueError):
        decode_context('{"attachments":[]}{}')
