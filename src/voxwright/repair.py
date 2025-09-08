"""Bounded confidence-driven policies for planted transcript mishearings."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from voxwright.events import HandoffEvent, RepairRequest
from voxwright.identifiers import Identifier


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

    def to_dict(self) -> dict[str, float | int]:
        return {
            "reask_below": self.reask_below,
            "menu_below": self.menu_below,
            "explicit_below": self.explicit_below,
            "implicit_below": self.implicit_below,
            "max_attempts": self.max_attempts,
        }

    @classmethod
    def from_dict(cls, value: object) -> RepairConfig:
        if not isinstance(value, dict) or set(value) != {
            "reask_below",
            "menu_below",
            "explicit_below",
            "implicit_below",
            "max_attempts",
        }:
            raise ValueError("invalid repair config shape")
        numbers = [
            value[name]
            for name in ("reask_below", "menu_below", "explicit_below", "implicit_below")
        ]
        if any(isinstance(item, bool) or not isinstance(item, (int, float)) for item in numbers):
            raise TypeError("repair thresholds must be numbers")
        attempts = value["max_attempts"]
        if isinstance(attempts, bool) or not isinstance(attempts, int):
            raise TypeError("max repair attempts must be an integer")
        return cls(
            float(numbers[0]),
            float(numbers[1]),
            float(numbers[2]),
            float(numbers[3]),
            attempts,
        )


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


@dataclass(frozen=True, slots=True)
class RepairState:
    """Immutable progress for one bounded misunderstanding repair."""

    attempt: int = 0
    resolved: bool = False
    handed_off: bool = False

    def __post_init__(self) -> None:
        if self.attempt < 0:
            raise ValueError("repair attempt cannot be negative")
        if self.resolved and self.handed_off:
            raise ValueError("repair cannot be both resolved and handed off")


def advance_repair(
    state: RepairState,
    confidence: float,
    alternatives: tuple[str, ...],
    config: RepairConfig,
) -> tuple[RepairState, RepairStrategy]:
    """Advance once, resolving accepts and terminating at handoff."""
    if state.resolved or state.handed_off:
        raise ValueError("repair state is already terminal")
    strategy = select_strategy(confidence, alternatives, state.attempt, config)
    if strategy is RepairStrategy.ACCEPT:
        return RepairState(state.attempt, resolved=True), strategy
    if strategy is RepairStrategy.HANDOFF:
        return RepairState(state.attempt, handed_off=True), strategy
    return RepairState(state.attempt + 1), strategy


def repair_event(
    strategy: RepairStrategy, attempt: int, alternatives: tuple[str, ...] = ()
) -> RepairRequest | HandoffEvent | None:
    """Translate a policy decision into an application event payload."""
    if strategy is RepairStrategy.ACCEPT:
        return None
    if strategy is RepairStrategy.HANDOFF:
        return HandoffEvent(Identifier("repair.exhausted"), "repair attempt bound reached")
    prompts = {
        RepairStrategy.SILENT_REASK: "Please repeat the request",
        RepairStrategy.N_BEST_MENU: "Select the intended transcript",
        RepairStrategy.IMPLICIT_CONFIRM: "I understood this request",
        RepairStrategy.EXPLICIT_CONFIRM: "Please confirm the request",
    }
    return RepairRequest(Identifier(strategy.value), prompts[strategy], attempt + 1, alternatives)


def disambiguate(selection: int, alternatives: tuple[str, ...]) -> str:
    """Resolve a one-based n-best menu selection with precise boundaries."""
    if not alternatives:
        raise ValueError("disambiguation menu cannot be empty")
    if not 1 <= selection <= len(alternatives):
        raise ValueError(f"selection must be between 1 and {len(alternatives)}")
    return alternatives[selection - 1]


def confirmation_matches(response: str) -> bool | None:
    """Map explicit synthetic confirmations without guessing unknown text."""
    normalized = response.strip().lower()
    if normalized in {"yes", "confirm", "correct", "对"}:
        return True
    if normalized in {"no", "cancel", "incorrect", "不对"}:
        return False
    return None


@dataclass(frozen=True, slots=True)
class RepairOutcome:
    resolved: bool
    handed_off: bool
    attempts: int
    strategies: tuple[RepairStrategy, ...]


@dataclass(frozen=True, slots=True)
class RepairMetrics:
    total: int
    resolved: int
    handed_off: int
    repair_rate: float
    mean_attempts: float


def summarize_repairs(outcomes: tuple[RepairOutcome, ...]) -> RepairMetrics:
    """Aggregate outcomes with production-point float quantization."""
    total = len(outcomes)
    if total == 0:
        return RepairMetrics(0, 0, 0, 0.0, 0.0)
    resolved = sum(outcome.resolved for outcome in outcomes)
    handed_off = sum(outcome.handed_off for outcome in outcomes)
    repaired = sum(outcome.attempts > 0 for outcome in outcomes)
    return RepairMetrics(
        total,
        resolved,
        handed_off,
        round(repaired / total, 6),
        round(sum(item.attempts for item in outcomes) / total, 6),
    )


def run_repair(
    confidences: tuple[float, ...],
    alternatives: tuple[str, ...] = (),
    config: RepairConfig | None = None,
) -> RepairOutcome:
    """Run a synthetic confidence sequence through the bounded policy."""
    policy = config if config is not None else RepairConfig()
    state = RepairState()
    strategies: list[RepairStrategy] = []
    for confidence in confidences:
        state, strategy = advance_repair(state, confidence, alternatives, policy)
        strategies.append(strategy)
        if state.resolved or state.handed_off:
            break
    if not state.resolved and not state.handed_off:
        while not state.handed_off:
            state, strategy = advance_repair(state, 0.0, alternatives, policy)
            strategies.append(strategy)
    return RepairOutcome(state.resolved, state.handed_off, state.attempt, tuple(strategies))
