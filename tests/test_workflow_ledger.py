"""Tests for workflow execution ledger and recovery."""

from __future__ import annotations

from dataclasses import replace

import pytest

import voxwright.workflow_ledger as ledgers
from voxwright.identifiers import Identifier


def test_workflow_ledger_chains_completed_steps() -> None:
    ledger = ledgers.WorkflowLedger()
    first = ledger.record(Identifier("prepare"), {"ready": True})
    second = ledger.record(Identifier("commit"), {"done": True})
    assert second.previous == first.digest
    assert ledger.completed_steps == (Identifier("prepare"), Identifier("commit"))
    assert ledger.validate() is None


def test_workflow_ledger_detects_tampering() -> None:
    ledger = ledgers.WorkflowLedger()
    ledger.record(Identifier("prepare"), {"ready": True})
    ledger.links[0] = replace(ledger.links[0], payload={"step_id": "skip", "state": {}})
    assert ledger.validate() == 0


def test_checkpoint_captures_verified_last_state() -> None:
    ledger = ledgers.WorkflowLedger()
    ledger.record(Identifier("prepare"), {"count": 1})
    last = ledger.record(Identifier("commit"), {"count": 2})
    checkpoint = ledger.checkpoint()
    assert checkpoint["completed"] == ["prepare", "commit"]
    assert checkpoint["state"] == {"count": 2}
    assert checkpoint["digest"] == last.digest


def test_empty_ledger_checkpoint_has_hash_identity() -> None:
    checkpoint = ledgers.WorkflowLedger().checkpoint()
    assert checkpoint["completed"] == []
    assert checkpoint["state"] == {}
    assert str(checkpoint["digest"]).startswith("sha256:")


def test_resume_skips_exact_completed_prefix() -> None:
    ordered = (Identifier("one"), Identifier("two"), Identifier("three"))
    checkpoint = {"completed": ["one", "two"]}
    assert ledgers.remaining_steps(ordered, checkpoint) == (Identifier("three"),)


def test_resume_rejects_nonprefix_checkpoint() -> None:
    ordered = (Identifier("one"), Identifier("two"))
    with pytest.raises(ValueError, match="not a prefix"):
        ledgers.remaining_steps(ordered, {"completed": ["two"]})
