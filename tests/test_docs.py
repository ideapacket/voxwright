from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from scripts.check_docs import check_docs, markdown_files

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
