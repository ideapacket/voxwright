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
