from __future__ import annotations

from voxwright.context import AttachmentKind, ContextAttachment
from voxwright.context_artifacts import attachment_to_dict
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
