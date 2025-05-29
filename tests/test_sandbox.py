"""Tests for the deterministic permissioned tool sandbox."""

from __future__ import annotations

import pytest

import voxwright.sandbox as sandbox
from voxwright.hashing import EMPTY_DIGEST
from voxwright.identifiers import Identifier
from voxwright.scenarios import INJECTION_TRANSCRIPTS


def test_permission_policy_defaults_to_deny() -> None:
    policy = sandbox.PermissionPolicy({})
    assert policy.decide("notes.add") is sandbox.PermissionDecision.DENY


def test_permission_policy_resolves_allow_confirm_and_deny() -> None:
    policy = sandbox.PermissionPolicy(
        {
            Identifier("timer.start"): sandbox.PermissionDecision.ALLOW,
            Identifier("messages.send"): sandbox.PermissionDecision.CONFIRM,
            Identifier("home.unlock"): sandbox.PermissionDecision.DENY,
        }
    )
    assert policy.decide("timer.start") is sandbox.PermissionDecision.ALLOW
    assert policy.decide("messages.send") is sandbox.PermissionDecision.CONFIRM
    assert policy.decide("home.unlock") is sandbox.PermissionDecision.DENY


def test_permission_policy_snapshots_mutable_rules() -> None:
    rules = {Identifier("timer.start"): sandbox.PermissionDecision.ALLOW}
    policy = sandbox.PermissionPolicy(rules)
    rules.clear()
    assert policy.decide("timer.start") is sandbox.PermissionDecision.ALLOW


def test_side_effect_ledger_chains_denied_and_executed_attempts() -> None:
    ledger = sandbox.SideEffectLedger()
    denied = ledger.record(Identifier("home.unlock"), {"door": "front"}, False, "denied")
    allowed = ledger.record(Identifier("timer.start"), {"seconds": 5}, True, {"timer_id": "t-1"})
    assert denied.previous == EMPTY_DIGEST
    assert allowed.previous == denied.digest
    assert ledger.validate() is None


def test_side_effect_ledger_detects_changed_execution_flag() -> None:
    from dataclasses import replace

    ledger = sandbox.SideEffectLedger()
    link = ledger.record(Identifier("home.unlock"), {}, False, "denied")
    ledger.links[0] = replace(link, payload={**link.payload, "executed": True})
    assert ledger.validate() == 0


def test_calendar_store_allocates_deterministic_ids() -> None:
    state = sandbox.SimulatedState.empty()
    first = state.calendar_create("review", 19)
    second = state.calendar_create("sync", 9)
    assert first == {"event_id": "event-1", "title": "review", "hour": 19}
    assert second["event_id"] == "event-2"
    assert state.calendar == [first, second]


def test_timer_store_is_independent_from_calendar_ids() -> None:
    state = sandbox.SimulatedState.empty()
    state.calendar_create("review", 19)
    assert state.timer_start(30) == {"timer_id": "timer-1", "seconds": 30, "active": True}


def test_empty_state_has_no_shared_mutable_stores() -> None:
    left = sandbox.SimulatedState.empty()
    right = sandbox.SimulatedState.empty()
    left.calendar_create("left", 1)
    assert right.calendar == []


def test_messaging_and_notes_append_synthetic_records() -> None:
    state = sandbox.SimulatedState.empty()
    assert state.message_send("student", "hello")["message_id"] == "message-1"
    assert state.note_add("buy milk") == {"note_id": "note-1", "text": "buy milk"}
    assert len(state.messages) == len(state.notes) == 1


def test_music_replaces_current_track_deterministically() -> None:
    state = sandbox.SimulatedState.empty()
    state.music_play("Blue Sky")
    assert state.music_play("Night Walk") == {"playing": True, "track": "Night Walk"}


def test_home_store_keeps_latest_boolean_state_per_room() -> None:
    state = sandbox.SimulatedState.empty()
    state.home_set("study", True)
    assert state.home_set("study", False) == {"room": "study", "on": False}
    assert state.home == {"study": False}


def test_denied_permission_records_nonexecution() -> None:
    box = sandbox.ToolSandbox(sandbox.PermissionPolicy({}))
    outcome = box.permission(Identifier("messages.send"))
    assert outcome == sandbox.ExecutionOutcome(False, "denied", sandbox.PermissionDecision.DENY)
    assert box.ledger.links[0].payload["executed"] is False  # type: ignore[index]


