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


def test_context_manager_replaces_only_with_newer_version() -> None:
    manager = context.ContextManager(10)
    manager.add(attachment())
    newer = context.ContextAttachment(
        Identifier("screen-1"),
        context.AttachmentKind.SCREEN_STATE,
        {"page": "music"},
        version=2,
        token_cost=2,
    )
    manager.add(newer)
    assert manager.attachments == (newer,)
    assert manager.token_cost == 2


def test_context_manager_rejects_stale_or_equal_version() -> None:
    manager = context.ContextManager(10)
    manager.add(attachment())
    with pytest.raises(ValueError, match="version must increase"):
        manager.add(attachment())


def test_context_budget_must_be_positive() -> None:
    with pytest.raises(ValueError, match="must be positive"):
        context.ContextManager(0)


def test_eviction_removes_low_priority_then_oldest() -> None:
    manager = context.ContextManager(5)
    manager.add(attachment("old-low", 3, 0))
    manager.add(attachment("high", 4, 2))
    manager.add(attachment("new-low", 2, 0))
    assert manager.evict_to_budget() == (Identifier("old-low"), Identifier("new-low"))
    assert [item.context_id.value for item in manager.attachments] == ["high"]


def test_eviction_is_identity_when_already_within_budget() -> None:
    manager = context.ContextManager(5)
    manager.add(attachment(cost=5))
    assert manager.evict_to_budget() == ()
    assert manager.token_cost == 5


def test_single_oversized_attachment_is_evicted() -> None:
    manager = context.ContextManager(2)
    manager.add(attachment(cost=3))
    assert manager.evict_to_budget() == (Identifier("screen-1"),)
    assert manager.attachments == ()
