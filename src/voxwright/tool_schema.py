"""Typed schemas for validating application tool calls."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from voxwright.core import JSONValue, canonical_json, ensure_json_value, parse_json
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
        name = checked["name"]
        description = checked["description"]
        idempotent = checked["idempotent"]
        if not isinstance(name, str):
            raise TypeError("$.name: expected string")
        if not isinstance(description, str):
            raise TypeError("$.description: expected string")
        if not isinstance(idempotent, bool):
            raise TypeError("$.idempotent: expected boolean")
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
            parameter_name = item["name"]
            parameter_type = item["type"]
            required = item["required"]
            nullable = item["nullable"]
            if not isinstance(parameter_name, str) or not isinstance(parameter_type, str):
                raise TypeError(f"$.parameters[{index}]: name and type must be strings")
            if not isinstance(required, bool) or not isinstance(nullable, bool):
                raise TypeError(f"$.parameters[{index}]: flags must be booleans")
            try:
                value_type = ValueType(parameter_type)
            except ValueError as error:
                raise ValueError(
                    f"$.parameters[{index}].type: unknown value type {parameter_type!r}"
                ) from error
            decoded.append(
                ParameterSpec(
                    Identifier(parameter_name),
                    value_type,
                    required,
                    nullable,
                    item["default"],
                )
            )
        return cls(
            Identifier(name),
            tuple(decoded),
            description,
            idempotent,
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

    def to_dict(self) -> dict[str, JSONValue]:
        return {
            "schema_version": 1,
            "tools": [self._tools[name].to_dict() for name in sorted(self._tools)],
        }

    @classmethod
    def from_dict(cls, value: object) -> ToolRegistry:
        checked = ensure_json_value(value, "$")
        if not isinstance(checked, dict) or set(checked) != {"schema_version", "tools"}:
            raise ValueError("invalid tool registry shape")
        if checked["schema_version"] != 1:
            raise ValueError("unsupported tool registry schema version")
        tools = checked["tools"]
        if not isinstance(tools, list):
            raise TypeError("$.tools: expected array")
        return cls(tuple(ToolSchema.from_dict(item) for item in tools))


def encode_registry(registry: ToolRegistry) -> str:
    return canonical_json(registry.to_dict()) + "\n"


def decode_registry(text: str) -> ToolRegistry:
    if not text.strip():
        raise ValueError("tool registry document is empty")
    return ToolRegistry.from_dict(parse_json(text))


def coerce_value(value: JSONValue, value_type: ValueType, path: str) -> JSONValue:
    """Apply explicit, narrow coercions suitable for grammar-emitted arguments."""
    if value is None:
        return None
    if value_type is ValueType.STRING:
        if isinstance(value, str):
            return value
    elif value_type is ValueType.INTEGER:
        if isinstance(value, int) and not isinstance(value, bool):
            return value
        if isinstance(value, str) and value.lstrip("-").isdigit():
            return int(value)
    elif value_type is ValueType.NUMBER:
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return value
        if isinstance(value, str):
            try:
                return float(value)
            except ValueError:
                pass
    elif value_type is ValueType.BOOLEAN:
        if isinstance(value, bool):
            return value
        if isinstance(value, str) and value.lower() in {"true", "false"}:
            return value.lower() == "true"
    elif (value_type is ValueType.OBJECT and isinstance(value, dict)) or (
        value_type is ValueType.ARRAY and isinstance(value, list)
    ):
        return value
    raise TypeError(f"{path}: cannot coerce to {value_type.value}")


def validate_arguments(schema: ToolSchema, arguments: dict[str, JSONValue]) -> dict[str, JSONValue]:
    """Reject unknowns, fill optional defaults, and return schema-ordered arguments."""
    specs = {str(parameter.name): parameter for parameter in schema.parameters}
    unknown = arguments.keys() - specs.keys()
    if unknown:
        raise ValueError(f"unknown argument: {sorted(unknown)[0]}")
    validated: dict[str, JSONValue] = {}
    for name, spec in specs.items():
        if name not in arguments:
            if spec.required:
                raise ValueError(f"missing required argument: {name}")
            validated[name] = spec.default
            continue
        value = arguments[name]
        if value is None:
            if not spec.nullable:
                raise ValueError(f"argument is not nullable: {name}")
            validated[name] = None
        else:
            validated[name] = coerce_value(value, spec.value_type, f"$.{name}")
    return validated
