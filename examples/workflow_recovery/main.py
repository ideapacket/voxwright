"""Render and execute a deterministic synthetic application workflow."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path

from voxwright.core import JSONValue, canonical_json
from voxwright.identifiers import Identifier
from voxwright.workflow import (
    StepKind,
    WorkflowDefinition,
    WorkflowStep,
    apply_effects,
    compensate,
    run_linear,
)
from voxwright.workflow_ledger import WorkflowLedger, remaining_steps
from voxwright.workflow_svg import workflow_svg


def example_workflow() -> WorkflowDefinition:
    reserve = WorkflowStep(
        Identifier("reserve"),
        StepKind.ACTION,
        (Identifier("charge"),),
        effects={"reserved": True},
        compensation={"reserved": False},
    )
    charge = WorkflowStep(
        Identifier("charge"),
        StepKind.ACTION,
        (Identifier("finish"),),
        preconditions={"reserved": True},
        effects={"charged": True},
        compensation={"charged": False},
    )
    finish = WorkflowStep(
        Identifier("finish"),
        StepKind.END,
        preconditions={"charged": True},
        effects={"complete": True},
    )
    return WorkflowDefinition(
        Identifier("synthetic-purchase"), 1, Identifier("reserve"), (reserve, charge, finish)
    )


def resume_after_crash(
    definition: WorkflowDefinition,
) -> tuple[dict[str, JSONValue], tuple[Identifier, ...], str]:
    """Simulate a crash after the first committed step, then resume its suffix."""
    order = tuple(step.step_id for step in definition.steps)
    ledger = WorkflowLedger()
    first = definition.step_map[order[0]]
    state = apply_effects(first, {})
    ledger.record(first.step_id, state)
    checkpoint = ledger.checkpoint()
    stored_state = checkpoint["state"]
    if not isinstance(stored_state, dict):
        raise RuntimeError("checkpoint state is not an object")
    resumed = dict(stored_state)
    suffix = remaining_steps(order, checkpoint)
    for step_id in suffix:
        step = definition.step_map[step_id]
        resumed = apply_effects(step, resumed)
        ledger.record(step_id, resumed)
    digest = checkpoint["digest"]
    if not isinstance(digest, str):
        raise RuntimeError("checkpoint digest is not text")
    return resumed, suffix, digest


def simulate_failed_charge(
    definition: WorkflowDefinition,
) -> tuple[dict[str, JSONValue], tuple[Identifier, ...]]:
    """Apply two side effects, then compensate them in reverse order."""
    completed = definition.steps[:2]
    state: dict[str, JSONValue] = {}
    for step in completed:
        state = apply_effects(step, state)
    return compensate(completed, state)


def run(output: Path) -> dict[str, object]:
    output.mkdir()
    definition = example_workflow()
    result = run_linear(definition)
    resumed_state, resumed_steps, checkpoint_digest = resume_after_crash(definition)
    rolled_back, compensated_steps = simulate_failed_charge(definition)
    if canonical_json(resumed_state) != canonical_json(result.state):
        raise RuntimeError("resumed state differs from straight execution")
    (output / "workflow.svg").write_text(workflow_svg(definition), encoding="utf-8", newline="\n")
    summary: dict[str, object] = {
        "final_state": result.state,
        "checkpoint_digest": checkpoint_digest,
        "resume_matches_straight": True,
        "resumed_steps": [str(step) for step in resumed_steps],
        "rollback_state": rolled_back,
        "compensated_steps": [str(step) for step in compensated_steps],
        "synthetic": True,
        "visited": [str(step) for step in result.visited],
        "workflow": str(definition.name),
        "workflow_version": definition.version,
    }
    (output / "summary.json").write_text(
        canonical_json(summary) + "\n", encoding="utf-8", newline="\n"
    )
    return summary


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args(argv)
    print(canonical_json(run(args.output)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
