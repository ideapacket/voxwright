"""Metrics against planted ground truth in offline synthetic scenarios."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class EvaluationRun:
    """Observed application outcome paired with synthetic planted truth."""

    run_id: str
    task_type: str
    difficulty: str
    noise_rate: float
    expected_slots: dict[str, str]
    predicted_slots: dict[str, str]
    expected_tools: tuple[str, ...]
    selected_tools: tuple[str, ...]
    goal_satisfied: bool
    turns: int
    repairs: int
    false_executes: int
    latency_ms: int
    latency_budget_ms: int

    def __post_init__(self) -> None:
        for label, value in (
            ("run id", self.run_id),
            ("task type", self.task_type),
            ("difficulty", self.difficulty),
        ):
            if not value.strip():
                raise ValueError(f"evaluation {label} cannot be empty")
        if not 0.0 <= self.noise_rate <= 1.0:
            raise ValueError("evaluation noise rate must be between 0 and 1")
        if any(not name or not value for name, value in self.expected_slots.items()):
            raise ValueError("expected slot names and values cannot be empty")
        if any(not name or not value for name, value in self.predicted_slots.items()):
            raise ValueError("predicted slot names and values cannot be empty")
        if any(not name for name in (*self.expected_tools, *self.selected_tools)):
            raise ValueError("tool names cannot be empty")
        if not isinstance(self.goal_satisfied, bool):
            raise TypeError("goal_satisfied must be boolean")
        for label, value in (
            ("turns", self.turns),
            ("repairs", self.repairs),
            ("false executes", self.false_executes),
            ("latency", self.latency_ms),
            ("latency budget", self.latency_budget_ms),
        ):
            if isinstance(value, bool) or value < 0:
                raise ValueError(f"evaluation {label} must be a non-negative integer")
        if self.turns == 0:
            raise ValueError("evaluation turns must be positive")
        if self.repairs > self.turns:
            raise ValueError("evaluation repairs cannot exceed turns")
