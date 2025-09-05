"""Metrics against planted ground truth in offline synthetic scenarios."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

from voxwright.core import JSONValue

METRIC_SCHEMA_VERSION = 1


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
        for label, text_value in (
            ("run id", self.run_id),
            ("task type", self.task_type),
            ("difficulty", self.difficulty),
        ):
            if not text_value.strip():
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
        for label, numeric_value in (
            ("turns", self.turns),
            ("repairs", self.repairs),
            ("false executes", self.false_executes),
            ("latency", self.latency_ms),
            ("latency budget", self.latency_budget_ms),
        ):
            if isinstance(numeric_value, bool) or numeric_value < 0:
                raise ValueError(f"evaluation {label} must be a non-negative integer")
        if self.turns == 0:
            raise ValueError("evaluation turns must be positive")
        if self.repairs > self.turns:
            raise ValueError("evaluation repairs cannot exceed turns")


@dataclass(frozen=True, slots=True)
class SlotScore:
    correct: int
    expected: int
    predicted: int
    accuracy: float


def task_success_rate(runs: tuple[EvaluationRun, ...]) -> float:
    """Return the fraction of planted goals reported satisfied."""
    if not runs:
        raise ValueError("task success requires at least one run")
    return round(sum(run.goal_satisfied for run in runs) / len(runs), 6)


def slot_score(runs: tuple[EvaluationRun, ...]) -> SlotScore:
    """Score exact key/value slot matches against planted values."""
    if not runs:
        raise ValueError("slot score requires at least one run")
    expected = sum(len(run.expected_slots) for run in runs)
    predicted = sum(len(run.predicted_slots) for run in runs)
    correct = sum(
        value == run.predicted_slots.get(name)
        for run in runs
        for name, value in run.expected_slots.items()
    )
    accuracy = (1.0 if predicted == 0 else 0.0) if expected == 0 else correct / expected
    return SlotScore(correct, expected, predicted, round(accuracy, 6))


@dataclass(frozen=True, slots=True)
class ToolScore:
    true_positive: int
    false_positive: int
    false_negative: int
    precision: float
    recall: float
    f1: float


def tool_score(runs: tuple[EvaluationRun, ...]) -> ToolScore:
    """Compute multiset tool-selection precision, recall, and F1."""
    if not runs:
        raise ValueError("tool score requires at least one run")
    pairs = tuple((Counter(run.expected_tools), Counter(run.selected_tools)) for run in runs)
    true_positive = sum(sum((expected & selected).values()) for expected, selected in pairs)
    false_positive = sum(sum((selected - expected).values()) for expected, selected in pairs)
    false_negative = sum(sum((expected - selected).values()) for expected, selected in pairs)
    precision_denominator = true_positive + false_positive
    recall_denominator = true_positive + false_negative
    precision = true_positive / precision_denominator if precision_denominator else 1.0
    recall = true_positive / recall_denominator if recall_denominator else 1.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return ToolScore(
        true_positive,
        false_positive,
        false_negative,
        round(precision, 6),
        round(recall, 6),
        round(f1, 6),
    )


@dataclass(frozen=True, slots=True)
class EfficiencyScore:
    mean_turns: float
    repair_rate: float
    false_execute_count: int
    latency_adherence: float


def efficiency_score(runs: tuple[EvaluationRun, ...]) -> EfficiencyScore:
    """Aggregate application turns, repair use, safety errors, and latency."""
    if not runs:
        raise ValueError("efficiency score requires at least one run")
    total_turns = sum(run.turns for run in runs)
    repairs = sum(run.repairs for run in runs)
    adherent = sum(run.latency_ms <= run.latency_budget_ms for run in runs)
    return EfficiencyScore(
        mean_turns=round(total_turns / len(runs), 6),
        repair_rate=round(repairs / total_turns, 6),
        false_execute_count=sum(run.false_executes for run in runs),
        latency_adherence=round(adherent / len(runs), 6),
    )


@dataclass(frozen=True, slots=True)
class MetricBundle:
    run_count: int
    task_success: float
    slots: SlotScore
    tools: ToolScore
    efficiency: EfficiencyScore

    def to_dict(self) -> dict[str, JSONValue]:
        return {
            "schema_version": METRIC_SCHEMA_VERSION,
            "run_count": self.run_count,
            "task_success": self.task_success,
            "slots": {
                "correct": self.slots.correct,
                "expected": self.slots.expected,
                "predicted": self.slots.predicted,
                "accuracy": self.slots.accuracy,
            },
            "tools": {
                "true_positive": self.tools.true_positive,
                "false_positive": self.tools.false_positive,
                "false_negative": self.tools.false_negative,
                "precision": self.tools.precision,
                "recall": self.tools.recall,
                "f1": self.tools.f1,
            },
            "efficiency": {
                "mean_turns": self.efficiency.mean_turns,
                "repair_rate": self.efficiency.repair_rate,
                "false_execute_count": self.efficiency.false_execute_count,
                "latency_adherence": self.efficiency.latency_adherence,
            },
        }


def score_runs(runs: tuple[EvaluationRun, ...]) -> MetricBundle:
    """Produce the complete public metric bundle for an executed campaign."""
    if not runs:
        raise ValueError("campaign scoring requires at least one run")
    return MetricBundle(
        len(runs),
        task_success_rate(runs),
        slot_score(runs),
        tool_score(runs),
        efficiency_score(runs),
    )
