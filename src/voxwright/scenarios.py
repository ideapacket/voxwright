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


@dataclass(frozen=True, slots=True)
class Persona:
    """Synthetic speaking traits that influence text-only fixture generation."""

    persona_id: Identifier
    locale: str
    pace: str
    quirks: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.locale or not self.pace:
            raise ValueError("persona locale and pace cannot be empty")
        if self.pace not in {"slow", "normal", "fast"}:
            raise ValueError(f"unsupported speaking pace: {self.pace}")
        if len(set(self.quirks)) != len(self.quirks):
            raise ValueError("persona quirks must be unique")


DEFAULT_PERSONAS = (
    Persona(Identifier("concise"), "zh-CN", "normal"),
    Persona(Identifier("hesitant"), "zh-CN", "slow", ("filler", "self-correction")),
    Persona(Identifier("rapid"), "en-US", "fast", ("run-on",)),
)


@dataclass(frozen=True, slots=True)
class SyntheticScenario:
    """An offline transcript fixture and its planted application truth."""

    scenario_id: Identifier
    seed: int
    persona: Persona
    transcript: str
    goals: tuple[TaskGoal, ...]
    difficulty: int = 1
    noise_rate: float = 0.0
    adversarial: bool = False

    def __post_init__(self) -> None:
        if isinstance(self.seed, bool) or self.seed < 0:
            raise ValueError("scenario seed must be non-negative")
        if not self.transcript:
            raise ValueError("scenario transcript cannot be empty")
        if not self.goals:
            raise ValueError("scenario needs at least one task goal")
        if not 1 <= self.difficulty <= 5:
            raise ValueError("scenario difficulty must be between 1 and 5")
        if not 0.0 <= self.noise_rate <= 1.0:
            raise ValueError("scenario noise rate must be between 0 and 1")
        object.__setattr__(self, "noise_rate", round(self.noise_rate, 6))

    @property
    def planted_calls(self) -> tuple[ExpectedToolCall, ...]:
        return tuple(call for goal in self.goals for call in goal.tool_calls)

    @property
    def planted_slots(self) -> dict[str, JSONValue]:
        slots: dict[str, JSONValue] = {}
        for goal in self.goals:
            for name, value in goal.slots.items():
                slots[f"{goal.goal_id}.{name}"] = value
        return slots
