"""Tests for versioned session events."""

from __future__ import annotations

import pytest

from voxwright.events import EVENT_SCHEMA_VERSION, AudioBlock, EventEnvelope, EventKind
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


def test_audio_block_payload_has_golden_shape() -> None:
    block = AudioBlock(Identifier("audio-1"), "AAA=", 16_000, 1, 20)
    assert block.to_payload() == {
        "block_id": "audio-1",
        "pcm16_base64": "AAA=",
        "sample_rate_hz": 16_000,
        "channels": 1,
        "duration_ms": 20,
    }
    assert AudioBlock.from_payload(block.to_payload()) == block


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"sample_rate_hz": 7999}, "sample rate"),
        ({"channels": 3}, "channels"),
        ({"duration_ms": 0}, "duration"),
        ({"pcm16_base64": "not base64!"}, "base64"),
    ],
)
def test_audio_block_rejects_invalid_transport_metadata(
    kwargs: dict[str, int | str], message: str
) -> None:
    values: dict[str, object] = {
        "block_id": Identifier("audio-1"),
        "pcm16_base64": "AAA=",
        "sample_rate_hz": 16_000,
        "channels": 1,
        "duration_ms": 20,
    }
    values.update(kwargs)
    with pytest.raises(ValueError, match=message):
        AudioBlock(**values)  # type: ignore[arg-type]
