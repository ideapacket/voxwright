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
    FitResult,
    ModelPrediction,
    ModelQuality,
    TorchJointModel,
    TrainingConfig,
    TrainingHistory,
    evaluate_model,
    fit_synthetic_model,
    predict,
    torch_available,
    train_model,
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


def test_training_configuration_rejects_invalid_optimization_ranges() -> None:
    for epochs in (0, -1, True):
        with pytest.raises(ValueError, match="epochs must be positive"):
            TrainingConfig(epochs=epochs)
    for rate in (0.0, -0.1, 1.1):
        with pytest.raises(ValueError, match="learning rate"):
            TrainingConfig(learning_rate=rate)
    with pytest.raises(ValueError, match="seed must be non-negative"):
        TrainingConfig(seed=-1)
    with pytest.raises(ValueError, match="non-negative losses"):
        TrainingHistory(())


@pytest.mark.slow
def test_training_produces_real_loss_decrease_on_synthetic_data() -> None:
    examples = synthetic_model_corpus(13, samples_per_task=8)
    vocabulary = TokenVocabulary.build(examples)
    slots = ClassInventory.for_slot_tags(examples)
    tools = ClassInventory.for_tools(examples)
    model = TorchJointModel(vocabulary, slots, tools, embedding_size=12, seed=13)
    history = train_model(model, examples, TrainingConfig(epochs=50, seed=13))
    assert len(history.losses) == 50
    assert history.losses[-1] < history.losses[0] * 0.2
    assert min(history.losses[-5:]) < min(history.losses[:5])


def test_quality_counts_match_public_accuracy_fields() -> None:
    examples = synthetic_model_corpus(21, samples_per_task=2)
    vocabulary = TokenVocabulary.build(examples)
    slots = ClassInventory.for_slot_tags(examples)
    tools = ClassInventory.for_tools(examples)
    quality = evaluate_model(TorchJointModel(vocabulary, slots, tools, seed=21), examples)
    assert isinstance(quality, ModelQuality)
    assert quality.token_count == sum(len(item.tokens) for item in examples)
    assert quality.example_count == len(examples)
    assert quality.slot_accuracy == round(quality.correct_tokens / quality.token_count, 6)
    assert quality.tool_accuracy == round(quality.correct_tools / quality.example_count, 6)


def test_quality_rejects_empty_or_inconsistent_measurements() -> None:
    vocabulary, slots, tools = model_parts()
    model = TorchJointModel(vocabulary, slots, tools)
    with pytest.raises(ValueError, match="evaluation requires examples"):
        evaluate_model(model, ())
    with pytest.raises(ValueError, match="requires observed"):
        ModelQuality(0, 0, 0.0, 1, 0, 0.0)
    with pytest.raises(ValueError, match="token count is inconsistent"):
        ModelQuality(1, 2, 1.0, 1, 0, 0.0)
    with pytest.raises(ValueError, match="tool count is inconsistent"):
        ModelQuality(1, 1, 1.0, 1, 2, 1.0)


@pytest.mark.slow
def test_trained_model_learns_the_embedded_synthetic_task_structure() -> None:
    examples = synthetic_model_corpus(8, samples_per_task=10)
    vocabulary = TokenVocabulary.build(examples)
    slots = ClassInventory.for_slot_tags(examples)
    tools = ClassInventory.for_tools(examples)
    model = TorchJointModel(vocabulary, slots, tools, embedding_size=16, seed=8)
    train_model(model, examples, TrainingConfig(epochs=70, seed=8))
    quality = evaluate_model(model, examples)
    assert quality.slot_accuracy >= 0.95
    assert quality.tool_accuracy >= 0.95


@pytest.mark.slow
def test_fit_pipeline_keeps_validation_examples_held_out() -> None:
    corpus = synthetic_model_corpus(44, samples_per_task=6)
    result = fit_synthetic_model(corpus, config=TrainingConfig(epochs=40, seed=44))
    assert isinstance(result, FitResult)
    assert result.train_count + result.validation_count == len(corpus)
    assert result.validation_count == round(len(corpus) * 0.25)
    assert len(result.history.losses) == 40
    assert 0.0 <= result.validation.slot_accuracy <= 1.0
    assert 0.0 <= result.validation.tool_accuracy <= 1.0
