"""Command-line behavior over offline artifacts."""

from __future__ import annotations

import subprocess
import sys

from voxwright.cli import build_parser, main
from voxwright.manifests import read_manifest

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
