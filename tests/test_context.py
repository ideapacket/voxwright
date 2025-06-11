"""Tests for multimodal application context management."""

from __future__ import annotations

import pytest

import voxwright.context as context
from voxwright.identifiers import Identifier


def attachment(
    name: str = "screen-1", cost: int = 3, priority: int = 0
) -> context.ContextAttachment:
    return context.ContextAttachment(
        Identifier(name),
        context.AttachmentKind.SCREEN_STATE,
        {"page": "calendar"},
        token_cost=cost,
        priority=priority,
    )


def test_attachment_kinds_cover_application_integration_inputs() -> None:
    assert [item.value for item in context.AttachmentKind] == [
        "screen-state",
        "document",
        "user-preferences",
    ]


def test_attachment_preserves_strict_structured_content() -> None:
    item = attachment()
    assert item.content == {"page": "calendar"}
    assert item.version == 1 and item.token_cost == 3


@pytest.mark.parametrize(("version", "cost", "priority"), [(0, 1, 0), (1, 0, 0), (1, 1, -1)])
def test_attachment_rejects_invalid_accounting(version: int, cost: int, priority: int) -> None:
    with pytest.raises(ValueError):
        context.ContextAttachment(
            Identifier("context-1"),
            context.AttachmentKind.DOCUMENT,
            "text",
            version,
            cost,
            priority,
        )
