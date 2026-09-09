"""Tests for typed application tool schemas."""

from __future__ import annotations

from pathlib import Path

import pytest

import voxwright.tool_schema as schemas
from voxwright.identifiers import Identifier

GOLDEN = Path(__file__).parent / "golden" / "tool_registry.json"


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


def test_schema_decoder_never_coerces_identity_or_idempotency_types() -> None:
    value = schemas.ToolSchema(Identifier("timer.start"), (), "start").to_dict()
    value["name"] = 7
    with pytest.raises(TypeError, match=r"\$\.name: expected string"):
        schemas.ToolSchema.from_dict(value)
    value = schemas.ToolSchema(Identifier("timer.start"), (), "start").to_dict()
    value["idempotent"] = 1
    with pytest.raises(TypeError, match=r"\$\.idempotent: expected boolean"):
        schemas.ToolSchema.from_dict(value)


def test_parameter_decoder_requires_exact_flag_and_type_values() -> None:
    value = schemas.ToolSchema(Identifier("notes.add"), (parameter("text"),), "add").to_dict()
    value["parameters"][0]["required"] = 1  # type: ignore[index]
    with pytest.raises(TypeError, match="flags must be booleans"):
        schemas.ToolSchema.from_dict(value)
    value = schemas.ToolSchema(Identifier("notes.add"), (parameter("text"),), "add").to_dict()
    value["parameters"][0]["type"] = "timestamp"  # type: ignore[index]
    with pytest.raises(ValueError, match="unknown value type 'timestamp'"):
        schemas.ToolSchema.from_dict(value)


def test_registry_resolves_tools_in_sorted_name_order() -> None:
    registry = schemas.ToolRegistry()
    notes = schemas.ToolSchema(Identifier("notes.add"), (), "add note")
    calendar = schemas.ToolSchema(Identifier("calendar.create"), (), "create event")
    registry.register(notes)
    registry.register(calendar)
    assert registry.resolve("notes.add") is notes
    assert [name.value for name in registry.names()] == ["calendar.create", "notes.add"]


def test_registry_rejects_duplicate_and_unknown_tools() -> None:
    schema = schemas.ToolSchema(Identifier("timer.start"), (), "start timer")
    registry = schemas.ToolRegistry((schema,))
    with pytest.raises(ValueError, match="already registered"):
        registry.register(schema)
    with pytest.raises(ValueError, match=r"unknown tool: timer\.stop"):
        registry.resolve("timer.stop")


@pytest.mark.parametrize(
    ("value", "value_type", "expected"),
    [
        ("42", schemas.ValueType.INTEGER, 42),
        ("-3", schemas.ValueType.INTEGER, -3),
        ("2.5", schemas.ValueType.NUMBER, 2.5),
        ("TRUE", schemas.ValueType.BOOLEAN, True),
        ({"x": 1}, schemas.ValueType.OBJECT, {"x": 1}),
        ([1, 2], schemas.ValueType.ARRAY, [1, 2]),
    ],
)
def test_argument_coercions_are_explicit(
    value: object, value_type: schemas.ValueType, expected: object
) -> None:
    assert schemas.coerce_value(value, value_type, "$.value") == expected  # type: ignore[arg-type]


def test_argument_coercion_never_treats_boolean_as_number() -> None:
    with pytest.raises(TypeError, match=r"\$\.count: cannot coerce"):
        schemas.coerce_value(True, schemas.ValueType.INTEGER, "$.count")


def test_argument_validation_fills_defaults_in_schema_order() -> None:
    schema = schemas.ToolSchema(
        Identifier("music.play"),
        (
            parameter("track"),
            schemas.ParameterSpec(Identifier("volume"), schemas.ValueType.INTEGER, False, False, 5),
        ),
        "play",
    )
    assert schemas.validate_arguments(schema, {"track": "Blue"}) == {"track": "Blue", "volume": 5}


def test_argument_validation_rejects_missing_unknown_and_null() -> None:
    schema = schemas.ToolSchema(Identifier("notes.add"), (parameter("text"),), "add")
    with pytest.raises(ValueError, match="missing required argument: text"):
        schemas.validate_arguments(schema, {})
    with pytest.raises(ValueError, match="unknown argument: extra"):
        schemas.validate_arguments(schema, {"text": "x", "extra": 1})
    with pytest.raises(ValueError, match="not nullable"):
        schemas.validate_arguments(schema, {"text": None})


