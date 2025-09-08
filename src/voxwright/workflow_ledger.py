"""Tamper-evident execution ledger for workflow checkpoints."""

from __future__ import annotations

from dataclasses import dataclass

from voxwright.core import JSONValue
from voxwright.hashing import EMPTY_DIGEST, ChainLink, append_link, validate_chain
from voxwright.identifiers import Identifier


@dataclass(slots=True)
class WorkflowLedger:
    links: list[ChainLink]

    def __init__(self) -> None:
        self.links = []

    def record(self, step_id: Identifier, state: dict[str, JSONValue]) -> ChainLink:
        link = append_link(self.links, {"step_id": str(step_id), "state": state})
        self.links.append(link)
        return link

    def validate(self) -> int | None:
        return validate_chain(self.links)

    @property
    def completed_steps(self) -> tuple[Identifier, ...]:
        completed: list[Identifier] = []
        for link in self.links:
            if not isinstance(link.payload, dict):
                raise ValueError("workflow ledger payload must be an object")
            step_id = link.payload.get("step_id")
            if not isinstance(step_id, str):
                raise ValueError("workflow ledger step_id must be a string")
            completed.append(Identifier(step_id))
        return tuple(completed)

    def checkpoint(self) -> dict[str, JSONValue]:
        """Return replayable state from the last verified ledger entry."""
        if self.validate() is not None:
            raise ValueError("cannot checkpoint invalid workflow ledger")
        if not self.links:
            return {"schema_version": 1, "completed": [], "state": {}, "digest": EMPTY_DIGEST}
        payload = self.links[-1].payload
        if not isinstance(payload, dict) or not isinstance(payload.get("state"), dict):
            raise ValueError("workflow ledger state must be an object")
        return {
            "schema_version": 1,
            "completed": [str(item) for item in self.completed_steps],
            "state": payload["state"],
            "digest": self.links[-1].digest,
        }


def remaining_steps(
    ordered: tuple[Identifier, ...], checkpoint: dict[str, JSONValue]
) -> tuple[Identifier, ...]:
    """Resume only after a checkpoint's completed prefix."""
    completed = checkpoint.get("completed")
    if not isinstance(completed, list):
        raise ValueError("checkpoint completed steps must be a string array")
    decoded_items: list[Identifier] = []
    for item in completed:
        if not isinstance(item, str):
            raise ValueError("checkpoint completed steps must be a string array")
        decoded_items.append(Identifier(item))
    decoded = tuple(decoded_items)
    if ordered[: len(decoded)] != decoded:
        raise ValueError("checkpoint is not a prefix of workflow order")
    return ordered[len(decoded) :]
