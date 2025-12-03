"""Generate a synthetic scenario and prove byte-identical session replay."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path

from voxwright.adapters import AdapterTurn, ScriptedAdapter
from voxwright.core import canonical_json
from voxwright.events import AgentUtterance, EventKind, Intent, Transcript, envelope_for
from voxwright.identifiers import Identifier
from voxwright.manifests import write_manifest
from voxwright.recording import SessionRecorder, load_session
from voxwright.replay import replay
from voxwright.scenarios import TaskType, application_scenario


def run(output: Path, seed: int) -> dict[str, object]:
    if seed < 0:
        raise ValueError("seed must be non-negative")
    output.mkdir()
    scenario = application_scenario(TaskType.MUSIC, seed)
    write_manifest(output / "scenarios.jsonl", [scenario])
    session_id = Identifier(f"scenario-replay-{seed}")
    transcript = envelope_for(
        session_id,
        0,
        10,
        EventKind.FINAL_TRANSCRIPT,
        Transcript(scenario.transcript, 1.0),
    )
    goal = scenario.goals[0]
    selected = str(goal.tool_calls[0].tool_name)
    intent = envelope_for(
        session_id,
        1,
        20,
        EventKind.INTENT,
        Intent(Identifier(selected), 1.0, goal.slots),
    )
    utterance = envelope_for(
        session_id,
        2,
        30,
        EventKind.AGENT_UTTERANCE,
        AgentUtterance("Scripted synthetic action selected", Identifier("scripted-example")),
    )
    adapter = ScriptedAdapter((AdapterTurn((intent, utterance)),))
    adapter.observe((transcript,))
    turn = adapter.act()
    recorder = SessionRecorder(output / "session.jsonl")
    for event in (transcript, *turn.events):
        recorder.append(event)
    records = load_session(output / "session.jsonl")
    first = replay(records, seed).to_bytes()
    second = replay(records, seed).to_bytes()
    if first != second:
        raise RuntimeError("same-seed replay was not byte-identical")
    (output / "trace.json").write_bytes(first)
    summary: dict[str, object] = {
        "adapter": "scripted",
        "byte_identical": True,
        "event_count": len(records),
        "scenario_id": str(scenario.scenario_id),
        "seed": seed,
        "synthetic": True,
        "tool": selected,
    }
    (output / "summary.json").write_text(
        canonical_json(summary) + "\n", encoding="utf-8", newline="\n"
    )
    return summary


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--seed", type=int, default=7)
    args = parser.parse_args(argv)
    print(canonical_json(run(args.output, args.seed)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
