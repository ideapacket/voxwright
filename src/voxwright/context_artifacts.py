"""Strict artifacts for versioned multimodal application context."""

from __future__ import annotations

from voxwright.context import ContextAttachment
from voxwright.core import JSONValue


def attachment_to_dict(item: ContextAttachment) -> dict[str, JSONValue]:
    return {
        "context_id": str(item.context_id),
        "kind": item.kind.value,
        "content": item.content,
        "version": item.version,
        "token_cost": item.token_cost,
        "priority": item.priority,
    }
