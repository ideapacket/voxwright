"""Command-line behavior over offline artifacts."""

from __future__ import annotations

import subprocess
import sys

from voxwright.checkpoints import WorkflowCheckpoint, write_checkpoint
from voxwright.cli import build_parser, main
from voxwright.events import EventEnvelope, EventKind
from voxwright.identifiers import Identifier
from voxwright.manifests import read_manifest
from voxwright.recording import SessionRecorder
from voxwright.run_artifacts import decode_runs
from voxwright.workflow import StepKind, WorkflowDefinition, WorkflowStep
from voxwright.workflow_codec import write_workflow

COMMANDS = (
    "simulate",
    "run",
    "replay",
    "diff",
    "validate",
    "score",
    "report",
    "bench",
    "demo",
)


def test_root_help_lists_every_public_subcommand(capsys: object) -> None:
    assert main([]) == 0
    output = capsys.readouterr().out  # type: ignore[attr-defined]
    for command in COMMANDS:
        assert command in output


def test_each_subcommand_has_dedicated_help() -> None:
    parser = build_parser()
    action = next(action for action in parser._actions if isinstance(action.choices, dict))
    assert set(action.choices) == set(COMMANDS)  # type: ignore[arg-type]


def test_module_help_is_successful_for_every_command() -> None:
    for command in COMMANDS:
        result = subprocess.run(
            [sys.executable, "-m", "voxwright.cli", command, "--help"],
            check=False,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, command
        assert f"usage: voxwright {command}" in result.stdout


def test_simulate_writes_seeded_manifest(tmp_path: object, capsys: object) -> None:
    path = tmp_path / "scenarios.jsonl"  # type: ignore[operator]
    assert main(["simulate", str(path), "--seed", "10", "--count", "2", "--task", "music"]) == 0
    scenarios = read_manifest(path)
    assert [item.seed for item in scenarios] == [10, 11]
    assert all(item.goals[0].task_type.value == "music" for item in scenarios)
    output = capsys.readouterr().out  # type: ignore[attr-defined]
    assert '"artifact":"synthetic-scenario-manifest"' in output


def test_simulate_rejects_destructive_or_invalid_requests(tmp_path: object, capsys: object) -> None:
    path = tmp_path / "exists.jsonl"  # type: ignore[operator]
    path.write_text("keep", encoding="utf-8")
    assert main(["simulate", str(path)]) == 2
    assert "already exists" in capsys.readouterr().err  # type: ignore[attr-defined]
    assert path.read_text(encoding="utf-8") == "keep"
    negative = tmp_path / "negative.jsonl"  # type: ignore[operator]
    assert main(["simulate", str(negative), "--seed", "-1"]) == 2
    assert "seed must be non-negative" in capsys.readouterr().err  # type: ignore[attr-defined]
    empty = tmp_path / "empty.jsonl"  # type: ignore[operator]
    assert main(["simulate", str(empty), "--count", "0"]) == 2
    assert "count must be positive" in capsys.readouterr().err  # type: ignore[attr-defined]


def write_session(path: object, *, text: str = "hello") -> None:
    writer = SessionRecorder(path)  # type: ignore[arg-type]
    writer.append(
        EventEnvelope(Identifier("session-cli"), 0, 10, EventKind.FINAL_TRANSCRIPT, {"text": text})
    )


def test_validate_reports_verified_artifact_facts(tmp_path: object, capsys: object) -> None:
    manifest = tmp_path / "manifest.jsonl"  # type: ignore[operator]
    main(["simulate", str(manifest)])
    capsys.readouterr()  # type: ignore[attr-defined]
    assert main(["validate", "manifest", str(manifest)]) == 0
    assert capsys.readouterr().out == '{"artifact":"manifest","count":1,"valid":true}\n'  # type: ignore[attr-defined]

    session = tmp_path / "session.jsonl"  # type: ignore[operator]
    write_session(session)
    assert main(["validate", "session", str(session)]) == 0
    assert '"count":1' in capsys.readouterr().out  # type: ignore[attr-defined]

    runs = tmp_path / "runs.jsonl"  # type: ignore[operator]
    assert main(["run", str(manifest), str(runs)]) == 0
    capsys.readouterr()  # type: ignore[attr-defined]
    assert main(["validate", "runs", str(runs)]) == 0
    assert capsys.readouterr().out == '{"artifact":"runs","count":1,"valid":true}\n'  # type: ignore[attr-defined]


def test_validate_reports_workflow_identity_and_digest(tmp_path: object, capsys: object) -> None:
    path = tmp_path / "workflow.json"  # type: ignore[operator]
    definition = WorkflowDefinition(
        Identifier("cli-flow"),
        3,
        Identifier("done"),
        (WorkflowStep(Identifier("done"), StepKind.END),),
    )
    write_workflow(path, definition)
    assert main(["validate", "workflow", str(path)]) == 0
    output = capsys.readouterr().out  # type: ignore[attr-defined]
    assert '"artifact":"workflow"' in output
    assert '"name":"cli-flow"' in output and '"version":3' in output
    assert '"steps":1' in output and '"digest":"sha256:' in output


def test_validate_reports_checkpoint_recovery_facts(tmp_path: object, capsys: object) -> None:
    path = tmp_path / "checkpoint.json"  # type: ignore[operator]
    checkpoint = WorkflowCheckpoint((Identifier("prepare"),), {"count": 1}, "sha256:" + "3" * 64)
    write_checkpoint(path, checkpoint)
    assert main(["validate", "checkpoint", str(path)]) == 0
    assert capsys.readouterr().out == (  # type: ignore[attr-defined]
        '{"artifact":"checkpoint","completed":1,'
        '"digest":"sha256:' + "3" * 64 + '","state_keys":["count"],"valid":true}\n'
    )


def test_validate_checkpoint_reports_shape_digest_and_truncation_errors(
    tmp_path: object, capsys: object
) -> None:
    path = tmp_path / "checkpoint.json"  # type: ignore[operator]
    path.write_text('{"schema_version":1}\n', encoding="utf-8")
    assert main(["validate", "checkpoint", str(path)]) == 2
    assert "checkpoint fields differ" in capsys.readouterr().err  # type: ignore[attr-defined]
    path.write_text(
        '{"completed":[],"digest":"bad","schema_version":1,"state":{}}\n',
        encoding="utf-8",
    )
    assert main(["validate", "checkpoint", str(path)]) == 2
    assert "algorithm-qualified" in capsys.readouterr().err  # type: ignore[attr-defined]
    path.write_text("{}", encoding="utf-8")
    assert main(["validate", "checkpoint", str(path)]) == 2
    assert "missing terminal newline" in capsys.readouterr().err  # type: ignore[attr-defined]


def test_validate_workflow_surfaces_graph_and_truncation_errors(
    tmp_path: object, capsys: object
) -> None:
    broken = tmp_path / "broken-workflow.json"  # type: ignore[operator]
    broken.write_text('{"schema_version":1}\n', encoding="utf-8")
    assert main(["validate", "workflow", str(broken)]) == 2
    assert "workflow fields differ" in capsys.readouterr().err  # type: ignore[attr-defined]
    broken.write_text("{}", encoding="utf-8")
    assert main(["validate", "workflow", str(broken)]) == 2
    assert "missing terminal newline" in capsys.readouterr().err  # type: ignore[attr-defined]


def test_validate_workflow_can_export_deterministic_svg(tmp_path: object, capsys: object) -> None:
    path = tmp_path / "workflow.json"  # type: ignore[operator]
    diagram = tmp_path / "workflow.svg"  # type: ignore[operator]
    definition = WorkflowDefinition(
        Identifier("diagram-flow"),
        1,
        Identifier("done"),
        (WorkflowStep(Identifier("done"), StepKind.END),),
    )
    write_workflow(path, definition)
    assert main(["validate", "workflow", str(path), "--diagram", str(diagram)]) == 0
    assert diagram.read_text(encoding="utf-8").startswith('<svg xmlns="http://www.w3.org/2000/svg"')
    assert f'"diagram":"{diagram}"' in capsys.readouterr().out  # type: ignore[attr-defined]


def test_workflow_diagram_export_never_overwrites_existing_output(
    tmp_path: object, capsys: object
) -> None:
    path = tmp_path / "workflow.json"  # type: ignore[operator]
    diagram = tmp_path / "workflow.svg"  # type: ignore[operator]
    definition = WorkflowDefinition(
        Identifier("safe-flow"),
        1,
        Identifier("done"),
        (WorkflowStep(Identifier("done"), StepKind.END),),
    )
    write_workflow(path, definition)
    diagram.write_text("keep", encoding="utf-8")
    assert main(["validate", "workflow", str(path), "--diagram", str(diagram)]) == 2
    assert "already exists" in capsys.readouterr().err  # type: ignore[attr-defined]
    assert diagram.read_text(encoding="utf-8") == "keep"


def test_validate_propagates_precise_artifact_errors(tmp_path: object, capsys: object) -> None:
    broken = tmp_path / "broken.jsonl"  # type: ignore[operator]
    broken.write_text("not-json\n", encoding="utf-8")
    assert main(["validate", "session", str(broken)]) == 2
    assert "line 1" in capsys.readouterr().err  # type: ignore[attr-defined]
    assert main(["validate", "manifest", str(broken)]) == 2
    assert "Expecting value" in capsys.readouterr().err  # type: ignore[attr-defined]
    assert main(["validate", "runs", str(broken)]) == 2
    assert "Expecting value" in capsys.readouterr().err  # type: ignore[attr-defined]


def test_validate_runs_detects_checksum_and_truncation_errors(
    tmp_path: object, capsys: object
) -> None:
    manifest = tmp_path / "manifest.jsonl"  # type: ignore[operator]
    runs = tmp_path / "runs.jsonl"  # type: ignore[operator]
    main(["simulate", str(manifest)])
    main(["run", str(manifest), str(runs)])
    content = runs.read_text(encoding="utf-8")
    runs.write_text(
        content.replace('"goal_satisfied":true', '"goal_satisfied":false'), encoding="utf-8"
    )
    assert main(["validate", "runs", str(runs)]) == 2
    assert "checksum mismatch" in capsys.readouterr().err  # type: ignore[attr-defined]
    runs.write_text(content.rstrip("\n"), encoding="utf-8")
    assert main(["validate", "runs", str(runs)]) == 2
    assert "incomplete line" in capsys.readouterr().err  # type: ignore[attr-defined]


def test_replay_prints_canonical_trace(tmp_path: object, capsys: object) -> None:
    session = tmp_path / "session.jsonl"  # type: ignore[operator]
    write_session(session)
    assert main(["replay", str(session), "--seed", "9"]) == 0
    output = capsys.readouterr().out  # type: ignore[attr-defined]
    assert '"schema_version":1' in output
    assert '"seed":9' in output
    assert '"session_id":"session-cli"' in output


def test_replay_is_byte_deterministic_for_same_seed(tmp_path: object, capsys: object) -> None:
    session = tmp_path / "session.jsonl"  # type: ignore[operator]
    write_session(session)
    main(["replay", str(session), "--seed", "4"])
    first = capsys.readouterr().out  # type: ignore[attr-defined]
    main(["replay", str(session), "--seed", "4"])
    second = capsys.readouterr().out  # type: ignore[attr-defined]
    assert first.encode() == second.encode()


def test_replay_rejects_negative_seed_and_empty_recording(tmp_path: object, capsys: object) -> None:
    session = tmp_path / "session.jsonl"  # type: ignore[operator]
    write_session(session)
    assert main(["replay", str(session), "--seed", "-1"]) == 2
    assert "seed must be non-negative" in capsys.readouterr().err  # type: ignore[attr-defined]
    empty = tmp_path / "empty.jsonl"  # type: ignore[operator]
    empty.write_text("", encoding="utf-8")
    assert main(["replay", str(empty)]) == 2
    assert "empty recording" in capsys.readouterr().err  # type: ignore[attr-defined]


def test_diff_returns_zero_for_identical_sessions(tmp_path: object, capsys: object) -> None:
    session = tmp_path / "session.jsonl"  # type: ignore[operator]
    write_session(session)
    assert main(["diff", str(session), str(session)]) == 0
    assert capsys.readouterr().out == "sessions are identical\n"  # type: ignore[attr-defined]


def test_diff_returns_one_and_prints_first_changed_field(tmp_path: object, capsys: object) -> None:
    left = tmp_path / "left.jsonl"  # type: ignore[operator]
    right = tmp_path / "right.jsonl"  # type: ignore[operator]
    write_session(left, text="left")
    write_session(right, text="right")
    assert main(["diff", str(left), str(right)]) == 1
    output = capsys.readouterr().out  # type: ignore[attr-defined]
    assert output.startswith("event 0 payload:")
    assert '"left"' in output and '"right"' in output


def test_cli_converts_missing_artifact_to_exit_two(tmp_path: object, capsys: object) -> None:
    missing = tmp_path / "missing.jsonl"  # type: ignore[operator]
    assert main(["validate", "session", str(missing)]) == 2
    error = capsys.readouterr().err  # type: ignore[attr-defined]
    assert error.startswith("voxwright: error:")
    assert "missing.jsonl" in error


def test_cli_requires_demo_output_without_traceback() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "voxwright.cli", "demo"],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 2
    assert "arguments are required: output" in result.stderr
    assert "Traceback" not in result.stderr


