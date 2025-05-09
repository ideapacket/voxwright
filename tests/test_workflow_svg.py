"""Tests for deterministic workflow diagrams."""

from __future__ import annotations

from voxwright.identifiers import Identifier
from voxwright.workflow import StepKind, WorkflowDefinition, WorkflowStep
from voxwright.workflow_svg import workflow_svg


def test_svg_export_is_deterministic_and_self_contained() -> None:
    definition = WorkflowDefinition(
        Identifier("diagram"),
        1,
        Identifier("start"),
        (
            WorkflowStep(Identifier("start"), StepKind.ACTION, (Identifier("done"),)),
            WorkflowStep(Identifier("done"), StepKind.END),
        ),
    )
    first = workflow_svg(definition)
    assert first == workflow_svg(definition)
    assert first.startswith('<svg xmlns="http://www.w3.org/2000/svg"')
    assert first.endswith("</svg>\n")
    assert "start [action]" in first and "done [end]" in first


def test_svg_export_escapes_labels() -> None:
    definition = WorkflowDefinition(
        Identifier("safe"),
        1,
        Identifier("start"),
        (WorkflowStep(Identifier("start"), StepKind.END),),
    )
    assert "<script" not in workflow_svg(definition)
