"""Typed workflow checkpoint artifacts and recovery validation."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from voxwright.core import JSONValue, canonical_json, ensure_json_value, parse_json
from voxwright.hashing import EMPTY_DIGEST, verify_digest
from voxwright.identifiers import Identifier
from voxwright.workflow_ledger import WorkflowLedger


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


CHECKPOINT_FIELDS = frozenset({"schema_version", "completed", "state", "digest"})


def checkpoint_to_dict(checkpoint: WorkflowCheckpoint) -> dict[str, JSONValue]:
    return {
        "schema_version": checkpoint.schema_version,
        "completed": [str(item) for item in checkpoint.completed],
        "state": checkpoint.state,
        "digest": checkpoint.digest,
    }


def checkpoint_from_dict(value: JSONValue) -> WorkflowCheckpoint:
    if not isinstance(value, dict):
        raise TypeError("$: expected checkpoint object")
    fields = set(value)
    if fields != CHECKPOINT_FIELDS:
        missing = sorted(CHECKPOINT_FIELDS - fields)
        unknown = sorted(fields - CHECKPOINT_FIELDS)
        raise ValueError(f"$: checkpoint fields differ; missing={missing}; unknown={unknown}")
    schema_version = value["schema_version"]
    completed = value["completed"]
    state = value["state"]
    digest = value["digest"]
    if isinstance(schema_version, bool) or not isinstance(schema_version, int):
        raise TypeError("$.schema_version: expected integer")
    if not isinstance(completed, list):
        raise TypeError("$.completed: expected string array")
    decoded: list[Identifier] = []
    for index, item in enumerate(completed):
        if not isinstance(item, str):
            raise TypeError(f"$.completed[{index}]: expected string")
        decoded.append(Identifier(item))
    if not isinstance(state, dict):
        raise TypeError("$.state: expected object")
    if not isinstance(digest, str):
        raise TypeError("$.digest: expected string")
    return WorkflowCheckpoint(tuple(decoded), state, digest, schema_version)


def encode_checkpoint(checkpoint: WorkflowCheckpoint) -> str:
    return canonical_json(checkpoint_to_dict(checkpoint)) + "\n"


def decode_checkpoint(text: str) -> WorkflowCheckpoint:
    if not text.strip():
        raise ValueError("checkpoint document is empty")
    return checkpoint_from_dict(parse_json(text))


def load_checkpoint(path: Path) -> WorkflowCheckpoint:
    text = path.read_text(encoding="utf-8")
    if text and not text.endswith("\n"):
        raise ValueError(f"checkpoint file is missing terminal newline: {path}")
    return decode_checkpoint(text)


def write_checkpoint(path: Path, checkpoint: WorkflowCheckpoint) -> None:
    try:
        with path.open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(encode_checkpoint(checkpoint))
    except FileExistsError as error:
        raise FileExistsError(f"checkpoint output already exists: {path}") from error


def checkpoint_from_ledger(ledger: WorkflowLedger) -> WorkflowCheckpoint:
    """Convert only a ledger-validated in-memory checkpoint."""
    return checkpoint_from_dict(ledger.checkpoint())


def verify_checkpoint(checkpoint: WorkflowCheckpoint, ledger: WorkflowLedger) -> None:
    """Require a checkpoint to exactly match the verified ledger tail."""
    if ledger.validate() is not None:
        raise ValueError("workflow ledger is invalid")
    expected = checkpoint_from_ledger(ledger)
    if checkpoint != expected:
        raise ValueError("checkpoint does not match workflow ledger")
