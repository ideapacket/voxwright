"""Tests for deterministic report synthesis."""

from __future__ import annotations

from voxwright.reports import CoverageFacts, coverage_limitations


def test_limitations_are_derived_from_actual_coverage() -> None:
    facts = CoverageFacts(5, ("schedule",), ("scripted",))
    assert coverage_limitations(facts) == (
        "Metrics cover 5 seeded synthetic scenarios with planted truth.",
        "No real speech recording was evaluated.",
        "No actual spoken-model endpoint was evaluated.",
    )
