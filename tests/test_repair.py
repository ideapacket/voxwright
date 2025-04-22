"""Tests for bounded mishearing-repair policies."""

from __future__ import annotations

import pytest

import voxwright.repair as repair
from voxwright.events import HandoffEvent, RepairRequest


def test_repair_strategy_bands_are_deterministic() -> None:
    config = repair.RepairConfig()
    assert repair.select_strategy(0.1, (), 0, config) is repair.RepairStrategy.SILENT_REASK
    assert (
        repair.select_strategy(0.4, ("one", "two"), 0, config) is repair.RepairStrategy.N_BEST_MENU
    )
    assert repair.select_strategy(0.6, (), 0, config) is repair.RepairStrategy.EXPLICIT_CONFIRM
    assert repair.select_strategy(0.8, (), 0, config) is repair.RepairStrategy.IMPLICIT_CONFIRM
    assert repair.select_strategy(0.95, (), 0, config) is repair.RepairStrategy.ACCEPT


def test_attempt_bound_overrides_confidence() -> None:
    config = repair.RepairConfig(max_attempts=2)
    assert repair.select_strategy(1.0, (), 2, config) is repair.RepairStrategy.HANDOFF


def test_repair_config_validates_threshold_order_and_attempts() -> None:
    with pytest.raises(ValueError, match="nondecreasing"):
        repair.RepairConfig(reask_below=0.8, menu_below=0.5)
    with pytest.raises(ValueError, match="must be positive"):
        repair.RepairConfig(max_attempts=0)


def test_repair_state_advances_then_resolves() -> None:
    config = repair.RepairConfig()
    state, strategy = repair.advance_repair(repair.RepairState(), 0.1, (), config)
    assert state.attempt == 1
    assert strategy is repair.RepairStrategy.SILENT_REASK
    resolved, strategy = repair.advance_repair(state, 1.0, (), config)
    assert resolved.resolved
    assert strategy is repair.RepairStrategy.ACCEPT


def test_terminal_repair_state_cannot_advance() -> None:
    with pytest.raises(ValueError, match="already terminal"):
        repair.advance_repair(repair.RepairState(resolved=True), 1.0, (), repair.RepairConfig())


def test_repair_decisions_map_to_typed_event_payloads() -> None:
    menu = repair.repair_event(repair.RepairStrategy.N_BEST_MENU, 0, ("light", "night"))
    handoff = repair.repair_event(repair.RepairStrategy.HANDOFF, 3)
    assert isinstance(menu, RepairRequest)
    assert menu.candidates == ("light", "night")
    assert isinstance(handoff, HandoffEvent)
    assert repair.repair_event(repair.RepairStrategy.ACCEPT, 0) is None
