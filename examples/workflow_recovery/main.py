"""Render and execute a deterministic synthetic application workflow."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path

from voxwright.core import canonical_json
from voxwright.identifiers import Identifier
from voxwright.workflow import StepKind, WorkflowDefinition, WorkflowStep, run_linear
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


def run(output: Path) -> dict[str, object]:
    output.mkdir()
    definition = example_workflow()
    result = run_linear(definition)
    (output / "workflow.svg").write_text(workflow_svg(definition), encoding="utf-8", newline="\n")
    summary: dict[str, object] = {
        "final_state": result.state,
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