def test_run_executes_scripted_manifest_offline(tmp_path: object, capsys: object) -> None:
    manifest = tmp_path / "manifest.jsonl"  # type: ignore[operator]
    output = tmp_path / "runs.jsonl"  # type: ignore[operator]
    assert main(["simulate", str(manifest), "--count", "2"]) == 0
    capsys.readouterr()  # type: ignore[attr-defined]
    assert main(["run", str(manifest), str(output)]) == 0
    runs = decode_runs(output.read_text(encoding="utf-8"))
    assert len(runs) == 2 and all(run.goal_satisfied for run in runs)
    assert '"artifact":"synthetic-runs"' in capsys.readouterr().out  # type: ignore[attr-defined]


def test_run_refuses_to_overwrite_observations(tmp_path: object, capsys: object) -> None:
    manifest = tmp_path / "manifest.jsonl"  # type: ignore[operator]
    output = tmp_path / "runs.jsonl"  # type: ignore[operator]
    main(["simulate", str(manifest)])
    output.write_text("keep", encoding="utf-8")
    assert main(["run", str(manifest), str(output)]) == 2
    assert output.read_text(encoding="utf-8") == "keep"
    assert "already exists" in capsys.readouterr().err  # type: ignore[attr-defined]


def test_score_prints_metrics_from_executed_runs(tmp_path: object, capsys: object) -> None:
    manifest = tmp_path / "manifest.jsonl"  # type: ignore[operator]
    output = tmp_path / "runs.jsonl"  # type: ignore[operator]
    main(["simulate", str(manifest)])
    main(["run", str(manifest), str(output)])
    capsys.readouterr()  # type: ignore[attr-defined]
    assert main(["score", str(output)]) == 0
    scored = capsys.readouterr().out  # type: ignore[attr-defined]
    assert '"task_success":1.0' in scored and '"false_execute_count":0' in scored


