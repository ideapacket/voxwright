"""Versioned event envelopes for deterministic voice application sessions."""

from __future__ import annotations

import base64
import binascii
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


@dataclass(frozen=True, slots=True)
class AudioBlock:
    """A transport-neutral PCM16 audio block encoded for JSON artifacts."""

    block_id: Identifier
    pcm16_base64: str
    sample_rate_hz: int
    channels: int
    duration_ms: int

    def __post_init__(self) -> None:
        if not 8_000 <= self.sample_rate_hz <= 192_000:
            raise ValueError("sample rate must be between 8000 and 192000 Hz")
        if self.channels not in (1, 2):
            raise ValueError("audio channels must be 1 or 2")
        if self.duration_ms <= 0:
            raise ValueError("audio duration must be positive")
        try:
            base64.b64decode(self.pcm16_base64, validate=True)
        except (binascii.Error, ValueError) as error:
            raise ValueError("pcm16_base64 is not valid base64") from error

    def to_payload(self) -> dict[str, JSONValue]:
        return {
            "block_id": str(self.block_id),
            "pcm16_base64": self.pcm16_base64,
            "sample_rate_hz": self.sample_rate_hz,
            "channels": self.channels,
            "duration_ms": self.duration_ms,
        }

    @classmethod
    def from_payload(cls, value: object) -> AudioBlock:
        data = _object(value, "$.payload")
        _exact(
            data,
            {"block_id", "pcm16_base64", "sample_rate_hz", "channels", "duration_ms"},
            "$.payload",
        )
        return cls(
            Identifier(_text(data["block_id"], "$.payload.block_id")),
            _text(data["pcm16_base64"], "$.payload.pcm16_base64"),
            _integer(data["sample_rate_hz"], "$.payload.sample_rate_hz"),
            _integer(data["channels"], "$.payload.channels"),
            _integer(data["duration_ms"], "$.payload.duration_ms"),
        )
