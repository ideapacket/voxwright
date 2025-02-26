"""Tests for reproducible synthetic scenario generation."""

from __future__ import annotations

import pytest

import voxwright.scenarios as scenarios
from voxwright.identifiers import Identifier


def expected_call(name: str = "calendar.create") -> scenarios.ExpectedToolCall:
    return scenarios.ExpectedToolCall(Identifier(name), {"title": "review"})


def test_task_families_are_public_and_stable() -> None:
    assert [item.value for item in scenarios.TaskType] == [
        "schedule",
        "music",
        "smart-home",
        "notes",
        "multi-task",
        "nested",
    ]


def test_goal_preserves_planted_slots_and_call_order() -> None:
    calls = (expected_call(), expected_call("timer.start"))
    goal = scenarios.TaskGoal(
        Identifier("goal-1"), scenarios.TaskType.SCHEDULE, {"hour": 19}, calls
    )
    assert goal.slots == {"hour": 19}
    assert goal.tool_calls == calls


def test_goal_requires_safe_slot_names_and_ground_truth_calls() -> None:
    with pytest.raises(ValueError, match="invalid identifier"):
        scenarios.TaskGoal(
            Identifier("goal-1"), scenarios.TaskType.NOTES, {"bad slot": "x"}, (expected_call(),)
        )
    with pytest.raises(ValueError, match="at least one"):
        scenarios.TaskGoal(Identifier("goal-1"), scenarios.TaskType.NOTES, {}, ())


def test_default_personas_cover_distinct_speech_quirks() -> None:
    assert {persona.pace for persona in scenarios.DEFAULT_PERSONAS} == {"slow", "normal", "fast"}
    assert len({persona.persona_id for persona in scenarios.DEFAULT_PERSONAS}) == 3


def test_persona_rejects_unknown_pace_and_duplicate_quirks() -> None:
    with pytest.raises(ValueError, match="unsupported speaking pace"):
        scenarios.Persona(Identifier("speaker"), "zh-CN", "rushed")
    with pytest.raises(ValueError, match="quirks must be unique"):
        scenarios.Persona(Identifier("speaker"), "zh-CN", "slow", ("filler", "filler"))


def test_scenario_flattens_planted_truth_without_losing_goal_scope() -> None:
    goal = scenarios.TaskGoal(
        Identifier("goal-1"), scenarios.TaskType.SCHEDULE, {"hour": 19}, (expected_call(),)
    )
    scenario = scenarios.SyntheticScenario(
        Identifier("scenario-1"), 9, scenarios.DEFAULT_PERSONAS[0], "schedule review", (goal,)
    )
    assert scenario.planted_calls == (expected_call(),)
    assert scenario.planted_slots == {"goal-1.hour": 19}


@pytest.mark.parametrize(("difficulty", "noise"), [(0, 0.0), (6, 0.0), (1, -0.1), (1, 1.1)])
def test_scenario_bounds_difficulty_and_noise(difficulty: int, noise: float) -> None:
    goal = scenarios.TaskGoal(
        Identifier("goal-1"), scenarios.TaskType.NOTES, {"text": "milk"}, (expected_call(),)
    )
    with pytest.raises(ValueError, match=r"difficulty|noise rate"):
        scenarios.SyntheticScenario(
            Identifier("scenario-1"),
            0,
            scenarios.DEFAULT_PERSONAS[0],
            "remember milk",
            (goal,),
            difficulty,
            noise,
        )


def test_schedule_factory_replays_from_seed() -> None:
    first = scenarios.schedule_scenario(41)
    second = scenarios.schedule_scenario(41)
    assert first == second
    assert first.goals[0].task_type is scenarios.TaskType.SCHEDULE
    assert first.planted_calls[0].tool_name == Identifier("calendar.create")


def test_schedule_factory_varies_planted_values_across_seeds() -> None:
    values = {tuple(scenarios.schedule_scenario(seed).goals[0].slots.values()) for seed in range(8)}
    assert len(values) > 1


@pytest.mark.parametrize(
    ("task_type", "tool_name"),
    [
        (scenarios.TaskType.MUSIC, "music.play"),
        (scenarios.TaskType.SMART_HOME, "home.set-light"),
        (scenarios.TaskType.NOTES, "notes.add"),
    ],
)
def test_application_factory_plants_matching_tool_truth(
    task_type: scenarios.TaskType, tool_name: str
) -> None:
    scenario = scenarios.application_scenario(task_type, 5)
    assert scenario.goals[0].task_type is task_type
    assert scenario.planted_calls[0].tool_name == Identifier(tool_name)
    assert scenario.planted_calls[0].arguments == scenario.goals[0].slots


def test_composite_types_require_their_dedicated_factory() -> None:
    with pytest.raises(ValueError, match="composite generator"):
        scenarios.application_scenario(scenarios.TaskType.NESTED, 1)


def test_multi_task_preserves_goal_and_call_order() -> None:
    scenario = scenarios.composite_scenario(22)
    calls_from_goals = tuple(call for goal in scenario.goals for call in goal.tool_calls)
    assert scenario.planted_calls == calls_from_goals
    assert len(scenario.goals) == 2
    assert " and " in scenario.transcript


def test_nested_scenario_marks_return_to_interrupted_task() -> None:
    nested = scenarios.composite_scenario(22, nested=True)
    assert nested.difficulty == 4
    assert " then return to " in nested.transcript
    assert nested.scenario_id.value.startswith("nested-")
