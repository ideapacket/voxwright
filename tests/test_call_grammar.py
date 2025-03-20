"""Tests for injection-safe function-call grammar."""

from __future__ import annotations

import pytest

import voxwright.call_grammar as grammar
from voxwright.identifiers import Identifier


def test_call_parser_roundtrips_canonical_syntax() -> None:
    call = grammar.ParsedCall(Identifier("home.set-light"), {"room": "study", "on": True})
    assert grammar.format_call(call) == 'CALL home.set-light {"on":true,"room":"study"}'
    assert grammar.parse_call(grammar.format_call(call)) == call


def test_parser_requires_dedicated_uppercase_prefix() -> None:
    with pytest.raises(grammar.CallParseError) as captured:
        grammar.parse_call('call notes.add {"text":"x"}')
    assert captured.value.code == "missing-prefix"
    assert captured.value.offset == 0


def test_parser_requires_argument_object() -> None:
    with pytest.raises(grammar.CallParseError) as captured:
        grammar.parse_call("CALL music.play []")
    assert captured.value.code == "arguments-not-object"
