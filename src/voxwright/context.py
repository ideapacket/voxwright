"""Versioned multimodal application context with deterministic budgeting."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum

from voxwright.core import JSONValue, ensure_json_value
from voxwright.identifiers import Identifier


class AttachmentKind(str, Enum):
    SCREEN_STATE = "screen-state"
    DOCUMENT = "document"
    USER_PREFERENCES = "user-preferences"


@dataclass(frozen=True, slots=True)
class ContextAttachment:
    """One structured application attachment and its approximate token cost."""

    context_id: Identifier
    kind: AttachmentKind
    content: JSONValue
    version: int = 1
    token_cost: int = 1
    priority: int = 0

    def __post_init__(self) -> None:
        object.__setattr__(self, "content", ensure_json_value(self.content, "$.content"))
        if self.version < 1:
            raise ValueError("context version must be positive")
        if self.token_cost < 1:
            raise ValueError("context token cost must be positive")
        if self.priority < 0:
            raise ValueError("context priority cannot be negative")


@dataclass(slots=True)
class ContextManager:
    """Store the latest version of each context identifier in insertion order."""

    token_budget: int
    _attachments: list[ContextAttachment]

    def __init__(self, token_budget: int) -> None:
        if token_budget < 1:
            raise ValueError("context token budget must be positive")
        self.token_budget = token_budget
        self._attachments = []

    @property
    def attachments(self) -> tuple[ContextAttachment, ...]:
        return tuple(self._attachments)

    @property
    def token_cost(self) -> int:
        return sum(item.token_cost for item in self._attachments)

    def add(self, attachment: ContextAttachment) -> None:
        matches = [item for item in self._attachments if item.context_id == attachment.context_id]
        if matches and attachment.version <= matches[-1].version:
            raise ValueError("context version must increase")
        self._attachments = [
            item for item in self._attachments if item.context_id != attachment.context_id
        ]
        self._attachments.append(attachment)

    def evict_to_budget(self) -> tuple[Identifier, ...]:
        """Evict lowest priority then oldest attachments until within budget."""
        evicted: list[Identifier] = []
        while self.token_cost > self.token_budget:
            victim_index = min(
                range(len(self._attachments)),
                key=lambda index: (self._attachments[index].priority, index),
            )
            evicted.append(self._attachments.pop(victim_index).context_id)
        return tuple(evicted)


_EMAIL = re.compile(r"(?<![\w.-])[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}(?![\w.-])")
_PHONE = re.compile(r"(?<!\d)(?:\+?\d[\d -]{7,}\d)(?!\d)")
_CARD = re.compile(r"(?<!\d)(?:\d[ -]?){13,19}(?!\d)")


@dataclass(frozen=True, slots=True)
class RedactionResult:
    text: str
    categories: tuple[str, ...]


def redact_private_text(text: str) -> RedactionResult:
    """Redact common PII-like patterns before adapter observation."""
    patterns = (("email", _EMAIL), ("phone", _PHONE), ("card", _CARD))
    categories = [name for name, pattern in patterns if pattern.search(text)]
    output = text
    for name, pattern in (("email", _EMAIL), ("card", _CARD), ("phone", _PHONE)):
        if name in categories:
            output = pattern.sub(f"[REDACTED:{name}]", output)
    return RedactionResult(output, tuple(categories))


def private_view(value: JSONValue) -> tuple[JSONValue, tuple[str, ...]]:
    """Recursively redact strings while preserving structured attachment shape."""
    categories: list[str] = []
    if isinstance(value, str):
        result = redact_private_text(value)
        return result.text, result.categories
    if isinstance(value, list):
        output = []
        for item in value:
            redacted, found = private_view(item)
            output.append(redacted)
            categories.extend(found)
        return output, tuple(dict.fromkeys(categories))
    if isinstance(value, dict):
        mapped: dict[str, JSONValue] = {}
        for name, item in value.items():
            mapped[name], found = private_view(item)
            categories.extend(found)
        return mapped, tuple(dict.fromkeys(categories))
    return value, ()


def adapter_context(manager: ContextManager) -> list[dict[str, JSONValue]]:
    """Build a redacted, budgeted adapter view with explicit context identifiers."""
    manager.evict_to_budget()
    output: list[dict[str, JSONValue]] = []
    for item in manager.attachments:
        content, categories = private_view(item.content)
        output.append(
            {
                "context_id": str(item.context_id),
                "kind": item.kind.value,
                "version": item.version,
                "content": content,
                "redactions": list(categories),
            }
        )
    return output
