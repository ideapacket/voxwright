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


def test_workflow_resume_artifacts_are_byte_deterministic(tmp_path: Path) -> None:
    left = tmp_path / "left-workflow"
    right = tmp_path / "right-workflow"
    assert run_example("workflow_recovery", left).returncode == 0
    assert run_example("workflow_recovery", right).returncode == 0
    assert (left / "summary.json").read_bytes() == (right / "summary.json").read_bytes()
    assert (left / "workflow.svg").read_bytes() == (right / "workflow.svg").read_bytes()


def test_workflow_example_refuses_to_overwrite_output(tmp_path: Path) -> None:
    output = tmp_path / "existing-workflow"
    output.mkdir()
    marker = output / "keep"
    marker.write_text("safe", encoding="utf-8")
    assert run_example("workflow_recovery", output).returncode != 0
    assert marker.read_text(encoding="utf-8") == "safe"


def test_workflow_example_compensates_in_reverse_completion_order(tmp_path: Path) -> None:
    output = tmp_path / "compensate"
    assert run_example("workflow_recovery", output).returncode == 0
    summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))
    assert summary["compensated_steps"] == ["charge", "reserve"]
    assert summary["rollback_state"] == {"charged": False, "reserved": False}


def test_repair_comparison_measures_planted_noise(tmp_path: Path) -> None:
    output = tmp_path / "repair"
    result = run_example("repair_comparison", output, "--seed", "7", "--samples", "12")
    assert result.returncode == 0, result.stderr
    metrics = json.loads((output / "metrics.json").read_text(encoding="utf-8"))
    assert metrics["synthetic"] is True
    assert metrics["samples_per_noise"] == 12
    assert metrics["noise_rates"] == [0.0, 0.2, 0.4, 0.6]
    assert set(metrics["curves"]) == {"cautious", "permissive"}
    assert all(len(points) == 4 for points in metrics["curves"].values())


def test_repair_metrics_are_bounded_and_reproducible(tmp_path: Path) -> None:
    left = tmp_path / "repair-left"
    right = tmp_path / "repair-right"
    arguments = ("--seed", "13", "--samples", "16")
    assert run_example("repair_comparison", left, *arguments).returncode == 0
    assert run_example("repair_comparison", right, *arguments).returncode == 0
    assert (left / "metrics.json").read_bytes() == (right / "metrics.json").read_bytes()
    metrics = json.loads((left / "metrics.json").read_text(encoding="utf-8"))
    for points in metrics["curves"].values():
        for point in points:
            assert 0.0 <= point["task_success"] <= 1.0
            assert 0.0 <= point["repair_rate"] <= 1.0
            assert 0.0 <= point["handoff_rate"] <= 1.0
    for policy in metrics["curves"].values():
        assert policy[0]["task_success"] == 1.0
        assert policy[0]["repair_rate"] == 0.0


def test_repair_example_rejects_invalid_or_existing_outputs(tmp_path: Path) -> None:
    existing = tmp_path / "repair-existing"
    existing.mkdir()
    marker = existing / "keep"
    marker.write_text("keep", encoding="utf-8")
    assert run_example("repair_comparison", existing).returncode != 0
    assert marker.read_text(encoding="utf-8") == "keep"
    assert run_example("repair_comparison", tmp_path / "bad", "--samples", "0").returncode != 0
    assert not (tmp_path / "bad").exists()


def test_repair_example_draws_measured_success_and_repair_curves(tmp_path: Path) -> None:
    output = tmp_path / "repair-charts"
    assert run_example("repair_comparison", output, "--samples", "8").returncode == 0
    names = {path.name for path in output.iterdir()}
    assert names == {
        "cautious-repair.svg",
        "cautious-success.svg",
        "metrics.json",
        "permissive-repair.svg",
        "permissive-success.svg",
    }
    for path in output.glob("*.svg"):
        content = path.read_text(encoding="utf-8")
        assert content.startswith('<svg xmlns="http://www.w3.org/2000/svg"')
        assert "<script" not in content


def test_mini_voice_app_executes_only_granted_synthetic_tools(tmp_path: Path) -> None:
    output = tmp_path / "mini-app"
    result = run_example("mini_voice_app", output)
    assert result.returncode == 0, result.stderr
    summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))
    assert summary["synthetic"] is True and summary["ledger_valid"] is True
    assert summary["calendar_prompt"] == "Confirm tool calendar.create"
    assert summary["home_prompt"] == "Confirm tool home.set-light"
    assert summary["calendar_executed"] is True
    assert summary["music_executed"] is True
    assert summary["home_executed"] is True
    assert summary["calendar"] == [{"event_id": "event-1", "title": "synthetic review", "hour": 14}]
    assert summary["home"] == {"study": True}
    assert summary["ledger_entries"] == 3


def test_mini_app_is_deterministic_and_refuses_overwrite(tmp_path: Path) -> None:
    left = tmp_path / "mini-left"
    right = tmp_path / "mini-right"
    assert run_example("mini_voice_app", left).returncode == 0
    assert run_example("mini_voice_app", right).returncode == 0
    assert (left / "summary.json").read_bytes() == (right / "summary.json").read_bytes()
    marker = left / "summary.json"
    before = marker.read_bytes()
    assert run_example("mini_voice_app", left).returncode != 0
    assert marker.read_bytes() == before


def test_mini_app_applies_atomic_barge_in_semantics(tmp_path: Path) -> None:
    output = tmp_path / "mini-interrupt"
    assert run_example("mini_voice_app", output).returncode == 0
    summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))
    assert summary["music_resolution"] == "finished"
    assert summary["calendar_resolution"] == "rolled-back"
    assert summary["calendar_terminal"] == "rolled-back"
    assert summary["calendar_committed"] is False


def test_mini_app_reports_no_partial_non_idempotent_commit(tmp_path: Path) -> None:
    output = tmp_path / "mini-atomic"
    assert run_example("mini_voice_app", output).returncode == 0
    summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))
    terminal = summary["calendar_terminal"]
    assert terminal in {"completed", "rolled-back"}
    assert summary["calendar_committed"] is (terminal == "completed")
