"""Strict deterministic codec for the versioned workflow DSL."""

from __future__ import annotations

from voxwright.core import JSONValue
from voxwright.identifiers import Identifier
from voxwright.workflow import (
    StepKind,
    WorkflowDefinition,
    WorkflowStep,
    validate_acyclic,
    validate_references,
)

STEP_FIELDS = frozenset(
    {"id", "kind", "next", "preconditions", "effects", "compensation", "max_iterations"}
)
WORKFLOW_FIELDS = frozenset({"schema_version", "name", "version", "start", "steps"})


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


def workflow_to_dict(definition: WorkflowDefinition) -> dict[str, JSONValue]:
    """Encode the complete graph in declared deterministic step order."""
    return {
        "schema_version": 1,
        "name": str(definition.name),
        "version": definition.version,
        "start": str(definition.start),
        "steps": [step_to_dict(step) for step in definition.steps],
    }


def workflow_from_dict(value: JSONValue) -> WorkflowDefinition:
    """Decode a graph only after strict envelope and graph validation."""
    if not isinstance(value, dict):
        raise TypeError("$: expected workflow object")
    fields = set(value)
    if fields != WORKFLOW_FIELDS:
        missing = sorted(WORKFLOW_FIELDS - fields)
        unknown = sorted(fields - WORKFLOW_FIELDS)
        raise ValueError(f"$: workflow fields differ; missing={missing}; unknown={unknown}")
    schema_version = value["schema_version"]
    version = value["version"]
    name = value["name"]
    start = value["start"]
    steps = value["steps"]
    if schema_version != 1 or isinstance(schema_version, bool):
        raise ValueError(f"$.schema_version: unsupported version {schema_version!r}")
    if isinstance(version, bool) or not isinstance(version, int):
        raise TypeError("$.version: expected integer")
    if not isinstance(name, str) or not isinstance(start, str):
        raise TypeError("$.name and $.start: expected strings")
    if not isinstance(steps, list) or not steps:
        raise ValueError("$.steps: expected nonempty array")
    definition = WorkflowDefinition(
        Identifier(name),
        version,
        Identifier(start),
        tuple(step_from_dict(item, f"$.steps[{index}]") for index, item in enumerate(steps)),
    )
    validate_references(definition)
    validate_acyclic(definition)
    return definition
