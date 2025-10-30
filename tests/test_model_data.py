"""Synthetic model-data contracts independent of the optional framework."""

from __future__ import annotations

import pytest

from voxwright.model_data import ModelExample, TokenVocabulary, scenario_example, tokenize
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


@pytest.mark.parametrize("seed", range(12))
@pytest.mark.parametrize(
    "task_type",
    (TaskType.SCHEDULE, TaskType.MUSIC, TaskType.SMART_HOME, TaskType.NOTES),
)
def test_planted_tags_align_with_every_factory_task(task_type: TaskType, seed: int) -> None:
    scenario = application_scenario(task_type, seed)
    example = scenario_example(scenario)
    assert len(example.tokens) == len(example.slot_tags)
    assert any(tag.startswith("B-") for tag in example.slot_tags)
    for slot_name, value in scenario.goals[0].slots.items():
        planted = tokenize(str(value))
        begin = example.slot_tags.index(f"B-{slot_name}")
        assert example.tokens[begin : begin + len(planted)] == planted
        assert example.slot_tags[begin + 1 : begin + len(planted)] == tuple(
            f"I-{slot_name}" for _ in planted[1:]
        )


def test_vocabulary_builds_a_sorted_reproducible_index() -> None:
    examples = tuple(
        scenario_example(application_scenario(task_type, 3))
        for task_type in (TaskType.MUSIC, TaskType.NOTES)
    )
    vocabulary = TokenVocabulary.build(examples)
    assert vocabulary.tokens[0] == "<unk>"
    assert vocabulary.tokens[1:] == tuple(sorted(vocabulary.tokens[1:]))
    assert vocabulary.decode(vocabulary.encode(examples[0].tokens)) == examples[0].tokens


def test_vocabulary_maps_unseen_tokens_without_mutating_itself() -> None:
    example = scenario_example(application_scenario(TaskType.NOTES, 8))
    vocabulary = TokenVocabulary.build((example,))
    before = vocabulary.tokens
    encoded = vocabulary.encode(("unseen", *example.tokens))
    assert encoded[0] == 0
    assert vocabulary.decode((encoded[0],)) == ("<unk>",)
    assert vocabulary.tokens == before


def test_vocabulary_rejects_invalid_counts_and_indices() -> None:
    example = scenario_example(application_scenario(TaskType.NOTES, 2))
    with pytest.raises(ValueError, match="requires examples"):
        TokenVocabulary.build(())
    with pytest.raises(ValueError, match="must be positive"):
        TokenVocabulary.build((example,), minimum_count=0)
    vocabulary = TokenVocabulary.build((example,), minimum_count=2)
    assert vocabulary.tokens == ("<unk>",)
    with pytest.raises(ValueError, match="outside vocabulary"):
        vocabulary.decode((1,))
