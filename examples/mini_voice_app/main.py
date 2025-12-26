"""Run a permissioned synthetic calendar, music, and smart-home application."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path

from voxwright.barge_in import (
    BargePolicy,
    InFlightOperation,
    InterruptResolution,
    OperationState,
    atomic_outcome,
    resolve_interrupt,
)
from voxwright.campaign import CampaignArtifact
from voxwright.core import JSONValue, canonical_json
from voxwright.evaluation import EvaluationRun, score_runs
from voxwright.identifiers import Identifier
from voxwright.reports import CoverageFacts, ReportSpec, bar_chart_svg, render_html
from voxwright.sandbox import PermissionDecision, PermissionPolicy, ToolSandbox


def run_tools() -> tuple[ToolSandbox, dict[str, JSONValue]]:
    calendar = Identifier("calendar.create")
    music = Identifier("music.play")
    home = Identifier("home.set-light")
    sandbox = ToolSandbox(
        PermissionPolicy(
            {
                calendar: PermissionDecision.CONFIRM,
                music: PermissionDecision.ALLOW,
                home: PermissionDecision.CONFIRM,
            }
        )
    )
    calendar_prompt = sandbox.execute(calendar, {"title": "synthetic review", "hour": 14})
    sandbox.grant(calendar)
    calendar_result = sandbox.execute(calendar, {"title": "synthetic review", "hour": 14})
    music_result = sandbox.execute(music, {"track": "Blue Sky"})
    home_prompt = sandbox.execute(home, {"room": "study", "on": True})
    sandbox.grant(home)
    home_result = sandbox.execute(home, {"room": "study", "on": True})
    facts: dict[str, JSONValue] = {
        "calendar_prompt": calendar_prompt.prompt,
        "calendar_executed": calendar_result.executed,
        "music_executed": music_result.executed,
        "home_prompt": home_prompt.prompt,
        "home_executed": home_result.executed,
        "ledger_entries": len(sandbox.ledger.links),
        "ledger_valid": sandbox.ledger.validate() is None,
    }
    return sandbox, facts


def run_interrupts() -> dict[str, JSONValue]:
    music = InFlightOperation(
        Identifier("music-operation"),
        Identifier("music.play"),
        {"track": "Blue Sky"},
        idempotent=True,
    ).start()
    finished_music, music_resolution = resolve_interrupt(music, BargePolicy.FINISH_IF_IDEMPOTENT)
    calendar = InFlightOperation(
        Identifier("calendar-operation"),
        Identifier("calendar.create"),
        {"title": "synthetic review", "hour": 14},
        idempotent=False,
    ).start()
    rolled_calendar, calendar_resolution = resolve_interrupt(calendar, BargePolicy.CANCEL)
    calendar_atomic = atomic_outcome(rolled_calendar)
    if music_resolution is not InterruptResolution.FINISHED:
        raise RuntimeError("idempotent music operation did not finish")
    if finished_music.state is not OperationState.COMPLETED:
        raise RuntimeError("music operation is not complete")
    return {
        "music_resolution": music_resolution.value,
        "calendar_resolution": calendar_resolution.value,
        "calendar_terminal": calendar_atomic.terminal_state.value,
        "calendar_committed": calendar_atomic.committed,
    }


def render_campaign_report() -> tuple[str, dict[str, JSONValue]]:
    runs = (
        EvaluationRun(
            "calendar-run",
            "schedule",
            "level-1",
            0.0,
            {"title": "synthetic review", "hour": "14"},
            {"title": "synthetic review", "hour": "14"},
            ("calendar.create",),
            ("calendar.create",),
            True,
            2,
            0,
            0,
            70,
            120,
        ),
        EvaluationRun(
            "music-run",
            "music",
            "level-1",
            0.0,
            {"track": "Blue Sky"},
            {"track": "Blue Sky"},
            ("music.play",),
            ("music.play",),
            True,
            1,
            0,
            0,
            45,
            120,
        ),
        EvaluationRun(
            "home-run",
            "smart-home",
            "level-1",
            0.0,
            {"room": "study", "on": "true"},
            {"room": "study", "on": "true"},
            ("home.set-light",),
            ("home.set-light",),
            True,
            2,
            0,
            0,
            60,
            120,
        ),
    )
    metrics = score_runs(runs)
    campaign = CampaignArtifact(
        "mini-voice-app", 0, {"adapter": "scripted", "synthetic": True}, metrics
    )
    spec = ReportSpec(
        "voxwright mini voice app",
        campaign,
        CoverageFacts(3, ("music", "schedule", "smart-home"), ("scripted",)),
    )
    chart = bar_chart_svg(
        "Synthetic logical latency (ms)",
        tuple((run.task_type, float(run.latency_ms)) for run in runs),
    )
    return render_html(spec, charts=(chart,)), metrics.to_dict()


def run(output: Path) -> dict[str, JSONValue]:
    output.mkdir()
    sandbox, facts = run_tools()
    report, metrics = render_campaign_report()
    summary: dict[str, JSONValue] = {
        **facts,
        **run_interrupts(),
        "calendar": sandbox.state.calendar,
        "home": sandbox.state.home,
        "music": sandbox.state.music,
        "metrics": metrics,
        "synthetic": True,
    }
    (output / "report.html").write_text(report, encoding="utf-8", newline="\n")
    (output / "summary.json").write_text(
        canonical_json(summary) + "\n", encoding="utf-8", newline="\n"
    )
    return summary


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args(argv)
    print(canonical_json(run(args.output)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
