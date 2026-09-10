from __future__ import annotations

from pathlib import Path

import pytest

from voxwright.frame_artifacts import (
    decode_frame_stack,
    encode_frame_stack,
    frame_stack_digest,
    load_frame_stack,
    stack_from_dict,
    write_frame_stack,
)
from voxwright.frames import FrameStack, GroundedSlot, TaskFrame
from voxwright.identifiers import Identifier


def sample_stack() -> FrameStack:
    stack = FrameStack()
    frame = TaskFrame(
        Identifier("schedule-1"),
        Identifier("calendar.create"),
        {Identifier("title"): GroundedSlot(Identifier("title"))},
    )
    stack.push(frame)
    stack.replace_current(stack.current.fill_slot("title", "review", 0.9, "review", 0, 6))  # type: ignore[union-attr]
    return stack


def test_frame_stack_codec_restores_exact_snapshot() -> None:
    stack = sample_stack()
    restored = stack_from_dict(stack.snapshot())
    assert restored.snapshot() == stack.snapshot()
    encoded = encode_frame_stack(stack)
    assert decode_frame_stack(encoded).snapshot() == stack.snapshot()
    assert encode_frame_stack(decode_frame_stack(encoded)).encode() == encoded.encode()


def test_frame_stack_decoder_rejects_unknown_version_and_bad_topology() -> None:
    snapshot = sample_stack().snapshot()
    snapshot["schema_version"] = True
    with pytest.raises(ValueError, match="unsupported version"):
        stack_from_dict(snapshot)
    snapshot = sample_stack().snapshot()
    snapshot["frames"][0]["state"] = "suspended"  # type: ignore[index]
    with pytest.raises(ValueError, match="top must be active or closed"):
        stack_from_dict(snapshot)


def test_frame_stack_decoder_reports_nested_slot_span_errors() -> None:
    snapshot = sample_stack().snapshot()
    slot = snapshot["frames"][0]["slots"]["title"]  # type: ignore[index]
    slot["span"] = [0, True]  # type: ignore[index]
    with pytest.raises(TypeError, match=r"slots\.title\.span\[1\]: expected integer"):
        stack_from_dict(snapshot)


def test_frame_stack_roundtrips_nested_suspended_parent() -> None:
    stack = sample_stack()
    child = TaskFrame(
        Identifier("music-1"),
        Identifier("music.play"),
        {Identifier("track"): GroundedSlot(Identifier("track"))},
    )
    stack.push(child)
    restored = decode_frame_stack(encode_frame_stack(stack))
    assert restored.snapshot() == stack.snapshot()
    assert restored.frames[0].state.value == "suspended"
    assert restored.current is not None and restored.current.frame_id == Identifier("music-1")


def test_frame_stack_decoder_rejects_duplicate_frame_identity() -> None:
    snapshot = sample_stack().snapshot()
    duplicate = dict(snapshot["frames"][0])  # type: ignore[index]
    duplicate["state"] = "active"
    snapshot["frames"][0]["state"] = "suspended"  # type: ignore[index]
    snapshot["frames"].append(duplicate)  # type: ignore[union-attr]
    with pytest.raises(ValueError, match="identifiers must be unique"):
        stack_from_dict(snapshot)


def test_frame_stack_files_are_identified_complete_and_nonclobbering(tmp_path: Path) -> None:
    stack = sample_stack()
    path = tmp_path / "frames.json"
    write_frame_stack(path, stack)
    restored = load_frame_stack(path)
    assert restored.snapshot() == stack.snapshot()
    assert frame_stack_digest(restored) == frame_stack_digest(stack)
    with pytest.raises(FileExistsError, match="output already exists"):
        write_frame_stack(path, FrameStack())
    path.unlink()
    path.write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="missing terminal newline"):
        load_frame_stack(path)
