"""Strict dedicated-channel grammar for model-emitted tool calls."""

from __future__ import annotations

from dataclasses import dataclass

from voxwright.core import JSONValue, canonical_json, parse_json
from voxwright.identifiers import Identifier
from voxwright.tool_schema import ToolRegistry, validate_arguments

CALL_PREFIX = "CALL "


@dataclass(frozen=True, slots=True)
class ParsedCall:
    tool_name: Identifier
    arguments: dict[str, JSONValue]


class CallParseError(ValueError):
    """A precise grammar failure with stable code and byte offset."""

    def __init__(self, code: str, offset: int, message: str) -> None:
        super().__init__(f"{code} at {offset}: {message}")
        self.code = code
        self.offset = offset
        self.message = message


def parse_call(text: str) -> ParsedCall:
    """Parse ``CALL tool.name {json-object}`` with no trailing material."""
    if not text.startswith(CALL_PREFIX):
        raise CallParseError("missing-prefix", 0, "expected 'CALL '")
    separator = text.find(" ", len(CALL_PREFIX))
    if separator < 0:
        raise CallParseError("missing-arguments", len(text), "expected JSON object")
    name_text = text[len(CALL_PREFIX) : separator]
    try:
        name = Identifier(name_text)
    except ValueError as error:
        raise CallParseError("invalid-tool", len(CALL_PREFIX), str(error)) from error
    argument_text = text[separator + 1 :]
    if argument_text != argument_text.strip():
        raise CallParseError("invalid-json", separator + 1, "argument object has outer whitespace")
    try:
        value = parse_json(argument_text)
    except (TypeError, ValueError) as error:
        raise CallParseError("invalid-json", separator + 1, str(error)) from error
    if not isinstance(value, dict):
        raise CallParseError("arguments-not-object", separator + 1, "expected object")
    return ParsedCall(name, value)


def format_call(call: ParsedCall) -> str:
    return f"{CALL_PREFIX}{call.tool_name} {canonical_json(call.arguments)}"


def parse_validated_call(text: str, registry: ToolRegistry) -> ParsedCall:
    """Parse syntax, resolve the tool, then coerce and validate arguments."""
    parsed = parse_call(text)
    schema = registry.resolve(parsed.tool_name)
    return ParsedCall(parsed.tool_name, validate_arguments(schema, parsed.arguments))


@dataclass(frozen=True, slots=True)
class ModelChannels:
    """Keep untrusted transcript text separate from explicit call syntax."""

    transcript: str
    call_texts: tuple[str, ...] = ()


def calls_from_channels(channels: ModelChannels, registry: ToolRegistry) -> tuple[ParsedCall, ...]:
    """Parse only the dedicated call channel; transcript contents remain inert."""
    return tuple(parse_validated_call(text, registry) for text in channels.call_texts)


@dataclass(frozen=True, slots=True)
class CallDiagnostic:
    index: int
    code: str
    message: str


def recover_calls(
    call_texts: tuple[str, ...], registry: ToolRegistry
) -> tuple[tuple[ParsedCall, ...], tuple[CallDiagnostic, ...]]:
    """Recover valid independent calls while retaining deterministic failures."""
    calls: list[ParsedCall] = []
    diagnostics: list[CallDiagnostic] = []
    for index, text in enumerate(call_texts):
        try:
            calls.append(parse_validated_call(text, registry))
        except CallParseError as error:
            diagnostics.append(CallDiagnostic(index, error.code, error.message))
        except (TypeError, ValueError) as error:
            diagnostics.append(CallDiagnostic(index, "validation", str(error)))
    return tuple(calls), tuple(diagnostics)
