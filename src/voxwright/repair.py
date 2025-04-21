"""Bounded confidence-driven policies for planted transcript mishearings."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class RepairStrategy(str, Enum):
    SILENT_REASK = "silent-reask"
    N_BEST_MENU = "n-best-menu"
    IMPLICIT_CONFIRM = "implicit-confirm"
    EXPLICIT_CONFIRM = "explicit-confirm"
    ACCEPT = "accept"
    HANDOFF = "handoff"


@dataclass(frozen=True, slots=True)
class RepairConfig:
    """Validated confidence bands and a hard repair-attempt bound."""

    reask_below: float = 0.35
    menu_below: float = 0.55
    explicit_below: float = 0.75
    implicit_below: float = 0.9
    max_attempts: int = 3

    def __post_init__(self) -> None:
        values = (self.reask_below, self.menu_below, self.explicit_below, self.implicit_below)
        if not all(0.0 <= value <= 1.0 for value in values):
            raise ValueError("repair thresholds must be between 0 and 1")
        if tuple(sorted(values)) != values:
            raise ValueError("repair thresholds must be nondecreasing")
        if self.max_attempts < 1:
            raise ValueError("max repair attempts must be positive")


def select_strategy(
    confidence: float, alternatives: tuple[str, ...], attempt: int, config: RepairConfig
) -> RepairStrategy:
    """Select a deterministic strategy without advancing repair state."""
    if not 0.0 <= confidence <= 1.0:
        raise ValueError("confidence must be between 0 and 1")
    if attempt >= config.max_attempts:
        return RepairStrategy.HANDOFF
    if confidence < config.reask_below:
        return RepairStrategy.SILENT_REASK
    if confidence < config.menu_below and alternatives:
        return RepairStrategy.N_BEST_MENU
    if confidence < config.explicit_below:
        return RepairStrategy.EXPLICIT_CONFIRM
    if confidence < config.implicit_below:
        return RepairStrategy.IMPLICIT_CONFIRM
    return RepairStrategy.ACCEPT
