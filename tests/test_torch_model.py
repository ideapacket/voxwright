"""Optional CPU model checks over seeded synthetic fixtures."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.model
pytest.importorskip("torch")

from voxwright.model_data import (  # noqa: E402
    ClassInventory,
    TokenVocabulary,
    synthetic_model_corpus,
)
from voxwright.torch_model import TorchJointModel, torch_available  # noqa: E402


def model_parts() -> tuple[TokenVocabulary, ClassInventory, ClassInventory]:
    examples = synthetic_model_corpus(5, samples_per_task=2)
    return (
        TokenVocabulary.build(examples),
        ClassInventory.for_slot_tags(examples),
        ClassInventory.for_tools(examples),
    )


def test_optional_torch_model_constructs_on_cpu() -> None:
    vocabulary, slots, tools = model_parts()
    model = TorchJointModel(vocabulary, slots, tools, embedding_size=8, seed=7)
    assert torch_available()
    assert model.embedding.weight.device.type == "cpu"
    assert tuple(model.embedding.weight.shape) == (len(vocabulary.tokens), 8)
    assert tuple(model.slot_head.weight.shape) == (len(slots.names), 8)
    assert tuple(model.tool_head.weight.shape) == (len(tools.names), 8)


def test_model_initialization_is_seeded_without_sharing_parameters() -> None:
    vocabulary, slots, tools = model_parts()
    first = TorchJointModel(vocabulary, slots, tools, seed=11)
    second = TorchJointModel(vocabulary, slots, tools, seed=11)
    third = TorchJointModel(vocabulary, slots, tools, seed=12)
    assert first.embedding.weight.tolist() == second.embedding.weight.tolist()
    assert first.embedding.weight.tolist() != third.embedding.weight.tolist()
    assert first.embedding.weight.data_ptr() != second.embedding.weight.data_ptr()


def test_model_rejects_invalid_architecture_parameters() -> None:
    vocabulary, slots, tools = model_parts()
    with pytest.raises(ValueError, match="embedding size must be positive"):
        TorchJointModel(vocabulary, slots, tools, embedding_size=0)
    with pytest.raises(ValueError, match="seed must be non-negative"):
        TorchJointModel(vocabulary, slots, tools, seed=-1)
