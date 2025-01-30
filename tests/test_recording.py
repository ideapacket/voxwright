"""Tests for append-only session recording."""

from __future__ import annotations

from dataclasses import replace

import pytest

import voxwright.recording as recording
from voxwright.events import EventEnvelope, EventKind
from voxwright.identifiers import Identifier


def event(sequence: int = 0, at_ms: int = 0) -> EventEnvelope:
    return EventEnvelope(
        Identifier("session-1"), sequence, at_ms, EventKind.FINAL_TRANSCRIPT, {"text": "hello"}
    )


def test_record_roundtrips_canonical_jsonl() -> None:
    record = recording.SessionRecord.create([], event())
    line = recording.encode_record(record)
    assert line.endswith("\n")
    assert line.count("\n") == 1
    assert recording.decode_record(line) == record


def test_records_chain_from_empty_digest() -> None:
    first = recording.SessionRecord.create([], event())
    second = recording.SessionRecord.create([first], event(1, 20))
    assert first.previous == recording.EMPTY_DIGEST
    assert second.previous == first.digest
    assert second.index == 1


def test_record_decoder_detects_payload_tampering() -> None:
    record = recording.SessionRecord.create([], event())
    changed = replace(record, event=event(at_ms=1))
    with pytest.raises(recording.RecordingError, match="digest mismatch"):
        recording.decode_record(recording.canonical_json(changed.to_dict()))
