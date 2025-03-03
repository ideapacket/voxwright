"""Protocols and offline adapters for spoken-model application mechanics."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from voxwright.events import EventEnvelope
from voxwright.identifiers import Identifier
from voxwright.replay import EventReplayer, ReplayTrace


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


class ScriptedAdapter:
    """Deterministically return pre-authored event batches for scenario fixtures."""

    name = Identifier("scripted")
    capabilities = AdapterCapabilities(True, True, True, False, True, "scripted offline events")

    def __init__(self, turns: Sequence[AdapterTurn]) -> None:
        self._turns = tuple(turns)
        self._observations: list[tuple[EventEnvelope, ...]] = []
        self._position = 0
        self._ready = False

    @property
    def observations(self) -> tuple[tuple[EventEnvelope, ...], ...]:
        return tuple(self._observations)

    def observe(self, events: Sequence[EventEnvelope]) -> None:
        if self._ready:
            raise RuntimeError("act must consume the previous observation")
        batch = tuple(events)
        if not batch:
            raise ValueError("scripted adapter observation cannot be empty")
        self._observations.append(batch)
        self._ready = True

    def act(self) -> AdapterTurn:
        if not self._ready:
            raise RuntimeError("observe must be called before act")
        if self._position >= len(self._turns):
            raise RuntimeError("scripted adapter has no remaining turn")
        turn = self._turns[self._position]
        self._position += 1
        self._ready = False
        return turn


class RecordedReplayAdapter:
    """Emit recorded agent-side events from an immutable replay trace."""

    name = Identifier("recorded-replay")
    capabilities = AdapterCapabilities(True, True, True, True, True, "verified session replay")

    def __init__(self, trace: ReplayTrace) -> None:
        self._cursor = EventReplayer(trace)
        self._ready = False

    def observe(self, events: Sequence[EventEnvelope]) -> None:
        if not events:
            raise ValueError("replay observation cannot be empty")
        self._ready = True

    def act(self) -> AdapterTurn:
        if not self._ready:
            raise RuntimeError("observe must be called before act")
        emitted = self._cursor.take()
        self._ready = False
        return AdapterTurn(() if emitted is None else (emitted,), emitted is None)
