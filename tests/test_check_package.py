from __future__ import annotations

import subprocess
import sys
from importlib.metadata import version
from pathlib import Path

import pytest

import voxwright
from scripts.check_package import contract_issues, find_built_wheel
from voxwright.schemas import ARTIFACT_SCHEMAS

ROOT = Path(__file__).parents[1]


def test_installed_metadata_matches_imported_package() -> None:
    assert version("voxwright") == voxwright.__version__


def test_package_contract_accepts_reviewed_public_surfaces() -> None:
    assert (
        contract_issues(
            voxwright.__version__,
            version("voxwright"),
            tuple(voxwright.__all__),
            tuple(schema.name for schema in ARTIFACT_SCHEMAS),
        )
        == ()
    )


def test_package_contract_explains_version_and_export_drift() -> None:
    assert contract_issues("0.1.0", "0.1.1", ("a",), ("event",)) == (
        "package and distribution versions differ",
    )
    assert contract_issues("1", "1", ("b", "a", "a"), ("event",)) == (
        "public exports must be nonempty, sorted, and unique",
    )


def test_package_contract_rejects_missing_or_unsorted_schemas() -> None:
    assert contract_issues("1", "1", ("a",), ()) == (
        "artifact schema names must be nonempty, sorted, and unique",
    )
    assert contract_issues("1", "1", ("a",), ("run", "event")) == (
        "artifact schema names must be nonempty, sorted, and unique",
    )


def test_package_smoke_checks_cli_without_loading_optional_model() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/check_package.py"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_base_import_keeps_optional_model_runtime_lazy() -> None:
    result = subprocess.run(
        [sys.executable, "-c", "import sys, voxwright; print('torch' in sys.modules)"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    assert result.stdout.strip() == "False"


def test_wheel_selector_requires_one_artifact_for_the_current_version(tmp_path: Path) -> None:
    wheel = tmp_path / "voxwright-0.1.2-py3-none-any.whl"
    wheel.write_bytes(b"wheel")
    assert find_built_wheel(tmp_path, "0.1.2") == wheel
    with pytest.raises(RuntimeError, match="found 0"):
        find_built_wheel(tmp_path, "0.1.3")
    duplicate = tmp_path / "voxwright-0.1.2-py3-none-linux.whl"
    duplicate.write_bytes(b"wheel")
    with pytest.raises(RuntimeError, match="found 2"):
        find_built_wheel(tmp_path, "0.1.2")
