"""Evaluation slices and reproducible synthetic campaign artifacts."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from voxwright.evaluation import EvaluationRun, MetricBundle, score_runs


class SliceDimension(str, Enum):
    TASK_TYPE = "task_type"
    DIFFICULTY = "difficulty"


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
    labels = {
        run.task_type if dimension is SliceDimension.TASK_TYPE else run.difficulty for run in runs
    }
    slices: list[CampaignSlice] = []
    for label in sorted(labels):
        selected = tuple(
            run
            for run in runs
            if (run.task_type if dimension is SliceDimension.TASK_TYPE else run.difficulty) == label
        )
        slices.append(
            CampaignSlice(
                dimension,
                label,
                tuple(run.run_id for run in selected),
                score_runs(selected),
            )
        )
    return tuple(slices)
