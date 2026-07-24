from __future__ import annotations

from pathlib import Path

import pytest

from voxwright.runtime import LatencySample, LatencyStage, LatencyTrace, RuntimeTurn, StreamBlock
from voxwright.runtime_artifacts import (
    block_from_dict,
    block_to_dict,
    decode_runtime,
    encode_runtime,
    load_runtime,
    runtime_digest,
    sample_from_dict,
    sample_to_dict,
    turn_from_dict,
    turn_to_dict,
    write_runtime,
)

GOLDEN = Path(__file__).parent / "golden" / "runtime_turns.json"


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


def test_runtime_turn_codec_preserves_stage_order_and_idle_gaps() -> None:
    trace = LatencyTrace(
        (
            LatencySample(LatencyStage.PERCEPTION, 10, 15),
            LatencySample(LatencyStage.DECISION, 18, 22),
        )
    )
    turn = RuntimeTurn(StreamBlock(0, 10, 5), trace)
    assert turn_from_dict(turn_to_dict(turn)) == turn
    assert turn_from_dict(turn_to_dict(turn)).trace.elapsed_ms == 12


def test_runtime_artifact_text_is_canonical_and_reversible() -> None:
    turn = RuntimeTurn(
        StreamBlock(0, 0, 10, True),
        LatencyTrace((LatencySample(LatencyStage.PERCEPTION, 0, 3),)),
    )
    encoded = encode_runtime((turn,))
    assert encoded.endswith("\n") and " " not in encoded
    assert decode_runtime(encoded) == (turn,)
    assert encode_runtime(decode_runtime(encoded)).encode() == encoded.encode()


def test_runtime_artifact_requires_nonempty_single_document() -> None:
    with pytest.raises(ValueError, match="at least one turn"):
        encode_runtime(())
    with pytest.raises(ValueError, match="document is empty"):
        decode_runtime("\n")
    with pytest.raises(ValueError):
        decode_runtime('{"schema_version":1,"turns":[]}{}')


def test_runtime_decoder_rejects_unknown_versions_and_field_drift() -> None:
    with pytest.raises(ValueError, match="unsupported version 2"):
        decode_runtime('{"schema_version":2,"turns":[{}]}')
    with pytest.raises(ValueError, match="exact runtime artifact fields"):
        decode_runtime('{"extra":1,"schema_version":1,"turns":[]}')


def test_runtime_decoder_enforces_trace_stage_order() -> None:
    turn = RuntimeTurn(
        StreamBlock(0, 0, 10),
        LatencyTrace((LatencySample(LatencyStage.PERCEPTION, 0, 2),)),
    )
    encoded = encode_runtime((turn,)).replace('"stage":"perception"', '"stage":"tool"')
    with pytest.raises(ValueError, match="stage order"):
        decode_runtime(encoded)


def test_runtime_decoder_reports_nested_block_paths() -> None:
    turn = RuntimeTurn(
        StreamBlock(0, 0, 10),
        LatencyTrace((LatencySample(LatencyStage.PERCEPTION, 0, 2),)),
    )
    encoded = encode_runtime((turn,)).replace('"duration_ms":10', '"duration_ms":true')
    with pytest.raises(TypeError, match=r"turns\[0\]\.block\.duration_ms"):
        decode_runtime(encoded)


def test_runtime_artifact_matches_reviewed_golden_bytes() -> None:
    turn = RuntimeTurn(
        StreamBlock(0, 0, 10, True),
        LatencyTrace((LatencySample(LatencyStage.PERCEPTION, 0, 3),)),
    )
    assert encode_runtime((turn,)).encode() == GOLDEN.read_bytes()
    assert decode_runtime(GOLDEN.read_text(encoding="utf-8")) == (turn,)


def test_runtime_files_are_complete_identified_and_nonclobbering(tmp_path: Path) -> None:
    turn = RuntimeTurn(
        StreamBlock(0, 0, 10, True),
        LatencyTrace((LatencySample(LatencyStage.PERCEPTION, 0, 3),)),
    )
    path = tmp_path / "runtime.json"
    write_runtime(path, (turn,))
    assert load_runtime(path) == (turn,)
    assert runtime_digest(load_runtime(path)) == runtime_digest((turn,))
    with pytest.raises(FileExistsError, match="output already exists"):
        write_runtime(path, (turn,))
    path.unlink()
    path.write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="missing terminal newline"):
        load_runtime(path)
