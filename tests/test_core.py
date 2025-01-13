"""Tests for deterministic core values."""

from __future__ import annotations

from voxwright.core import canonical_bytes, canonical_json, parse_json


def test_canonical_json_sorts_nested_objects() -> None:
    value = {"z": 1, "a": {"two": 2, "one": 1}}
    assert canonical_json(value) == '{"a":{"one":1,"two":2},"z":1}'


def test_canonical_bytes_preserve_unicode() -> None:
    assert canonical_bytes({"utterance": "打开灯"}) == '{"utterance":"打开灯"}'.encode()


def test_parse_json_roundtrip() -> None:
    value = {"flag": True, "items": [None, 3, 2.5, "x"]}
    assert parse_json(canonical_json(value)) == value
