"""Run a permissioned synthetic calendar, music, and smart-home application."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path

from voxwright.core import JSONValue, canonical_json
from voxwright.identifiers import Identifier
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


def run(output: Path) -> dict[str, JSONValue]:
    output.mkdir()
    sandbox, facts = run_tools()
    summary: dict[str, JSONValue] = {
        **facts,
        "calendar": sandbox.state.calendar,
        "home": sandbox.state.home,
        "music": sandbox.state.music,
        "synthetic": True,
    }
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