def test_score_rejects_empty_or_tampered_run_streams(tmp_path: object, capsys: object) -> None:
    empty = tmp_path / "empty.jsonl"  # type: ignore[operator]
    empty.write_text("", encoding="utf-8")
    assert main(["score", str(empty)]) == 2
    assert "at least one run" in capsys.readouterr().err  # type: ignore[attr-defined]


def test_report_renders_executed_runs_without_external_services(
    tmp_path: object, capsys: object
) -> None:
    manifest = tmp_path / "manifest.jsonl"  # type: ignore[operator]
    runs = tmp_path / "runs.jsonl"  # type: ignore[operator]
    report = tmp_path / "report.html"  # type: ignore[operator]
    main(["simulate", str(manifest), "--task", "notes"])
    main(["run", str(manifest), str(runs)])
    capsys.readouterr()  # type: ignore[attr-defined]
    assert main(["report", str(runs), str(report), "--title", "Synthetic <facts>"]) == 0
    content = report.read_text(encoding="utf-8")
    assert content.startswith("<!doctype html>")
    assert "Synthetic &lt;facts&gt;" in content
    assert "No real speech recording was evaluated" in content
    assert '"artifact":"html-report"' in capsys.readouterr().out  # type: ignore[attr-defined]


def test_report_supports_markdown_and_protects_existing_files(
    tmp_path: object, capsys: object
) -> None:
    manifest = tmp_path / "manifest.jsonl"  # type: ignore[operator]
    runs = tmp_path / "runs.jsonl"  # type: ignore[operator]
    report = tmp_path / "report.md"  # type: ignore[operator]
    main(["simulate", str(manifest)])
    main(["run", str(manifest), str(runs)])
    assert main(["report", str(runs), str(report), "--format", "markdown"]) == 0
    assert report.read_text(encoding="utf-8").startswith("# voxwright")
    original = report.read_bytes()
    assert main(["report", str(runs), str(report), "--format", "markdown"]) == 2
    assert report.read_bytes() == original
    assert "already exists" in capsys.readouterr().err  # type: ignore[attr-defined]


