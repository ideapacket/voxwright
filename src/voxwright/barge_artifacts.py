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


def checkpoint_manager(manager: InterruptManager) -> BargeCheckpoint:
    """Capture an active manager without sharing its mutable queue."""
    return BargeCheckpoint(manager.operation, manager.policy, tuple(manager.queued))


def resume_manager(checkpoint: BargeCheckpoint) -> InterruptManager:
    """Restore a manager that can continue resolving or draining interrupts."""
    manager = InterruptManager(checkpoint.operation, checkpoint.policy)
    manager.queued.extend(checkpoint.queued)
    return manager
