"""Tests for synthetic campaign slicing and artifacts."""

from __future__ import annotations

from dataclasses import replace

import pytest

from voxwright.campaign import (
    CampaignArtifact,
    SliceDimension,
    compare_metrics,
    decode_campaign,
    encode_campaign,
    noise_band,
    slice_campaign,
    slot_breakdown,
    tool_breakdown,
)
from voxwright.core import canonical_json
from voxwright.evaluation import EvaluationRun, score_runs


def run(run_id: str, *, task: str = "schedule", difficulty: str = "easy") -> EvaluationRun:
    return EvaluationRun(
        run_id=run_id,
        task_type=task,
        difficulty=difficulty,
        noise_rate=0.1,
        expected_slots={"value": run_id},
        predicted_slots={"value": run_id},
        expected_tools=(f"{task}.tool",),
        selected_tools=(f"{task}.tool",),
        goal_satisfied=True,
        turns=1,
        repairs=0,
        false_executes=0,
        latency_ms=10,
        latency_budget_ms=20,
    )


def test_campaign_slices_task_type_with_independent_metrics() -> None:
    runs = (run("b", task="music"), run("a"), run("c", task="music"))
    slices = slice_campaign(runs, SliceDimension.TASK_TYPE)
    assert [(item.label, item.run_ids) for item in slices] == [
        ("music", ("b", "c")),
        ("schedule", ("a",)),
    ]
    assert [item.metrics.run_count for item in slices] == [2, 1]


def test_campaign_slices_difficulty_without_losing_runs() -> None:
    runs = (run("a", difficulty="hard"), run("b", difficulty="easy"))
    slices = slice_campaign(runs, SliceDimension.DIFFICULTY)
    assert sum(item.metrics.run_count for item in slices) == len(runs)
    assert {item.label for item in slices} == {"easy", "hard"}


def test_campaign_slice_order_is_independent_of_input_order() -> None:
    forward = (run("a", task="schedule"), run("b", task="music"))
    reverse = tuple(reversed(forward))
    assert [item.label for item in slice_campaign(forward, SliceDimension.TASK_TYPE)] == [
        item.label for item in slice_campaign(reverse, SliceDimension.TASK_TYPE)
    ]


def test_campaign_slicing_rejects_no_observations() -> None:
    with pytest.raises(ValueError, match="at least one run"):
        slice_campaign((), SliceDimension.TASK_TYPE)


def test_campaign_slice_retains_original_order_within_label() -> None:
    runs = (run("z", task="music"), run("a", task="music"))
    [music] = slice_campaign(runs, SliceDimension.TASK_TYPE)
    assert music.run_ids == ("z", "a")


def test_campaign_noise_bands_are_machine_readable() -> None:
    assert [noise_band(value) for value in (0.0, 0.19, 0.2, 0.49, 0.5, 1.0)] == [
        "low",
        "low",
        "medium",
        "medium",
        "high",
        "high",
    ]


def test_noise_slice_places_every_boundary_once() -> None:
    runs = tuple(
        replace(run(f"run-{index}"), noise_rate=rate) for index, rate in enumerate((0.0, 0.2, 0.5))
    )
    slices = slice_campaign(runs, SliceDimension.NOISE_BAND)
    assert [(item.label, item.metrics.run_count) for item in slices] == [
        ("high", 1),
        ("low", 1),
        ("medium", 1),
    ]


def test_noise_band_rejects_out_of_range_values() -> None:
    with pytest.raises(ValueError, match="between 0 and 1"):
        noise_band(-0.01)
    with pytest.raises(ValueError, match="between 0 and 1"):
        noise_band(1.01)


def test_slot_breakdown_explains_per_name_accuracy() -> None:
    runs = (
        run("a"),
        replace(
            run("b"),
            expected_slots={"value": "b", "room": "study"},
            predicted_slots={"value": "wrong", "room": "study"},
        ),
    )
    scores = slot_breakdown(runs)
    assert [(score.name, score.correct, score.expected, score.accuracy) for score in scores] == [
        ("room", 1, 1, 1.0),
        ("value", 1, 2, 0.5),
    ]


def test_slot_breakdown_marks_spurious_only_names() -> None:
    item = replace(
        run("a"),
        expected_slots={},
        predicted_slots={"phantom": "value"},
    )
    [score] = slot_breakdown((item,))
    assert (score.name, score.correct, score.expected, score.predicted, score.accuracy) == (
        "phantom",
        0,
        0,
        1,
        0.0,
    )


def test_slot_breakdown_handles_slotless_campaign_and_empty_input() -> None:
    slotless = replace(run("a"), expected_slots={}, predicted_slots={})
    assert slot_breakdown((slotless,)) == ()
    with pytest.raises(ValueError, match="at least one run"):
        slot_breakdown(())


def test_tool_breakdown_reports_each_tool_error_family() -> None:
    item = replace(
        run("a"),
        expected_tools=("notes.add", "notes.add", "music.play"),
        selected_tools=("notes.add", "music.stop"),
    )
    assert [
        (score.name, score.true_positive, score.false_positive, score.false_negative)
        for score in tool_breakdown((item,))
    ] == [
        ("music.play", 0, 0, 1),
        ("music.stop", 0, 1, 0),
        ("notes.add", 1, 0, 1),
    ]


