"""Command-line behavior over offline artifacts."""

from __future__ import annotations

import subprocess
import sys

from voxwright.cli import build_parser, main

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
