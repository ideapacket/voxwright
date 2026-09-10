"""Strict restoration and persistence for frame-stack snapshots."""

from __future__ import annotations

from pathlib import Path

from voxwright.core import JSONValue, canonical_json, parse_json
from voxwright.frames import FrameStack, FrameState, GroundedSlot, SlotState, TaskFrame
from voxwright.hashing import content_digest
from voxwright.identifiers import Identifier


def _integer(value: JSONValue, path: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{path}: expected integer")
    return value


def _slot_from_dict(name: str, value: JSONValue, path: str) -> GroundedSlot:
    fields = {"value", "confidence", "source_text", "span", "state"}
    if not isinstance(value, dict) or set(value) != fields:
        raise ValueError(f"{path}: expected exact slot fields")
    confidence = value["confidence"]
    source = value["source_text"]
    span = value["span"]
    state = value["state"]
    if isinstance(confidence, bool) or not isinstance(confidence, (int, float)):
        raise TypeError(f"{path}.confidence: expected number")
    if not isinstance(source, str) or not isinstance(state, str):
        raise TypeError(f"{path}: source_text and state must be strings")
    if not isinstance(span, list) or len(span) != 2:
        raise ValueError(f"{path}.span: expected two integers")
    try:
        slot_state = SlotState(state)
    except ValueError as error:
        raise ValueError(f"{path}.state: unknown slot state {state!r}") from error
    return GroundedSlot(
        Identifier(name),
        value["value"],
        float(confidence),
        source,
        _integer(span[0], f"{path}.span[0]"),
        _integer(span[1], f"{path}.span[1]"),
        slot_state,
    )


def frame_from_dict(value: JSONValue, path: str = "$.frame") -> TaskFrame:
    fields = {"frame_id", "intent", "state", "slots"}
    if not isinstance(value, dict) or set(value) != fields:
        raise ValueError(f"{path}: expected exact frame fields")
    frame_id, intent, state, slots = (
        value["frame_id"],
        value["intent"],
        value["state"],
        value["slots"],
    )
    if not all(isinstance(item, str) for item in (frame_id, intent, state)):
        raise TypeError(f"{path}: identity and state must be strings")
    if not isinstance(slots, dict):
        raise TypeError(f"{path}.slots: expected object")
    try:
        frame_state = FrameState(state)
    except ValueError as error:
        raise ValueError(f"{path}.state: unknown frame state {state!r}") from error
    decoded = {
        Identifier(name): _slot_from_dict(name, item, f"{path}.slots.{name}")
        for name, item in slots.items()
    }
    return TaskFrame(Identifier(frame_id), Identifier(intent), decoded, frame_state)


def stack_from_dict(value: JSONValue) -> FrameStack:
    if not isinstance(value, dict) or set(value) != {"schema_version", "frames"}:
        raise ValueError("$: expected exact frame stack fields")
    if value["schema_version"] != 1 or isinstance(value["schema_version"], bool):
        raise ValueError(f"$.schema_version: unsupported version {value['schema_version']!r}")
    frames = value["frames"]
    if not isinstance(frames, list):
        raise TypeError("$.frames: expected array")
    decoded = [frame_from_dict(item, f"$.frames[{index}]") for index, item in enumerate(frames)]
    frame_ids = [item.frame_id for item in decoded]
    if len(set(frame_ids)) != len(frame_ids):
        raise ValueError("frame stack identifiers must be unique")
    if decoded:
        if decoded[-1].state not in {FrameState.ACTIVE, FrameState.CLOSED}:
            raise ValueError("frame stack top must be active or closed")
        if any(item.state is not FrameState.SUSPENDED for item in decoded[:-1]):
            raise ValueError("non-top frames must be suspended")
    stack = FrameStack()
    stack._frames = decoded
    return stack


def encode_frame_stack(stack: FrameStack) -> str:
    return canonical_json(stack.snapshot()) + "\n"


def decode_frame_stack(text: str) -> FrameStack:
    if not text.strip():
        raise ValueError("frame stack document is empty")
    return stack_from_dict(parse_json(text))


def frame_stack_digest(stack: FrameStack) -> str:
    return content_digest(encode_frame_stack(stack).encode("utf-8"))


def load_frame_stack(path: Path) -> FrameStack:
    text = path.read_text(encoding="utf-8")
    if text and not text.endswith("\n"):
        raise ValueError(f"frame stack is missing terminal newline: {path}")
    return decode_frame_stack(text)


def write_frame_stack(path: Path, stack: FrameStack) -> None:
    try:
        with path.open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(encode_frame_stack(stack))
    except FileExistsError as error:
        raise FileExistsError(f"frame stack output already exists: {path}") from error
