"""Bootstrap package contracts."""

from __future__ import annotations

import subprocess
import sys

import voxwright
from voxwright.events import EventEnvelope


def test_version_is_semantic_patch_version() -> None:
    parts = voxwright.__version__.split(".")
    assert len(parts) == 3
    assert all(part.isdigit() for part in parts)


def test_module_cli_reports_help() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "voxwright.cli", "--help"],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "voxwright" in result.stdout


def test_public_event_exports_are_deliberate() -> None:
    assert voxwright.__all__ == ["EventEnvelope", "EventKind", "__version__", "envelope_for"]
    assert voxwright.EventEnvelope is EventEnvelope
