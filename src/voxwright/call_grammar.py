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
