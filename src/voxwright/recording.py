"""Checksummed JSONL records for append-only session artifacts."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

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


class SessionRecorder:
    """A writer that appends each verified event as one durable JSONL line."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self._records: list[SessionRecord] = []
        with self.path.open("x", encoding="utf-8", newline="\n"):
            pass

    @property
    def records(self) -> tuple[SessionRecord, ...]:
        return tuple(self._records)

    def append(self, event: EventEnvelope) -> SessionRecord:
        record = SessionRecord.create(self._records, event)
        with self.path.open("a", encoding="utf-8", newline="\n") as stream:
            stream.write(encode_record(record))
            stream.flush()
        self._records.append(record)
        return record


def load_session(path: str | Path) -> list[SessionRecord]:
    """Load a complete recording and validate line, digest, and chain order."""
    content = Path(path).read_text(encoding="utf-8")
    if not content:
        return []
    if not content.endswith("\n"):
        raise RecordingError("recording ends with an incomplete line")
    records: list[SessionRecord] = []
    previous = EMPTY_DIGEST
    for line_number, line in enumerate(content.splitlines(keepends=True), start=1):
        try:
            record = decode_record(line)
        except (TypeError, ValueError) as error:
            raise RecordingError(f"line {line_number}: {error}") from error
        if record.index != len(records):
            raise RecordingError(f"line {line_number}: expected record index {len(records)}")
        if record.previous != previous:
            raise RecordingError(f"line {line_number}: previous digest mismatch")
        records.append(record)
        previous = record.digest
    return records
