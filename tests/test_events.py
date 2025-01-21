"""Tests for versioned session events."""

from __future__ import annotations

import pytest

from voxwright.events import EVENT_SCHEMA_VERSION, EventEnvelope, EventKind
from voxwright.identifiers import Identifier


def test_event_envelope_roundtrips_public_shape() -> None:
    event = EventEnvelope(Identifier("session-1"), 2, 40, EventKind.INTENT, {"name": "music.play"})
    assert EventEnvelope.from_dict(event.to_dict()) == event
    assert event.to_dict()["schema_version"] == EVENT_SCHEMA_VERSION


def test_event_kind_registry_is_complete() -> None:
    assert {kind.value for kind in EventKind} == {
        "audio-block",
        "partial-transcript",
        "final-transcript",
        "intent",
        "tool-call",
        "tool-result",
        "agent-utterance",
        "repair-request",
        "error",
        "handoff",
    }


@pytest.mark.parametrize("field", ["sequence", "at_ms"])
def test_event_rejects_negative_ordering_fields(field: str) -> None:
    values = {"sequence": 0, "at_ms": 0}
    values[field] = -1
    with pytest.raises(ValueError, match="non-negative"):
        EventEnvelope(
            Identifier("session-1"),
            values["sequence"],
            values["at_ms"],
            EventKind.ERROR,
            {},
        )
