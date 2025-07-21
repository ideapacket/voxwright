"""Evaluation slices and reproducible synthetic campaign artifacts."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from enum import Enum

from voxwright.core import JSONValue
from voxwright.evaluation import EvaluationRun, MetricBundle, score_runs
from voxwright.hashing import object_digest

CAMPAIGN_SCHEMA_VERSION = 1


class SliceDimension(str, Enum):
    TASK_TYPE = "task_type"
    DIFFICULTY = "difficulty"
    NOISE_BAND = "noise_band"


def noise_band(noise_rate: float) -> str:
    """Map a validated noise rate to a documented campaign band."""
    if not 0.0 <= noise_rate <= 1.0:
        raise ValueError("noise rate must be between 0 and 1")
    if noise_rate < 0.2:
        return "low"
    if noise_rate < 0.5:
        return "medium"
    return "high"


def _slice_label(run: EvaluationRun, dimension: SliceDimension) -> str:
    if dimension is SliceDimension.TASK_TYPE:
        return run.task_type
    if dimension is SliceDimension.DIFFICULTY:
        return run.difficulty
    return noise_band(run.noise_rate)


@dataclass(frozen=True, slots=True)
class CampaignSlice:
    dimension: SliceDimension
    label: str
    run_ids: tuple[str, ...]
    metrics: MetricBundle


def slice_campaign(
    runs: tuple[EvaluationRun, ...], dimension: SliceDimension
) -> tuple[CampaignSlice, ...]:
    """Partition campaign runs and score slices in stable label order."""
    if not runs:
        raise ValueError("campaign slicing requires at least one run")
    labels = {_slice_label(run, dimension) for run in runs}
    slices: list[CampaignSlice] = []
    for label in sorted(labels):
        selected = tuple(run for run in runs if _slice_label(run, dimension) == label)
        slices.append(
            CampaignSlice(
                dimension,
                label,
                tuple(run.run_id for run in selected),
                score_runs(selected),
            )
        )
    return tuple(slices)


@dataclass(frozen=True, slots=True)
class NamedSlotScore:
    name: str
    correct: int
    expected: int
    predicted: int
    accuracy: float


def slot_breakdown(runs: tuple[EvaluationRun, ...]) -> tuple[NamedSlotScore, ...]:
    """Explain exact slot accuracy by planted slot name."""
    if not runs:
        raise ValueError("slot breakdown requires at least one run")
    names = sorted(
        {name for run in runs for name in (*run.expected_slots.keys(), *run.predicted_slots.keys())}
    )
    result: list[NamedSlotScore] = []
    for name in names:
        expected = sum(name in run.expected_slots for run in runs)
        predicted = sum(name in run.predicted_slots for run in runs)
        correct = sum(
            name in run.expected_slots and run.expected_slots[name] == run.predicted_slots.get(name)
            for run in runs
        )
        accuracy = correct / expected if expected else 0.0
        result.append(NamedSlotScore(name, correct, expected, predicted, round(accuracy, 6)))
    return tuple(result)


@dataclass(frozen=True, slots=True)
class NamedToolScore:
    name: str
    true_positive: int
    false_positive: int
    false_negative: int


def tool_breakdown(runs: tuple[EvaluationRun, ...]) -> tuple[NamedToolScore, ...]:
    """Explain multiset tool errors per tool without cross-run matching."""
    if not runs:
        raise ValueError("tool breakdown requires at least one run")
    names = sorted({name for run in runs for name in (*run.expected_tools, *run.selected_tools)})
    scores: list[NamedToolScore] = []
    for name in names:
        true_positive = false_positive = false_negative = 0
        for run in runs:
            expected = Counter(run.expected_tools)[name]
            selected = Counter(run.selected_tools)[name]
            true_positive += min(expected, selected)
            false_positive += max(0, selected - expected)
            false_negative += max(0, expected - selected)
        scores.append(NamedToolScore(name, true_positive, false_positive, false_negative))
    return tuple(scores)


@dataclass(frozen=True, slots=True)
class MetricDelta:
    task_success: float
    slot_accuracy: float
    tool_f1: float
    mean_turns: float
    repair_rate: float
    false_executes: int
    latency_adherence: float


def compare_metrics(baseline: MetricBundle, candidate: MetricBundle) -> MetricDelta:
    """Return candidate-minus-baseline deltas with production quantization."""
    return MetricDelta(
        task_success=round(candidate.task_success - baseline.task_success, 6),
        slot_accuracy=round(candidate.slots.accuracy - baseline.slots.accuracy, 6),
        tool_f1=round(candidate.tools.f1 - baseline.tools.f1, 6),
        mean_turns=round(candidate.efficiency.mean_turns - baseline.efficiency.mean_turns, 6),
        repair_rate=round(candidate.efficiency.repair_rate - baseline.efficiency.repair_rate, 6),
        false_executes=(
            candidate.efficiency.false_execute_count - baseline.efficiency.false_execute_count
        ),
        latency_adherence=round(
            candidate.efficiency.latency_adherence - baseline.efficiency.latency_adherence, 6
        ),
    )


@dataclass(frozen=True, slots=True)
class CampaignArtifact:
    name: str
    seed: int
    config: dict[str, JSONValue]
    metrics: MetricBundle

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("campaign name cannot be empty")
        if isinstance(self.seed, bool) or self.seed < 0:
            raise ValueError("campaign seed must be a non-negative integer")

    @property
    def config_digest(self) -> str:
        return object_digest(self.config)

    def to_dict(self) -> dict[str, JSONValue]:
        return {
            "schema_version": CAMPAIGN_SCHEMA_VERSION,
            "name": self.name,
            "seed": self.seed,
            "config": self.config,
            "config_digest": self.config_digest,
            "metrics": self.metrics.to_dict(),
        }
