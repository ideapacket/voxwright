from __future__ import annotations

from importlib.metadata import version

import voxwright
from scripts.check_package import contract_issues
from voxwright.schemas import ARTIFACT_SCHEMAS


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
