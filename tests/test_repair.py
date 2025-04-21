"""Tests for bounded mishearing-repair policies."""

from __future__ import annotations

import pytest

import voxwright.repair as repair


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
