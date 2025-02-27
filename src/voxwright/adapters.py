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


def conformance_issues(adapter: SpokenAdapter) -> list[str]:
    """Exercise adapter ordering and repeatability rules without model assumptions."""
    issues: list[str] = []
    if not str(adapter.name):
        issues.append("adapter name is empty")
    if not adapter.capabilities.description.strip():
        issues.append("capability description is empty")
    try:
        empty = adapter.act()
    except RuntimeError:
        empty = None
    if empty is not None and empty.events:
        issues.append("adapter emitted events before observation")
    return issues
