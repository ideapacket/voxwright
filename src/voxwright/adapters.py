"""Protocols and offline adapters for spoken-model application mechanics."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from voxwright.events import EventEnvelope
from voxwright.identifiers import Identifier


@dataclass(frozen=True, slots=True)
class AdapterCapabilities:
    """Honest, machine-readable mechanics supported by an adapter."""

    streaming_input: bool
    streaming_output: bool
    structured_tool_calls: bool
    context_attachments: bool
    offline: bool
    description: str

    def __post_init__(self) -> None:
        if not self.description.strip():
            raise ValueError("adapter capability description cannot be empty")


@dataclass(frozen=True, slots=True)
class AdapterTurn:
    """Events emitted after observing one ordered input batch."""

    events: tuple[EventEnvelope, ...]
    finished: bool = True


class SpokenAdapter(Protocol):
    """Pluggable observe-then-act contract for application integration."""

    name: Identifier
    capabilities: AdapterCapabilities

    def observe(self, events: Sequence[EventEnvelope]) -> None: ...

    def act(self) -> AdapterTurn: ...
