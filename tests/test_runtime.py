"""Tests for logical streaming runtime and latency accounting."""

from __future__ import annotations

import pytest

import voxwright.runtime as runtime
from voxwright.clock import LogicalClock


def budget() -> runtime.LatencyBudget:
    return runtime.LatencyBudget(100, 200, 300, 150)


def test_latency_budget_maps_every_stage() -> None:
    expected = {"perception": 100, "decision": 200, "tool": 300, "response": 150}
    assert {stage.value: budget().for_stage(stage) for stage in runtime.LatencyStage} == expected
    assert budget().total_ms == 750


def test_latency_budget_allows_zero_but_not_negative() -> None:
    assert runtime.LatencyBudget(0, 0, 0, 0).total_ms == 0
    with pytest.raises(ValueError, match="cannot be negative"):
        runtime.LatencyBudget(-1, 0, 0, 0)


def test_latency_sample_uses_inclusive_budget_boundary() -> None:
    exact = runtime.LatencySample(runtime.LatencyStage.DECISION, 10, 210)
    over = runtime.LatencySample(runtime.LatencyStage.DECISION, 10, 211)
    assert exact.duration_ms == 200 and exact.within(budget())
    assert not over.within(budget())


@pytest.mark.parametrize(("start", "end"), [(-1, 0), (10, 9)])
def test_latency_sample_rejects_invalid_interval(start: int, end: int) -> None:
    with pytest.raises(ValueError, match="invalid logical interval"):
        runtime.LatencySample(runtime.LatencyStage.TOOL, start, end)


def test_latency_trace_accumulates_ordered_samples_immutably() -> None:
    first = runtime.LatencySample(runtime.LatencyStage.PERCEPTION, 10, 30)
    second = runtime.LatencySample(runtime.LatencyStage.DECISION, 35, 55)
    empty = runtime.LatencyTrace()
    trace = empty.append(first).append(second)
    assert empty.samples == ()
    assert trace.samples == (first, second)
    assert trace.active_ms == 40
    assert trace.elapsed_ms == 45
    assert not trace.complete


def test_latency_trace_is_complete_after_every_stage() -> None:
    trace = runtime.LatencyTrace()
    for index, stage in enumerate(runtime.LatencyStage):
        trace = trace.append(runtime.LatencySample(stage, index * 10, index * 10 + 5))
    assert trace.complete
    assert trace.active_ms == 20
    assert trace.elapsed_ms == 35


def test_latency_trace_rejects_skipped_duplicate_and_overlapping_stages() -> None:
    perception = runtime.LatencySample(runtime.LatencyStage.PERCEPTION, 0, 10)
    with pytest.raises(ValueError, match="stage order"):
        runtime.LatencyTrace((perception, runtime.LatencySample(runtime.LatencyStage.TOOL, 10, 20)))
    with pytest.raises(ValueError, match="stage order"):
        runtime.LatencyTrace((perception, perception))
    with pytest.raises(ValueError, match="cannot overlap"):
        runtime.LatencyTrace(
            (perception, runtime.LatencySample(runtime.LatencyStage.DECISION, 9, 20))
        )


def test_empty_latency_trace_has_zero_durations() -> None:
    trace = runtime.LatencyTrace()
    assert trace.active_ms == trace.elapsed_ms == 0
    assert not trace.complete


def test_latency_assessment_reports_precise_stage_overruns() -> None:
    samples = tuple(
        runtime.LatencySample(stage, index * 500, index * 500 + duration)
        for index, (stage, duration) in enumerate(
            zip(runtime.LatencyStage, (100, 201, 310, 150), strict=True)
        )
    )
    assessment = runtime.assess_latency(runtime.LatencyTrace(samples), budget())
    assert not assessment.within_budget
    assert [(item.stage.value, item.overrun_ms) for item in assessment.violations] == [
        ("decision", 1),
        ("tool", 10),
    ]
    assert assessment.active_ms == 761


def test_latency_assessment_requires_a_complete_turn() -> None:
    partial = runtime.LatencyTrace().append(
        runtime.LatencySample(runtime.LatencyStage.PERCEPTION, 0, 1)
    )
    assessment = runtime.assess_latency(partial, budget())
    assert not assessment.complete
    assert not assessment.within_budget
    assert assessment.violations == ()


def test_idle_gaps_do_not_count_as_active_stage_overrun() -> None:
    trace = runtime.LatencyTrace(
        (
            runtime.LatencySample(runtime.LatencyStage.PERCEPTION, 0, 100),
            runtime.LatencySample(runtime.LatencyStage.DECISION, 1_000, 1_200),
            runtime.LatencySample(runtime.LatencyStage.TOOL, 2_000, 2_300),
            runtime.LatencySample(runtime.LatencyStage.RESPONSE, 3_000, 3_150),
        )
    )
    assessment = runtime.assess_latency(trace, budget())
    assert assessment.within_budget
    assert trace.elapsed_ms == 3_150
    assert assessment.active_ms == assessment.total_budget_ms == 750


