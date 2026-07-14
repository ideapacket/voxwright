"""Versioned event envelopes for deterministic voice application sessions."""

from __future__ import annotations

import base64
import binascii
from dataclasses import dataclass
from enum import Enum
from typing import Protocol, TypeAlias, cast

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
    CONTEXT_UPDATE = "context-update"


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


def _confidence(value: JSONValue, path: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{path}: expected number")
    number = float(value)
    if not 0.0 <= number <= 1.0:
        raise ValueError(f"{path}: confidence must be between 0 and 1")
    return round(number, 6)


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


@dataclass(frozen=True, slots=True)
class Transcript:
    """A partial or final transcript hypothesis with optional alternatives."""

    text: str
    confidence: float
    alternatives: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "confidence", _confidence(self.confidence, "$.confidence"))
        if any(not item for item in self.alternatives):
            raise ValueError("transcript alternatives cannot be empty")
        if len(set(self.alternatives)) != len(self.alternatives):
            raise ValueError("transcript alternatives must be unique")

    def to_payload(self) -> dict[str, JSONValue]:
        return {
            "text": self.text,
            "confidence": self.confidence,
            "alternatives": list(self.alternatives),
        }

    @classmethod
    def from_payload(cls, value: object) -> Transcript:
        data = _object(value, "$.payload")
        _exact(data, {"text", "confidence", "alternatives"}, "$.payload")
        alternatives = data["alternatives"]
        if not isinstance(alternatives, list):
            raise TypeError("$.payload.alternatives: expected array")
        return cls(
            _text(data["text"], "$.payload.text"),
            _confidence(data["confidence"], "$.payload.confidence"),
            tuple(
                _text(item, f"$.payload.alternatives[{index}]")
                for index, item in enumerate(alternatives)
            ),
        )


@dataclass(frozen=True, slots=True)
class Intent:
    """An application intent and grounded JSON slot candidates."""

    name: Identifier
    confidence: float
    slots: dict[str, JSONValue]

    def __post_init__(self) -> None:
        object.__setattr__(self, "confidence", _confidence(self.confidence, "$.confidence"))
        object.__setattr__(self, "slots", _object(self.slots, "$.slots"))
        for name in self.slots:
            Identifier(name)

    def to_payload(self) -> dict[str, JSONValue]:
        return {"name": str(self.name), "confidence": self.confidence, "slots": self.slots}

    @classmethod
    def from_payload(cls, value: object) -> Intent:
        data = _object(value, "$.payload")
        _exact(data, {"name", "confidence", "slots"}, "$.payload")
        return cls(
            Identifier(_text(data["name"], "$.payload.name")),
            _confidence(data["confidence"], "$.payload.confidence"),
            _object(data["slots"], "$.payload.slots"),
        )


@dataclass(frozen=True, slots=True)
class ToolCallEvent:
    """A validated call proposal emitted on the dedicated tool channel."""

    call_id: Identifier
    tool_name: Identifier
    arguments: dict[str, JSONValue]

    def __post_init__(self) -> None:
        object.__setattr__(self, "arguments", _object(self.arguments, "$.arguments"))

    def to_payload(self) -> dict[str, JSONValue]:
        return {
            "call_id": str(self.call_id),
            "tool_name": str(self.tool_name),
            "arguments": self.arguments,
        }

    @classmethod
    def from_payload(cls, value: object) -> ToolCallEvent:
        data = _object(value, "$.payload")
        _exact(data, {"call_id", "tool_name", "arguments"}, "$.payload")
        return cls(
            Identifier(_text(data["call_id"], "$.payload.call_id")),
            Identifier(_text(data["tool_name"], "$.payload.tool_name")),
            _object(data["arguments"], "$.payload.arguments"),
        )


@dataclass(frozen=True, slots=True)
class ToolResultEvent:
    """The success or failure returned for a particular tool call."""

    call_id: Identifier
    ok: bool
    result: JSONValue

    def __post_init__(self) -> None:
        object.__setattr__(self, "result", ensure_json_value(self.result, "$.result"))

    def to_payload(self) -> dict[str, JSONValue]:
        return {"call_id": str(self.call_id), "ok": self.ok, "result": self.result}

    @classmethod
    def from_payload(cls, value: object) -> ToolResultEvent:
        data = _object(value, "$.payload")
        _exact(data, {"call_id", "ok", "result"}, "$.payload")
        ok = data["ok"]
        if not isinstance(ok, bool):
            raise TypeError("$.payload.ok: expected boolean")
        return cls(
            Identifier(_text(data["call_id"], "$.payload.call_id")),
            ok,
            data["result"],
        )


