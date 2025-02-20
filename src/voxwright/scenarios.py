"""Seeded synthetic scenarios with planted application ground truth."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from voxwright.core import JSONValue, ensure_json_value
from voxwright.identifiers import Identifier
from voxwright.seeding import SeedStream


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


def schedule_scenario(seed: int) -> SyntheticScenario:
    """Generate a reproducible calendar task with planted title and hour."""
    stream = SeedStream(seed, "schedule")
    titles = ("project review", "lab meeting", "study session", "team sync")
    hours = (9, 10, 14, 19)
    title = stream.choose(titles)
    hour = stream.choose(hours)
    goal = TaskGoal(
        Identifier("schedule-main"),
        TaskType.SCHEDULE,
        {"title": title, "hour": hour},
        (ExpectedToolCall(Identifier("calendar.create"), {"title": title, "hour": hour}),),
    )
    persona = stream.choose(DEFAULT_PERSONAS)
    return SyntheticScenario(
        Identifier(f"schedule-{seed}"),
        seed,
        persona,
        f"schedule {title} at {hour}",
        (goal,),
        difficulty=1 + stream.next_int() % 3,
    )


def application_scenario(task_type: TaskType, seed: int) -> SyntheticScenario:
    """Generate music, smart-home, or notes tasks from compact offline catalogs."""
    if task_type is TaskType.SCHEDULE:
        return schedule_scenario(seed)
    stream = SeedStream(seed, task_type.value)
    catalog: dict[TaskType, tuple[str, str, tuple[tuple[str, JSONValue], ...]]] = {
        TaskType.MUSIC: (
            "play",
            "music.play",
            (("track", stream.choose(("Blue Sky", "Night Walk", "Morning Light"))),),
        ),
        TaskType.SMART_HOME: (
            "set",
            "home.set-light",
            (("room", stream.choose(("study", "bedroom", "kitchen"))), ("on", True)),
        ),
        TaskType.NOTES: (
            "remember",
            "notes.add",
            (("text", stream.choose(("buy milk", "submit form", "call home"))),),
        ),
    }
    if task_type not in catalog:
        raise ValueError(f"task type requires composite generator: {task_type.value}")
    verb, tool_name, pairs = catalog[task_type]
    slots = dict(pairs)
    goal = TaskGoal(
        Identifier(f"{task_type.value}-main"),
        task_type,
        slots,
        (ExpectedToolCall(Identifier(tool_name), slots),),
    )
    rendered = " ".join(str(value) for value in slots.values())
    return SyntheticScenario(
        Identifier(f"{task_type.value}-{seed}"),
        seed,
        stream.choose(DEFAULT_PERSONAS),
        f"{verb} {rendered}",
        (goal,),
        difficulty=1 + stream.next_int() % 3,
    )
