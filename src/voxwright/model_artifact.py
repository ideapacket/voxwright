"""Deterministic JSON artifacts for the optional trainable model."""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from voxwright.core import JSONValue, canonical_json, ensure_json_value, parse_json
from voxwright.hashing import object_digest
from voxwright.model_data import ClassInventory, TokenVocabulary
from voxwright.torch_model import TorchJointModel

MODEL_ARTIFACT_VERSION = 1
PARAMETER_NAMES = (
    "embedding.weight",
    "slot_head.weight",
    "slot_head.bias",
    "tool_head.weight",
    "tool_head.bias",
)


@dataclass(frozen=True, slots=True)
class ModelArtifact:
    vocabulary: tuple[str, ...]
    slot_classes: tuple[str, ...]
    tool_classes: tuple[str, ...]
    embedding_size: int
    seed: int
    parameters: dict[str, JSONValue]

    def __post_init__(self) -> None:
        TokenVocabulary(self.vocabulary)
        ClassInventory(self.slot_classes)
        ClassInventory(self.tool_classes)
        if isinstance(self.embedding_size, bool) or self.embedding_size < 1:
            raise ValueError("model artifact embedding size must be positive")
        if isinstance(self.seed, bool) or self.seed < 0:
            raise ValueError("model artifact seed must be non-negative")
        if set(self.parameters) != set(PARAMETER_NAMES):
            raise ValueError("model artifact parameter names are invalid")
        expected_shapes = {
            "embedding.weight": (len(self.vocabulary), self.embedding_size),
            "slot_head.weight": (len(self.slot_classes), self.embedding_size),
            "slot_head.bias": (len(self.slot_classes),),
            "tool_head.weight": (len(self.tool_classes), self.embedding_size),
            "tool_head.bias": (len(self.tool_classes),),
        }
        checked = ensure_json_value(self.parameters, "$.parameters")
        if not isinstance(checked, dict):
            raise TypeError("model artifact parameters must be an object")
        for name, shape in expected_shapes.items():
            try:
                array = np.asarray(checked[name], dtype=np.float64)
            except (TypeError, ValueError) as error:
                raise ValueError(f"model parameter {name} must be numeric") from error
            if array.shape != shape:
                raise ValueError(
                    f"model parameter {name} has shape {array.shape}, expected {shape}"
                )
            if any(not math.isfinite(float(value)) for value in array.flat):
                raise ValueError(f"model parameter {name} must contain finite values")
        object.__setattr__(self, "parameters", checked)

    def to_dict(self) -> dict[str, JSONValue]:
        return {
            "vocabulary": list(self.vocabulary),
            "slot_classes": list(self.slot_classes),
            "tool_classes": list(self.tool_classes),
            "embedding_size": self.embedding_size,
            "seed": self.seed,
            "parameters": self.parameters,
        }


def model_artifact_from_dict(value: object) -> ModelArtifact:
    fields = {
        "vocabulary",
        "slot_classes",
        "tool_classes",
        "embedding_size",
        "seed",
        "parameters",
    }
    if not isinstance(value, dict) or set(value) != fields:
        raise ValueError("invalid model artifact shape")
    for name in ("vocabulary", "slot_classes", "tool_classes"):
        if not isinstance(value[name], list) or not all(
            isinstance(item, str) for item in value[name]
        ):
            raise TypeError(f"model artifact {name} must be a string array")
    if isinstance(value["embedding_size"], bool) or not isinstance(value["embedding_size"], int):
        raise TypeError("model artifact embedding size must be an integer")
    if isinstance(value["seed"], bool) or not isinstance(value["seed"], int):
        raise TypeError("model artifact seed must be an integer")
    parameters = value["parameters"]
    if not isinstance(parameters, dict):
        raise TypeError("model artifact parameters must be an object")
    return ModelArtifact(
        tuple(value["vocabulary"]),
        tuple(value["slot_classes"]),
        tuple(value["tool_classes"]),
        value["embedding_size"],
        value["seed"],
        parameters,
    )


def encode_model_artifact(artifact: ModelArtifact) -> str:
    unsigned: dict[str, JSONValue] = {
        "schema_version": MODEL_ARTIFACT_VERSION,
        "model": artifact.to_dict(),
    }
    return canonical_json({**unsigned, "checksum": object_digest(unsigned)}) + "\n"


def decode_model_artifact(content: str) -> ModelArtifact:
    if not content.endswith("\n") or content.count("\n") != 1:
        raise ValueError("model artifact must contain one complete JSON line")
    value = parse_json(content)
    if not isinstance(value, dict) or set(value) != {"schema_version", "model", "checksum"}:
        raise ValueError("invalid model artifact envelope")
    if value["schema_version"] != MODEL_ARTIFACT_VERSION:
        raise ValueError("unsupported model artifact schema version")
    unsigned = {"schema_version": value["schema_version"], "model": value["model"]}
    if value["checksum"] != object_digest(unsigned):
        raise ValueError("model artifact checksum mismatch")
    return model_artifact_from_dict(value["model"])


def export_model(model: TorchJointModel) -> ModelArtifact:
    """Snapshot model parameters as inspectable CPU JSON values."""
    tensors = {
        "embedding.weight": model.embedding.weight,
        "slot_head.weight": model.slot_head.weight,
        "slot_head.bias": model.slot_head.bias,
        "tool_head.weight": model.tool_head.weight,
        "tool_head.bias": model.tool_head.bias,
    }
    parameters: dict[str, JSONValue] = {}
    for name, tensor in tensors.items():
        value = ensure_json_value(tensor.detach().cpu().tolist(), f"$.parameters.{name}")
        parameters[name] = value
    return ModelArtifact(
        model.vocabulary.tokens,
        model.slot_classes.names,
        model.tool_classes.names,
        model.embedding_size,
        model.seed,
        parameters,
    )
