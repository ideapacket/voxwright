"""Versioned artifacts for deterministic logical-clock runtime turns."""

from __future__ import annotations

from voxwright.core import JSONValue
from voxwright.runtime import LatencySample, LatencyStage


def sample_to_dict(sample: LatencySample) -> dict[str, JSONValue]:
    return {
        "stage": sample.stage.value,
        "started_ms": sample.started_ms,
        "ended_ms": sample.ended_ms,
    }


def sample_from_dict(value: JSONValue, path: str = "$.sample") -> LatencySample:
    if not isinstance(value, dict) or set(value) != {"stage", "started_ms", "ended_ms"}:
        raise ValueError(f"{path}: expected exact latency sample fields")
    stage = value["stage"]
    started = value["started_ms"]
    ended = value["ended_ms"]
    if not isinstance(stage, str):
        raise TypeError(f"{path}.stage: expected string")
    if any(isinstance(item, bool) or not isinstance(item, int) for item in (started, ended)):
        raise TypeError(f"{path}: logical times must be integers")
    try:
        latency_stage = LatencyStage(stage)
    except ValueError as error:
        raise ValueError(f"{path}.stage: unknown latency stage {stage!r}") from error
    return LatencySample(latency_stage, started, ended)
