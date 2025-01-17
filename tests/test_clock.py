"""Tests for the logical clock."""

import pytest

from voxwright.clock import LogicalClock


def test_clock_advances_only_when_requested() -> None:
    clock = LogicalClock(10)
    assert clock.deadline(5) == 15
    assert clock.now_ms == 10
    assert clock.advance(5) == 15


def test_clock_can_move_to_future_instant() -> None:
    clock = LogicalClock()
    assert clock.move_to(25) == 25


def test_deadline_expires_at_exact_instant() -> None:
    clock = LogicalClock(99)
    assert not clock.expired(100)
    clock.advance(1)
    assert clock.expired(100)


@pytest.mark.parametrize("operation", ["advance", "move_to"])
def test_clock_rejects_reversal(operation: str) -> None:
    clock = LogicalClock(5)
    with pytest.raises(ValueError, match="backwards"):
        getattr(clock, operation)(-1 if operation == "advance" else 4)


def test_zero_duration_advance_is_stable() -> None:
    clock = LogicalClock(7)
    assert clock.advance(0) == 7


def test_negative_initial_time_is_invalid() -> None:
    with pytest.raises(ValueError, match="negative"):
        LogicalClock(-1)


def test_negative_budget_is_invalid() -> None:
    with pytest.raises(ValueError, match="budget"):
        LogicalClock().deadline(-1)
