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


class InterruptResolution(str, Enum):
    CANCELLED = "cancelled"
    QUEUED = "queued"
    FINISHED = "finished"
    ROLLED_BACK = "rolled-back"


def resolve_interrupt(
    operation: InFlightOperation, policy: BargePolicy
) -> tuple[InFlightOperation, InterruptResolution]:
    """Resolve one interrupt using tool idempotency and explicit policy."""
    if operation.state is not OperationState.RUNNING:
        raise ValueError("barge-in requires a running operation")
    if policy is BargePolicy.QUEUE:
        return operation, InterruptResolution.QUEUED
    if policy is BargePolicy.CANCEL:
        if operation.idempotent:
            return operation.cancel(), InterruptResolution.CANCELLED
        return operation.rollback(), InterruptResolution.ROLLED_BACK
    if operation.idempotent:
        return operation.complete(), InterruptResolution.FINISHED
    return operation.rollback(), InterruptResolution.ROLLED_BACK


@dataclass(frozen=True, order=True, slots=True)
class Interrupt:
    """A logically timed user interrupt ordered without wall-clock races."""

    at_ms: int
    sequence: int
    interrupt_id: Identifier
    transcript: str

    def __post_init__(self) -> None:
        if self.at_ms < 0 or self.sequence < 0:
            raise ValueError("interrupt time and sequence must be non-negative")
        if not self.transcript:
            raise ValueError("interrupt transcript cannot be empty")


def order_interrupts(interrupts: tuple[Interrupt, ...]) -> tuple[Interrupt, ...]:
    """Resolve races by logical instant, sequence, then stable identifier."""
    return tuple(sorted(interrupts))


@dataclass(slots=True)
class InterruptManager:
    """Track one operation and a deterministic queue of pending interrupts."""

    operation: InFlightOperation
    policy: BargePolicy
    queued: list[Interrupt]

    def __init__(self, operation: InFlightOperation, policy: BargePolicy) -> None:
        if operation.state is not OperationState.RUNNING:
            raise ValueError("interrupt manager requires running operation")
        self.operation = operation
        self.policy = policy
        self.queued = []

    def interrupt(self, item: Interrupt) -> InterruptResolution:
        operation, resolution = resolve_interrupt(self.operation, self.policy)
        self.operation = operation
        if resolution is InterruptResolution.QUEUED:
            self.queued.append(item)
            self.queued[:] = order_interrupts(tuple(self.queued))
        return resolution