def test_cli_file_commands_reject_existing_symlink_targets(
    tmp_path: object, capsys: object
) -> None:
    protected = tmp_path / "protected.txt"  # type: ignore[operator]
    protected.write_text("unchanged", encoding="utf-8")
    simulated = tmp_path / "simulated.jsonl"  # type: ignore[operator]
    simulated.symlink_to(protected)
    assert main(["simulate", str(simulated)]) == 2
    assert protected.read_text(encoding="utf-8") == "unchanged"
    assert "already exists" in capsys.readouterr().err  # type: ignore[attr-defined]

    manifest = tmp_path / "manifest.jsonl"  # type: ignore[operator]
    main(["simulate", str(manifest)])
    runs = tmp_path / "runs.jsonl"  # type: ignore[operator]
    runs.symlink_to(protected)
    assert main(["run", str(manifest), str(runs)]) == 2
    assert protected.read_text(encoding="utf-8") == "unchanged"


def test_report_rejects_invalid_campaign_identity(tmp_path: object, capsys: object) -> None:
    manifest = tmp_path / "manifest.jsonl"  # type: ignore[operator]
    runs = tmp_path / "runs.jsonl"  # type: ignore[operator]
    main(["simulate", str(manifest)])
    main(["run", str(manifest), str(runs)])
    assert main(["report", str(runs), str(tmp_path / "bad.html"), "--seed", "-1"]) == 2
    assert "seed must be a non-negative" in capsys.readouterr().err  # type: ignore[attr-defined]


