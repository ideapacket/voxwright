"""Permissioned in-process tool sandbox over deterministic synthetic stores."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

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
