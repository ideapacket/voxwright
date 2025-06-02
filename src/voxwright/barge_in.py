"""Application-state semantics for interrupts during in-flight tool calls."""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum

from voxwright.core import JSONValue, ensure_json_value
from voxwright.identifiers import Identifier


class BargePolicy(str, Enum):
    CANCEL = "cancel"
    QUEUE = "queue"
    FINISH_IF_IDEMPOTENT = "finish-if-idempotent"


class OperationState(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    ROLLED_BACK = "rolled-back"


@dataclass(frozen=True, slots=True)
class InFlightOperation:
    operation_id: Identifier
    tool_name: Identifier
    arguments: dict[str, JSONValue]
    idempotent: bool
    state: OperationState = OperationState.PENDING

    def __post_init__(self) -> None:
        checked = ensure_json_value(self.arguments, "$.arguments")
        if not isinstance(checked, dict):
            raise TypeError("$.arguments: expected object")
        object.__setattr__(self, "arguments", checked)

    def start(self) -> InFlightOperation:
        if self.state is not OperationState.PENDING:
            raise ValueError("only pending operation can start")
        return replace(self, state=OperationState.RUNNING)

    def complete(self) -> InFlightOperation:
        if self.state is not OperationState.RUNNING:
            raise ValueError("only running operation can complete")
        return replace(self, state=OperationState.COMPLETED)

    def cancel(self) -> InFlightOperation:
        if self.state not in {OperationState.PENDING, OperationState.RUNNING}:
            raise ValueError("only live operation can cancel")
        return replace(self, state=OperationState.CANCELLED)

    def rollback(self) -> InFlightOperation:
        if self.state is not OperationState.RUNNING:
            raise ValueError("only running operation can rollback")
        return replace(self, state=OperationState.ROLLED_BACK)
