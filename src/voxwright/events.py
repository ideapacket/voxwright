"""Versioned event envelopes for deterministic voice application sessions."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from voxwright.core import JSONValue, ensure_json_value
from voxwright.identifiers import Identifier

EVENT_SCHEMA_VERSION = 1


class EventKind(str, Enum):
    """Kinds carried by the public session stream."""

    AUDIO_BLOCK = "audio-block"
    PARTIAL_TRANSCRIPT = "partial-transcript"
    FINAL_TRANSCRIPT = "final-transcript"
    INTENT = "intent"
    TOOL_CALL = "tool-call"
    TOOL_RESULT = "tool-result"
    AGENT_UTTERANCE = "agent-utterance"
    REPAIR_REQUEST = "repair-request"
    ERROR = "error"
    HANDOFF = "handoff"


def _object(value: object, path: str) -> dict[str, JSONValue]:
    checked = ensure_json_value(value, path)
    if not isinstance(checked, dict):
        raise TypeError(f"{path}: expected object")
    return checked


def _exact(value: dict[str, JSONValue], names: set[str], path: str) -> None:
    missing = names - value.keys()
    extra = value.keys() - names
    if missing:
        raise ValueError(f"{path}: missing field {sorted(missing)[0]!r}")
    if extra:
        raise ValueError(f"{path}: unexpected field {sorted(extra)[0]!r}")


def _integer(value: JSONValue, path: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{path}: expected integer")
    return value


def _text(value: JSONValue, path: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{path}: expected string")
    return value


@dataclass(frozen=True, slots=True)
class EventEnvelope:
    """One ordered, logically timed event with a strict JSON payload."""

    session_id: Identifier
    sequence: int
    at_ms: int
    kind: EventKind
    payload: dict[str, JSONValue]
    schema_version: int = EVENT_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.schema_version != EVENT_SCHEMA_VERSION:
            raise ValueError(f"unsupported event schema version: {self.schema_version}")
        if isinstance(self.sequence, bool) or self.sequence < 0:
            raise ValueError("event sequence must be a non-negative integer")
        if isinstance(self.at_ms, bool) or self.at_ms < 0:
            raise ValueError("event time must be a non-negative integer")
        object.__setattr__(self, "payload", _object(self.payload, "$.payload"))

    def to_dict(self) -> dict[str, JSONValue]:
        """Return the canonical public object representation."""
        return {
            "schema_version": self.schema_version,
            "session_id": str(self.session_id),
            "sequence": self.sequence,
            "at_ms": self.at_ms,
            "kind": self.kind.value,
            "payload": self.payload,
        }

    @classmethod
    def from_dict(cls, value: object) -> EventEnvelope:
        """Decode an envelope while rejecting missing and unknown fields."""
        data = _object(value, "$")
        _exact(data, {"schema_version", "session_id", "sequence", "at_ms", "kind", "payload"}, "$")
        version = _integer(data["schema_version"], "$.schema_version")
        sequence = _integer(data["sequence"], "$.sequence")
        at_ms = _integer(data["at_ms"], "$.at_ms")
        session_id = Identifier(_text(data["session_id"], "$.session_id"))
        kind_text = _text(data["kind"], "$.kind")
        try:
            kind = EventKind(kind_text)
        except ValueError as error:
            raise ValueError(f"$.kind: unknown event kind {kind_text!r}") from error
        return cls(
            session_id,
            sequence,
            at_ms,
            kind,
            _object(data["payload"], "$.payload"),
            version,
        )
