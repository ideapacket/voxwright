"""Permissioned in-process tool sandbox over deterministic synthetic stores."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from voxwright.core import JSONValue
from voxwright.hashing import ChainLink, append_link, validate_chain
from voxwright.identifiers import Identifier


class PermissionDecision(str, Enum):
    ALLOW = "allow"
    CONFIRM = "confirm"
    DENY = "deny"


@dataclass(frozen=True, slots=True)
class PermissionPolicy:
    """Resolve exact tool rules with deny-by-default semantics."""

    rules: dict[Identifier, PermissionDecision]

    def __post_init__(self) -> None:
        object.__setattr__(self, "rules", dict(self.rules))

    def decide(self, tool_name: str | Identifier) -> PermissionDecision:
        name = tool_name if isinstance(tool_name, Identifier) else Identifier(tool_name)
        return self.rules.get(name, PermissionDecision.DENY)


@dataclass(slots=True)
class SideEffectLedger:
    """Tamper-evident ordered evidence for attempted and executed tools."""

    links: list[ChainLink]

    def __init__(self) -> None:
        self.links = []

    def record(
        self,
        tool_name: Identifier,
        arguments: dict[str, JSONValue],
        executed: bool,
        result: JSONValue,
    ) -> ChainLink:
        payload: dict[str, JSONValue] = {
            "tool_name": str(tool_name),
            "arguments": arguments,
            "executed": executed,
            "result": result,
        }
        link = append_link(self.links, payload)
        self.links.append(link)
        return link

    def validate(self) -> int | None:
        return validate_chain(self.links)
