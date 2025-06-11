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
