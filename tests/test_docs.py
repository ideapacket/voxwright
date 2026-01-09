from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from scripts.check_docs import (
    FORBIDDEN_PUBLIC_PHRASES,
    TIMELINE_DISCLOSURE,
    check_docs,
    markdown_files,
)

ROOT = Path(__file__).parents[1]


def test_tracked_documentation_has_valid_links_and_disclosures() -> None:
    assert check_docs(ROOT) == ()
    names = {path.relative_to(ROOT).as_posix() for path in markdown_files(ROOT)}
    assert "README.md" in names
    assert "docs/architecture.md" in names
    assert "examples/mini_voice_app/README.md" in names


def test_docs_checker_is_runnable_from_the_repository() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/check_docs.py"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_docs_checker_reports_broken_links_and_forbidden_claims(tmp_path: Path) -> None:
    (tmp_path / "docs").mkdir()
    (tmp_path / "examples").mkdir()
    (tmp_path / "README.md").write_text(
        TIMELINE_DISCLOSURE + "\n[missing](docs/missing.md)\n", encoding="utf-8"
    )
    (tmp_path / "docs" / "bad.md").write_text(
        f"This {FORBIDDEN_PUBLIC_PHRASES[0]} uses {FORBIDDEN_PUBLIC_PHRASES[1]}.\n",
        encoding="utf-8",
    )
    issues = check_docs(tmp_path)
    assert "README.md: broken link 'docs/missing.md'" in issues
    assert f"docs/bad.md: forbidden phrase {FORBIDDEN_PUBLIC_PHRASES[0]!r}" in issues
    assert f"docs/bad.md: forbidden phrase {FORBIDDEN_PUBLIC_PHRASES[1]!r}" in issues


def test_docs_checker_confines_relative_links_to_the_repository(tmp_path: Path) -> None:
    (tmp_path / "docs").mkdir()
    (tmp_path / "examples").mkdir()
    (tmp_path / "README.md").write_text(
        TIMELINE_DISCLOSURE + "\n[outside](../outside.md)\n", encoding="utf-8"
    )
    assert "README.md: broken link '../outside.md'" in check_docs(tmp_path)
