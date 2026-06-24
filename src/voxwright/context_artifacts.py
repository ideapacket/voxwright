"""Strict artifacts for versioned multimodal application context."""

from __future__ import annotations

from pathlib import Path

from voxwright.context import AttachmentKind, ContextAttachment, ContextManager
from voxwright.core import JSONValue, canonical_json, parse_json
from voxwright.events import ContextUpdate
from voxwright.hashing import content_digest
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


def encode_context(manager: ContextManager) -> str:
    return canonical_json(context_to_dict(manager)) + "\n"


def decode_context(text: str) -> ContextManager:
    if not text.strip():
        raise ValueError("context snapshot document is empty")
    return context_from_dict(parse_json(text))


def load_context(path: Path) -> ContextManager:
    text = path.read_text(encoding="utf-8")
    if text and not text.endswith("\n"):
        raise ValueError(f"context snapshot is missing terminal newline: {path}")
    return decode_context(text)


def write_context(path: Path, manager: ContextManager) -> None:
    try:
        with path.open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(encode_context(manager))
    except FileExistsError as error:
        raise FileExistsError(f"context snapshot output already exists: {path}") from error


def context_digest(manager: ContextManager) -> str:
    """Identify exact canonical context bytes, including versions and budget."""
    return content_digest(encode_context(manager).encode("utf-8"))


def context_update(manager: ContextManager, evicted: tuple[Identifier, ...] = ()) -> ContextUpdate:
    """Describe the exact context versions visible after deterministic eviction."""
    versions = {str(item.context_id): item.version for item in manager.attachments}
    return ContextUpdate(context_digest(manager), versions, manager.token_cost, evicted)
