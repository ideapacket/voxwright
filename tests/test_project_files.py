"""Repository policy and release contract checks."""

from __future__ import annotations

import tomllib
from pathlib import Path

ROOT = Path(__file__).parents[1]
PYPROJECT = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
MAKEFILE = (ROOT / "Makefile").read_text(encoding="utf-8")
CI = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
RELEASE = (ROOT / ".github/workflows/release.yml").read_text(encoding="utf-8")


def test_runtime_dependency_surface_is_intentionally_small() -> None:
    assert PYPROJECT["project"]["dependencies"] == ["numpy>=1.26,<3"]
    assert PYPROJECT["project"]["requires-python"] == ">=3.11"
    assert PYPROJECT["project"]["optional-dependencies"]["torch"] == ["torch>=2.5,<3"]


def test_fresh_development_install_can_build_without_isolation() -> None:
    requirements = PYPROJECT["build-system"]["requires"]
    development = PYPROJECT["project"]["optional-dependencies"]["dev"]
    assert requirements == ["hatchling==1.27.0"]
    assert requirements[0] in development
    assert "build==1.2.2.post1" in development


def test_typecheck_configuration_is_cross_version() -> None:
    mypy = PYPROJECT["tool"]["mypy"]
    assert mypy == {"strict": True, "packages": ["voxwright"]}
    assert "python_version" not in mypy


def test_makefile_exposes_required_validation_commands() -> None:
    assert '.venv/bin/python -m pytest -q -m "not slow"' in MAKEFILE
    assert ".venv/bin/python -m pytest -q\n" in MAKEFILE
    assert ".venv/bin/python -m build --wheel --no-isolation" in MAKEFILE
    assert ".venv/bin/mypy src" in MAKEFILE
    assert ".venv/bin/ruff format --check src tests examples scripts" in MAKEFILE


def test_reproducibility_locks_pin_direct_tooling() -> None:
    development = (ROOT / "requirements-dev.lock").read_text(encoding="utf-8")
    model = (ROOT / "requirements-torch.lock").read_text(encoding="utf-8")
    for requirement in ("build==", "hatchling==", "mypy==", "numpy==", "pytest==", "ruff=="):
        assert requirement in development
    assert "torch==2.15.0+cpu" in model
    assert "CPU-only" in model


def test_ci_matrix_matches_supported_interpreters() -> None:
    assert 'python-version: ["3.11", "3.12", "3.13"]' in CI
    assert "actions/setup-python@v5" in CI
    assert 'uv venv --python "${{ matrix.python-version }}" .venv' in CI


def test_ci_uses_cpu_model_index_without_first_index_trap() -> None:
    assert "https://download.pytorch.org/whl/cpu" in CI
    assert "--index-strategy unsafe-best-match" in CI
    assert '-e ".[dev,torch]"' in CI


def test_ci_mirrors_all_makefile_quality_gates() -> None:
    targets = ("build", "test-all", "format-check", "lint", "typecheck")
    positions = [CI.index(f"make {target}") for target in targets]
    assert positions == sorted(positions)


def test_release_uses_github_artifacts_without_registry_credentials() -> None:
    assert 'tags: ["v*"]' in RELEASE
    assert "make release" in RELEASE
    assert "actions/upload-artifact@v4" in RELEASE
    assert "softprops/action-gh-release@v2" in RELEASE
    assert "pypi" not in RELEASE.lower()
    assert "password" not in RELEASE.lower()


def test_community_health_files_cover_reporting_paths() -> None:
    contributing = (ROOT / "CONTRIBUTING.md").read_text(encoding="utf-8")
    security = (ROOT / "SECURITY.md").read_text(encoding="utf-8")
    assert "make typecheck" in contributing and "seeded synthetic fixtures" in contributing
    assert "private GitHub security advisory" in security
    assert "permission bypass" in security


def test_issue_forms_separate_public_and_sensitive_reports() -> None:
    config = (ROOT / ".github/ISSUE_TEMPLATE/config.yml").read_text(encoding="utf-8")
    bug = (ROOT / ".github/ISSUE_TEMPLATE/bug.yml").read_text(encoding="utf-8")
    hardening = (ROOT / ".github/ISSUE_TEMPLATE/security-hardening.yml").read_text(encoding="utf-8")
    assert "blank_issues_enabled: false" in config
    assert "/security/advisories/new" in config
    assert "Minimal offline reproduction" in bug
    assert "Use a private security advisory" in hardening


def test_dependency_updates_cover_packages_and_workflows() -> None:
    config = (ROOT / ".github/dependabot.yml").read_text(encoding="utf-8")
    assert "package-ecosystem: pip" in config
    assert "package-ecosystem: github-actions" in config
    assert "open-pull-requests-limit" in config


def test_license_is_mit_and_names_the_project_author() -> None:
    license_text = (ROOT / "LICENSE").read_text(encoding="utf-8")
    assert license_text.startswith("MIT License")
    assert "Li Xilai" in license_text
    assert "Permission is hereby granted" in license_text
