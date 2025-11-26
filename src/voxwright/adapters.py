"""Protocols and offline adapters for spoken-model application mechanics."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from voxwright.core import JSONValue
from voxwright.events import (
    AgentUtterance,
    EventEnvelope,
    EventKind,
    Intent,
    Transcript,
    envelope_for,
)
from voxwright.identifiers import Identifier
from voxwright.replay import EventReplayer, ReplayTrace
from voxwright.torch_model import TorchJointModel, predict, prediction_slots


@dataclass(frozen=True, slots=True)
class AdapterCapabilities:
    """Honest, machine-readable mechanics supported by an adapter."""

    streaming_input: bool
    streaming_output: bool
    structured_tool_calls: bool
    context_attachments: bool
    offline: bool
    description: str

    def __post_init__(self) -> None:
        if not self.description.strip():
            raise ValueError("adapter capability description cannot be empty")


@dataclass(frozen=True, slots=True)
class AdapterTurn:
    """Events emitted after observing one ordered input batch."""

    events: tuple[EventEnvelope, ...]
    finished: bool = True


class SpokenAdapter(Protocol):
    """Pluggable observe-then-act contract for application integration."""

    name: Identifier
    capabilities: AdapterCapabilities

    def observe(self, events: Sequence[EventEnvelope]) -> None: ...

    def act(self) -> AdapterTurn: ...


def conformance_issues(adapter: SpokenAdapter) -> list[str]:
    """Exercise adapter ordering and repeatability rules without model assumptions."""
    issues: list[str] = []
    if not str(adapter.name):
        issues.append("adapter name is empty")
    if not adapter.capabilities.description.strip():
        issues.append("capability description is empty")
    try:
        empty = adapter.act()
    except RuntimeError:
        empty = None
    if empty is not None and empty.events:
        issues.append("adapter emitted events before observation")
    return issues


class ScriptedAdapter:
    """Deterministically return pre-authored event batches for scenario fixtures."""

    name = Identifier("scripted")
    capabilities = AdapterCapabilities(True, True, True, False, True, "scripted offline events")

    def __init__(self, turns: Sequence[AdapterTurn]) -> None:
        self._turns = tuple(turns)
        self._observations: list[tuple[EventEnvelope, ...]] = []
        self._position = 0
        self._ready = False

    @property
    def observations(self) -> tuple[tuple[EventEnvelope, ...], ...]:
        return tuple(self._observations)

    def observe(self, events: Sequence[EventEnvelope]) -> None:
        if self._ready:
            raise RuntimeError("act must consume the previous observation")
        batch = tuple(events)
        if not batch:
            raise ValueError("scripted adapter observation cannot be empty")
        self._observations.append(batch)
        self._ready = True

    def act(self) -> AdapterTurn:
        if not self._ready:
            raise RuntimeError("observe must be called before act")
        if self._position >= len(self._turns):
            raise RuntimeError("scripted adapter has no remaining turn")
        turn = self._turns[self._position]
        self._position += 1
        self._ready = False
        return turn


class RecordedReplayAdapter:
    """Emit recorded agent-side events from an immutable replay trace."""

    name = Identifier("recorded-replay")
    capabilities = AdapterCapabilities(True, True, True, True, True, "verified session replay")

    def __init__(self, trace: ReplayTrace) -> None:
        self._cursor = EventReplayer(trace)
        self._ready = False

    def observe(self, events: Sequence[EventEnvelope]) -> None:
        if not events:
            raise ValueError("replay observation cannot be empty")
        self._ready = True

    def act(self) -> AdapterTurn:
        if not self._ready:
            raise RuntimeError("observe must be called before act")
        emitted = self._cursor.take()
        self._ready = False
        return AdapterTurn(() if emitted is None else (emitted,), emitted is None)


class TemplateAdapter:
    """A small rule agent for exercising application flow without a language model."""

    name = Identifier("template")
    capabilities = AdapterCapabilities(False, False, True, False, True, "offline keyword rules")

    _RULES = (
        ("music", "music.play", "I will play the requested synthetic track"),
        ("light", "home.set-light", "I will update the synthetic light"),
        ("note", "notes.add", "I will add the synthetic note"),
        ("schedule", "calendar.create", "I will create the synthetic event"),
    )

    def __init__(self) -> None:
        self._observed: tuple[EventEnvelope, ...] = ()

    def observe(self, events: Sequence[EventEnvelope]) -> None:
        self._observed = tuple(events)
        if not self._observed:
            raise ValueError("template observation cannot be empty")

    def act(self) -> AdapterTurn:
        if not self._observed:
            raise RuntimeError("observe must be called before act")
        source = self._observed[-1]
        transcript = Transcript.from_payload(source.payload)
        selected = next((rule for rule in self._RULES if rule[0] in transcript.text.lower()), None)
        base_sequence = source.sequence + 1
        events: tuple[EventEnvelope, ...]
        if selected is None:
            utterance = AgentUtterance(
                "Please restate the application task", Identifier("response-rule")
            )
            events = (
                envelope_for(
                    source.session_id,
                    base_sequence,
                    source.at_ms,
                    EventKind.AGENT_UTTERANCE,
                    utterance,
                ),
            )
        else:
            _, intent_name, response = selected
            intent_id = Identifier(intent_name)
            intent = Intent(intent_id, 1.0, extract_rule_slots(transcript.text, intent_id))
            utterance = AgentUtterance(response, Identifier("response-rule"))
            events = (
                envelope_for(
                    source.session_id, base_sequence, source.at_ms, EventKind.INTENT, intent
                ),
                envelope_for(
                    source.session_id,
                    base_sequence + 1,
                    source.at_ms,
                    EventKind.AGENT_UTTERANCE,
                    utterance,
                ),
            )
        self._observed = ()
        return AdapterTurn(events)


class TorchAdapter:
    """Offline adapter backed by a caller-trained synthetic joint model."""

    name = Identifier("torch-synthetic")
    capabilities = AdapterCapabilities(
        False,
        False,
        True,
        False,
        True,
        "caller-trained CPU model over seeded synthetic text",
    )

    def __init__(self, model: TorchJointModel) -> None:
        self._model = model
        self._source: EventEnvelope | None = None
        self._transcript: Transcript | None = None

    def observe(self, events: Sequence[EventEnvelope]) -> None:
        if self._source is not None:
            raise RuntimeError("act must consume the previous model observation")
        batch = tuple(events)
        if not batch:
            raise ValueError("model adapter observation cannot be empty")
        source = next(
            (event for event in reversed(batch) if event.kind is EventKind.FINAL_TRANSCRIPT),
            None,
        )
        if source is None:
            raise ValueError("model adapter requires a final transcript event")
        self._source = source
        self._transcript = Transcript.from_payload(source.payload)

    def act(self) -> AdapterTurn:
        if self._source is None or self._transcript is None:
            raise RuntimeError("observe must be called before act")
        source = self._source
        prediction = predict(self._model, self._transcript.text)
        slots: dict[str, JSONValue] = {
            item.name: item.value for item in prediction_slots(prediction)
        }
        intent = Intent(Identifier(prediction.tool_label), prediction.tool_confidence, slots)
        utterance = AgentUtterance(
            f"Synthetic fixture selected {prediction.tool_label}",
            Identifier("response-torch-synthetic"),
        )
        events = (
            envelope_for(
                source.session_id,
                source.sequence + 1,
                source.at_ms,
                EventKind.INTENT,
                intent,
            ),
            envelope_for(
                source.session_id,
                source.sequence + 2,
                source.at_ms,
                EventKind.AGENT_UTTERANCE,
                utterance,
            ),
        )
        self._source = None
        self._transcript = None
        return AdapterTurn(events)


def extract_rule_slots(text: str, intent_name: Identifier) -> dict[str, JSONValue]:
    """Extract transparent synthetic slots for template-adapter demonstrations."""
    words = text.lower().split()
    if intent_name.value == "home.set-light":
        rooms = ("study", "bedroom", "kitchen")
        room = next((item for item in rooms if item in words), "study")
        return {"room": room, "on": "off" not in words}
    if intent_name.value == "music.play":
        marker = words.index("music") + 1 if "music" in words else len(words)
        return {"track": " ".join(words[marker:]) or "synthetic track"}
    if intent_name.value == "notes.add":
        return {"text": " ".join(word for word in words if word not in {"make", "a", "note"})}
    if intent_name.value == "calendar.create":
        return {"title": " ".join(word for word in words if word != "schedule")}
    return {}


ADAPTER_CAPABILITIES: dict[str, AdapterCapabilities] = {
    str(ScriptedAdapter.name): ScriptedAdapter.capabilities,
    str(RecordedReplayAdapter.name): RecordedReplayAdapter.capabilities,
    str(TemplateAdapter.name): TemplateAdapter.capabilities,
}


def capability_descriptor(name: str) -> dict[str, str | bool]:
    """Return a stable public capability record without instantiating adapters."""
    try:
        capabilities = ADAPTER_CAPABILITIES[name]
    except KeyError as error:
        raise ValueError(f"unknown adapter: {name}") from error
    return {
        "streaming_input": capabilities.streaming_input,
        "streaming_output": capabilities.streaming_output,
        "structured_tool_calls": capabilities.structured_tool_calls,
        "context_attachments": capabilities.context_attachments,
        "offline": capabilities.offline,
        "description": capabilities.description,
    }