def test_tool_breakdown_never_matches_calls_across_runs() -> None:
    expected_only = replace(run("a"), expected_tools=("notes.add",), selected_tools=())
    selected_only = replace(run("b"), expected_tools=(), selected_tools=("notes.add",))
    [score] = tool_breakdown((expected_only, selected_only))
    assert (score.true_positive, score.false_positive, score.false_negative) == (0, 1, 1)


def test_tool_breakdown_handles_toolless_and_empty_campaigns() -> None:
    tooless = replace(run("a"), expected_tools=(), selected_tools=())
    assert tool_breakdown((tooless,)) == ()
    with pytest.raises(ValueError, match="at least one run"):
        tool_breakdown(())


def test_metric_comparison_uses_candidate_minus_baseline() -> None:
    baseline = score_runs((run("base"),))
    degraded_run = replace(
        run("candidate"),
        goal_satisfied=False,
        predicted_slots={"value": "wrong"},
        selected_tools=(),
        turns=2,
        repairs=1,
        false_executes=1,
        latency_ms=30,
    )
    delta = compare_metrics(baseline, score_runs((degraded_run,)))
    assert (delta.task_success, delta.slot_accuracy, delta.tool_f1) == (-1.0, -1.0, -1.0)
    assert (delta.mean_turns, delta.repair_rate, delta.false_executes) == (1.0, 0.5, 1)
    assert delta.latency_adherence == -1.0


def test_injected_errors_never_improve_quality_metrics() -> None:
    baseline_run = run("baseline")
    error_run = replace(
        baseline_run,
        run_id="error",
        goal_satisfied=False,
        predicted_slots={},
        selected_tools=(),
    )
    delta = compare_metrics(score_runs((baseline_run,)), score_runs((error_run,)))
    assert delta.task_success <= 0
    assert delta.slot_accuracy <= 0
    assert delta.tool_f1 <= 0


def test_identical_metric_bundles_have_exact_zero_deltas() -> None:
    metrics = score_runs((run("same"),))
    delta = compare_metrics(metrics, metrics)
    assert (
        delta.task_success,
        delta.slot_accuracy,
        delta.tool_f1,
        delta.mean_turns,
        delta.repair_rate,
        delta.false_executes,
        delta.latency_adherence,
    ) == (0.0, 0.0, 0.0, 0.0, 0.0, 0, 0.0)


def test_campaign_artifact_embeds_seed_config_digest_and_metrics() -> None:
    artifact = CampaignArtifact(
        "offline-smoke", 42, {"adapter": "scripted", "synthetic": True}, score_runs((run("a"),))
    )
    encoded = artifact.to_dict()
    assert encoded["schema_version"] == 1
    assert encoded["seed"] == 42
    assert str(encoded["config_digest"]).startswith("sha256:")
    assert encoded["metrics"] == artifact.metrics.to_dict()


def test_campaign_artifact_is_canonical_and_repeatable() -> None:
    first = CampaignArtifact("repeatable", 7, {"z": 1, "a": 2}, score_runs((run("a"),)))
    second = CampaignArtifact("repeatable", 7, {"a": 2, "z": 1}, score_runs((run("a"),)))
    assert canonical_json(first.to_dict()) == canonical_json(second.to_dict())
    assert first.config_digest == second.config_digest


def test_campaign_artifact_validates_identity_and_seed() -> None:
    metrics = score_runs((run("a"),))
    with pytest.raises(ValueError, match="name cannot be empty"):
        CampaignArtifact(" ", 0, {}, metrics)
    with pytest.raises(ValueError, match="non-negative integer"):
        CampaignArtifact("bad-seed", -1, {}, metrics)


def test_campaign_artifact_object_roundtrips_metrics_and_config() -> None:
    artifact = CampaignArtifact(
        "roundtrip", 9, {"adapter": "scripted", "synthetic": True}, score_runs((run("a"),))
    )
    assert CampaignArtifact.from_dict(artifact.to_dict()) == artifact


def test_campaign_decoder_rejects_config_checksum_and_field_drift() -> None:
    artifact = CampaignArtifact("strict", 1, {"seeded": True}, score_runs((run("a"),)))
    encoded = artifact.to_dict()
    encoded["config"]["seeded"] = False  # type: ignore[index]
    with pytest.raises(ValueError, match="checksum mismatch"):
        CampaignArtifact.from_dict(encoded)
    encoded = artifact.to_dict()
    encoded["extra"] = True
    with pytest.raises(ValueError, match="exact campaign fields"):
        CampaignArtifact.from_dict(encoded)


def test_campaign_text_codec_is_canonical_and_reversible() -> None:
    artifact = CampaignArtifact("text", 5, {"adapter": "scripted"}, score_runs((run("a"),)))
    encoded = encode_campaign(artifact)
    assert encoded.endswith("\n") and " " not in encoded
    assert decode_campaign(encoded) == artifact
    assert encode_campaign(decode_campaign(encoded)).encode() == encoded.encode()


def test_campaign_text_decoder_rejects_empty_and_trailing_documents() -> None:
    with pytest.raises(ValueError, match="document is empty"):
        decode_campaign("\n")
    artifact = CampaignArtifact("x", 0, {}, score_runs((run("a"),)))
    with pytest.raises(ValueError):
        decode_campaign(encode_campaign(artifact) + "{}")
