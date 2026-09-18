"""Byte-deterministic replay traces over verified session records."""

from __future__ import annotations

from dataclasses import dataclass

from voxwright.core import JSONValue, canonical_bytes, ensure_json_value
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

    @classmethod
    def from_dict(cls, value: object) -> ReplayTrace:
        """Decode a trace while rejecting ambiguous or unknown fields."""
        data = ensure_json_value(value)
        fields = {"schema_version", "session_id", "seed", "events"}
        if not isinstance(data, dict) or set(data) != fields:
            raise ValueError("$: expected exact replay trace fields")
        version = data["schema_version"]
        seed = data["seed"]
        session_id = data["session_id"]
        events = data["events"]
        if isinstance(version, bool) or not isinstance(version, int) or version != 1:
            raise ValueError(f"$.schema_version: unsupported version {version!r}")
        if isinstance(seed, bool) or not isinstance(seed, int):
            raise TypeError("$.seed: expected integer")
        if not isinstance(session_id, str):
            raise TypeError("$.session_id: expected string")
        if not isinstance(events, list):
            raise TypeError("$.events: expected array")
        decoded = tuple(EventEnvelope.from_dict(event) for event in events)
        return cls(Identifier(session_id), seed, decoded)


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
