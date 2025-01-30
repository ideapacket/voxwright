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


def test_record_json_has_stable_golden_shape() -> None:
    record = recording.SessionRecord.create([], event())
    assert recording.encode_record(record) == (
        '{"digest":"sha256:2b6c947a40a64462b2eaab38a9d3851461d6987d4131b5c78c4f33192fa2ec21",'
        '"event":{"at_ms":0,"kind":"final-transcript","payload":{"text":"hello"},'
        '"schema_version":1,"sequence":0,"session_id":"session-1"},"index":0,'
        '"previous":"sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",'
        '"schema_version":1}\n'
    )


@pytest.mark.parametrize("line", ["", "\n", "{}\n{}", "{}\r\n"])
def test_record_decoder_rejects_non_jsonl_boundaries(line: str) -> None:
    with pytest.raises((recording.RecordingError, ValueError)):
        recording.decode_record(line)


def test_record_decoder_rejects_unknown_fields_before_digest_check() -> None:
    value = recording.SessionRecord.create([], event()).to_dict()
    value["future"] = True
    with pytest.raises(recording.RecordingError, match="unexpected record field 'future'"):
        recording.SessionRecord.from_dict(value)


def test_record_schema_rejects_forward_version() -> None:
    record = recording.SessionRecord.create([], event())
    value = record.to_dict()
    value["schema_version"] = 2
    unsigned = {key: item for key, item in value.items() if key != "digest"}
    value["digest"] = recording.object_digest(unsigned)
    with pytest.raises(recording.RecordingError, match="unsupported record schema version"):
        recording.SessionRecord.from_dict(value)


def test_recorder_appends_one_line_per_event(tmp_path: object) -> None:
    path = tmp_path / "session.jsonl"  # type: ignore[operator]
    recorder = recording.SessionRecorder(path)
    first = recorder.append(event())
    second = recorder.append(event(1, 20))
    assert path.read_text(encoding="utf-8") == (
        recording.encode_record(first) + recording.encode_record(second)
    )
    assert recorder.records == (first, second)


def test_recorder_uses_exclusive_creation(tmp_path: object) -> None:
    path = tmp_path / "session.jsonl"  # type: ignore[operator]
    path.write_text("existing", encoding="utf-8")
    with pytest.raises(FileExistsError):
        recording.SessionRecorder(path)
