"""Tests for deterministic session replay and comparison."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

import voxwright.replay as replaying
import voxwright.session_diff as session_diff
from voxwright.events import EventEnvelope, EventKind
from voxwright.identifiers import Identifier
from voxwright.recording import RecordingError, SessionRecord


def replay_event(sequence: int, at_ms: int = 0, text: str = "hello") -> EventEnvelope:
    return EventEnvelope(
        Identifier("session-1"),
        sequence,
        at_ms,
        EventKind.FINAL_TRANSCRIPT,
        {"text": text},
    )


def replay_records() -> list[SessionRecord]:
    first = SessionRecord.create([], replay_event(0))
    return [first, SessionRecord.create([first], replay_event(1, 20, "world"))]


def test_same_session_and_seed_produce_identical_trace_bytes() -> None:
    left = replaying.replay(replay_records(), seed=17)
    right = replaying.replay(replay_records(), seed=17)
    assert left == right
    assert left.to_bytes() == right.to_bytes()


def test_replay_seed_is_part_of_deterministic_artifact() -> None:
    assert (
        replaying.replay(replay_records(), 1).to_bytes()
        != replaying.replay(replay_records(), 2).to_bytes()
    )


def test_replay_trace_decodes_its_public_object_without_byte_drift() -> None:
    trace = replaying.replay(replay_records(), 17)
    restored = replaying.ReplayTrace.from_dict(trace.to_dict())
    assert restored == trace
    assert restored.to_bytes() == trace.to_bytes()


def test_empty_replay_trace_can_roundtrip_with_an_explicit_session() -> None:
    trace = replaying.ReplayTrace(Identifier("empty-session"), 0, ())
    assert replaying.ReplayTrace.from_dict(trace.to_dict()) == trace


def test_replay_trace_decoder_rejects_shape_version_and_scalar_types() -> None:
    value = replaying.replay(replay_records(), 1).to_dict()
    value["extra"] = None
    with pytest.raises(ValueError, match="exact replay trace fields"):
        replaying.ReplayTrace.from_dict(value)
    value = replaying.replay(replay_records(), 1).to_dict()
    value["schema_version"] = True
    with pytest.raises(ValueError, match="unsupported version True"):
        replaying.ReplayTrace.from_dict(value)
    value = replaying.replay(replay_records(), 1).to_dict()
    value["seed"] = False
    with pytest.raises(TypeError, match="seed: expected integer"):
        replaying.ReplayTrace.from_dict(value)
    value = replaying.replay(replay_records(), 1).to_dict()
    value["events"] = {}
    with pytest.raises(TypeError, match="events: expected array"):
        replaying.ReplayTrace.from_dict(value)


def test_replay_trace_decoder_reapplies_event_and_sequence_invariants() -> None:
    value = replaying.replay(replay_records(), 1).to_dict()
    value["events"][0]["kind"] = "invented"  # type: ignore[index]
    with pytest.raises(ValueError, match="unknown event kind"):
        replaying.ReplayTrace.from_dict(value)
    value = replaying.replay(replay_records(), 1).to_dict()
    value["events"][1]["sequence"] = 3  # type: ignore[index]
    with pytest.raises(RecordingError, match="non-contiguous event sequence"):
        replaying.ReplayTrace.from_dict(value)
    value = replaying.replay(replay_records(), 1).to_dict()
    value["events"][1]["session_id"] = "another-session"  # type: ignore[index]
    with pytest.raises(RecordingError, match="session identifier mismatch"):
        replaying.ReplayTrace.from_dict(value)


def test_replay_trace_file_roundtrip_preserves_bytes_and_digest(tmp_path: Path) -> None:
    trace = replaying.replay(replay_records(), 23)
    path = tmp_path / "trace.json"
    replaying.write_trace(path, trace)
    assert path.read_text(encoding="utf-8") == replaying.encode_trace(trace)
    restored = replaying.load_trace(path)
    assert restored == trace
    assert replaying.trace_digest(restored) == replaying.trace_digest(trace)


def test_replay_trace_files_reject_clobbering_truncation_and_empty_input(tmp_path: Path) -> None:
    path = tmp_path / "trace.json"
    trace = replaying.replay(replay_records(), 0)
    replaying.write_trace(path, trace)
    with pytest.raises(FileExistsError, match="output already exists"):
        replaying.write_trace(path, trace)
    path.write_text(replaying.encode_trace(trace).rstrip("\n"), encoding="utf-8")
    with pytest.raises(ValueError, match="missing terminal newline"):
        replaying.load_trace(path)
    with pytest.raises(ValueError, match="document is empty"):
        replaying.decode_trace("\n")


def test_replay_requires_records_to_infer_session() -> None:
    with pytest.raises(RecordingError, match="empty recording"):
        replaying.replay([], 0)


def test_replayer_cursor_peeks_takes_and_resets() -> None:
    cursor = replaying.EventReplayer(replaying.replay(replay_records(), 3))
    assert cursor.peek() == replay_event(0)
    assert cursor.take() == replay_event(0)
    assert cursor.take() == replay_event(1, 20, "world")
    assert cursor.take() is None
    cursor.reset()
    assert cursor.position == 0


def test_replayer_rejects_position_outside_trace() -> None:
    trace = replaying.replay(replay_records(), 3)
    with pytest.raises(ValueError, match="outside trace"):
        replaying.EventReplayer(trace, len(trace.events) + 1)


def test_trace_rejects_cross_session_or_sequence_drift() -> None:
    good = replay_event(0)
    other = replace(replay_event(1), session_id=Identifier("session-2"))
    with pytest.raises(RecordingError, match="session identifier"):
        replaying.ReplayTrace(Identifier("session-1"), 0, (good, other))
    with pytest.raises(RecordingError, match="non-contiguous"):
        replaying.ReplayTrace(Identifier("session-1"), 0, (replace(good, sequence=1),))


def test_session_diff_reports_first_changed_field_per_event() -> None:
    left = replaying.replay(replay_records(), 1)
    changed_events = list(left.events)
    changed_events[1] = replace(changed_events[1], payload={"text": "changed"})
    right = replaying.ReplayTrace(left.session_id, left.seed, tuple(changed_events))
    assert session_diff.diff_traces(left, right) == [
        session_diff.EventDifference(1, "payload", {"text": "world"}, {"text": "changed"})
    ]


def test_session_diff_reports_missing_tail_event() -> None:
    left = replaying.replay(replay_records(), 1)
    right = replaying.ReplayTrace(left.session_id, left.seed, left.events[:1])
    difference = session_diff.diff_traces(left, right)[0]
    assert difference.index == 1
    assert difference.field == "event"
    assert difference.right is None


def test_formatted_diff_is_stable_and_newline_terminated() -> None:
    differences = [
        session_diff.EventDifference(2, "kind", "intent", "error"),
        session_diff.EventDifference(3, "event", None, {"sequence": 3}),
    ]
    assert session_diff.format_differences(differences) == (
        'event 2 kind: "intent" -> "error"\nevent 3 event: null -> {"sequence":3}\n'
    )


def test_empty_diff_has_explicit_identity_message() -> None:
    assert session_diff.format_differences([]) == "sessions are identical\n"


def test_identical_traces_have_no_differences_even_with_distinct_seeds() -> None:
    left = replaying.replay(replay_records(), 1)
    right = replaying.replay(replay_records(), 999)
    assert session_diff.diff_traces(left, right) == []


def test_diff_order_is_event_order_for_multiple_changes() -> None:
    left = replaying.replay(replay_records(), 1)
    changed = (
        replace(left.events[0], at_ms=1),
        replace(left.events[1], kind=EventKind.ERROR, payload={"message": "failed"}),
    )
    right = replaying.ReplayTrace(left.session_id, left.seed, changed)
    differences = session_diff.diff_traces(left, right)
    assert [(item.index, item.field) for item in differences] == [(0, "at_ms"), (1, "kind")]


def test_diff_payload_values_remain_machine_readable() -> None:
    left = replaying.replay(replay_records(), 1)
    right_event = replace(left.events[0], payload={"confidence": 0.5, "alternatives": ["a"]})
    right = replaying.ReplayTrace(left.session_id, left.seed, (right_event, left.events[1]))
    difference = session_diff.diff_traces(left, right)[0]
    assert difference.left == {"text": "hello"}
    assert difference.right == {"confidence": 0.5, "alternatives": ["a"]}