@dataclass(frozen=True, slots=True)
class AgentUtterance:
    """Text selected for application playback and its response revision."""

    text: str
    response_id: Identifier
    revision: int = 0
    final: bool = True

    def __post_init__(self) -> None:
        if not self.text:
            raise ValueError("agent utterance text cannot be empty")
        if isinstance(self.revision, bool) or self.revision < 0:
            raise ValueError("utterance revision must be non-negative")

    def to_payload(self) -> dict[str, JSONValue]:
        return {
            "text": self.text,
            "response_id": str(self.response_id),
            "revision": self.revision,
            "final": self.final,
        }

    @classmethod
    def from_payload(cls, value: object) -> AgentUtterance:
        data = _object(value, "$.payload")
        _exact(data, {"text", "response_id", "revision", "final"}, "$.payload")
        final = data["final"]
        if not isinstance(final, bool):
            raise TypeError("$.payload.final: expected boolean")
        return cls(
            _text(data["text"], "$.payload.text"),
            Identifier(_text(data["response_id"], "$.payload.response_id")),
            _integer(data["revision"], "$.payload.revision"),
            final,
        )


@dataclass(frozen=True, slots=True)
class RepairRequest:
    """A bounded request for evidence needed to repair a misunderstanding."""

    strategy: Identifier
    prompt: str
    attempt: int
    candidates: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.prompt:
            raise ValueError("repair prompt cannot be empty")
        if self.attempt <= 0:
            raise ValueError("repair attempt must be positive")
        if any(not candidate for candidate in self.candidates):
            raise ValueError("repair candidates cannot be empty")

    def to_payload(self) -> dict[str, JSONValue]:
        return {
            "strategy": str(self.strategy),
            "prompt": self.prompt,
            "attempt": self.attempt,
            "candidates": list(self.candidates),
        }

    @classmethod
    def from_payload(cls, value: object) -> RepairRequest:
        data = _object(value, "$.payload")
        _exact(data, {"strategy", "prompt", "attempt", "candidates"}, "$.payload")
        candidates = data["candidates"]
        if not isinstance(candidates, list):
            raise TypeError("$.payload.candidates: expected array")
        return cls(
            Identifier(_text(data["strategy"], "$.payload.strategy")),
            _text(data["prompt"], "$.payload.prompt"),
            _integer(data["attempt"], "$.payload.attempt"),
            tuple(
                _text(item, f"$.payload.candidates[{index}]")
                for index, item in enumerate(candidates)
            ),
        )


@dataclass(frozen=True, slots=True)
class ErrorEvent:
    """A machine-readable application failure safe for session artifacts."""

    code: Identifier
    message: str
    retryable: bool = False
    details: dict[str, JSONValue] | None = None

    def __post_init__(self) -> None:
        if not self.message:
            raise ValueError("error message cannot be empty")
        if self.details is not None:
            object.__setattr__(self, "details", _object(self.details, "$.details"))

    def to_payload(self) -> dict[str, JSONValue]:
        return {
            "code": str(self.code),
            "message": self.message,
            "retryable": self.retryable,
            "details": self.details,
        }

    @classmethod
    def from_payload(cls, value: object) -> ErrorEvent:
        data = _object(value, "$.payload")
        _exact(data, {"code", "message", "retryable", "details"}, "$.payload")
        retryable = data["retryable"]
        if not isinstance(retryable, bool):
            raise TypeError("$.payload.retryable: expected boolean")
        details = data["details"]
        return cls(
            Identifier(_text(data["code"], "$.payload.code")),
            _text(data["message"], "$.payload.message"),
            retryable,
            None if details is None else _object(details, "$.payload.details"),
        )


@dataclass(frozen=True, slots=True)
class HandoffEvent:
    """An explicit transfer from the offline application policy to a person."""

    reason: Identifier
    summary: str
    queue: str | None = None

    def __post_init__(self) -> None:
        if not self.summary:
            raise ValueError("handoff summary cannot be empty")
        if self.queue == "":
            raise ValueError("handoff queue cannot be empty")

    def to_payload(self) -> dict[str, JSONValue]:
        return {"reason": str(self.reason), "summary": self.summary, "queue": self.queue}

    @classmethod
    def from_payload(cls, value: object) -> HandoffEvent:
        data = _object(value, "$.payload")
        _exact(data, {"reason", "summary", "queue"}, "$.payload")
        queue = data["queue"]
        if queue is not None and not isinstance(queue, str):
            raise TypeError("$.payload.queue: expected string or null")
        return cls(
            Identifier(_text(data["reason"], "$.payload.reason")),
            _text(data["summary"], "$.payload.summary"),
            queue,
        )


