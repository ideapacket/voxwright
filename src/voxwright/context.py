"""Versioned multimodal application context with deterministic budgeting."""

from __future__ import annotations

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
