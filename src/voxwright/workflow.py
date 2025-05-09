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


def validate_acyclic(definition: WorkflowDefinition) -> None:
    """Reject cycles unless their back edge originates at a bounded loop node."""
    graph = definition.step_map
    visiting: set[Identifier] = set()
    visited: set[Identifier] = set()

    def visit(node: Identifier) -> None:
        if node in visiting:
            raise ValueError(f"unbounded workflow cycle at {node}")
        if node in visited:
            return
        visiting.add(node)
        current = graph[node]
        for target in current.next_steps:
            if current.kind is StepKind.LOOP and target in visiting:
                continue
            visit(target)
        visiting.remove(node)
        visited.add(node)

    visit(definition.start)


def preconditions_met(step: WorkflowStep, state: dict[str, JSONValue]) -> bool:
    """Evaluate exact-match preconditions without truthy coercion."""
    for name, expected in (step.preconditions or {}).items():
        if name not in state:
            return False
        actual = state[name]
        if type(actual) is not type(expected) or actual != expected:
            return False
    return True


def apply_effects(step: WorkflowStep, state: dict[str, JSONValue]) -> dict[str, JSONValue]:
    """Return a copied state with deterministic shallow effects."""
    result = dict(state)
    result.update(step.effects or {})
    return result


@dataclass(frozen=True, slots=True)
class ExecutionResult:
    state: dict[str, JSONValue]
    visited: tuple[Identifier, ...]


def run_linear(
    definition: WorkflowDefinition, initial: dict[str, JSONValue] | None = None
) -> ExecutionResult:
    """Execute action chains until an end node using deterministic successor order."""
    validate_references(definition)
    validate_acyclic(definition)
    state = dict(initial or {})
    visited: list[Identifier] = []
    current = definition.start
    while True:
        item = definition.step_map[current]
        if not preconditions_met(item, state):
            raise RuntimeError(f"step precondition failed: {item.step_id}")
        visited.append(current)
        state = apply_effects(item, state)
        if item.kind is StepKind.END or not item.next_steps:
            break
        if item.kind is not StepKind.ACTION:
            raise RuntimeError(f"run_linear cannot execute {item.kind.value} step")
        current = item.next_steps[0]
    return ExecutionResult(state, tuple(visited))


def branch_target(step: WorkflowStep, state: dict[str, JSONValue]) -> Identifier:
    """Choose true then false successor from a branch precondition."""
    if step.kind is not StepKind.BRANCH or len(step.next_steps) != 2:
        raise ValueError("branch target requires a two-way branch step")
    return step.next_steps[0 if preconditions_met(step, state) else 1]


def loop_target(step: WorkflowStep, iteration: int) -> Identifier:
    """Choose body then exit using an explicit zero-based iteration counter."""
    if step.kind is not StepKind.LOOP or len(step.next_steps) != 2:
        raise ValueError("loop target requires a two-way loop step")
    if iteration < 0:
        raise ValueError("loop iteration cannot be negative")
    return step.next_steps[0 if iteration < step.max_iterations else 1]


def parallel_order(step: WorkflowStep) -> tuple[Identifier, ...]:
    """Return fan-out targets in declared order after duplicate rejection."""
    if step.kind is not StepKind.PARALLEL or not step.next_steps:
        raise ValueError("parallel order requires a fan-out step")
    if len(set(step.next_steps)) != len(step.next_steps):
        raise ValueError("parallel fan-out targets must be unique")
    return step.next_steps


def compensate(
    completed: tuple[WorkflowStep, ...], state: dict[str, JSONValue]
) -> tuple[dict[str, JSONValue], tuple[Identifier, ...]]:
    """Apply compensation effects in reverse completion order."""
    result = dict(state)
    compensated: list[Identifier] = []
    for item in reversed(completed):
        if item.compensation is not None:
            result.update(item.compensation)
            compensated.append(item.step_id)
    return result, tuple(compensated)
