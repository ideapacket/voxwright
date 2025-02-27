"""Adapter contract and offline implementation tests."""

from __future__ import annotations

import pytest

import voxwright.adapters as adapters
from voxwright.events import EventEnvelope, EventKind
from voxwright.identifiers import Identifier


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
