"""Deterministic primitives shared by versioned artifacts."""

from __future__ import annotations

import json
import math
from typing import TypeAlias, cast

JSONScalar: TypeAlias = None | bool | int | float | str
JSONValue: TypeAlias = JSONScalar | list["JSONValue"] | dict[str, "JSONValue"]


def ensure_json_value(value: object, path: str = "$") -> JSONValue:
    """Return a strictly JSON-shaped value or raise with its failing path."""
    if value is None or isinstance(value, (bool, str)):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError(f"{path}: non-finite number")
        return value
    if isinstance(value, list):
        return [ensure_json_value(item, f"{path}[{index}]") for index, item in enumerate(value)]
    if isinstance(value, dict):
        output: dict[str, JSONValue] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise TypeError(f"{path}: object key must be a string")
            output[key] = ensure_json_value(item, f"{path}.{key}")
        return output
    raise TypeError(f"{path}: unsupported JSON value {type(value).__name__}")


def canonical_json(value: object) -> str:
    """Serialize a strict JSON value with stable ordering and spacing."""
    checked = ensure_json_value(value)
    return json.dumps(checked, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def canonical_bytes(value: object) -> bytes:
    """Encode canonical JSON as UTF-8."""
    return canonical_json(value).encode("utf-8")


def parse_json(text: str) -> JSONValue:
    """Parse text and enforce the strict JSON value contract."""
    return ensure_json_value(cast(object, json.loads(text)))
