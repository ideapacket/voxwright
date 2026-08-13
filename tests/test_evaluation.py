"""Golden evaluation checks over synthetic planted truth."""

from __future__ import annotations

import pytest

from voxwright.core import canonical_json
from voxwright.evaluation import (
    EvaluationRun,
    efficiency_score,
    metric_bundle_from_dict,
    score_runs,
    slot_score,
    task_success_rate,
    tool_score,
)


def run(**overrides: object) -> EvaluationRun:
    values: dict[str, object] = {
        "run_id": "run-1",
        "task_type": "schedule",
        "difficulty": "easy",
        "noise_rate": 0.1,
        "expected_slots": {"title": "lab"},
        "predicted_slots": {"title": "lab"},
        "expected_tools": ("calendar.create",),
        "selected_tools": ("calendar.create",),
        "goal_satisfied": True,
        "turns": 2,
        "repairs": 0,
        "false_executes": 0,
        "latency_ms": 100,
        "latency_budget_ms": 150,
    }
    values.update(overrides)
    return EvaluationRun(**values)  # type: ignore[arg-type]


def test_evaluation_run_preserves_planted_and_observed_values() -> None:
    item = run()
    assert item.expected_slots == item.predicted_slots
    assert item.expected_tools == item.selected_tools
    assert item.goal_satisfied and item.false_executes == 0


def test_evaluation_run_validates_identity_and_probability_fields() -> None:
    with pytest.raises(ValueError, match="run id cannot be empty"):
        run(run_id=" ")
    with pytest.raises(ValueError, match="noise rate"):
        run(noise_rate=1.01)
    with pytest.raises(TypeError, match="goal_satisfied"):
        run(goal_satisfied=1)


def test_evaluation_run_rejects_malformed_ground_truth() -> None:
    with pytest.raises(ValueError, match="expected slot"):
        run(expected_slots={"title": ""})
    with pytest.raises(ValueError, match="predicted slot"):
        run(predicted_slots={"": "lab"})
    with pytest.raises(ValueError, match="tool names"):
        run(expected_tools=("",))


def test_evaluation_run_enforces_counter_boundaries() -> None:
    with pytest.raises(ValueError, match="turns must be positive"):
        run(turns=0)
    with pytest.raises(ValueError, match="repairs cannot exceed"):
        run(turns=1, repairs=2)
    with pytest.raises(ValueError, match="false executes"):
        run(false_executes=-1)
    with pytest.raises(ValueError, match="latency budget"):
        run(latency_budget_ms=-1)


def test_task_and_slot_scores_use_planted_truth() -> None:
    runs = (
        run(),
        run(
            run_id="run-2",
            goal_satisfied=False,
            expected_slots={"room": "study", "on": "yes"},
            predicted_slots={"room": "study", "extra": "ignored"},
        ),
    )
    assert task_success_rate(runs) == 0.5
    score = slot_score(runs)
    assert (score.correct, score.expected, score.predicted, score.accuracy) == (
        2,
        3,
        3,
        0.666667,
    )


def test_task_and_slot_scores_reject_empty_campaigns() -> None:
    with pytest.raises(ValueError, match="task success"):
        task_success_rate(())
    with pytest.raises(ValueError, match="slot score"):
        slot_score(())


def test_slotless_tasks_are_perfect_only_without_spurious_slots() -> None:
    empty = run(expected_slots={}, predicted_slots={})
    spurious = run(expected_slots={}, predicted_slots={"unexpected": "value"})
    assert slot_score((empty,)).accuracy == 1.0
    assert slot_score((spurious,)).accuracy == 0.0


def test_wrong_slot_value_is_not_a_partial_match() -> None:
    score = slot_score((run(predicted_slots={"title": "wrong"}),))
    assert score.correct == 0
    assert score.accuracy == 0.0


def test_tool_score_counts_repeated_planted_calls_as_a_multiset() -> None:
    item = run(
        expected_tools=("notes.add", "notes.add", "calendar.create"),
        selected_tools=("notes.add", "calendar.create", "music.play"),
    )
    score = tool_score((item,))
    assert (score.true_positive, score.false_positive, score.false_negative) == (2, 1, 1)
    assert (score.precision, score.recall, score.f1) == (0.666667, 0.666667, 0.666667)


def test_tool_score_defines_empty_denominators_explicitly() -> None:
    no_tools = run(expected_tools=(), selected_tools=())
    missed = run(expected_tools=("notes.add",), selected_tools=())
    spurious = run(expected_tools=(), selected_tools=("notes.add",))
    assert (tool_score((no_tools,)).precision, tool_score((no_tools,)).recall) == (1.0, 1.0)
    assert tool_score((missed,)).precision == 1.0
    assert tool_score((missed,)).recall == 0.0
    assert tool_score((spurious,)).precision == 0.0
    assert tool_score((spurious,)).recall == 1.0