@dataclass(frozen=True, slots=True)
class ContextUpdate:
    """A session-visible reference to an exact versioned context snapshot."""

    snapshot_digest: str
    versions: dict[str, int]
    token_cost: int
    evicted: tuple[Identifier, ...] = ()

    def __post_init__(self) -> None:
        if not self.snapshot_digest.startswith("sha256:") or len(self.snapshot_digest) != 71:
            raise ValueError("context snapshot digest must be algorithm-qualified SHA-256")
        if isinstance(self.token_cost, bool) or self.token_cost < 0:
            raise ValueError("context token cost must be a non-negative integer")
        checked: dict[str, int] = {}
        for name, version in self.versions.items():
            Identifier(name)
            if isinstance(version, bool) or not isinstance(version, int) or version < 1:
                raise ValueError("context versions must be positive integers")
            checked[name] = version
        object.__setattr__(self, "versions", checked)
        if len(set(self.evicted)) != len(self.evicted):
            raise ValueError("evicted context identifiers must be unique")

    def to_payload(self) -> dict[str, JSONValue]:
        encoded_versions: dict[str, JSONValue] = dict(self.versions)
        return {
            "snapshot_digest": self.snapshot_digest,
            "versions": encoded_versions,
            "token_cost": self.token_cost,
            "evicted": [str(item) for item in self.evicted],
        }

    @classmethod
    def from_payload(cls, value: object) -> ContextUpdate:
        data = _object(value, "$.payload")
        _exact(data, {"snapshot_digest", "versions", "token_cost", "evicted"}, "$.payload")
        versions = _object(data["versions"], "$.payload.versions")
        decoded_versions: dict[str, int] = {}
        for name, version in versions.items():
            decoded_versions[name] = _integer(version, f"$.payload.versions.{name}")
        evicted = data["evicted"]
        if not isinstance(evicted, list):
            raise TypeError("$.payload.evicted: expected array")
        return cls(
            _text(data["snapshot_digest"], "$.payload.snapshot_digest"),
            decoded_versions,
            _integer(data["token_cost"], "$.payload.token_cost"),
            tuple(
                Identifier(_text(item, f"$.payload.evicted[{index}]"))
                for index, item in enumerate(evicted)
            ),
        )


class PayloadCodec(Protocol):
    """Structural contract shared by typed event payload classes."""

    def to_payload(self) -> dict[str, JSONValue]: ...


EventPayload: TypeAlias = (
    AudioBlock
    | Transcript
    | Intent
    | ToolCallEvent
    | ToolResultEvent
    | AgentUtterance
    | RepairRequest
    | ErrorEvent
    | HandoffEvent
    | ContextUpdate
)

PAYLOAD_TYPES: dict[EventKind, type[EventPayload]] = {
    EventKind.AUDIO_BLOCK: AudioBlock,
    EventKind.PARTIAL_TRANSCRIPT: Transcript,
    EventKind.FINAL_TRANSCRIPT: Transcript,
    EventKind.INTENT: Intent,
    EventKind.TOOL_CALL: ToolCallEvent,
    EventKind.TOOL_RESULT: ToolResultEvent,
    EventKind.AGENT_UTTERANCE: AgentUtterance,
    EventKind.REPAIR_REQUEST: RepairRequest,
    EventKind.ERROR: ErrorEvent,
    EventKind.HANDOFF: HandoffEvent,
    EventKind.CONTEXT_UPDATE: ContextUpdate,
}


def decode_payload(event: EventEnvelope) -> EventPayload:
    """Decode the envelope payload according to its registered kind."""
    payload_type = PAYLOAD_TYPES[event.kind]
    decoder = cast(object, payload_type.from_payload)
    return cast(EventPayload, decoder(event.payload))  # type: ignore[operator]


def envelope_for(
    session_id: Identifier,
    sequence: int,
    at_ms: int,
    kind: EventKind,
    payload: EventPayload,
) -> EventEnvelope:
    """Wrap a typed payload, rejecting mismatched event kinds."""
    expected = PAYLOAD_TYPES[kind]
    if not isinstance(payload, expected):
        raise TypeError(f"{kind.value} requires {expected.__name__}, got {type(payload).__name__}")
    return EventEnvelope(session_id, sequence, at_ms, kind, payload.to_payload())
