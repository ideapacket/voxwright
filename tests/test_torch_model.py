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
from voxwright.torch_model import (  # noqa: E402
    ModelPrediction,
    TorchJointModel,
    predict,
    torch_available,
)


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


def test_untrained_model_prediction_has_aligned_bounded_outputs() -> None:
    vocabulary, slots, tools = model_parts()
    prediction = predict(TorchJointModel(vocabulary, slots, tools, seed=3), "play Blue Sky")
    assert isinstance(prediction, ModelPrediction)
    assert prediction.tokens == ("play", "blue", "sky")
    assert len(prediction.slot_tags) == len(prediction.slot_confidences) == 3
    assert set(prediction.slot_tags) <= set(slots.names)
    assert prediction.tool_label in tools.names
    assert all(0.0 <= confidence <= 1.0 for confidence in prediction.slot_confidences)
    assert 0.0 <= prediction.tool_confidence <= 1.0


def test_prediction_is_repeatable_and_handles_unknown_tokens() -> None:
    vocabulary, slots, tools = model_parts()
    model = TorchJointModel(vocabulary, slots, tools, seed=23)
    first = predict(model, "entirely unseen request")
    second = predict(model, "entirely unseen request")
    assert first == second
    assert first.tokens == ("entirely", "unseen", "request")
    assert vocabulary.encode(first.tokens) == (0, 0, 0)


def test_prediction_rejects_tokenless_input_and_invalid_records() -> None:
    vocabulary, slots, tools = model_parts()
    with pytest.raises(ValueError, match="requires transcript tokens"):
        predict(TorchJointModel(vocabulary, slots, tools), "... ")
    with pytest.raises(ValueError, match="nonempty and aligned"):
        ModelPrediction((), (), (), "music.play", 0.5)
    with pytest.raises(ValueError, match="confidences must align"):
        ModelPrediction(("play",), ("O",), (), "music.play", 0.5)
    with pytest.raises(ValueError, match="tool output is invalid"):
        ModelPrediction(("play",), ("O",), (0.5,), "", 0.5)
