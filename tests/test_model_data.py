"""Synthetic model-data contracts independent of the optional framework."""

from __future__ import annotations

import pytest

from voxwright.model_data import ModelExample, scenario_example, tokenize
from voxwright.scenarios import TaskType, application_scenario, composite_scenario


def test_tokenizer_is_case_normalized_and_punctuation_stable() -> None:
    assert tokenize("Play 'Blue-Sky', NOW!") == ("play", "'blue-sky'", "now")
    assert tokenize("...   ") == ()


def test_scenario_example_tags_planted_spans_and_tool() -> None:
    example = scenario_example(application_scenario(TaskType.MUSIC, 7))
    assert example.tokens[0] == "play"
    assert example.slot_tags[0] == "O"
    assert example.slot_tags[1].startswith("B-track")
    assert example.tool_label == "music.play"


def test_model_example_rejects_misaligned_or_empty_records() -> None:
    with pytest.raises(ValueError, match="cannot be empty"):
        ModelExample("", (), (), "music.play")
    with pytest.raises(ValueError, match="counts must match"):
        ModelExample("play", ("play",), (), "music.play")
    with pytest.raises(ValueError, match="labels cannot be empty"):
        ModelExample("play", ("play",), ("O",), "")


def test_composite_scenarios_are_not_silently_flattened() -> None:
    with pytest.raises(ValueError, match="exactly one synthetic task goal"):
        scenario_example(composite_scenario(4))
