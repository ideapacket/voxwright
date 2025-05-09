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
        return tuple(Identifier(str(link.payload["step_id"])) for link in self.links)  # type: ignore[index]

    def checkpoint(self) -> dict[str, JSONValue]:
        """Return replayable state from the last verified ledger entry."""
        if self.validate() is not None:
            raise ValueError("cannot checkpoint invalid workflow ledger")
        if not self.links:
            return {"schema_version": 1, "completed": [], "state": {}, "digest": EMPTY_DIGEST}
        payload = self.links[-1].payload
        return {
            "schema_version": 1,
            "completed": [str(item) for item in self.completed_steps],
            "state": payload["state"],  # type: ignore[index]
            "digest": self.links[-1].digest,
        }
