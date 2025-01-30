"""Checksummed JSONL records for append-only session artifacts."""

from __future__ import annotations

from dataclasses import dataclass

from voxwright.core import JSONValue, canonical_json, ensure_json_value, parse_json
from voxwright.events import EventEnvelope
from voxwright.hashing import EMPTY_DIGEST, object_digest

RECORD_SCHEMA_VERSION = 1


class RecordingError(ValueError):
    """A session recording cannot be decoded or verified."""


def _record_object(value: object) -> dict[str, JSONValue]:
    checked = ensure_json_value(value, "$")
    if not isinstance(checked, dict):
        raise TypeError("$: expected record object")
    return checked


def _record_integer(value: JSONValue, path: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{path}: expected integer")
    return value


def _record_text(value: JSONValue, path: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{path}: expected string")
    return value


@dataclass(frozen=True, slots=True)
class SessionRecord:
    """One chained event record in a session JSONL stream."""

    index: int
    previous: str
    event: EventEnvelope
    digest: str
    schema_version: int = RECORD_SCHEMA_VERSION

    def unsigned(self) -> dict[str, JSONValue]:
        return {
            "schema_version": self.schema_version,
            "index": self.index,
            "previous": self.previous,
            "event": self.event.to_dict(),
        }

    def to_dict(self) -> dict[str, JSONValue]:
        return {**self.unsigned(), "digest": self.digest}

    @classmethod
    def create(cls, records: list[SessionRecord], event: EventEnvelope) -> SessionRecord:
        previous = records[-1].digest if records else EMPTY_DIGEST
        unsigned: dict[str, JSONValue] = {
            "schema_version": RECORD_SCHEMA_VERSION,
            "index": len(records),
            "previous": previous,
            "event": event.to_dict(),
        }
        return cls(len(records), previous, event, object_digest(unsigned))

    @classmethod
    def from_dict(cls, value: object) -> SessionRecord:
        data = _record_object(value)
        expected = {"schema_version", "index", "previous", "event", "digest"}
        if data.keys() != expected:
            missing = expected - data.keys()
            extra = data.keys() - expected
            if missing:
                raise RecordingError(f"missing record field {sorted(missing)[0]!r}")
            raise RecordingError(f"unexpected record field {sorted(extra)[0]!r}")
        record = cls(
            _record_integer(data["index"], "$.index"),
            _record_text(data["previous"], "$.previous"),
            EventEnvelope.from_dict(data["event"]),
            _record_text(data["digest"], "$.digest"),
            _record_integer(data["schema_version"], "$.schema_version"),
        )
        if record.schema_version != RECORD_SCHEMA_VERSION:
            raise RecordingError(f"unsupported record schema version: {record.schema_version}")
        if object_digest(record.unsigned()) != record.digest:
            raise RecordingError(f"record {record.index}: digest mismatch")
        return record


def encode_record(record: SessionRecord) -> str:
    """Encode exactly one newline-terminated canonical JSON record."""
    return canonical_json(record.to_dict()) + "\n"


def decode_record(line: str) -> SessionRecord:
    """Decode one JSONL line and verify its content digest."""
    text = line[:-1] if line.endswith("\n") else line
    if not text or "\n" in text or "\r" in text:
        raise RecordingError("record must occupy exactly one non-empty line")
    return SessionRecord.from_dict(parse_json(text))
