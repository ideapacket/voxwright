"""Versioned artifacts for deterministic logical-clock runtime turns."""

from __future__ import annotations

from voxwright.core import JSONValue, canonical_json, parse_json
from voxwright.runtime import LatencySample, LatencyStage, LatencyTrace, RuntimeTurn, StreamBlock


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


def block_to_dict(block: StreamBlock) -> dict[str, JSONValue]:
    return {
        "sequence": block.sequence,
        "received_at_ms": block.received_at_ms,
        "duration_ms": block.duration_ms,
        "final": block.final,
    }


def block_from_dict(value: JSONValue, path: str = "$.block") -> StreamBlock:
    fields = {"sequence", "received_at_ms", "duration_ms", "final"}
    if not isinstance(value, dict) or set(value) != fields:
        raise ValueError(f"{path}: expected exact stream block fields")
    integers: list[int] = []
    for field in ("sequence", "received_at_ms", "duration_ms"):
        item = value[field]
        if isinstance(item, bool) or not isinstance(item, int):
            raise TypeError(f"{path}.{field}: expected integer")
        integers.append(item)
    final = value["final"]
    if not isinstance(final, bool):
        raise TypeError(f"{path}.final: expected boolean")
    return StreamBlock(*integers, final)


def turn_to_dict(turn: RuntimeTurn) -> dict[str, JSONValue]:
    return {
        "block": block_to_dict(turn.block),
        "samples": [sample_to_dict(item) for item in turn.trace.samples],
    }


def turn_from_dict(value: JSONValue, path: str = "$.turn") -> RuntimeTurn:
    if not isinstance(value, dict) or set(value) != {"block", "samples"}:
        raise ValueError(f"{path}: expected exact runtime turn fields")
    samples = value["samples"]
    if not isinstance(samples, list):
        raise TypeError(f"{path}.samples: expected array")
    trace = LatencyTrace(
        tuple(
            sample_from_dict(item, f"{path}.samples[{index}]") for index, item in enumerate(samples)
        )
    )
    return RuntimeTurn(block_from_dict(value["block"], f"{path}.block"), trace)


def runtime_to_dict(turns: tuple[RuntimeTurn, ...]) -> dict[str, JSONValue]:
    if not turns:
        raise ValueError("runtime artifact requires at least one turn")
    return {"schema_version": 1, "turns": [turn_to_dict(item) for item in turns]}


def runtime_from_dict(value: JSONValue) -> tuple[RuntimeTurn, ...]:
    if not isinstance(value, dict) or set(value) != {"schema_version", "turns"}:
        raise ValueError("$: expected exact runtime artifact fields")
    if value["schema_version"] != 1 or isinstance(value["schema_version"], bool):
        raise ValueError(f"$.schema_version: unsupported version {value['schema_version']!r}")
    turns = value["turns"]
    if not isinstance(turns, list) or not turns:
        raise ValueError("$.turns: expected nonempty array")
    return tuple(turn_from_dict(item, f"$.turns[{index}]") for index, item in enumerate(turns))


def encode_runtime(turns: tuple[RuntimeTurn, ...]) -> str:
    return canonical_json(runtime_to_dict(turns)) + "\n"


def decode_runtime(text: str) -> tuple[RuntimeTurn, ...]:
    if not text.strip():
        raise ValueError("runtime artifact document is empty")
    return runtime_from_dict(parse_json(text))
