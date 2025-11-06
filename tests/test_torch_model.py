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
