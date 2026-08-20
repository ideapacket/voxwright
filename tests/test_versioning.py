from __future__ import annotations

import re
import tomllib
from importlib.metadata import version
from pathlib import Path

import voxwright

ROOT = Path(__file__).parents[1]


def test_dynamic_version_matches_distribution_and_latest_changelog() -> None:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    assert project["dynamic"] == ["version"]
    assert version("voxwright") == voxwright.__version__
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    [latest] = re.findall(r"^## \[([^]]+)\]", changelog, flags=re.MULTILINE)[:1]
    assert latest == voxwright.__version__


def test_public_version_is_a_three_part_numeric_release() -> None:
    parts = voxwright.__version__.split(".")
    assert len(parts) == 3
    assert all(part.isdigit() for part in parts)
