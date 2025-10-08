from __future__ import annotations

import json

import pytest

from voxwright.evaluation import EvaluationRun
from voxwright.run_artifacts import (
    decode_runs,
    encode_runs,
    run_from_dict,
    run_to_dict,
    scripted_run,
)
from voxwright.scenarios import schedule_scenario


def observed_run() -> EvaluationRun:
    return EvaluationRun(
        "run-1",
        "notes",
        "easy",
        0.1,
        {"text": "milk"},
        {"text": "milk"},
        ("notes.add",),
        ("notes.add",),
        True,
        2,
        1,
        0,
        80,
        100,
    )


def test_run_artifact_roundtrips_every_observed_field() -> None:
    assert run_from_dict(run_to_dict(observed_run())) == observed_run()


def test_run_decoder_rejects_schema_and_nested_type_drift() -> None:
    value = run_to_dict(observed_run())
    value["extra"] = True
    with pytest.raises(ValueError, match="invalid evaluation run shape"):
        run_from_dict(value)


def test_run_jsonl_is_checksummed_and_replayable() -> None:
    runs = (observed_run(), observed_run())
    encoded = encode_runs(runs)
    assert encoded.count("\n") == 2
    assert '"checksum":"sha256:' in encoded
    assert decode_runs(encoded) == runs


def test_run_stream_detects_tampering_and_truncation() -> None:
    value = json.loads(encode_runs((observed_run(),)))
    value["run"]["goal_satisfied"] = False
    with pytest.raises(ValueError, match="checksum mismatch"):
        decode_runs(json.dumps(value) + "\n")
    with pytest.raises(ValueError, match="incomplete line"):
        decode_runs(encode_runs((observed_run(),)).rstrip())


def test_scripted_run_copies_only_planted_synthetic_truth() -> None:
    scenario = schedule_scenario(7)
    run = scripted_run(scenario)
    assert run.run_id == str(scenario.scenario_id)
    assert run.expected_slots == run.predicted_slots
    assert run.expected_tools == run.selected_tools
    assert run.goal_satisfied and run.false_executes == 0


def test_scripted_run_latency_and_repairs_come_from_fixture_facts() -> None:
    clean = scripted_run(schedule_scenario(3))
    assert clean.latency_ms == 40 + schedule_scenario(3).difficulty * 10
    assert clean.latency_budget_ms == 120
    assert clean.repairs == 0
    value = run_to_dict(observed_run())
    value["expected_slots"] = {"text": 1}
    with pytest.raises(TypeError, match="expected slots"):
        run_from_dict(value)
    value = run_to_dict(observed_run())
    value["selected_tools"] = "notes.add"
    with pytest.raises(TypeError, match="selected tools"):
        run_from_dict(value)
