"""Strict deterministic codec for the versioned workflow DSL."""

from __future__ import annotations

from voxwright.core import JSONValue
from voxwright.identifiers import Identifier
from voxwright.workflow import StepKind, WorkflowStep

STEP_FIELDS = frozenset(
    {"id", "kind", "next", "preconditions", "effects", "compensation", "max_iterations"}
)


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


def _optional_object(value: JSONValue, path: str) -> dict[str, JSONValue] | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        raise TypeError(f"{path}: expected object or null")
    return value


def step_from_dict(value: JSONValue, path: str = "$.step") -> WorkflowStep:
    """Decode one strict step object with path-oriented diagnostics."""
    if not isinstance(value, dict):
        raise TypeError(f"{path}: expected object")
    fields = set(value)
    if fields != STEP_FIELDS:
        missing = sorted(STEP_FIELDS - fields)
        unknown = sorted(fields - STEP_FIELDS)
        raise ValueError(f"{path}: fields differ; missing={missing}; unknown={unknown}")
    identifier = value["id"]
    kind = value["kind"]
    successors = value["next"]
    iterations = value["max_iterations"]
    if not isinstance(identifier, str):
        raise TypeError(f"{path}.id: expected string")
    if not isinstance(kind, str):
        raise TypeError(f"{path}.kind: expected string")
    if not isinstance(successors, list) or not all(isinstance(item, str) for item in successors):
        raise TypeError(f"{path}.next: expected string array")
    if isinstance(iterations, bool) or not isinstance(iterations, int):
        raise TypeError(f"{path}.max_iterations: expected integer")
    try:
        step_kind = StepKind(kind)
    except ValueError as error:
        raise ValueError(f"{path}.kind: unknown step kind {kind!r}") from error
    return WorkflowStep(
        Identifier(identifier),
        step_kind,
        tuple(Identifier(item) for item in successors),
        _optional_object(value["preconditions"], f"{path}.preconditions"),
        _optional_object(value["effects"], f"{path}.effects"),
        _optional_object(value["compensation"], f"{path}.compensation"),
        iterations,
    )
