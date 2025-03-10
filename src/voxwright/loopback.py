"""Bounded HTTP-style loopback adapter transport with no external defaults."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass

from voxwright.adapters import AdapterCapabilities, AdapterTurn
from voxwright.core import JSONValue
from voxwright.events import EventEnvelope
from voxwright.identifiers import Identifier


@dataclass(frozen=True, slots=True)
class LoopbackResponse:
    status: int
    events: tuple[EventEnvelope, ...] = ()
    error: str | None = None


LoopbackTransport = Callable[[dict[str, JSONValue], int], LoopbackResponse]


class LoopbackAdapter:
    """Exercise HTTP retry mechanics through an injected local-only transport."""

    name = Identifier("loopback-http")
    capabilities = AdapterCapabilities(True, True, True, True, True, "local mock HTTP only")

    def __init__(
        self,
        transport: LoopbackTransport,
        *,
        timeout_ms: int = 100,
        max_attempts: int = 3,
        retry_statuses: frozenset[int] = frozenset({408, 429, 500, 502, 503, 504}),
    ) -> None:
        if timeout_ms <= 0 or max_attempts <= 0:
            raise ValueError("timeout and max attempts must be positive")
        self._transport = transport
        self.timeout_ms = timeout_ms
        self.max_attempts = max_attempts
        self.retry_statuses = retry_statuses
        self._observed: tuple[EventEnvelope, ...] = ()
        self.attempts = 0

    def observe(self, events: Sequence[EventEnvelope]) -> None:
        self._observed = tuple(events)
        if not self._observed:
            raise ValueError("loopback observation cannot be empty")

    def act(self) -> AdapterTurn:
        if not self._observed:
            raise RuntimeError("observe must be called before act")
        request: dict[str, JSONValue] = {
            "schema_version": 1,
            "events": [event.to_dict() for event in self._observed],
        }
        for attempt in range(1, self.max_attempts + 1):
            self.attempts = attempt
            response = self._transport(request, self.timeout_ms)
            if 200 <= response.status < 300:
                self._observed = ()
                return AdapterTurn(response.events)
            if response.status not in self.retry_statuses:
                raise RuntimeError(f"loopback request failed with status {response.status}")
        raise TimeoutError(f"loopback request exhausted {self.max_attempts} attempts")
