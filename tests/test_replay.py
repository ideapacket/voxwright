"""Tests for deterministic session replay and comparison."""

from __future__ import annotations

import pytest

import voxwright.replay as replaying
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
