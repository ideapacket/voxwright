"""Public catalog of versioned serialized artifact envelopes."""

from __future__ import annotations

from dataclasses import dataclass

from voxwright.core import JSONValue


@dataclass(frozen=True, slots=True)
class ArtifactSchema:
    name: str
    version: int
    media_type: str
    required_fields: tuple[str, ...]
    checksummed: bool

    def __post_init__(self) -> None:
        if not self.name or self.version < 1:
            raise ValueError("artifact schema needs a name and positive version")
        if not self.media_type.startswith("application/"):
            raise ValueError("artifact schema media type must be an application type")
        if not self.required_fields or len(set(self.required_fields)) != len(self.required_fields):
            raise ValueError("artifact schema fields must be nonempty and unique")

    def to_dict(self) -> dict[str, JSONValue]:
        return {
            "name": self.name,
            "version": self.version,
            "media_type": self.media_type,
            "required_fields": list(self.required_fields),
            "checksummed": self.checksummed,
        }


ARTIFACT_SCHEMAS = (
    ArtifactSchema(
        "campaign",
        1,
        "application/json",
        ("schema_version", "name", "seed", "config", "config_digest", "metrics"),
        False,
    ),
    ArtifactSchema(
        "context-snapshot",
        1,
        "application/json",
        ("schema_version", "token_budget", "attachments"),
        False,
    ),
    ArtifactSchema(
        "event",
        1,
        "application/json",
        ("schema_version", "session_id", "sequence", "at_ms", "kind", "payload"),
        False,
    ),
    ArtifactSchema(
        "frame-snapshot",
        1,
        "application/json",
        ("schema_version", "frame_id", "task_type", "state", "slots"),
        False,
    ),
    ArtifactSchema(
        "metric-bundle",
        1,
        "application/json",
        ("schema_version", "run_count", "task_success", "slots", "tools", "efficiency"),
        False,
    ),
    ArtifactSchema(
        "model-artifact",
        1,
        "application/x-ndjson",
        ("schema_version", "model", "checksum"),
        True,
    ),
    ArtifactSchema(
        "replay-trace",
        1,
        "application/json",
        ("schema_version", "session_id", "seed", "events"),
        False,
    ),
    ArtifactSchema(
        "run-stream",
        1,
        "application/x-ndjson",
        ("schema_version", "run", "checksum"),
        True,
    ),
    ArtifactSchema(
        "runtime-turns",
        1,
        "application/json",
        ("schema_version", "turns"),
        False,
    ),
    ArtifactSchema(
        "scenario-manifest",
        1,
        "application/x-ndjson",
        ("schema_version", "scenario", "checksum"),
        True,
    ),
    ArtifactSchema(
        "session-record",
        1,
        "application/x-ndjson",
        ("schema_version", "index", "previous", "event", "digest"),
        True,
    ),
    ArtifactSchema(
        "side-effect-ledger",
        1,
        "application/json",
        ("schema_version", "links"),
        True,
    ),
    ArtifactSchema(
        "tool-registry",
        1,
        "application/json",
        ("schema_version", "tools"),
        False,
    ),
    ArtifactSchema(
        "workflow-checkpoint",
        1,
        "application/json",
        ("schema_version", "completed", "state", "digest"),
        True,
    ),
    ArtifactSchema(
        "workflow-definition",
        1,
        "application/json",
        ("schema_version", "name", "version", "start", "steps"),
        False,
    ),
)


def artifact_schema(name: str) -> ArtifactSchema:
    try:
        return next(item for item in ARTIFACT_SCHEMAS if item.name == name)
    except StopIteration as error:
        raise ValueError(f"unknown artifact schema: {name}") from error


def schema_catalog() -> list[dict[str, JSONValue]]:
    return [item.to_dict() for item in ARTIFACT_SCHEMAS]
