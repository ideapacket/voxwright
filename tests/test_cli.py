"""Command-line behavior over offline artifacts."""

from __future__ import annotations

import subprocess
import sys

from voxwright.cli import build_parser, main
from voxwright.events import EventEnvelope, EventKind
from voxwright.identifiers import Identifier
from voxwright.manifests import read_manifest
from voxwright.recording import SessionRecorder

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


def test_validate_propagates_precise_artifact_errors(tmp_path: object, capsys: object) -> None:
    broken = tmp_path / "broken.jsonl"  # type: ignore[operator]
    broken.write_text("not-json\n", encoding="utf-8")
    assert main(["validate", "session", str(broken)]) == 2
    assert "line 1" in capsys.readouterr().err  # type: ignore[attr-defined]
    assert main(["validate", "manifest", str(broken)]) == 2
    assert "Expecting value" in capsys.readouterr().err  # type: ignore[attr-defined]


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


def test_cli_pending_command_fails_without_traceback(capsys: object) -> None:
    assert main(["run"]) == 2
    captured = capsys.readouterr()  # type: ignore[attr-defined]
    assert captured.out == ""
    assert captured.err == "voxwright: error: command is not implemented: run\n"
    assert "Traceback" not in captured.err
