"""Deterministic Markdown, HTML, and SVG reports for executed campaigns."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CoverageFacts:
    """Facts about what an offline campaign actually exercised."""

    scenario_count: int
    task_types: tuple[str, ...]
    adapter_names: tuple[str, ...]
    used_real_audio: bool = False
    used_model_endpoint: bool = False

    def __post_init__(self) -> None:
        if isinstance(self.scenario_count, bool) or self.scenario_count < 0:
            raise ValueError("coverage scenario count must be a non-negative integer")
        for label, values in (("task type", self.task_types), ("adapter", self.adapter_names)):
            if any(not value.strip() for value in values):
                raise ValueError(f"coverage {label} names cannot be empty")
            if len(set(values)) != len(values):
                raise ValueError(f"coverage {label} names must be unique")


def coverage_limitations(facts: CoverageFacts) -> tuple[str, ...]:
    """Generate honest limitations directly from recorded coverage facts."""
    items = [f"Metrics cover {facts.scenario_count} seeded synthetic scenarios with planted truth."]
    if not facts.used_real_audio:
        items.append("No real speech recording was evaluated.")
    if not facts.used_model_endpoint:
        items.append("No actual spoken-model endpoint was evaluated.")
    if not facts.task_types:
        items.append("No task type was represented in this campaign.")
    if not facts.adapter_names:
        items.append("No adapter execution was represented in this campaign.")
    return tuple(items)