def test_confirm_permission_prompts_until_session_grant() -> None:
    name = Identifier("messages.send")
    box = sandbox.ToolSandbox(sandbox.PermissionPolicy({name: sandbox.PermissionDecision.CONFIRM}))
    prompt = box.permission(name)
    assert prompt is not None and prompt.prompt == "Confirm tool messages.send"
    box.grant(name)
    assert box.permission(name) is None


def test_allow_permission_needs_no_grant() -> None:
    name = Identifier("timer.start")
    box = sandbox.ToolSandbox(sandbox.PermissionPolicy({name: sandbox.PermissionDecision.ALLOW}))
    assert box.permission(name) is None


def test_allowed_tool_executes_and_records_result() -> None:
    name = Identifier("notes.add")
    box = sandbox.ToolSandbox(sandbox.PermissionPolicy({name: sandbox.PermissionDecision.ALLOW}))
    outcome = box.execute(name, {"text": "buy milk"})
    assert outcome.executed
    assert outcome.result == {"note_id": "note-1", "text": "buy milk"}
    assert box.ledger.links[-1].payload["executed"] is True  # type: ignore[index]


def test_dry_run_never_mutates_synthetic_state() -> None:
    name = Identifier("calendar.create")
    box = sandbox.ToolSandbox(sandbox.PermissionPolicy({name: sandbox.PermissionDecision.ALLOW}))
    outcome = box.execute(name, {"title": "review", "hour": 19}, dry_run=True)
    assert not outcome.executed
    assert box.state.calendar == []
    assert outcome.result == {
        "dry_run": True,
        "tool_name": "calendar.create",
        "arguments": {"title": "review", "hour": 19},
    }


def test_unknown_backend_fails_without_ledger_execution() -> None:
    name = Identifier("custom.tool")
    box = sandbox.ToolSandbox(sandbox.PermissionPolicy({name: sandbox.PermissionDecision.ALLOW}))
    with pytest.raises(ValueError, match="no simulated backend"):
        box.execute(name, {})
    assert box.ledger.links == []


def test_atomic_batch_commits_all_successful_calls() -> None:
    names = (Identifier("notes.add"), Identifier("timer.start"))
    box = sandbox.ToolSandbox(
        sandbox.PermissionPolicy({name: sandbox.PermissionDecision.ALLOW for name in names})
    )
    outcomes = box.execute_atomic(((names[0], {"text": "milk"}), (names[1], {"seconds": 30})))
    assert len(outcomes) == 2
    assert len(box.state.notes) == len(box.state.timers) == 1


def test_atomic_batch_rolls_back_prior_effect_when_later_call_is_denied() -> None:
    allowed = Identifier("notes.add")
    denied = Identifier("messages.send")
    box = sandbox.ToolSandbox(sandbox.PermissionPolicy({allowed: sandbox.PermissionDecision.ALLOW}))
    with pytest.raises(PermissionError, match="did not execute"):
        box.execute_atomic(
            ((allowed, {"text": "temporary"}), (denied, {"recipient": "x", "text": "x"}))
        )
    assert box.state.notes == []
    assert box.ledger.links == []


@pytest.mark.parametrize("attack", INJECTION_TRANSCRIPTS)
def test_injection_text_cannot_change_denied_execution(attack: str) -> None:
    box = sandbox.ToolSandbox(sandbox.PermissionPolicy({}))
    outcome = box.execute("notes.add", {"text": attack})
    assert not outcome.executed
    assert box.state.notes == []
    assert box.ledger.links[-1].payload["executed"] is False  # type: ignore[index]


def test_ungranted_confirm_tool_never_executes_across_repeated_attempts() -> None:
    name = Identifier("messages.send")
    box = sandbox.ToolSandbox(sandbox.PermissionPolicy({name: sandbox.PermissionDecision.CONFIRM}))
    for _ in range(20):
        outcome = box.execute(name, {"recipient": "synthetic", "text": "hello"})
        assert not outcome.executed
    assert box.state.messages == []
    assert box.ledger.links == []
