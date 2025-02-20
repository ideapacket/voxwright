"""Seeded synthetic scenarios with planted application ground truth."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from voxwright.core import JSONValue, ensure_json_value
from voxwright.identifiers import Identifier


class TaskType(str, Enum):
    """Application task families supplied by the offline factory."""

    SCHEDULE = "schedule"
    MUSIC = "music"
    SMART_HOME = "smart-home"
    NOTES = "notes"
    MULTI_TASK = "multi-task"
    NESTED = "nested"


@dataclass(frozen=True, slots=True)
class ExpectedToolCall:
    """One planted tool invocation used only as synthetic ground truth."""

    tool_name: Identifier
    arguments: dict[str, JSONValue]

    def __post_init__(self) -> None:
        checked = ensure_json_value(self.arguments, "$.arguments")
        if not isinstance(checked, dict):
            raise TypeError("$.arguments: expected object")
        object.__setattr__(self, "arguments", checked)


@dataclass(frozen=True, slots=True)
class TaskGoal:
    """A synthetic task with planted slots and ordered tool calls."""

    goal_id: Identifier
    task_type: TaskType
    slots: dict[str, JSONValue]
    tool_calls: tuple[ExpectedToolCall, ...]

    def __post_init__(self) -> None:
        checked = ensure_json_value(self.slots, "$.slots")
        if not isinstance(checked, dict):
            raise TypeError("$.slots: expected object")
        for name in checked:
            Identifier(name)
        if not self.tool_calls:
            raise ValueError("task goal needs at least one planted tool call")
        object.__setattr__(self, "slots", checked)
