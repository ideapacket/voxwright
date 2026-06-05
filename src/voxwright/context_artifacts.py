"""Strict artifacts for versioned multimodal application context."""

from __future__ import annotations

from voxwright.context import AttachmentKind, ContextAttachment, ContextManager
from voxwright.core import JSONValue
from voxwright.identifiers import Identifier


def attachment_to_dict(item: ContextAttachment) -> dict[str, JSONValue]:
    return {
        "context_id": str(item.context_id),
        "kind": item.kind.value,
        "content": item.content,
        "version": item.version,
        "token_cost": item.token_cost,
        "priority": item.priority,
    }


ATTACHMENT_FIELDS = frozenset(
    {"context_id", "kind", "content", "version", "token_cost", "priority"}
)


def attachment_from_dict(value: JSONValue, path: str = "$.attachment") -> ContextAttachment:
    if not isinstance(value, dict) or set(value) != ATTACHMENT_FIELDS:
        raise ValueError(f"{path}: expected exact context attachment fields")
    context_id = value["context_id"]
    kind = value["kind"]
    if not isinstance(context_id, str) or not isinstance(kind, str):
        raise TypeError(f"{path}: context_id and kind must be strings")
    integers: list[int] = []
    for field in ("version", "token_cost", "priority"):
        item = value[field]
        if isinstance(item, bool) or not isinstance(item, int):
            raise TypeError(f"{path}.{field}: expected integer")
        integers.append(item)
    try:
        attachment_kind = AttachmentKind(kind)
    except ValueError as error:
        raise ValueError(f"{path}.kind: unknown attachment kind {kind!r}") from error
    return ContextAttachment(Identifier(context_id), attachment_kind, value["content"], *integers)


def context_to_dict(manager: ContextManager) -> dict[str, JSONValue]:
    return {
        "schema_version": 1,
        "token_budget": manager.token_budget,
        "attachments": [attachment_to_dict(item) for item in manager.attachments],
    }


def context_from_dict(value: JSONValue) -> ContextManager:
    expected = {"schema_version", "token_budget", "attachments"}
    if not isinstance(value, dict) or set(value) != expected:
        raise ValueError("$: expected exact context snapshot fields")
    if value["schema_version"] != 1 or isinstance(value["schema_version"], bool):
        raise ValueError(f"$.schema_version: unsupported version {value['schema_version']!r}")
    budget = value["token_budget"]
    attachments = value["attachments"]
    if isinstance(budget, bool) or not isinstance(budget, int):
        raise TypeError("$.token_budget: expected integer")
    if not isinstance(attachments, list):
        raise TypeError("$.attachments: expected array")
    manager = ContextManager(budget)
    for index, item in enumerate(attachments):
        manager.add(attachment_from_dict(item, f"$.attachments[{index}]"))
    return manager
