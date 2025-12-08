"""Runnable offline example checks."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from voxwright.manifests import read_manifest
from voxwright.recording import load_session

ROOT = Path(__file__).parents[1]


def run_example(name: str, output: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(ROOT / "examples" / name / "main.py"), str(output), *arguments],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )


def test_scenario_replay_example_runs_offline(tmp_path: Path) -> None:
    output = tmp_path / "scenario"
    result = run_example("scenario_replay", output, "--seed", "11")
    assert result.returncode == 0, result.stderr
    assert sorted(path.name for path in output.iterdir()) == [
        "scenarios.jsonl",
        "session.jsonl",
        "summary.json",
        "trace.json",
    ]
    summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))
    assert summary["byte_identical"] is True
    assert summary["synthetic"] is True and summary["adapter"] == "scripted"
    assert len(read_manifest(output / "scenarios.jsonl")) == 1
    assert len(load_session(output / "session.jsonl")) == 3


def test_scenario_replay_outputs_are_seed_deterministic(tmp_path: Path) -> None:
    left = tmp_path / "left"
    right = tmp_path / "right"
    first = run_example("scenario_replay", left, "--seed", "29")
    second = run_example("scenario_replay", right, "--seed", "29")
    assert first.returncode == second.returncode == 0
    for name in ("scenarios.jsonl", "session.jsonl", "trace.json", "summary.json"):
        assert (left / name).read_bytes() == (right / name).read_bytes()
    changed = tmp_path / "changed"
    assert run_example("scenario_replay", changed, "--seed", "30").returncode == 0
    assert (left / "scenarios.jsonl").read_bytes() != (changed / "scenarios.jsonl").read_bytes()


def test_scenario_replay_refuses_destructive_requests(tmp_path: Path) -> None:
    output = tmp_path / "existing"
    output.mkdir()
    marker = output / "keep.txt"
    marker.write_text("keep", encoding="utf-8")
    result = run_example("scenario_replay", output)
    assert result.returncode != 0
    assert marker.read_text(encoding="utf-8") == "keep"
    negative = run_example("scenario_replay", tmp_path / "negative", "--seed", "-1")
    assert negative.returncode != 0
    assert not (tmp_path / "negative").exists()


def test_workflow_recovery_example_renders_executed_graph(tmp_path: Path) -> None:
    output = tmp_path / "workflow"
    result = run_example("workflow_recovery", output)
    assert result.returncode == 0, result.stderr
    summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))
    assert summary["visited"] == ["reserve", "charge", "finish"]
    assert summary["final_state"] == {"reserved": True, "charged": True, "complete": True}
    svg = (output / "workflow.svg").read_text(encoding="utf-8")
    assert svg.startswith('<svg xmlns="http://www.w3.org/2000/svg"')
    assert "reserve [action]" in svg and "finish [end]" in svg


def test_workflow_example_resumes_from_a_verified_prefix(tmp_path: Path) -> None:
    output = tmp_path / "resume"
    assert run_example("workflow_recovery", output).returncode == 0
    summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))
    assert summary["resume_matches_straight"] is True
    assert summary["resumed_steps"] == ["charge", "finish"]
    assert str(summary["checkpoint_digest"]).startswith("sha256:")
