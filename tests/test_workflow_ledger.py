"""Tests for workflow execution ledger and recovery."""

from __future__ import annotations

from dataclasses import replace

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
