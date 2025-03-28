"""Tests for frame-state slot grounding."""

from __future__ import annotations

import pytest

import voxwright.frames as frames
from voxwright.identifiers import Identifier


def open_slot(name: str = "room") -> frames.GroundedSlot:
    return frames.GroundedSlot(Identifier(name))


def test_slot_lifecycle_values_are_stable() -> None:
    assert [state.value for state in frames.SlotState] == ["open", "filled", "confirmed", "closed"]


def test_grounded_slot_exposes_exact_transcript_span() -> None:
    slot = frames.GroundedSlot(
        Identifier("room"), "study", 0.85, "turn on study light", 8, 13, frames.SlotState.FILLED
    )
    assert slot.grounded_text == "study"
    assert slot.confidence == 0.85


def test_slot_rejects_impossible_span_and_open_value() -> None:
    with pytest.raises(ValueError, match="outside source text"):
        frames.GroundedSlot(Identifier("room"), None, 0.0, "short", 0, 6)
    with pytest.raises(ValueError, match="open slot cannot carry"):
        frames.GroundedSlot(Identifier("room"), "study")


def test_slot_moves_fill_confirm_close_in_order() -> None:
    filled = open_slot().fill("study", 0.9, "study light", 0, 5)
    confirmed = filled.confirm()
    closed = confirmed.close()
    assert (filled.state, confirmed.state, closed.state) == (
        frames.SlotState.FILLED,
        frames.SlotState.CONFIRMED,
        frames.SlotState.CLOSED,
    )
    assert closed.value == "study"


@pytest.mark.parametrize("operation", ["confirm", "close"])
def test_slot_rejects_out_of_order_transition(operation: str) -> None:
    with pytest.raises(ValueError, match="only"):
        getattr(open_slot(), operation)()


def test_closed_slot_is_immutable_to_new_grounding() -> None:
    closed = open_slot().fill("study", 1.0, "study", 0, 5).confirm().close()
    with pytest.raises(ValueError, match="closed slot"):
        closed.fill("bedroom", 1.0, "bedroom", 0, 7)
