"""Tests for deterministic session replay and comparison."""

from __future__ import annotations

from dataclasses import replace

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
