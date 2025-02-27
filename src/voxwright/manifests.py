"""Versioned, checksummed JSONL manifests for synthetic scenarios."""

from __future__ import annotations

from pathlib import Path

from voxwright.core import JSONValue, canonical_json, parse_json
from voxwright.hashing import object_digest
from voxwright.identifiers import Identifier
from voxwright.scenarios import (
    ExpectedToolCall,
    Persona,
    SyntheticScenario,
    TaskGoal,
    TaskType,
)

MANIFEST_SCHEMA_VERSION = 1


def scenario_to_dict(scenario: SyntheticScenario) -> dict[str, JSONValue]:
    """Encode every planted scenario fact into its versioned public shape."""
    return {
        "scenario_id": str(scenario.scenario_id),
        "seed": scenario.seed,
        "persona": {
            "persona_id": str(scenario.persona.persona_id),
            "locale": scenario.persona.locale,
            "pace": scenario.persona.pace,
            "quirks": list(scenario.persona.quirks),
        },
        "transcript": scenario.transcript,
        "goals": [
            {
                "goal_id": str(goal.goal_id),
                "task_type": goal.task_type.value,
                "slots": goal.slots,
                "tool_calls": [
                    {"tool_name": str(call.tool_name), "arguments": call.arguments}
                    for call in goal.tool_calls
                ],
            }
            for goal in scenario.goals
        ],
        "difficulty": scenario.difficulty,
        "noise_rate": scenario.noise_rate,
        "adversarial": scenario.adversarial,
    }


def manifest_entry(scenario: SyntheticScenario) -> dict[str, JSONValue]:
    payload = scenario_to_dict(scenario)
    unsigned: dict[str, JSONValue] = {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "scenario": payload,
    }
    return {**unsigned, "checksum": object_digest(unsigned)}


def encode_manifest(scenarios: list[SyntheticScenario]) -> str:
    return "".join(canonical_json(manifest_entry(scenario)) + "\n" for scenario in scenarios)


def write_manifest(path: str | Path, scenarios: list[SyntheticScenario]) -> None:
    Path(path).write_text(encode_manifest(scenarios), encoding="utf-8", newline="\n")


def _scenario_from_dict(value: dict[str, JSONValue]) -> SyntheticScenario:
    persona_value = value["persona"]
    goals_value = value["goals"]
    if not isinstance(persona_value, dict) or not isinstance(goals_value, list):
        raise ValueError("manifest scenario has invalid persona or goals")
    persona = Persona(
        Identifier(str(persona_value["persona_id"])),
        str(persona_value["locale"]),
        str(persona_value["pace"]),
        tuple(str(item) for item in persona_value["quirks"]),  # type: ignore[union-attr]
    )
    goals = []
    for item in goals_value:
        if not isinstance(item, dict):
            raise ValueError("manifest goal must be an object")
        calls = item["tool_calls"]
        if not isinstance(calls, list):
            raise ValueError("manifest tool_calls must be an array")
        goals.append(
            TaskGoal(
                Identifier(str(item["goal_id"])),
                TaskType(str(item["task_type"])),
                item["slots"],  # type: ignore[arg-type]
                tuple(
                    ExpectedToolCall(
                        Identifier(str(call["tool_name"])),
                        call["arguments"],  # type: ignore[arg-type,index]
                    )
                    for call in calls
                ),
            )
        )
    return SyntheticScenario(
        Identifier(str(value["scenario_id"])),
        int(value["seed"]),  # type: ignore[arg-type]
        persona,
        str(value["transcript"]),
        tuple(goals),
        int(value["difficulty"]),  # type: ignore[arg-type]
        float(value["noise_rate"]),  # type: ignore[arg-type]
        bool(value["adversarial"]),
    )


def read_manifest(path: str | Path) -> list[SyntheticScenario]:
    """Read a complete manifest and verify every content checksum."""
    content = Path(path).read_text(encoding="utf-8")
    if content and not content.endswith("\n"):
        raise ValueError("manifest ends with an incomplete line")
    scenarios = []
    for line_number, line in enumerate(content.splitlines(), start=1):
        entry = parse_json(line)
        if not isinstance(entry, dict) or set(entry) != {"schema_version", "scenario", "checksum"}:
            raise ValueError(f"manifest line {line_number}: invalid entry shape")
        unsigned = {"schema_version": entry["schema_version"], "scenario": entry["scenario"]}
        if entry["schema_version"] != MANIFEST_SCHEMA_VERSION:
            raise ValueError(f"manifest line {line_number}: unsupported schema version")
        if entry["checksum"] != object_digest(unsigned):
            raise ValueError(f"manifest line {line_number}: checksum mismatch")
        scenario_value = entry["scenario"]
        if not isinstance(scenario_value, dict):
            raise ValueError(f"manifest line {line_number}: scenario must be an object")
        scenarios.append(_scenario_from_dict(scenario_value))
    return scenarios