def test_bench_measures_latency_curves_from_observed_runs(tmp_path: object, capsys: object) -> None:
    manifest = tmp_path / "manifest.jsonl"  # type: ignore[operator]
    runs = tmp_path / "runs.jsonl"  # type: ignore[operator]
    main(["simulate", str(manifest), "--count", "3"])
    main(["run", str(manifest), str(runs)])
    capsys.readouterr()  # type: ignore[attr-defined]
    assert main(["bench", str(runs), "--budgets", "40", "60", "120"]) == 0
    output = capsys.readouterr().out  # type: ignore[attr-defined]
    assert '"artifact":"synthetic-latency-benchmark"' in output
    assert '"budget_ms":40' in output and '"budget_ms":120' in output
    assert '"run_count":3' in output


def test_bench_output_is_ordered_and_byte_deterministic(tmp_path: object, capsys: object) -> None:
    manifest = tmp_path / "manifest.jsonl"  # type: ignore[operator]
    runs = tmp_path / "runs.jsonl"  # type: ignore[operator]
    main(["simulate", str(manifest)])
    main(["run", str(manifest), str(runs)])
    capsys.readouterr()  # type: ignore[attr-defined]
    arguments = ["bench", str(runs), "--budgets", "120", "40", "80"]
    assert main(arguments) == 0
    first = capsys.readouterr().out  # type: ignore[attr-defined]
    assert main(arguments) == 0
    second = capsys.readouterr().out  # type: ignore[attr-defined]
    assert first.encode() == second.encode()
    assert first.index('"budget_ms":40') < first.index('"budget_ms":120')


