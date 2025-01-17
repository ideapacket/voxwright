"""Integer logical clocks for replayable timed behavior."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class LogicalClock:
    """A monotonic clock advanced explicitly by application events."""

    now_ms: int = 0

    def __post_init__(self) -> None:
        if self.now_ms < 0:
            raise ValueError("logical time cannot be negative")

    def advance(self, delta_ms: int) -> int:
        """Advance by a non-negative duration and return the new instant."""
        if delta_ms < 0:
            raise ValueError("logical clock cannot move backwards")
        self.now_ms += delta_ms
        return self.now_ms

    def move_to(self, instant_ms: int) -> int:
        """Move to an absolute instant without permitting reversal."""
        if instant_ms < self.now_ms:
            raise ValueError("logical clock cannot move backwards")
        self.now_ms = instant_ms
        return self.now_ms

    def deadline(self, budget_ms: int) -> int:
        """Compute a deadline without advancing the clock."""
        if budget_ms < 0:
            raise ValueError("budget cannot be negative")
        return self.now_ms + budget_ms

    def expired(self, deadline_ms: int) -> bool:
        """Return whether the clock is at or beyond a deadline."""
        return self.now_ms >= deadline_ms
