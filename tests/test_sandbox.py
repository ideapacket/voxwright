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
