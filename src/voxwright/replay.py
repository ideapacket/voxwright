"""Byte-deterministic replay traces over verified session records."""

from __future__ import annotations

from dataclasses import dataclass

from voxwright.core import JSONValue, canonical_bytes
from voxwright.events import EventEnvelope
from voxwright.identifiers import Identifier
from voxwright.recording import RecordingError, SessionRecord


@dataclass(frozen=True, slots=True)
class ReplayTrace:
    """A replayable ordered trace identified by session and explicit seed."""

    session_id: Identifier
    seed: int
    events: tuple[EventEnvelope, ...]

    def __post_init__(self) -> None:
        if isinstance(self.seed, bool) or self.seed < 0:
            raise ValueError("replay seed must be a non-negative integer")
        for index, event in enumerate(self.events):
            if event.session_id != self.session_id:
                raise RecordingError(f"event {index}: session identifier mismatch")
            if event.sequence != index:
                raise RecordingError(f"event {index}: non-contiguous event sequence")
            if index and event.at_ms < self.events[index - 1].at_ms:
                raise RecordingError(f"event {index}: logical time moved backwards")

    def to_dict(self) -> dict[str, JSONValue]:
        return {
            "schema_version": 1,
            "session_id": str(self.session_id),
            "seed": self.seed,
            "events": [event.to_dict() for event in self.events],
        }

    def to_bytes(self) -> bytes:
        return canonical_bytes(self.to_dict())


def replay(records: list[SessionRecord], seed: int) -> ReplayTrace:
    """Create an immutable trace from an already verified record list."""
    if not records:
        raise RecordingError("cannot infer session identifier from empty recording")
    return ReplayTrace(
        records[0].event.session_id,
        seed,
        tuple(record.event for record in records),
    )


@dataclass(slots=True)
class EventReplayer:
    """A resettable cursor that never mutates its immutable source trace."""

    trace: ReplayTrace
    position: int = 0

    def __post_init__(self) -> None:
        if not 0 <= self.position <= len(self.trace.events):
            raise ValueError("replay position is outside trace")

    def peek(self) -> EventEnvelope | None:
        if self.position == len(self.trace.events):
            return None
        return self.trace.events[self.position]

    def take(self) -> EventEnvelope | None:
        event = self.peek()
        if event is not None:
            self.position += 1
        return event

    def reset(self) -> None:
        self.position = 0
