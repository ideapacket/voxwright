"""Deterministic SVG export for workflow definitions."""

from __future__ import annotations

import html

from voxwright.workflow import WorkflowDefinition


def workflow_svg(definition: WorkflowDefinition) -> str:
    """Render nodes in declaration order with escaped labels and fixed geometry."""
    width = 240
    height = 80 * len(definition.steps) + 20
    lines = [
        (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
            f'viewBox="0 0 {width} {height}">'
        ),
        "<style>text{font:12px sans-serif}.node{fill:#eef;stroke:#335}</style>",
    ]
    for index, item in enumerate(definition.steps):
        y = 20 + index * 80
        lines.append(f'<rect class="node" x="20" y="{y}" width="200" height="40" rx="6"/>')
        label = html.escape(f"{item.step_id} [{item.kind.value}]")
        lines.append(f'<text x="30" y="{y + 25}">{label}</text>')
        if index + 1 < len(definition.steps):
            lines.append(f'<path d="M120 {y + 40} V{y + 80}" stroke="#335"/>')
    lines.append("</svg>")
    return "\n".join(lines) + "\n"
