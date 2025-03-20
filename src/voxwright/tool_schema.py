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

    def to_dict(self) -> dict[str, JSONValue]:
        return {
            "name": str(self.name),
            "description": self.description,
            "idempotent": self.idempotent,
            "parameters": [
                {
                    "name": str(item.name),
                    "type": item.value_type.value,
                    "required": item.required,
                    "nullable": item.nullable,
                    "default": item.default,
                }
                for item in self.parameters
            ],
        }

    @classmethod
    def from_dict(cls, value: object) -> ToolSchema:
        checked = ensure_json_value(value, "$")
        if not isinstance(checked, dict) or set(checked) != {
            "name",
            "description",
            "idempotent",
            "parameters",
        }:
            raise ValueError("invalid tool schema shape")
        parameters = checked["parameters"]
        if not isinstance(parameters, list):
            raise TypeError("$.parameters: expected array")
        decoded = []
        for index, item in enumerate(parameters):
            if not isinstance(item, dict) or set(item) != {
                "name",
                "type",
                "required",
                "nullable",
                "default",
            }:
                raise ValueError(f"$.parameters[{index}]: invalid parameter shape")
            decoded.append(
                ParameterSpec(
                    Identifier(str(item["name"])),
                    ValueType(str(item["type"])),
                    bool(item["required"]),
                    bool(item["nullable"]),
                    item["default"],
                )
            )
        return cls(
            Identifier(str(checked["name"])),
            tuple(decoded),
            str(checked["description"]),
            bool(checked["idempotent"]),
        )


class ToolRegistry:
    """An immutable-name registry that rejects ambiguous tool definitions."""

    def __init__(self, tools: tuple[ToolSchema, ...] = ()) -> None:
        self._tools: dict[Identifier, ToolSchema] = {}
        for tool in tools:
            self.register(tool)

    def register(self, schema: ToolSchema) -> None:
        if schema.name in self._tools:
            raise ValueError(f"tool already registered: {schema.name}")
        self._tools[schema.name] = schema

    def resolve(self, name: str | Identifier) -> ToolSchema:
        identifier = name if isinstance(name, Identifier) else Identifier(name)
        try:
            return self._tools[identifier]
        except KeyError as error:
            raise ValueError(f"unknown tool: {identifier}") from error

    def names(self) -> tuple[Identifier, ...]:
        return tuple(sorted(self._tools))
