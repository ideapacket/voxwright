"""Tests for deterministic synthetic choice streams."""

from __future__ import annotations

import pytest

from voxwright.seeding import SeedStream


def test_seed_stream_has_stable_golden_values() -> None:
    stream = SeedStream(7, "scenario")
    assert [stream.next_int() for _ in range(3)] == [
        11056473727452698443,
        9895025804299893810,
        8371972226159904353,
    ]


def test_choice_and_shuffle_replay_from_seed() -> None:
    left = SeedStream(12, "persona")
    right = SeedStream(12, "persona")
    assert left.choose(["a", "b", "c"]) == right.choose(["a", "b", "c"])
    assert left.shuffled(range(8)) == right.shuffled(range(8))


def test_seed_namespaces_are_independent() -> None:
    assert SeedStream(1, "goals").next_int() != SeedStream(1, "noise").next_int()


@pytest.mark.parametrize("probability", [-0.1, 1.1])
def test_chance_rejects_invalid_probability(probability: float) -> None:
    with pytest.raises(ValueError, match="between 0 and 1"):
        SeedStream(1).chance(probability)


def test_empty_choice_is_a_precise_error() -> None:
    with pytest.raises(ValueError, match="empty sequence"):
        SeedStream(1).choose([])
