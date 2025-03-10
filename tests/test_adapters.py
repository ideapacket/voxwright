"""Adapter contract and offline implementation tests."""

from __future__ import annotations

import pytest

import voxwright.adapters as adapters
from voxwright.events import (
    EventEnvelope,
    EventKind,
    Intent,
    Transcript,
    decode_payload,
    envelope_for,
)
from voxwright.identifiers import Identifier
from voxwright.replay import ReplayTrace


def input_event(sequence: int = 0, text: str = "play music") -> EventEnvelope:
    return EventEnvelope(
        Identifier("session-1"), sequence, sequence * 10, EventKind.FINAL_TRANSCRIPT, {"text": text}
    )


def test_capabilities_require_an_honest_description() -> None:
    with pytest.raises(ValueError, match="description cannot be empty"):
        adapters.AdapterCapabilities(False, False, False, False, True, "  ")


def test_adapter_turn_preserves_event_order() -> None:
    events = (input_event(0), input_event(1))
    turn = adapters.AdapterTurn(events, finished=False)
    assert turn.events == events
    assert not turn.finished


def test_protocol_accepts_structural_implementation() -> None:
    class Minimal:
        name = Identifier("minimal")
        capabilities = adapters.AdapterCapabilities(False, False, False, False, True, "test")

        def observe(self, events: object) -> None:
            self.events = events

        def act(self) -> adapters.AdapterTurn:
            return adapters.AdapterTurn(())

    implementation: adapters.SpokenAdapter = Minimal()
    implementation.observe([input_event()])
    assert implementation.act().events == ()


def test_conformance_check_allows_explicit_no_observation_error() -> None:
    class Strict:
        name = Identifier("strict")
        capabilities = adapters.AdapterCapabilities(False, False, False, False, True, "strict")

        def observe(self, events: object) -> None:
            del events

        def act(self) -> adapters.AdapterTurn:
            raise RuntimeError("observe first")

    assert adapters.conformance_issues(Strict()) == []


def test_conformance_detects_unsolicited_output() -> None:
    class Eager:
        name = Identifier("eager")
        capabilities = adapters.AdapterCapabilities(False, False, False, False, True, "eager")

        def observe(self, events: object) -> None:
            del events

        def act(self) -> adapters.AdapterTurn:
            return adapters.AdapterTurn((input_event(),))

    assert adapters.conformance_issues(Eager()) == ["adapter emitted events before observation"]


def test_scripted_adapter_replays_turns_and_records_observations() -> None:
    output = input_event(1, "playing")
    adapter = adapters.ScriptedAdapter([adapters.AdapterTurn((output,))])
    observed = input_event()
    adapter.observe([observed])
    assert adapter.act() == adapters.AdapterTurn((output,))
    assert adapter.observations == ((observed,),)


def test_scripted_adapter_enforces_observe_act_alternation() -> None:
    adapter = adapters.ScriptedAdapter([adapters.AdapterTurn(())])
    with pytest.raises(RuntimeError, match="observe must"):
        adapter.act()
    adapter.observe([input_event()])
    with pytest.raises(RuntimeError, match="consume"):
        adapter.observe([input_event()])


def test_scripted_adapter_reports_exhaustion_after_valid_observation() -> None:
    adapter = adapters.ScriptedAdapter([adapters.AdapterTurn(())])
    adapter.observe([input_event()])
    adapter.act()
    adapter.observe([input_event(1)])
    with pytest.raises(RuntimeError, match="no remaining turn"):
        adapter.act()


def test_scripted_adapter_snapshots_mutable_turn_input() -> None:
    turns = [adapters.AdapterTurn((input_event(1),))]
    adapter = adapters.ScriptedAdapter(turns)
    turns.clear()
    adapter.observe([input_event()])
    assert adapter.act().events == (input_event(1),)


def test_scripted_capabilities_distinguish_mechanics_from_intelligence() -> None:
    capabilities = adapters.ScriptedAdapter.capabilities
    assert capabilities.offline
    assert capabilities.structured_tool_calls
    assert "scripted" in capabilities.description


def test_recorded_adapter_emits_trace_events_in_order() -> None:
    trace = ReplayTrace(Identifier("session-1"), 4, (input_event(0), input_event(1)))
    adapter = adapters.RecordedReplayAdapter(trace)
    adapter.observe([input_event()])
    assert adapter.act().events == (input_event(0),)
    adapter.observe([input_event(1)])
    assert adapter.act().events == (input_event(1),)
    adapter.observe([input_event(2)])
    assert adapter.act() == adapters.AdapterTurn((), finished=True)


def test_recorded_adapter_requires_nonempty_observation() -> None:
    trace = ReplayTrace(Identifier("session-1"), 0, ())
    adapter = adapters.RecordedReplayAdapter(trace)
    with pytest.raises(ValueError, match="cannot be empty"):
        adapter.observe([])


def transcript_event(text: str) -> EventEnvelope:
    return envelope_for(
        Identifier("session-1"), 0, 0, EventKind.FINAL_TRANSCRIPT, Transcript(text, 1.0)
    )


@pytest.mark.parametrize(
    ("text", "intent_name"),
    [
        ("play music", "music.play"),
        ("turn on light", "home.set-light"),
        ("make a note", "notes.add"),
        ("schedule review", "calendar.create"),
    ],
)
def test_template_adapter_selects_planted_keyword_rule(text: str, intent_name: str) -> None:
    adapter = adapters.TemplateAdapter()
    adapter.observe([transcript_event(text)])
    turn = adapter.act()
    assert isinstance(decode_payload(turn.events[0]), Intent)
    assert decode_payload(turn.events[0]).name == Identifier(intent_name)  # type: ignore[union-attr]
    assert turn.events[1].kind is EventKind.AGENT_UTTERANCE


def test_template_adapter_requests_restatement_for_unknown_task() -> None:
    adapter = adapters.TemplateAdapter()
    adapter.observe([transcript_event("unmapped request")])
    turn = adapter.act()
    assert [event.kind for event in turn.events] == [EventKind.AGENT_UTTERANCE]


def test_template_slot_extraction_is_visible_and_deterministic() -> None:
    light = adapters.extract_rule_slots("turn off bedroom light", Identifier("home.set-light"))
    music = adapters.extract_rule_slots("play music Blue Sky", Identifier("music.play"))
    assert light == {"room": "bedroom", "on": False}
    assert music == {"track": "blue sky"}


def test_template_adapter_places_extracted_slots_in_intent() -> None:
    adapter = adapters.TemplateAdapter()
    adapter.observe([transcript_event("turn on kitchen light")])
    intent = decode_payload(adapter.act().events[0])
    assert isinstance(intent, Intent)
    assert intent.slots == {"room": "kitchen", "on": True}


def test_template_adapter_rejects_non_transcript_payload() -> None:
    adapter = adapters.TemplateAdapter()
    adapter.observe([input_event()])
    with pytest.raises(ValueError, match="missing field"):
        adapter.act()


def test_template_adapter_consumes_observation_once() -> None:
    adapter = adapters.TemplateAdapter()
    adapter.observe([transcript_event("play music")])
    adapter.act()
    with pytest.raises(RuntimeError, match="observe must"):
        adapter.act()


def test_rule_slot_defaults_are_explicit() -> None:
    assert adapters.extract_rule_slots("turn on light", Identifier("home.set-light")) == {
        "room": "study",
        "on": True,
    }
    assert adapters.extract_rule_slots("play music", Identifier("music.play")) == {
        "track": "synthetic track"
    }
    assert adapters.extract_rule_slots("unknown", Identifier("unknown.intent")) == {}
