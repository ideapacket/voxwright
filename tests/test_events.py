"""Tests for versioned session events."""

from __future__ import annotations

import pytest

from voxwright.events import (
    EVENT_SCHEMA_VERSION,
    AgentUtterance,
    AudioBlock,
    EventEnvelope,
    EventKind,
    Intent,
    RepairRequest,
    ToolCallEvent,
    ToolResultEvent,
    Transcript,
)
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


def _valid_event_object() -> dict[str, object]:
    return {
        "schema_version": 1,
        "session_id": "session-1",
        "sequence": 0,
        "at_ms": 0,
        "kind": "handoff",
        "payload": {},
    }


@pytest.mark.parametrize("field", sorted(_valid_event_object()))
def test_event_decoder_names_missing_fields(field: str) -> None:
    data = _valid_event_object()
    del data[field]
    with pytest.raises(ValueError, match=f"missing field '{field}'"):
        EventEnvelope.from_dict(data)


def test_event_decoder_rejects_unknown_fields() -> None:
    data = _valid_event_object()
    data["future"] = True
    with pytest.raises(ValueError, match="unexpected field 'future'"):
        EventEnvelope.from_dict(data)


@pytest.mark.parametrize("field", ["schema_version", "sequence", "at_ms"])
def test_event_integer_fields_do_not_accept_booleans(field: str) -> None:
    data = _valid_event_object()
    data[field] = True
    with pytest.raises(TypeError, match=f"{field}: expected integer"):
        EventEnvelope.from_dict(data)


def test_event_decoder_reports_unknown_kind_at_path() -> None:
    data = _valid_event_object()
    data["kind"] = "voice-thought"
    with pytest.raises(ValueError, match=r"\$\.kind: unknown event kind"):
        EventEnvelope.from_dict(data)


def test_transcript_roundtrips_alternatives() -> None:
    transcript = Transcript("播放周杰伦", 0.81234567, ("播放周杰轮", "播放音乐"))
    assert transcript.confidence == 0.812346
    assert Transcript.from_payload(transcript.to_payload()) == transcript


@pytest.mark.parametrize("confidence", [-0.01, 1.01, True])
def test_transcript_rejects_invalid_confidence(confidence: object) -> None:
    with pytest.raises((TypeError, ValueError), match=r"confidence|number"):
        Transcript("hello", confidence)  # type: ignore[arg-type]


def test_transcript_requires_distinct_nonempty_alternatives() -> None:
    with pytest.raises(ValueError, match="unique"):
        Transcript("light", 0.5, ("night", "night"))
    with pytest.raises(ValueError, match="empty"):
        Transcript("light", 0.5, ("",))


def test_intent_preserves_typed_slot_values() -> None:
    intent = Intent(
        Identifier("calendar.create"),
        0.9,
        {"title": "复习", "hour": 19, "notify": True},
    )
    assert Intent.from_payload(intent.to_payload()) == intent
    assert intent.to_payload()["name"] == "calendar.create"


def test_intent_rejects_slot_names_unsafe_for_artifacts() -> None:
    with pytest.raises(ValueError, match="invalid identifier"):
        Intent(Identifier("notes.add"), 1.0, {"bad slot": "value"})


def test_tool_call_keeps_arguments_on_structured_channel() -> None:
    call = ToolCallEvent(
        Identifier("call-7"), Identifier("home.set-light"), {"room": "study", "on": True}
    )
    assert ToolCallEvent.from_payload(call.to_payload()) == call
    assert call.to_payload()["tool_name"] == "home.set-light"


def test_tool_result_supports_scalar_and_object_results() -> None:
    success = ToolResultEvent(Identifier("call-7"), True, {"changed": 1})
    failure = ToolResultEvent(Identifier("call-8"), False, "permission denied")
    assert ToolResultEvent.from_payload(success.to_payload()) == success
    assert ToolResultEvent.from_payload(failure.to_payload()) == failure


def test_tool_result_requires_boolean_status() -> None:
    with pytest.raises(TypeError, match="expected boolean"):
        ToolResultEvent.from_payload({"call_id": "call-1", "ok": 1, "result": None})


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        ({"call_id": "call-1", "tool_name": "timer.start"}, "missing field 'arguments'"),
        (
            {"call_id": "call-1", "tool_name": "timer.start", "arguments": {}, "text": "x"},
            "unexpected field 'text'",
        ),
        ({"call_id": 7, "tool_name": "timer.start", "arguments": {}}, "expected string"),
        ({"call_id": "call-1", "tool_name": "timer.start", "arguments": []}, "expected object"),
    ],
)
def test_tool_call_payload_reports_structural_errors(
    payload: dict[str, object], message: str
) -> None:
    with pytest.raises((TypeError, ValueError), match=message):
        ToolCallEvent.from_payload(payload)


def test_tool_event_payloads_have_stable_golden_objects() -> None:
    call = ToolCallEvent(Identifier("call-3"), Identifier("notes.add"), {"text": "买牛奶"})
    result = ToolResultEvent(Identifier("call-3"), True, {"note_id": "note-1"})
    assert call.to_payload() == {
        "call_id": "call-3",
        "tool_name": "notes.add",
        "arguments": {"text": "买牛奶"},
    }
    assert result.to_payload() == {
        "call_id": "call-3",
        "ok": True,
        "result": {"note_id": "note-1"},
    }


def test_agent_utterance_tracks_streaming_revisions() -> None:
    partial = AgentUtterance("正在查询", Identifier("response-1"), revision=2, final=False)
    assert AgentUtterance.from_payload(partial.to_payload()) == partial
    assert partial.to_payload()["final"] is False


def test_agent_utterance_rejects_empty_or_negative_revision() -> None:
    with pytest.raises(ValueError, match="cannot be empty"):
        AgentUtterance("", Identifier("response-1"))
    with pytest.raises(ValueError, match="non-negative"):
        AgentUtterance("完成", Identifier("response-1"), revision=-1)


def test_repair_request_roundtrips_disambiguation_menu() -> None:
    repair = RepairRequest(Identifier("n-best"), "你是指哪个房间?", 1, ("书房", "卧室"))
    assert RepairRequest.from_payload(repair.to_payload()) == repair


def test_repair_attempts_start_at_one() -> None:
    with pytest.raises(ValueError, match="positive"):
        RepairRequest(Identifier("reask"), "请再说一次", 0)
