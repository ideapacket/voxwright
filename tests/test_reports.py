"""Tests for deterministic report synthesis."""

from __future__ import annotations

import pytest

from voxwright.reports import CoverageFacts, coverage_limitations


def test_limitations_are_derived_from_actual_coverage() -> None:
    facts = CoverageFacts(5, ("schedule",), ("scripted",))
    assert coverage_limitations(facts) == (
        "Metrics cover 5 seeded synthetic scenarios with planted truth.",
        "No real speech recording was evaluated.",
        "No actual spoken-model endpoint was evaluated.",
    )


def test_coverage_can_record_explicitly_exercised_interfaces() -> None:
    facts = CoverageFacts(
        1,
        ("music",),
        ("loopback",),
        used_real_audio=True,
        used_model_endpoint=True,
    )
    limitations = coverage_limitations(facts)
    assert len(limitations) == 1
    assert "seeded synthetic" in limitations[0]


def test_empty_coverage_explains_missing_dimensions() -> None:
    limitations = coverage_limitations(CoverageFacts(0, (), ()))
    assert "No task type was represented in this campaign." in limitations
    assert "No adapter execution was represented in this campaign." in limitations


def test_coverage_facts_reject_invalid_counts_and_names() -> None:
    with pytest.raises(ValueError, match="non-negative integer"):
        CoverageFacts(-1, (), ())
    with pytest.raises(ValueError, match="cannot be empty"):
        CoverageFacts(1, ("",), ())
    with pytest.raises(ValueError, match="must be unique"):
        CoverageFacts(1, (), ("scripted", "scripted"))