def test_bench_rejects_duplicate_negative_or_empty_inputs(tmp_path: object, capsys: object) -> None:
    empty = tmp_path / "empty.jsonl"  # type: ignore[operator]
    empty.write_text("", encoding="utf-8")
    assert main(["bench", str(empty)]) == 2
    assert "at least one outcome" in capsys.readouterr().err  # type: ignore[attr-defined]
    manifest = tmp_path / "manifest.jsonl"  # type: ignore[operator]
    runs = tmp_path / "runs.jsonl"  # type: ignore[operator]
    main(["simulate", str(manifest)])
    main(["run", str(manifest), str(runs)])
    assert main(["bench", str(runs), "--budgets", "10", "10"]) == 2
    assert "unique" in capsys.readouterr().err  # type: ignore[attr-defined]
    assert main(["bench", str(runs), "--budgets", "-1"]) == 2
    assert "non-negative" in capsys.readouterr().err  # type: ignore[attr-defined]


def test_demo_runs_the_complete_offline_artifact_loop(tmp_path: object, capsys: object) -> None:
    output = tmp_path / "demo"  # type: ignore[operator]
    assert main(["demo", str(output), "--seed", "19", "--count", "4"]) == 0
    assert sorted(path.name for path in output.iterdir()) == [
        "report.html",
        "runs.jsonl",
        "scenarios.jsonl",
        "summary.json",
    ]
    assert len(read_manifest(output / "scenarios.jsonl")) == 4
    assert len(decode_runs((output / "runs.jsonl").read_text(encoding="utf-8"))) == 4
    summary = (output / "summary.json").read_text(encoding="utf-8")
    assert '"task_success":1.0' in summary and '"seed":19' in summary
    assert capsys.readouterr().out.endswith(summary)  # type: ignore[attr-defined]


def test_demo_artifacts_are_reproducible_for_the_same_seed(
    tmp_path: object, capsys: object
) -> None:
    left = tmp_path / "left"  # type: ignore[operator]
    right = tmp_path / "right"  # type: ignore[operator]
    assert main(["demo", str(left), "--seed", "23", "--count", "3"]) == 0
    capsys.readouterr()  # type: ignore[attr-defined]
    assert main(["demo", str(right), "--seed", "23", "--count", "3"]) == 0
    for name in ("scenarios.jsonl", "runs.jsonl", "report.html"):
        assert (left / name).read_bytes() == (right / name).read_bytes()


def test_demo_rejects_invalid_or_destructive_requests(tmp_path: object, capsys: object) -> None:
    existing = tmp_path / "existing"  # type: ignore[operator]
    existing.mkdir()
    marker = existing / "keep.txt"
    marker.write_text("keep", encoding="utf-8")
    assert main(["demo", str(existing)]) == 2
    assert marker.read_text(encoding="utf-8") == "keep"
    assert "already exists" in capsys.readouterr().err  # type: ignore[attr-defined]
    assert main(["demo", str(tmp_path / "negative"), "--seed", "-1"]) == 2  # type: ignore[operator]
    assert "seed must be non-negative" in capsys.readouterr().err  # type: ignore[attr-defined]
    assert main(["demo", str(tmp_path / "empty"), "--count", "0"]) == 2  # type: ignore[operator]
    assert "count must be positive" in capsys.readouterr().err  # type: ignore[attr-defined]
