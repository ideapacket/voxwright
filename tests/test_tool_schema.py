"""Tests for typed application tool schemas."""

from __future__ import annotations

import pytest

import voxwright.tool_schema as schemas
from voxwright.identifiers import Identifier


def parameter(name: str = "title", required: bool = True) -> schemas.ParameterSpec:
    return schemas.ParameterSpec(Identifier(name), schemas.ValueType.STRING, required)


def test_value_type_contract_is_stable() -> None:
    assert [item.value for item in schemas.ValueType] == [
        "string",
        "integer",
        "number",
        "boolean",
        "object",
        "array",
    ]


def test_tool_schema_preserves_parameter_order_and_idempotency() -> None:
    schema = schemas.ToolSchema(
        Identifier("calendar.create"), (parameter(), parameter("location", False)), "create event"
    )
    assert [item.name.value for item in schema.parameters] == ["title", "location"]
    assert not schema.idempotent


def test_tool_schema_rejects_duplicate_parameters_and_empty_description() -> None:
    with pytest.raises(ValueError, match="must be unique"):
        schemas.ToolSchema(Identifier("notes.add"), (parameter(), parameter()), "add")
    with pytest.raises(ValueError, match="description cannot be empty"):
        schemas.ToolSchema(Identifier("notes.add"), (), " ")


def test_schema_roundtrip_has_golden_public_shape() -> None:
    schema = schemas.ToolSchema(
        Identifier("music.play"), (parameter("track"),), "play synthetic track", True
    )
    assert schema.to_dict() == {
        "name": "music.play",
        "description": "play synthetic track",
        "idempotent": True,
        "parameters": [
            {
                "name": "track",
                "type": "string",
                "required": True,
                "nullable": False,
                "default": None,
            }
        ],
    }
    assert schemas.ToolSchema.from_dict(schema.to_dict()) == schema


def test_schema_decoder_rejects_unknown_top_level_field() -> None:
    value = schemas.ToolSchema(Identifier("timer.start"), (), "start").to_dict()
    value["future"] = True
    with pytest.raises(ValueError, match="invalid tool schema shape"):
        schemas.ToolSchema.from_dict(value)
