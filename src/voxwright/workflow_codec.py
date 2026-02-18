"""Strict deterministic codec for the versioned workflow DSL."""

from __future__ import annotations

from voxwright.core import JSONValue
from voxwright.workflow import WorkflowStep


def step_to_dict(step: WorkflowStep) -> dict[str, JSONValue]:
    """Encode every step field so defaults remain visible in reviewed artifacts."""
    return {
        "id": str(step.step_id),
        "kind": step.kind.value,
        "next": [str(target) for target in step.next_steps],
        "preconditions": step.preconditions,
        "effects": step.effects,
        "compensation": step.compensation,
        "max_iterations": step.max_iterations,
    }
