"""Tests for application-level barge-in semantics."""

from __future__ import annotations

import pytest

import voxwright.barge_in as barge
from voxwright.identifiers import Identifier


def operation(idempotent: bool = False) -> barge.InFlightOperation:
    return barge.InFlightOperation(
        Identifier("operation-1"), Identifier("messages.send"), {"text": "hello"}, idempotent
    )


def test_public_barge_policies_are_distinct_from_turn_taking() -> None:
    assert [item.value for item in barge.BargePolicy] == ["cancel", "queue", "finish-if-idempotent"]


def test_operation_snapshots_strict_json_arguments() -> None:
    arguments = {"text": "hello"}
    item = operation()
    arguments["text"] = "changed"
    assert item.arguments == {"text": "hello"}


def test_operation_rejects_nonobject_arguments() -> None:
    with pytest.raises(TypeError, match="expected object"):
        barge.InFlightOperation(
            Identifier("operation-1"),
            Identifier("tool"),
            [],
            False,  # type: ignore[arg-type]
        )


def test_operation_runs_to_completion_in_order() -> None:
    running = operation().start()
    completed = running.complete()
    assert running.state is barge.OperationState.RUNNING
    assert completed.state is barge.OperationState.COMPLETED


def test_live_operation_can_cancel_and_running_can_rollback() -> None:
    assert operation().cancel().state is barge.OperationState.CANCELLED
    assert operation().start().rollback().state is barge.OperationState.ROLLED_BACK


@pytest.mark.parametrize("method", ["complete", "rollback"])
def test_pending_operation_rejects_running_only_transition(method: str) -> None:
    with pytest.raises(ValueError, match="only running"):
        getattr(operation(), method)()


def test_cancel_policy_cancels_idempotent_operation() -> None:
    resolved, outcome = barge.resolve_interrupt(operation(True).start(), barge.BargePolicy.CANCEL)
    assert resolved.state is barge.OperationState.CANCELLED
    assert outcome is barge.InterruptResolution.CANCELLED


def test_nonidempotent_operation_rolls_back_for_cancel_or_finish_policy() -> None:
    for policy in (barge.BargePolicy.CANCEL, barge.BargePolicy.FINISH_IF_IDEMPOTENT):
        resolved, outcome = barge.resolve_interrupt(operation().start(), policy)
        assert resolved.state is barge.OperationState.ROLLED_BACK
        assert outcome is barge.InterruptResolution.ROLLED_BACK


def test_queue_policy_leaves_running_state_unchanged() -> None:
    running = operation().start()
    resolved, outcome = barge.resolve_interrupt(running, barge.BargePolicy.QUEUE)
    assert resolved == running
    assert outcome is barge.InterruptResolution.QUEUED
