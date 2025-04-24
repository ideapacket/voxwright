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


def test_n_best_menu_uses_one_based_user_selection() -> None:
    alternatives = ("study light", "study night", "steady light")
    assert repair.disambiguate(1, alternatives) == "study light"
    assert repair.disambiguate(3, alternatives) == "steady light"


@pytest.mark.parametrize("selection", [0, 4])
def test_n_best_menu_rejects_out_of_range_selection(selection: int) -> None:
    with pytest.raises(ValueError, match="between 1 and 3"):
        repair.disambiguate(selection, ("a", "b", "c"))


@pytest.mark.parametrize("response", ["yes", " Confirm ", "correct", "对"])
def test_explicit_confirmation_accepts_known_positive_forms(response: str) -> None:
    assert repair.confirmation_matches(response) is True


@pytest.mark.parametrize("response", ["no", "cancel", "incorrect", "不对"])
def test_explicit_confirmation_accepts_known_negative_forms(response: str) -> None:
    assert repair.confirmation_matches(response) is False


def test_explicit_confirmation_does_not_guess_unknown_response() -> None:
    assert repair.confirmation_matches("maybe") is None


@pytest.mark.parametrize("max_attempts", range(1, 8))
def test_repair_loop_always_terminates_at_configured_bound(max_attempts: int) -> None:
    config = repair.RepairConfig(max_attempts=max_attempts)
    state = repair.RepairState()
    steps = 0
    while not state.handed_off:
        state, _ = repair.advance_repair(state, 0.0, (), config)
        steps += 1
        assert steps <= max_attempts + 1
    assert steps == max_attempts + 1


def test_high_confidence_repair_terminates_without_attempt_increment() -> None:
    state, strategy = repair.advance_repair(
        repair.RepairState(), 1.0, (), repair.RepairConfig(max_attempts=5)
    )
    assert state == repair.RepairState(0, resolved=True)
    assert strategy is repair.RepairStrategy.ACCEPT


def test_synthetic_repair_run_records_strategy_trace() -> None:
    outcome = repair.run_repair((0.1, 0.6, 0.95))
    assert outcome.resolved
    assert not outcome.handed_off
    assert outcome.attempts == 2
    assert outcome.strategies == (
        repair.RepairStrategy.SILENT_REASK,
        repair.RepairStrategy.EXPLICIT_CONFIRM,
        repair.RepairStrategy.ACCEPT,
    )


def test_incomplete_confidence_sequence_falls_back_to_bounded_handoff() -> None:
    outcome = repair.run_repair((0.2,), config=repair.RepairConfig(max_attempts=2))
    assert outcome.handed_off
    assert len(outcome.strategies) == 3
