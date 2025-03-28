"""Frame-state slot grounding for nested application tasks."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from voxwright.core import JSONValue, ensure_json_value
from voxwright.identifiers import Identifier


class SlotState(str, Enum):
    OPEN = "open"
    FILLED = "filled"
    CONFIRMED = "confirmed"
    CLOSED = "closed"


@dataclass(frozen=True, slots=True)
class GroundedSlot:
    """A typed JSON slot linked to an exact transcript span."""

    name: Identifier
    value: JSONValue = None
    confidence: float = 0.0
    source_text: str = ""
    span_start: int = 0
    span_end: int = 0
    state: SlotState = SlotState.OPEN

    def __post_init__(self) -> None:
        object.__setattr__(self, "value", ensure_json_value(self.value, "$.value"))
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("slot confidence must be between 0 and 1")
        object.__setattr__(self, "confidence", round(self.confidence, 6))
        if not 0 <= self.span_start <= self.span_end <= len(self.source_text):
            raise ValueError("slot grounding span is outside source text")
        if self.state is SlotState.OPEN and self.value is not None:
            raise ValueError("open slot cannot carry a value")

    @property
    def grounded_text(self) -> str:
        return self.source_text[self.span_start : self.span_end]
