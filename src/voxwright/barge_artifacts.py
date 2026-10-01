"""Versioned checkpoints for resumable application-level interrupts."""

from __future__ import annotations

from dataclasses import dataclass

from voxwright.barge_in import (
    BargePolicy,
    InFlightOperation,
    Interrupt,
    InterruptManager,
    OperationState,
    order_interrupts,
)
from voxwright.core import JSONValue, canonical_json, ensure_json_value, parse_json
from voxwright.identifiers import Identifier


@dataclass(frozen=True, slots=True)
class BargeCheckpoint:
    """An active operation and its deterministically ordered interrupt queue."""

    operation: InFlightOperation
    policy: BargePolicy
    queued: tuple[Interrupt, ...] = ()
    schema_version: int = 1

    def __post_init__(self) -> None:
        if self.schema_version != 1:
            raise ValueError(f"unsupported barge checkpoint version: {self.schema_version}")
        if self.operation.state is not OperationState.RUNNING:
            raise ValueError("barge checkpoint operation must be running")
        if self.policy is not BargePolicy.QUEUE and self.queued:
            raise ValueError("only queue policy may retain interrupts")
        if self.queued != order_interrupts(self.queued):
            raise ValueError("checkpoint interrupts must be in deterministic order")


def _object(value: JSONValue, path: str) -> dict[str, JSONValue]:
    checked = ensure_json_value(value, path)
    if not isinstance(checked, dict):
        raise TypeError(f"{path}: expected object")
    return checked


def _text(value: JSONValue, path: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{path}: expected string")
    return value


def _integer(value: JSONValue, path: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{path}: expected integer")
    return value


def checkpoint_to_dict(checkpoint: BargeCheckpoint) -> dict[str, JSONValue]:
    operation = checkpoint.operation
    return {
        "schema_version": checkpoint.schema_version,
        "operation": {
            "operation_id": str(operation.operation_id),
            "tool_name": str(operation.tool_name),
            "arguments": operation.arguments,
            "idempotent": operation.idempotent,
            "state": operation.state.value,
        },
        "policy": checkpoint.policy.value,
        "queued": [
            {
                "at_ms": item.at_ms,
                "sequence": item.sequence,
                "interrupt_id": str(item.interrupt_id),
                "transcript": item.transcript,
            }
            for item in checkpoint.queued
        ],
    }


def checkpoint_from_dict(value: JSONValue) -> BargeCheckpoint:
    data = _object(value, "$")
    if set(data) != {"schema_version", "operation", "policy", "queued"}:
        raise ValueError("$: expected exact barge checkpoint fields")
    version = _integer(data["schema_version"], "$.schema_version")
    operation = _object(data["operation"], "$.operation")
    if set(operation) != {"operation_id", "tool_name", "arguments", "idempotent", "state"}:
        raise ValueError("$.operation: expected exact operation fields")
    idempotent = operation["idempotent"]
    if not isinstance(idempotent, bool):
        raise TypeError("$.operation.idempotent: expected boolean")
    state_text = _text(operation["state"], "$.operation.state")
    try:
        state = OperationState(state_text)
    except ValueError as error:
        raise ValueError(f"$.operation.state: unknown state {state_text!r}") from error
    policy_text = _text(data["policy"], "$.policy")
    try:
        policy = BargePolicy(policy_text)
    except ValueError as error:
        raise ValueError(f"$.policy: unknown policy {policy_text!r}") from error
    queued = data["queued"]
    if not isinstance(queued, list):
        raise TypeError("$.queued: expected array")
    decoded: list[Interrupt] = []
    for index, value_item in enumerate(queued):
        path = f"$.queued[{index}]"
        item = _object(value_item, path)
        if set(item) != {"at_ms", "sequence", "interrupt_id", "transcript"}:
            raise ValueError(f"{path}: expected exact interrupt fields")
        decoded.append(
            Interrupt(
                _integer(item["at_ms"], f"{path}.at_ms"),
                _integer(item["sequence"], f"{path}.sequence"),
                Identifier(_text(item["interrupt_id"], f"{path}.interrupt_id")),
                _text(item["transcript"], f"{path}.transcript"),
            )
        )
    restored = InFlightOperation(
        Identifier(_text(operation["operation_id"], "$.operation.operation_id")),
        Identifier(_text(operation["tool_name"], "$.operation.tool_name")),
        _object(operation["arguments"], "$.operation.arguments"),
        idempotent,
        state,
    )
    return BargeCheckpoint(restored, policy, tuple(decoded), version)


def encode_barge_checkpoint(checkpoint: BargeCheckpoint) -> str:
    return canonical_json(checkpoint_to_dict(checkpoint)) + "\n"


def decode_barge_checkpoint(text: str) -> BargeCheckpoint:
    if not text.strip():
        raise ValueError("barge checkpoint document is empty")
    return checkpoint_from_dict(parse_json(text))


def checkpoint_manager(manager: InterruptManager) -> BargeCheckpoint:
    """Capture an active manager without sharing its mutable queue."""
    return BargeCheckpoint(manager.operation, manager.policy, tuple(manager.queued))


def resume_manager(checkpoint: BargeCheckpoint) -> InterruptManager:
    """Restore a manager that can continue resolving or draining interrupts."""
    manager = InterruptManager(checkpoint.operation, checkpoint.policy)
    manager.queued.extend(checkpoint.queued)
    return manager
