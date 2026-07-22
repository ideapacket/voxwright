from __future__ import annotations

import pytest

from voxwright.runtime import LatencySample, LatencyStage, StreamBlock
from voxwright.runtime_artifacts import (
    block_from_dict,
    block_to_dict,
    sample_from_dict,
    sample_to_dict,
)


def test_latency_sample_artifact_roundtrips_logical_interval() -> None:
    sample = LatencySample(LatencyStage.DECISION, 10, 24)
    assert sample_to_dict(sample) == {"stage": "decision", "started_ms": 10, "ended_ms": 24}
    assert sample_from_dict(sample_to_dict(sample)) == sample


def test_latency_sample_decoder_rejects_stage_and_time_coercion() -> None:
    with pytest.raises(ValueError, match="unknown latency stage"):
        sample_from_dict({"stage": "network", "started_ms": 0, "ended_ms": 1})
    with pytest.raises(TypeError, match="logical times must be integers"):
        sample_from_dict({"stage": "tool", "started_ms": False, "ended_ms": 1})


def test_stream_block_artifact_roundtrips_arrival_and_finality() -> None:
    block = StreamBlock(2, 40, 20, True)
    assert block_from_dict(block_to_dict(block)) == block
    assert block_to_dict(block) == {
        "sequence": 2,
        "received_at_ms": 40,
        "duration_ms": 20,
        "final": True,
    }


def test_stream_block_decoder_rejects_boolean_integer_aliases() -> None:
    encoded = block_to_dict(StreamBlock(0, 0, 10))
    encoded["sequence"] = False
    with pytest.raises(TypeError, match="sequence: expected integer"):
        block_from_dict(encoded)
