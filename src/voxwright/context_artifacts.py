"""Strict artifacts for versioned multimodal application context."""

from __future__ import annotations

from voxwright.context import AttachmentKind, ContextAttachment
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
