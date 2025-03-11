"""Typed schemas for validating application tool calls."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from voxwright.core import JSONValue, ensure_json_value
from voxwright.identifiers import Identifier


class ValueType(str, Enum):
    STRING = "string"
    INTEGER = "integer"
    NUMBER = "number"
    BOOLEAN = "boolean"
    OBJECT = "object"
    ARRAY = "array"


@dataclass(frozen=True, slots=True)
class ParameterSpec:
    """One named tool argument and its application-level constraints."""

    name: Identifier
    value_type: ValueType
    required: bool = True
    nullable: bool = False
    default: JSONValue = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "default", ensure_json_value(self.default, "$.default"))
        if self.required and self.default is not None:
            raise ValueError("required parameter cannot declare a default")
        if self.default is None and not self.nullable and not self.required:
            return


@dataclass(frozen=True, slots=True)
class ToolSchema:
    """A tool name, ordered parameters, and side-effect metadata."""

    name: Identifier
    parameters: tuple[ParameterSpec, ...]
    description: str
    idempotent: bool = False

    def __post_init__(self) -> None:
        if not self.description.strip():
            raise ValueError("tool description cannot be empty")
        names = [parameter.name for parameter in self.parameters]
        if len(set(names)) != len(names):
            raise ValueError("tool parameter names must be unique")