def test_stream_block_preserves_logical_arrival_metadata() -> None:
    block = runtime.StreamBlock(sequence=3, received_at_ms=250, duration_ms=40, final=True)
    assert (block.sequence, block.received_at_ms, block.duration_ms, block.final) == (
        3,
        250,
        40,
        True,
    )


@pytest.mark.parametrize(
    ("values", "message"),
    [
        ((-1, 0, 1, False), "sequence"),
        ((0, -1, 1, False), "arrival"),
        ((0, 0, 0, False), "duration"),
        ((0, 0, -1, False), "duration"),
    ],
)
def test_stream_block_rejects_invalid_numeric_boundaries(
    values: tuple[int, int, int, bool], message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        runtime.StreamBlock(*values)


def test_stream_block_rejects_boolean_integer_aliases() -> None:
    with pytest.raises(ValueError, match="sequence"):
        runtime.StreamBlock(True, 0, 1)
    with pytest.raises(ValueError, match="arrival"):
        runtime.StreamBlock(0, False, 1)
    with pytest.raises(ValueError, match="duration"):
        runtime.StreamBlock(0, 0, True)
    with pytest.raises(TypeError, match="final flag"):
        runtime.StreamBlock(0, 0, 1, final=1)  # type: ignore[arg-type]


def test_block_runtime_accounts_each_stage_on_logical_clock() -> None:
    clock = LogicalClock(50)
    engine = runtime.BlockRuntime(clock)
    turn = engine.process(runtime.StreamBlock(0, 100, 20), runtime.StageDurations(10, 20, 30, 40))
    observed = [
        (sample.stage.value, sample.started_ms, sample.ended_ms) for sample in turn.trace.samples
    ]
    assert observed == [
        ("perception", 100, 110),
        ("decision", 110, 130),
        ("tool", 130, 160),
        ("response", 160, 200),
    ]
    assert clock.now_ms == 200


def test_block_runtime_rejects_out_of_order_and_post_final_input() -> None:
    engine = runtime.BlockRuntime()
    durations = runtime.StageDurations(1, 1, 1, 1)
    with pytest.raises(ValueError, match="expected stream block 0, got 1"):
        engine.process(runtime.StreamBlock(1, 0, 1), durations)
    engine.process(runtime.StreamBlock(0, 0, 1, final=True), durations)
    with pytest.raises(RuntimeError, match="after the final block"):
        engine.process(runtime.StreamBlock(1, 1, 1), durations)


def test_block_runtime_never_rewinds_for_late_arrivals() -> None:
    engine = runtime.BlockRuntime(LogicalClock(500))
    turn = engine.process(runtime.StreamBlock(0, 100, 10), runtime.StageDurations(1, 2, 3, 4))
    assert turn.trace.samples[0].started_ms == 500
    assert engine.clock.now_ms == 510


def test_stage_durations_reject_negative_and_boolean_values() -> None:
    with pytest.raises(ValueError, match="non-negative"):
        runtime.StageDurations(0, -1, 0, 0)
    with pytest.raises(ValueError, match="non-negative"):
        runtime.StageDurations(0, 0, True, 0)


def test_partial_policy_selects_fresh_useful_fragments_stably() -> None:
    policy = runtime.PartialResponsePolicy(max_staleness_ms=100, min_characters=4)
    late = runtime.PartialCandidate("later", 100, 180)
    early = runtime.PartialCandidate("early", 80, 120)
    stale = runtime.PartialCandidate("stale", 0, 101)
    short = runtime.PartialCandidate("no", 100, 110)
    assert policy.select((late, stale, early, short)) == (early, late)


def test_partial_staleness_boundary_is_inclusive() -> None:
    policy = runtime.PartialResponsePolicy(50)
    assert policy.accepts(runtime.PartialCandidate("fresh", 100, 150))
    assert not policy.accepts(runtime.PartialCandidate("old", 100, 151))


def test_partial_candidates_validate_content_and_time_direction() -> None:
    with pytest.raises(ValueError, match="text cannot be empty"):
        runtime.PartialCandidate("  ", 0, 0)
    with pytest.raises(ValueError, match="invalid logical times"):
        runtime.PartialCandidate("fragment", -1, 0)
    with pytest.raises(ValueError, match="invalid logical times"):
        runtime.PartialCandidate("fragment", 10, 9)


def test_partial_policy_validates_configuration() -> None:
    with pytest.raises(ValueError, match="cannot be negative"):
        runtime.PartialResponsePolicy(-1)
    with pytest.raises(ValueError, match="must be positive"):
        runtime.PartialResponsePolicy(0, 0)


def test_partial_selection_retains_input_order_for_equal_ready_times() -> None:
    candidates = (
        runtime.PartialCandidate("first", 0, 10),
        runtime.PartialCandidate("second", 2, 10),
    )
    assert runtime.PartialResponsePolicy(20).select(candidates) == candidates
