"""Smoke-check an installed wheel without network access."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from importlib.metadata import version
from pathlib import Path

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


def find_built_wheel(dist: Path, package_version: str) -> Path:
    """Select exactly one wheel for the version under verification."""
    candidates = sorted(dist.glob(f"voxwright-{package_version}-*.whl"))
    if len(candidates) != 1:
        raise RuntimeError(
            f"expected one voxwright {package_version} wheel in {dist}, found {len(candidates)}"
        )
    return candidates[0]


def _checked(
    arguments: list[str], *, cwd: Path, env: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        arguments, cwd=cwd, env=env, check=False, capture_output=True, text=True
    )
    if result.returncode != 0:
        detail = (result.stdout + result.stderr).strip()
        raise RuntimeError(f"package smoke command failed: {detail}")
    return result


def smoke_built_wheel(wheel: Path, package_version: str) -> None:
    """Install the wheel offline and verify import, metadata, and CLI entry point."""
    with tempfile.TemporaryDirectory(prefix="voxwright-wheel-") as temporary:
        root = Path(temporary)
        target = root / "site"
        uv = shutil.which("uv")
        installer: list[str]
        if uv is not None:
            installer = [uv, "pip", "install", "--no-deps", "--target", str(target), str(wheel)]
        else:
            # Minimal verification images may not ship uv; pip installs the
            # wheel into the target directory with identical semantics.
            installer = [
                sys.executable,
                "-m",
                "pip",
                "install",
                "--quiet",
                "--no-deps",
                "--target",
                str(target),
                str(wheel),
            ]
        _checked(installer, cwd=root)
        environment = {
            "PATH": os.environ.get("PATH", ""),
            "PYTHONNOUSERSITE": "1",
            "PYTHONPATH": str(target),
        }
        probe = (
            "import sys; from importlib.metadata import version; from pathlib import Path; "
            "import voxwright; "
            f"assert voxwright.__version__ == version('voxwright') == {package_version!r}; "
            f"assert Path(voxwright.__file__).is_relative_to(Path({str(target)!r})); "
            "assert 'torch' not in sys.modules"
        )
        _checked([sys.executable, "-c", probe], cwd=root, env=environment)
        result = _checked(
            [sys.executable, "-m", "voxwright.cli", "--version"], cwd=root, env=environment
        )
        if package_version not in result.stdout:
            raise RuntimeError("wheel CLI version does not match package version")


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
    if "torch" in sys.modules:
        raise RuntimeError("base package import loaded optional torch")
    for arguments, marker in ((["--version"], voxwright.__version__), (["--help"], "simulate")):
        result = subprocess.run(
            [sys.executable, "-m", "voxwright.cli", *arguments],
            check=False,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0 or marker not in result.stdout:
            raise RuntimeError(f"CLI smoke check failed for {arguments[0]}")
    root = Path(__file__).parents[1]
    smoke_built_wheel(find_built_wheel(root / "dist", voxwright.__version__), voxwright.__version__)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