def test_registry_roundtrip_sorts_tools_for_determinism() -> None:
    registry = schemas.ToolRegistry(
        (
            schemas.ToolSchema(Identifier("notes.add"), (), "note"),
            schemas.ToolSchema(Identifier("calendar.create"), (), "calendar"),
        )
    )
    encoded = registry.to_dict()
    assert [item["name"] for item in encoded["tools"]] == [  # type: ignore[index]
        "calendar.create",
        "notes.add",
    ]
    assert schemas.ToolRegistry.from_dict(encoded).to_dict() == encoded


def test_registry_decoder_rejects_future_schema() -> None:
    value = schemas.ToolRegistry().to_dict()
    value["schema_version"] = 2
    with pytest.raises(ValueError, match="unsupported tool registry"):
        schemas.ToolRegistry.from_dict(value)
    value["schema_version"] = True
    with pytest.raises(ValueError, match="unsupported tool registry"):
        schemas.ToolRegistry.from_dict(value)


def test_registry_text_codec_is_canonical_and_reversible() -> None:
    registry = schemas.ToolRegistry(
        (schemas.ToolSchema(Identifier("notes.add"), (parameter("text"),), "add note"),)
    )
    encoded = schemas.encode_registry(registry)
    assert encoded.endswith("\n") and ": " not in encoded and ", " not in encoded
    assert schemas.decode_registry(encoded).to_dict() == registry.to_dict()
    assert schemas.encode_registry(schemas.decode_registry(encoded)).encode() == encoded.encode()


def test_registry_text_decoder_rejects_empty_and_trailing_documents() -> None:
    with pytest.raises(ValueError, match="document is empty"):
        schemas.decode_registry("\n")
    with pytest.raises(ValueError):
        schemas.decode_registry(schemas.encode_registry(schemas.ToolRegistry()) + "{}")


def test_registry_files_roundtrip_without_overwrite(tmp_path: Path) -> None:
    registry = schemas.ToolRegistry(
        (schemas.ToolSchema(Identifier("notes.add"), (parameter("text"),), "add"),)
    )
    path = tmp_path / "tools.json"
    schemas.write_registry(path, registry)
    assert schemas.load_registry(path).to_dict() == registry.to_dict()
    with pytest.raises(FileExistsError, match="output already exists"):
        schemas.write_registry(path, schemas.ToolRegistry())
    path.unlink()
    path.write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="missing terminal newline"):
        schemas.load_registry(path)


def test_tool_registry_matches_reviewed_golden_bytes() -> None:
    registry = schemas.ToolRegistry(
        (schemas.ToolSchema(Identifier("notes.add"), (parameter("text"),), "add synthetic note"),)
    )
    assert schemas.encode_registry(registry).encode() == GOLDEN.read_bytes()
    assert schemas.decode_registry(GOLDEN.read_text(encoding="utf-8")).to_dict() == (
        registry.to_dict()
    )


def test_parameter_defaults_must_be_optional() -> None:
    with pytest.raises(ValueError, match="required parameter cannot declare a default"):
        schemas.ParameterSpec(Identifier("count"), schemas.ValueType.INTEGER, True, False, 1)


def test_nullable_parameter_accepts_null_without_coercion() -> None:
    schema = schemas.ToolSchema(
        Identifier("notes.add"),
        (schemas.ParameterSpec(Identifier("folder"), schemas.ValueType.STRING, False, True),),
        "add",
    )
    assert schemas.validate_arguments(schema, {"folder": None}) == {"folder": None}


@pytest.mark.parametrize(
    ("value", "value_type"),
    [
        (1.5, schemas.ValueType.INTEGER),
        ("yes", schemas.ValueType.BOOLEAN),
        ([], schemas.ValueType.OBJECT),
    ],
)
def test_coercion_rejects_lossy_or_shape_changing_values(
    value: object, value_type: schemas.ValueType
) -> None:
    with pytest.raises(TypeError, match="cannot coerce"):
        schemas.coerce_value(value, value_type, "$.value")  # type: ignore[arg-type]
