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


def test_confirmation_policy_is_inclusive_at_threshold() -> None:
    policy = frames.ConfirmationPolicy(0.8)
    exact = open_slot().fill("study", 0.8, "study", 0, 5)
    below = open_slot().fill("study", 0.799, "study", 0, 5)
    assert policy.decide(exact) is frames.ConfirmationAction.AUTO_CONFIRM
    assert policy.decide(below) is frames.ConfirmationAction.EXPLICIT_CONFIRM


def test_confirmation_policy_requires_filled_slot_and_valid_threshold() -> None:
    with pytest.raises(ValueError, match="between 0 and 1"):
        frames.ConfirmationPolicy(1.1)
    with pytest.raises(ValueError, match="requires a filled slot"):
        frames.ConfirmationPolicy().decide(open_slot())


def task_frame() -> frames.TaskFrame:
    slot = open_slot()
    return frames.TaskFrame(Identifier("frame-1"), Identifier("home.light"), {slot.name: slot})


def test_frame_activates_and_suspends_explicitly() -> None:
    active = task_frame().activate()
    suspended = active.suspend()
    assert active.state is frames.FrameState.ACTIVE
    assert suspended.state is frames.FrameState.SUSPENDED
    assert suspended.activate().state is frames.FrameState.ACTIVE


def test_frame_rejects_mismatched_slot_index() -> None:
    with pytest.raises(ValueError, match="key does not match"):
        frames.TaskFrame(
            Identifier("frame-1"), Identifier("home.light"), {Identifier("wrong"): open_slot()}
        )


def test_active_frame_fills_and_confirms_named_slot() -> None:
    active = task_frame().activate()
    filled = active.fill_slot("room", "study", 0.9, "study light", 0, 5)
    confirmed = filled.confirm_slot("room")
    assert confirmed.slots[Identifier("room")].state is frames.SlotState.CONFIRMED
    assert task_frame().slots[Identifier("room")].state is frames.SlotState.OPEN


def test_frame_slot_operations_reject_inactive_or_unknown_slot() -> None:
    with pytest.raises(ValueError, match="requires active frame"):
        task_frame().fill_slot("room", "study", 1.0, "study", 0, 5)
    with pytest.raises(ValueError, match="unknown frame slot"):
        task_frame().activate().fill_slot("device", "lamp", 1.0, "lamp", 0, 4)


def test_frame_closes_only_after_all_slots_are_confirmed() -> None:
    active = task_frame().activate()
    with pytest.raises(ValueError, match="unconfirmed slots"):
        active.close()
    confirmed = active.fill_slot("room", "study", 1.0, "study", 0, 5).confirm_slot("room")
    closed = confirmed.close()
    assert closed.state is frames.FrameState.CLOSED
    assert closed.slots[Identifier("room")].state is frames.SlotState.CLOSED


def test_empty_frame_is_not_accidentally_ready() -> None:
    frame = frames.TaskFrame(Identifier("frame-1"), Identifier("intent"), {}).activate()
    assert not frame.ready_to_close
