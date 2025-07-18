"""Evaluation slices and reproducible synthetic campaign artifacts."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from voxwright.evaluation import EvaluationRun, MetricBundle, score_runs


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
