"""Smoke-check an installed wheel without network access."""

from __future__ import annotations

import subprocess
import sys
from importlib.metadata import version

import voxwright
from voxwright.schemas import ARTIFACT_SCHEMAS


def contract_issues(
    package_version: str,
    installed_version: str,
    exports: tuple[str, ...],
    schema_names: tuple[str, ...],
) -> tuple[str, ...]:
    """Return stable diagnostics for an installed package surface."""
    issues: list[str] = []
    if not package_version or package_version != installed_version:
        issues.append("package and distribution versions differ")
    if not exports or tuple(sorted(set(exports))) != exports:
        issues.append("public exports must be nonempty, sorted, and unique")
    if not schema_names or tuple(sorted(set(schema_names))) != schema_names:
        issues.append("artifact schema names must be nonempty, sorted, and unique")
    return tuple(issues)


def main() -> int:
    """Verify import and the installed command entry point."""
    issues = contract_issues(
        voxwright.__version__,
        version("voxwright"),
        tuple(voxwright.__all__),
        tuple(schema.name for schema in ARTIFACT_SCHEMAS),
    )
    if issues:
        raise RuntimeError("; ".join(issues))
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
