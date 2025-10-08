"""Versioned artifacts for observed synthetic application runs."""

from __future__ import annotations

from voxwright.core import JSONValue, canonical_json, parse_json
from voxwright.evaluation import EvaluationRun
from voxwright.hashing import object_digest
from voxwright.scenarios import SyntheticScenario

RUN_SCHEMA_VERSION = 1
RUN_FIELDS = {
    "run_id",
    "task_type",
    "difficulty",
    "noise_rate",
    "expected_slots",
    "predicted_slots",
    "expected_tools",
    "selected_tools",
    "goal_satisfied",
    "turns",
    "repairs",
    "false_executes",
    "latency_ms",
    "latency_budget_ms",
}


def run_to_dict(run: EvaluationRun) -> dict[str, JSONValue]:
    return {
        "run_id": run.run_id,
        "task_type": run.task_type,
        "difficulty": run.difficulty,
        "noise_rate": run.noise_rate,
        "expected_slots": run.expected_slots,
        "predicted_slots": run.predicted_slots,
        "expected_tools": list(run.expected_tools),
        "selected_tools": list(run.selected_tools),
        "goal_satisfied": run.goal_satisfied,
        "turns": run.turns,
        "repairs": run.repairs,
        "false_executes": run.false_executes,
        "latency_ms": run.latency_ms,
        "latency_budget_ms": run.latency_budget_ms,
    }


def run_from_dict(value: object) -> EvaluationRun:
    if not isinstance(value, dict) or set(value) != RUN_FIELDS:
        raise ValueError("invalid evaluation run shape")
    expected_slots = value["expected_slots"]
    predicted_slots = value["predicted_slots"]
    expected_tools = value["expected_tools"]
    selected_tools = value["selected_tools"]
    if not isinstance(expected_slots, dict) or not isinstance(predicted_slots, dict):
        raise TypeError("run slots must be objects")
    if not all(
        isinstance(key, str) and isinstance(item, str) for key, item in expected_slots.items()
    ):
        raise TypeError("expected slots must contain strings")
    if not all(
        isinstance(key, str) and isinstance(item, str) for key, item in predicted_slots.items()
    ):
        raise TypeError("predicted slots must contain strings")
    if not isinstance(expected_tools, list) or not all(
        isinstance(item, str) for item in expected_tools
    ):
        raise TypeError("expected tools must be a string array")
    if not isinstance(selected_tools, list) or not all(
        isinstance(item, str) for item in selected_tools
    ):
        raise TypeError("selected tools must be a string array")
    text_fields = ("run_id", "task_type", "difficulty")
    if any(not isinstance(value[name], str) for name in text_fields):
        raise TypeError("run identity fields must be strings")
    integer_fields = (
        "turns",
        "repairs",
        "false_executes",
        "latency_ms",
        "latency_budget_ms",
    )
    if any(
        isinstance(value[name], bool) or not isinstance(value[name], int) for name in integer_fields
    ):
        raise TypeError("run counters must be integers")
    noise = value["noise_rate"]
    if isinstance(noise, bool) or not isinstance(noise, (int, float)):
        raise TypeError("run noise rate must be numeric")
    goal = value["goal_satisfied"]
    if not isinstance(goal, bool):
        raise TypeError("run goal_satisfied must be boolean")
    return EvaluationRun(
        str(value["run_id"]),
        str(value["task_type"]),
        str(value["difficulty"]),
        float(noise),
        expected_slots,
        predicted_slots,
        tuple(expected_tools),
        tuple(selected_tools),
        goal,
        int(value["turns"]),
        int(value["repairs"]),
        int(value["false_executes"]),
        int(value["latency_ms"]),
        int(value["latency_budget_ms"]),
    )


def encode_runs(runs: tuple[EvaluationRun, ...]) -> str:
    lines = []
    for run in runs:
        unsigned: dict[str, JSONValue] = {
            "schema_version": RUN_SCHEMA_VERSION,
            "run": run_to_dict(run),
        }
        lines.append(canonical_json({**unsigned, "checksum": object_digest(unsigned)}))
    return "\n".join(lines) + ("\n" if lines else "")


def decode_runs(content: str) -> tuple[EvaluationRun, ...]:
    if content and not content.endswith("\n"):
        raise ValueError("run artifact ends with an incomplete line")
    runs = []
    for line_number, line in enumerate(content.splitlines(), 1):
        value = parse_json(line)
        if not isinstance(value, dict) or set(value) != {"schema_version", "run", "checksum"}:
            raise ValueError(f"run line {line_number}: invalid envelope shape")
        unsigned = {"schema_version": value["schema_version"], "run": value["run"]}
        if value["schema_version"] != RUN_SCHEMA_VERSION:
            raise ValueError(f"run line {line_number}: unsupported schema version")
        if value["checksum"] != object_digest(unsigned):
            raise ValueError(f"run line {line_number}: checksum mismatch")
        try:
            runs.append(run_from_dict(value["run"]))
        except (TypeError, ValueError) as error:
            raise ValueError(f"run line {line_number}: {error}") from error
    return tuple(runs)


def scripted_run(scenario: SyntheticScenario) -> EvaluationRun:
    """Create an observation for a scripted fixture that follows its planted truth."""
    slots = {
        name: item if isinstance(item, str) else canonical_json(item)
        for name, item in scenario.planted_slots.items()
    }
    tools = tuple(str(call.tool_name) for call in scenario.planted_calls)
    return EvaluationRun(
        str(scenario.scenario_id),
        scenario.goals[0].task_type.value,
        f"level-{scenario.difficulty}",
        scenario.noise_rate,
        slots,
        dict(slots),
        tools,
        tools,
        True,
        max(1, len(scenario.goals)),
        int(scenario.noise_rate > 0),
        0,
        40 + scenario.difficulty * 10,
        120,
    )
