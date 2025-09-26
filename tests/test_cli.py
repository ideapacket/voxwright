"""Command-line behavior over offline artifacts."""

from __future__ import annotations

import subprocess
import sys

import pytest

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


def test_simulate_rejects_destructive_or_invalid_requests(tmp_path: object) -> None:
    path = tmp_path / "exists.jsonl"  # type: ignore[operator]
    path.write_text("keep", encoding="utf-8")
    with pytest.raises(FileExistsError, match="already exists"):
        main(["simulate", str(path)])
    assert path.read_text(encoding="utf-8") == "keep"
    with pytest.raises(ValueError, match="seed must be non-negative"):
        main(["simulate", str(tmp_path / "negative.jsonl"), "--seed", "-1"])  # type: ignore[operator]
    with pytest.raises(ValueError, match="count must be positive"):
        main(["simulate", str(tmp_path / "empty.jsonl"), "--count", "0"])  # type: ignore[operator]


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
