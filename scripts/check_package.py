"""Smoke-check an installed wheel without network access."""

from __future__ import annotations

import subprocess
import sys

import voxwright


def main() -> int:
    """Verify import and the installed command entry point."""
    if not voxwright.__version__:
        raise RuntimeError("package version is empty")
    result = subprocess.run(
        [sys.executable, "-m", "voxwright.cli", "--version"],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0 or voxwright.__version__ not in result.stdout:
        raise RuntimeError("CLI smoke check failed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
