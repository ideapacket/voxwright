from __future__ import annotations

import pytest

from voxwright.evaluation import EvaluationRun
from voxwright.run_artifacts import run_from_dict, run_to_dict


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
    value = run_to_dict(observed_run())
    value["expected_slots"] = {"text": 1}
    with pytest.raises(TypeError, match="expected slots"):
        run_from_dict(value)
    value = run_to_dict(observed_run())
    value["selected_tools"] = "notes.add"
    with pytest.raises(TypeError, match="selected tools"):
        run_from_dict(value)
