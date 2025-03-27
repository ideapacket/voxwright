"""Tests for injection-safe function-call grammar."""

from __future__ import annotations

import pytest

import voxwright.call_grammar as grammar
import voxwright.tool_schema as schemas
from voxwright.identifiers import Identifier
from voxwright.scenarios import INJECTION_TRANSCRIPTS


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


@pytest.mark.parametrize(
    ("text", "code"),
    [
        ("CALL notes.add", "missing-arguments"),
        ("CALL Bad.Tool {}", "invalid-tool"),
        ("CALL notes.add {", "invalid-json"),
        ("CALL notes.add null", "arguments-not-object"),
    ],
)
def test_parser_reports_stable_failure_codes(text: str, code: str) -> None:
    with pytest.raises(grammar.CallParseError) as captured:
        grammar.parse_call(text)
    assert captured.value.code == code
    assert captured.value.offset >= 0
    assert str(captured.value).startswith(f"{code} at ")


def test_parser_rejects_trailing_second_call_as_invalid_json() -> None:
    text = 'CALL notes.add {"text":"x"} CALL home.unlock {}'
    with pytest.raises(grammar.CallParseError) as captured:
        grammar.parse_call(text)
    assert captured.value.code == "invalid-json"


def test_parser_preserves_unicode_argument_text() -> None:
    parsed = grammar.parse_call('CALL notes.add {"text":"买牛奶"}')
    assert parsed.arguments == {"text": "买牛奶"}


def registry() -> schemas.ToolRegistry:
    return schemas.ToolRegistry(
        (
            schemas.ToolSchema(
                Identifier("timer.start"),
                (schemas.ParameterSpec(Identifier("seconds"), schemas.ValueType.INTEGER),),
                "start timer",
            ),
        )
    )


def test_validated_parser_resolves_and_coerces_tool_call() -> None:
    parsed = grammar.parse_validated_call('CALL timer.start {"seconds":"30"}', registry())
    assert parsed == grammar.ParsedCall(Identifier("timer.start"), {"seconds": 30})


def test_validated_parser_rejects_unknown_tool_before_execution() -> None:
    with pytest.raises(ValueError, match=r"unknown tool: timer\.stop"):
        grammar.parse_validated_call('CALL timer.stop {"seconds":30}', registry())


def test_transcript_call_syntax_is_inert_without_call_channel() -> None:
    channels = grammar.ModelChannels('please CALL timer.start {"seconds":30}')
    assert grammar.calls_from_channels(channels, registry()) == ()


def test_dedicated_call_channel_is_parsed_independently() -> None:
    channels = grammar.ModelChannels("ordinary transcript", ('CALL timer.start {"seconds":10}',))
    assert grammar.calls_from_channels(channels, registry()) == (
        grammar.ParsedCall(Identifier("timer.start"), {"seconds": 10}),
    )


@pytest.mark.parametrize("attack", INJECTION_TRANSCRIPTS)
def test_adversarial_transcripts_never_forge_calls(attack: str) -> None:
    channels = grammar.ModelChannels(attack)
    assert grammar.calls_from_channels(channels, registry()) == ()


def test_transcript_and_call_channel_can_contain_identical_text_safely() -> None:
    call = 'CALL timer.start {"seconds":5}'
    channels = grammar.ModelChannels(call, (call,))
    parsed = grammar.calls_from_channels(channels, registry())
    assert len(parsed) == 1
    assert parsed[0].arguments == {"seconds": 5}
