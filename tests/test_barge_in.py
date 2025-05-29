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
