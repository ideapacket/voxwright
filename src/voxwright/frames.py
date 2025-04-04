"""Frame-state slot grounding for nested application tasks."""

from __future__ import annotations

from dataclasses import dataclass, replace
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

    def fill(
        self, value: JSONValue, confidence: float, source_text: str, start: int, end: int
    ) -> GroundedSlot:
        """Fill or revise a non-closed slot from a transcript span."""
        if self.state is SlotState.CLOSED:
            raise ValueError("closed slot cannot be filled")
        if value is None:
            raise ValueError("filled slot value cannot be null")
        return GroundedSlot(self.name, value, confidence, source_text, start, end, SlotState.FILLED)

    def confirm(self) -> GroundedSlot:
        if self.state is not SlotState.FILLED:
            raise ValueError("only filled slot can be confirmed")
        return replace(self, state=SlotState.CONFIRMED)

    def close(self) -> GroundedSlot:
        if self.state is not SlotState.CONFIRMED:
            raise ValueError("only confirmed slot can be closed")
        return replace(self, state=SlotState.CLOSED)


class ConfirmationAction(str, Enum):
    AUTO_CONFIRM = "auto-confirm"
    EXPLICIT_CONFIRM = "explicit-confirm"


@dataclass(frozen=True, slots=True)
class ConfirmationPolicy:
    """Choose explicit confirmation below a validated confidence threshold."""

    auto_threshold: float = 0.85

    def __post_init__(self) -> None:
        if not 0.0 <= self.auto_threshold <= 1.0:
            raise ValueError("auto confirmation threshold must be between 0 and 1")

    def decide(self, slot: GroundedSlot) -> ConfirmationAction:
        if slot.state is not SlotState.FILLED:
            raise ValueError("confirmation policy requires a filled slot")
        if slot.confidence >= self.auto_threshold:
            return ConfirmationAction.AUTO_CONFIRM
        return ConfirmationAction.EXPLICIT_CONFIRM


class FrameState(str, Enum):
    OPEN = "open"
    ACTIVE = "active"
    SUSPENDED = "suspended"
    CLOSED = "closed"


@dataclass(frozen=True, slots=True)
class TaskFrame:
    """A task intent with named slots and explicit lifecycle state."""

    frame_id: Identifier
    intent: Identifier
    slots: dict[Identifier, GroundedSlot]
    state: FrameState = FrameState.OPEN

    def __post_init__(self) -> None:
        copied = dict(self.slots)
        if any(name != slot.name for name, slot in copied.items()):
            raise ValueError("frame slot key does not match slot name")
        object.__setattr__(self, "slots", copied)

    def activate(self) -> TaskFrame:
        if self.state not in {FrameState.OPEN, FrameState.SUSPENDED}:
            raise ValueError("only open or suspended frame can activate")
        return replace(self, state=FrameState.ACTIVE)

    def suspend(self) -> TaskFrame:
        if self.state is not FrameState.ACTIVE:
            raise ValueError("only active frame can suspend")
        return replace(self, state=FrameState.SUSPENDED)

    def fill_slot(
        self,
        name: str | Identifier,
        value: JSONValue,
        confidence: float,
        source_text: str,
        start: int,
        end: int,
    ) -> TaskFrame:
        if self.state is not FrameState.ACTIVE:
            raise ValueError("slot filling requires active frame")
        identifier = name if isinstance(name, Identifier) else Identifier(name)
        if identifier not in self.slots:
            raise ValueError(f"unknown frame slot: {identifier}")
        slots = dict(self.slots)
        slots[identifier] = slots[identifier].fill(value, confidence, source_text, start, end)
        return replace(self, slots=slots)

    def confirm_slot(self, name: str | Identifier) -> TaskFrame:
        identifier = name if isinstance(name, Identifier) else Identifier(name)
        if identifier not in self.slots:
            raise ValueError(f"unknown frame slot: {identifier}")
        slots = dict(self.slots)
        slots[identifier] = slots[identifier].confirm()
        return replace(self, slots=slots)

    @property
    def ready_to_close(self) -> bool:
        return bool(self.slots) and all(
            slot.state in {SlotState.CONFIRMED, SlotState.CLOSED} for slot in self.slots.values()
        )

    def close(self) -> TaskFrame:
        if self.state is not FrameState.ACTIVE:
            raise ValueError("only active frame can close")
        if not self.ready_to_close:
            raise ValueError("frame has unconfirmed slots")
        slots = {
            name: slot if slot.state is SlotState.CLOSED else slot.close()
            for name, slot in self.slots.items()
        }
        return replace(self, slots=slots, state=FrameState.CLOSED)


def inherit_slots(parent: TaskFrame, child: TaskFrame, names: tuple[Identifier, ...]) -> TaskFrame:
    """Copy confirmed related slots into open child slots without aliasing state."""
    slots = dict(child.slots)
    for name in names:
        if name not in parent.slots or name not in slots:
            raise ValueError(f"cannot inherit unknown slot: {name}")
        source = parent.slots[name]
        if source.state not in {SlotState.CONFIRMED, SlotState.CLOSED}:
            raise ValueError(f"cannot inherit unconfirmed slot: {name}")
        if slots[name].state is not SlotState.OPEN:
            raise ValueError(f"inheritance target is not open: {name}")
        slots[name] = replace(source, state=SlotState.CONFIRMED)
    return replace(child, slots=slots)