def test_tool_score_rejects_an_empty_campaign() -> None:
    with pytest.raises(ValueError, match="at least one run"):
        tool_score(())


def test_efficiency_score_uses_turn_weighted_repair_rate() -> None:
    score = efficiency_score(
        (
            run(turns=2, repairs=1, false_executes=0, latency_ms=100, latency_budget_ms=100),
            run(
                run_id="run-2",
                turns=4,
                repairs=2,
                false_executes=1,
                latency_ms=101,
                latency_budget_ms=100,
            ),
        )
    )
    assert (
        score.mean_turns,
        score.repair_rate,
        score.false_execute_count,
        score.latency_adherence,
    ) == (3.0, 0.5, 1, 0.5)


def test_efficiency_includes_exact_latency_budget_boundary() -> None:
    score = efficiency_score((run(latency_ms=100, latency_budget_ms=100),))
    assert score.latency_adherence == 1.0


def test_efficiency_rejects_empty_campaigns() -> None:
    with pytest.raises(ValueError, match="at least one run"):
        efficiency_score(())


def test_repair_rate_is_zero_for_unrepaired_runs() -> None:
    score = efficiency_score((run(turns=3, repairs=0),))
    assert score.repair_rate == 0.0
    assert score.mean_turns == 3.0


def test_score_runs_assembles_every_metric_family() -> None:
    metrics = score_runs((run(),))
    assert metrics.run_count == 1
    assert metrics.task_success == 1.0
    assert metrics.slots.accuracy == 1.0
    assert metrics.tools.f1 == 1.0
    assert metrics.efficiency.false_execute_count == 0


def test_perfect_run_has_no_error_or_safety_counts() -> None:
    metrics = score_runs((run(),))
    assert metrics.slots.expected - metrics.slots.correct == 0
    assert metrics.tools.false_positive == 0
    assert metrics.tools.false_negative == 0
    assert metrics.efficiency.false_execute_count == 0
    assert metrics.efficiency.repair_rate == 0.0


def test_campaign_bundle_rejects_no_runs() -> None:
    with pytest.raises(ValueError, match="at least one run"):
        score_runs(())


def test_metric_bundle_has_a_versioned_canonical_shape() -> None:
    encoded = canonical_json(score_runs((run(),)).to_dict())
    assert encoded == (
        '{"efficiency":{"false_execute_count":0,"latency_adherence":1.0,'
        '"mean_turns":2.0,"repair_rate":0.0},"run_count":1,"schema_version":1,'
        '"slots":{"accuracy":1.0,"correct":1,"expected":1,"predicted":1},'
        '"task_success":1.0,"tools":{"f1":1.0,"false_negative":0,'
        '"false_positive":0,"precision":1.0,"recall":1.0,"true_positive":1}}'
    )


def test_metric_serialization_changes_with_real_observations() -> None:
    perfect = score_runs((run(),)).to_dict()
    degraded = score_runs(
        (
            run(
                goal_satisfied=False,
                predicted_slots={"title": "wrong"},
                selected_tools=(),
                repairs=1,
            ),
        )
    ).to_dict()
    assert perfect != degraded
    assert degraded["task_success"] == 0.0
    assert degraded["slots"] != perfect["slots"]
    assert degraded["tools"] != perfect["tools"]


def test_metric_bundle_codec_roundtrips_hand_computed_scores() -> None:
    metrics = score_runs((run(), run(run_id="run-2", repairs=1)))
    assert metric_bundle_from_dict(metrics.to_dict()) == metrics


def test_metric_bundle_decoder_rejects_field_and_range_drift() -> None:
    encoded = score_runs((run(),)).to_dict()
    encoded["extra"] = True
    with pytest.raises(ValueError, match="metric fields differ"):
        metric_bundle_from_dict(encoded)
    encoded = score_runs((run(),)).to_dict()
    encoded["task_success"] = 1.1
    with pytest.raises(ValueError, match="between 0 and 1"):
        metric_bundle_from_dict(encoded)


def test_metric_bundle_decoder_rejects_impossible_slot_counts() -> None:
    encoded = score_runs((run(),)).to_dict()
    encoded["slots"]["correct"] = 2  # type: ignore[index]
    with pytest.raises(ValueError, match="correct count exceeds"):
        metric_bundle_from_dict(encoded)


def test_metric_bundle_requires_positive_observation_count() -> None:
    encoded = score_runs((run(),)).to_dict()
    encoded["run_count"] = 0
    with pytest.raises(ValueError, match="run count must be positive"):
        metric_bundle_from_dict(encoded)
