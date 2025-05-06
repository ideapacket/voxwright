"""Versioned deterministic workflow DSL for application orchestration."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from voxwright.core import JSONValue, ensure_json_value
from voxwright.identifiers import Identifier


class StepKind(str, Enum):
    ACTION = "action"
    BRANCH = "branch"
    LOOP = "loop"
    PARALLEL = "parallel"
    END = "end"


@dataclass(frozen=True, slots=True)
class WorkflowStep:
    """One node with conditions, effects, successors, and optional compensation."""

    step_id: Identifier
    kind: StepKind
    next_steps: tuple[Identifier, ...] = ()
    preconditions: dict[str, JSONValue] | None = None
    effects: dict[str, JSONValue] | None = None
    compensation: dict[str, JSONValue] | None = None
    max_iterations: int = 0

    def __post_init__(self) -> None:
        for field in ("preconditions", "effects", "compensation"):
            value = getattr(self, field)
            if value is not None:
                checked = ensure_json_value(value, f"$.{field}")
                if not isinstance(checked, dict):
                    raise TypeError(f"$.{field}: expected object")
                object.__setattr__(self, field, checked)
        if self.kind is StepKind.LOOP and self.max_iterations < 1:
            raise ValueError("loop step requires a positive iteration bound")
        if self.kind is not StepKind.LOOP and self.max_iterations:
            raise ValueError("only loop step can declare iteration bound")
        if self.kind is StepKind.END and self.next_steps:
            raise ValueError("end step cannot have successors")


@dataclass(frozen=True, slots=True)
class WorkflowDefinition:
    """A named, versioned graph with a single explicit entry step."""

    name: Identifier
    version: int
    start: Identifier
    steps: tuple[WorkflowStep, ...]

    def __post_init__(self) -> None:
        if self.version < 1:
            raise ValueError("workflow version must be positive")
        by_id = {item.step_id: item for item in self.steps}
        if len(by_id) != len(self.steps):
            raise ValueError("workflow step identifiers must be unique")
        if self.start not in by_id:
            raise ValueError(f"workflow start step does not exist: {self.start}")

    @property
    def step_map(self) -> dict[Identifier, WorkflowStep]:
        return {item.step_id: item for item in self.steps}


def validate_references(definition: WorkflowDefinition) -> None:
    """Reject dangling targets and kind-specific successor arity errors."""
    known = definition.step_map
    for item in definition.steps:
        for target in item.next_steps:
            if target not in known:
                raise ValueError(f"step {item.step_id}: dangling reference {target}")
        expected = {
            StepKind.ACTION: {0, 1},
            StepKind.BRANCH: {2},
            StepKind.LOOP: {2},
            StepKind.PARALLEL: set(range(1, 1000)),
            StepKind.END: {0},
        }[item.kind]
        if len(item.next_steps) not in expected:
            raise ValueError(f"step {item.step_id}: invalid successor count for {item.kind.value}")
