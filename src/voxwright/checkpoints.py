"""Typed workflow checkpoint artifacts and recovery validation."""

from __future__ import annotations

from dataclasses import dataclass

from voxwright.core import JSONValue, ensure_json_value
from voxwright.hashing import EMPTY_DIGEST, verify_digest
from voxwright.identifiers import Identifier


@dataclass(frozen=True, slots=True)
class WorkflowCheckpoint:
    """A completed workflow prefix and its last verified state."""

    completed: tuple[Identifier, ...]
    state: dict[str, JSONValue]
    digest: str = EMPTY_DIGEST
    schema_version: int = 1

    def __post_init__(self) -> None:
        if self.schema_version != 1:
            raise ValueError(f"unsupported checkpoint schema version: {self.schema_version}")
        checked = ensure_json_value(self.state, "$.state")
        if not isinstance(checked, dict):
            raise TypeError("$.state: expected object")
        object.__setattr__(self, "state", checked)
        if len(set(self.completed)) != len(self.completed):
            raise ValueError("checkpoint completed steps must be unique")
        if not verify_digest(b"", self.digest) and not (
            self.digest.startswith("sha256:") and len(self.digest) == 71
        ):
            raise ValueError("checkpoint digest must be algorithm-qualified SHA-256")
