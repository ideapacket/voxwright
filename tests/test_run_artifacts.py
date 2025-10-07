from __future__ import annotations

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
