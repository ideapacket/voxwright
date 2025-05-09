"""Tests for the deterministic permissioned tool sandbox."""

from __future__ import annotations

import voxwright.sandbox as sandbox
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
