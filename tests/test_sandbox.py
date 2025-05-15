"""Tests for the deterministic permissioned tool sandbox."""

from __future__ import annotations

import voxwright.sandbox as sandbox
from voxwright.hashing import EMPTY_DIGEST
from voxwright.identifiers import Identifier


def test_permission_policy_defaults_to_deny() -> None:
    policy = sandbox.PermissionPolicy({})
    assert policy.decide("notes.add") is sandbox.PermissionDecision.DENY


def test_permission_policy_resolves_allow_confirm_and_deny() -> None:
    policy = sandbox.PermissionPolicy(
        {
            Identifier("timer.start"): sandbox.PermissionDecision.ALLOW,
            Identifier("messages.send"): sandbox.PermissionDecision.CONFIRM,
            Identifier("home.unlock"): sandbox.PermissionDecision.DENY,
        }
    )
    assert policy.decide("timer.start") is sandbox.PermissionDecision.ALLOW
    assert policy.decide("messages.send") is sandbox.PermissionDecision.CONFIRM
    assert policy.decide("home.unlock") is sandbox.PermissionDecision.DENY


def test_permission_policy_snapshots_mutable_rules() -> None:
    rules = {Identifier("timer.start"): sandbox.PermissionDecision.ALLOW}
    policy = sandbox.PermissionPolicy(rules)
    rules.clear()
    assert policy.decide("timer.start") is sandbox.PermissionDecision.ALLOW


def test_side_effect_ledger_chains_denied_and_executed_attempts() -> None:
    ledger = sandbox.SideEffectLedger()
    denied = ledger.record(Identifier("home.unlock"), {"door": "front"}, False, "denied")
    allowed = ledger.record(Identifier("timer.start"), {"seconds": 5}, True, {"timer_id": "t-1"})
    assert denied.previous == EMPTY_DIGEST
    assert allowed.previous == denied.digest
    assert ledger.validate() is None


def test_side_effect_ledger_detects_changed_execution_flag() -> None:
    from dataclasses import replace

    ledger = sandbox.SideEffectLedger()
    link = ledger.record(Identifier("home.unlock"), {}, False, "denied")
    ledger.links[0] = replace(link, payload={**link.payload, "executed": True})
    assert ledger.validate() == 0


def test_calendar_store_allocates_deterministic_ids() -> None:
    state = sandbox.SimulatedState.empty()
    first = state.calendar_create("review", 19)
    second = state.calendar_create("sync", 9)
    assert first == {"event_id": "event-1", "title": "review", "hour": 19}
    assert second["event_id"] == "event-2"
    assert state.calendar == [first, second]


def test_timer_store_is_independent_from_calendar_ids() -> None:
    state = sandbox.SimulatedState.empty()
    state.calendar_create("review", 19)
    assert state.timer_start(30) == {"timer_id": "timer-1", "seconds": 30, "active": True}


def test_empty_state_has_no_shared_mutable_stores() -> None:
    left = sandbox.SimulatedState.empty()
    right = sandbox.SimulatedState.empty()
    left.calendar_create("left", 1)
    assert right.calendar == []
