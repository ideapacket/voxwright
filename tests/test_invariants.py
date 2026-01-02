"""Seeded stress checks for the project's cross-module safety invariants."""

from __future__ import annotations

import pytest

from voxwright.barge_in import BargePolicy, InFlightOperation, OperationState, atomic_outcome
from voxwright.call_grammar import ModelChannels, calls_from_channels
from voxwright.core import JSONValue, canonical_json
from voxwright.evaluation import EvaluationRun, score_runs
from voxwright.events import EventEnvelope, EventKind
from voxwright.identifiers import Identifier
from voxwright.recording import SessionRecord
from voxwright.repair import RepairConfig, run_repair
from voxwright.replay import replay
from voxwright.sandbox import PermissionPolicy, SimulatedState, ToolSandbox
from voxwright.scenarios import adversarial_scenario
from voxwright.tool_schema import ParameterSpec, ToolRegistry, ToolSchema, ValueType
from voxwright.workflow import StepKind, WorkflowDefinition, WorkflowStep, apply_effects, run_linear
from voxwright.workflow_ledger import WorkflowLedger, remaining_steps


def timer_registry() -> ToolRegistry:
    return ToolRegistry(
        (
            ToolSchema(
                Identifier("timer.start"),
                (ParameterSpec(Identifier("seconds"), ValueType.INTEGER),),
                "synthetic timer",
            ),
        )
    )


@pytest.mark.parametrize("seed", range(32))
def test_seeded_injection_transcripts_never_enter_the_call_channel(seed: int) -> None:
    scenario = adversarial_scenario(seed)
    channels = ModelChannels(scenario.transcript)
    assert calls_from_channels(channels, timer_registry()) == ()
    box = ToolSandbox(PermissionPolicy({}))
    outcome = box.execute("notes.add", {"text": scenario.transcript})
    assert not outcome.executed
    assert box.state == SimulatedState.empty()
    assert box.ledger.validate() is None


@pytest.mark.parametrize("seed", range(24))
def test_deny_by_default_blocks_every_synthetic_backend(seed: int) -> None:
    attack = adversarial_scenario(seed).transcript
    calls: tuple[tuple[str, dict[str, JSONValue]], ...] = (
        ("calendar.create", {"title": attack, "hour": 9}),
        ("timer.start", {"seconds": 10}),
        ("messages.send", {"recipient": "fixture", "text": attack}),
        ("music.play", {"track": attack}),
        ("home.set-light", {"room": "study", "on": True}),
        ("notes.add", {"text": attack}),
    )
    box = ToolSandbox(PermissionPolicy({}))
    for tool_name, arguments in calls:
        assert not box.execute(tool_name, arguments).executed
    assert box.state == SimulatedState.empty()
    assert len(box.ledger.links) == len(calls)
    assert box.ledger.validate() is None


@pytest.mark.parametrize("seed", range(32))
def test_repair_sequences_always_reach_a_bounded_terminal_state(seed: int) -> None:
    maximum = 1 + seed % 5
    confidence = round((seed % 17) / 20, 6)
    outcome = run_repair(
        (confidence, confidence, confidence),
        ("first", "second"),
        RepairConfig(max_attempts=maximum),
    )
    assert outcome.resolved is not outcome.handed_off
    assert outcome.attempts <= maximum
    assert len(outcome.strategies) <= maximum + 1


@pytest.mark.parametrize("seed", range(24))
def test_seeded_session_replay_is_byte_identical(seed: int) -> None:
    scenario = adversarial_scenario(seed)
    event = EventEnvelope(
        Identifier(f"invariant-session-{seed}"),
        0,
        seed * 10,
        EventKind.FINAL_TRANSCRIPT,
        {"text": scenario.transcript},
    )
    records = [SessionRecord.create([], event)]
    assert replay(records, seed).to_bytes() == replay(records, seed).to_bytes()
    assert replay(records, seed).events == (event,)


def generated_workflow(seed: int) -> WorkflowDefinition:
    action_count = 2 + seed % 5
    steps = []
    for index in range(action_count):
        next_id = Identifier(f"step-{index + 1}")
        steps.append(
            WorkflowStep(
                Identifier(f"step-{index}"),
                StepKind.ACTION,
                (next_id,),
                effects={f"effect-{index}": seed + index},
            )
        )
    steps.append(
        WorkflowStep(
            Identifier(f"step-{action_count}"),
            StepKind.END,
            effects={"complete": True},
        )
    )
    return WorkflowDefinition(
        Identifier(f"generated-{seed}"), 1, Identifier("step-0"), tuple(steps)
    )


@pytest.mark.parametrize("seed", range(24))
def test_checkpoint_resume_matches_straight_execution_bytes(seed: int) -> None:
    definition = generated_workflow(seed)
    straight = run_linear(definition)
    order = tuple(step.step_id for step in definition.steps)
    ledger = WorkflowLedger()
    state: dict[str, JSONValue] = {}
    prefix_length = 1 + seed % (len(order) - 1)
    for step_id in order[:prefix_length]:
        state = apply_effects(definition.step_map[step_id], state)
        ledger.record(step_id, state)
    checkpoint = ledger.checkpoint()
    for step_id in remaining_steps(order, checkpoint):
        state = apply_effects(definition.step_map[step_id], state)
    assert canonical_json(state) == canonical_json(straight.state)
    assert ledger.validate() is None


@pytest.mark.parametrize("seed", range(24))
def test_non_idempotent_interrupts_finish_or_roll_back_atomically(seed: int) -> None:
    policy = tuple(BargePolicy)[seed % len(BargePolicy)]
    operation = InFlightOperation(
        Identifier(f"operation-{seed}"),
        Identifier("calendar.create"),
        {"title": "fixture", "hour": 9},
        idempotent=False,
    ).start()
    if policy is BargePolicy.QUEUE:
        terminal = operation.complete()
    else:
        from voxwright.barge_in import resolve_interrupt

        terminal, _ = resolve_interrupt(operation, policy)
    outcome = atomic_outcome(terminal)
    assert outcome.terminal_state in {OperationState.COMPLETED, OperationState.ROLLED_BACK}
    assert outcome.committed is (outcome.terminal_state is OperationState.COMPLETED)


def metric_runs(errors: int) -> tuple[EvaluationRun, ...]:
    runs = []
    for index in range(20):
        failed = index < errors
        runs.append(
            EvaluationRun(
                f"run-{index}",
                "notes",
                "level-1",
                0.0,
                {"text": "milk"},
                {} if failed else {"text": "milk"},
                ("notes.add",),
                () if failed else ("notes.add",),
                not failed,
                1,
                0,
                int(failed),
                150 if failed else 50,
                100,
            )
        )
    return tuple(runs)


@pytest.mark.parametrize("errors", range(21))
def test_injected_errors_degrade_metrics_monotonically(errors: int) -> None:
    current = score_runs(metric_runs(errors))
    assert all(
        0.0 <= value <= 1.0
        for value in (
            current.task_success,
            current.slots.accuracy,
            current.tools.precision,
            current.tools.recall,
            current.tools.f1,
            current.efficiency.latency_adherence,
        )
    )
    if errors:
        previous = score_runs(metric_runs(errors - 1))
        assert current.task_success <= previous.task_success
        assert current.slots.accuracy <= previous.slots.accuracy
        assert current.tools.f1 <= previous.tools.f1
        assert current.efficiency.latency_adherence <= previous.efficiency.latency_adherence
        assert current.efficiency.false_execute_count >= previous.efficiency.false_execute_count
