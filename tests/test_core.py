"""Tests for deterministic core values."""

from __future__ import annotations

import pytest

from voxwright.core import canonical_bytes, canonical_json, parse_json


def test_canonical_json_sorts_nested_objects() -> None:
    value = {"z": 1, "a": {"two": 2, "one": 1}}
    assert canonical_json(value) == '{"a":{"one":1,"two":2},"z":1}'


def test_canonical_bytes_preserve_unicode() -> None:
    assert canonical_bytes({"utterance": "打开灯"}) == '{"utterance":"打开灯"}'.encode()


def test_parse_json_roundtrip() -> None:
    value = {"flag": True, "items": [None, 3, 2.5, "x"]}
    assert parse_json(canonical_json(value)) == value


@pytest.mark.parametrize("number", [float("nan"), float("inf"), float("-inf")])
def test_canonical_json_rejects_non_finite_numbers(number: float) -> None:
    with pytest.raises(ValueError, match=r"\$\.score: non-finite"):
        canonical_json({"score": number})


def test_canonical_json_rejects_non_string_keys() -> None:
    with pytest.raises(TypeError, match="object key must be a string"):
        canonical_json({1: "one"})


def test_canonical_json_rejects_tuple_to_avoid_implicit_coercion() -> None:
    with pytest.raises(TypeError, match="unsupported JSON value tuple"):
        canonical_json(("audio", "final"))


def test_parse_json_reports_invalid_syntax() -> None:
    with pytest.raises(ValueError):
        parse_json('{"missing":}')
