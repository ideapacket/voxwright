"""Tests for the logical clock."""

from voxwright.clock import LogicalClock


def test_clock_advances_only_when_requested() -> None:
    clock = LogicalClock(10)
    assert clock.deadline(5) == 15
    assert clock.now_ms == 10
    assert clock.advance(5) == 15


def test_clock_can_move_to_future_instant() -> None:
    clock = LogicalClock()
    assert clock.move_to(25) == 25
