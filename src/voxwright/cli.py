"""Command-line entry point."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable, Sequence
from pathlib import Path

from voxwright import __version__
from voxwright.campaign import CampaignArtifact
from voxwright.core import canonical_json
from voxwright.evaluation import score_runs
from voxwright.latency import RunOutcome, latency_success_curve
from voxwright.manifests import encode_manifest, read_manifest
from voxwright.recording import load_session, summarize
from voxwright.replay import replay
from voxwright.reports import CoverageFacts, ReportSpec, render_html, render_markdown
from voxwright.run_artifacts import decode_runs, encode_runs, scripted_run
from voxwright.scenarios import TaskType, application_scenario, composite_scenario
from voxwright.session_diff import diff_traces, format_differences

CommandHandler = Callable[[argparse.Namespace], int]


def _pending(args: argparse.Namespace) -> int:
    raise ValueError(f"command is not implemented: {args.command}")


def _simulate(args: argparse.Namespace) -> int:
    output: Path = args.output
    if args.seed < 0:
        raise ValueError("seed must be non-negative")
    if args.count < 1:
        raise ValueError("count must be positive")
    if output.exists():
        raise FileExistsError(f"output already exists: {output}")
    scenarios = []
    task_type = TaskType(args.task)
    for offset in range(args.count):
        seed = args.seed + offset
        if task_type is TaskType.MULTI_TASK:
            scenarios.append(composite_scenario(seed))
        elif task_type is TaskType.NESTED:
            scenarios.append(composite_scenario(seed, nested=True))
        else:
            scenarios.append(application_scenario(task_type, seed))
    output.write_text(encode_manifest(scenarios), encoding="utf-8", newline="\n")
    print(
        canonical_json(
            {
                "artifact": "synthetic-scenario-manifest",
                "count": len(scenarios),
                "output": str(output),
                "seed": args.seed,
                "task": task_type.value,
            }
        )
    )
    return 0


def _validate(args: argparse.Namespace) -> int:
    path: Path = args.path
    if args.artifact == "manifest":
        scenarios = read_manifest(path)
        result = {"artifact": "manifest", "count": len(scenarios), "valid": True}
    else:
        records = load_session(path)
        summary = summarize(records)
        result = {
            "artifact": "session",
            "count": summary.event_count,
            "digest": summary.final_digest,
            "valid": True,
        }
    print(canonical_json(result))
    return 0


def _replay(args: argparse.Namespace) -> int:
    if args.seed < 0:
        raise ValueError("replay seed must be non-negative")
    trace = replay(load_session(args.path), args.seed)
    print(trace.to_bytes().decode("utf-8"))
    return 0


def _diff(args: argparse.Namespace) -> int:
    left = replay(load_session(args.left), args.seed)
    right = replay(load_session(args.right), args.seed)
    differences = diff_traces(left, right)
    print(format_differences(differences), end="")
    return 1 if differences else 0


def _run(args: argparse.Namespace) -> int:
    if args.output.exists():
        raise FileExistsError(f"output already exists: {args.output}")
    scenarios = read_manifest(args.manifest)
    encoded = encode_runs(tuple(scripted_run(item) for item in scenarios))
    args.output.write_text(encoded, encoding="utf-8")
    print(
        canonical_json(
            {
                "artifact": "synthetic-runs",
                "count": len(scenarios),
                "output": str(args.output),
            }
        )
    )
    return 0


def _score(args: argparse.Namespace) -> int:
    runs = decode_runs(args.path.read_text(encoding="utf-8"))
    print(canonical_json(score_runs(runs).to_dict()))
    return 0


def _report(args: argparse.Namespace) -> int:
    if args.output.exists():
        raise FileExistsError(f"output already exists: {args.output}")
    runs = decode_runs(args.path.read_text(encoding="utf-8"))
    metrics = score_runs(runs)
    campaign = CampaignArtifact(
        args.name,
        args.seed,
        {"adapter": "scripted", "source": "synthetic-runs"},
        metrics,
    )
    coverage = CoverageFacts(
        len(runs),
        tuple(sorted({run.task_type for run in runs})),
        ("scripted",),
    )
    spec = ReportSpec(args.title, campaign, coverage)
    content = render_html(spec) if args.format == "html" else render_markdown(spec)
    args.output.write_text(content, encoding="utf-8", newline="\n")
    print(
        canonical_json(
            {"artifact": f"{args.format}-report", "output": str(args.output), "runs": len(runs)}
        )
    )
    return 0


def _bench(args: argparse.Namespace) -> int:
    runs = decode_runs(args.path.read_text(encoding="utf-8"))
    outcomes = tuple(RunOutcome(run.latency_ms, run.goal_satisfied) for run in runs)
    points = latency_success_curve(outcomes, tuple(args.budgets))
    print(
        canonical_json(
            {
                "artifact": "synthetic-latency-benchmark",
                "run_count": len(runs),
                "points": [
                    {
                        "budget_ms": point.budget_ms,
                        "completed": point.completed,
                        "successes": point.successes,
                        "adherence_rate": point.adherence_rate,
                        "success_rate": point.success_rate,
                    }
                    for point in points
                ],
            }
        )
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    """Build the root command parser."""
    parser = argparse.ArgumentParser(
        prog="voxwright",
        description="离线验证语音应用机制的可复现工具箱",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    subcommands = parser.add_subparsers(dest="command", metavar="COMMAND")
    commands: dict[str, argparse.ArgumentParser] = {}
    for name, help_text in (
        ("simulate", "生成带植入真值的离线合成场景"),
        ("run", "运行离线应用流程"),
        ("replay", "重放校验过的会话记录"),
        ("diff", "逐事件比较两个会话"),
        ("validate", "校验版本化制品"),
        ("score", "评分合成任务运行"),
        ("report", "生成自包含报告"),
        ("bench", "测量逻辑时钟延迟"),
        ("demo", "运行小型离线演示"),
    ):
        command = subcommands.add_parser(name, help=help_text, description=help_text)
        command.set_defaults(handler=_pending)
        commands[name] = command
    simulate = commands["simulate"]
    simulate.add_argument("output", type=Path, help="目标 JSONL 文件 (必须不存在)")
    simulate.add_argument("--seed", type=int, default=0, help="首个非负种子")
    simulate.add_argument("--count", type=int, default=1, help="场景数量")
    simulate.add_argument("--task", choices=[item.value for item in TaskType], default="schedule")
    simulate.set_defaults(handler=_simulate)
    validate = commands["validate"]
    validate.add_argument("artifact", choices=("manifest", "session"))
    validate.add_argument("path", type=Path)
    validate.set_defaults(handler=_validate)
    replay_command = commands["replay"]
    replay_command.add_argument("path", type=Path)
    replay_command.add_argument("--seed", type=int, default=0)
    replay_command.set_defaults(handler=_replay)
    diff_command = commands["diff"]
    diff_command.add_argument("left", type=Path)
    diff_command.add_argument("right", type=Path)
    diff_command.add_argument("--seed", type=int, default=0)
    diff_command.set_defaults(handler=_diff)
    run_command = commands["run"]
    run_command.add_argument("manifest", type=Path)
    run_command.add_argument("output", type=Path)
    run_command.set_defaults(handler=_run)
    score_command = commands["score"]
    score_command.add_argument("path", type=Path)
    score_command.set_defaults(handler=_score)
    report_command = commands["report"]
    report_command.add_argument("path", type=Path, help="校验过的运行 JSONL")
    report_command.add_argument("output", type=Path, help="目标报告文件 (必须不存在)")
    report_command.add_argument("--format", choices=("markdown", "html"), default="html")
    report_command.add_argument("--title", default="voxwright 离线合成评估")
    report_command.add_argument("--name", default="offline-campaign")
    report_command.add_argument("--seed", type=int, default=0)
    report_command.set_defaults(handler=_report)
    bench_command = commands["bench"]
    bench_command.add_argument("path", type=Path, help="校验过的运行 JSONL")
    bench_command.add_argument(
        "--budgets", nargs="+", type=int, default=[50, 75, 100, 150], metavar="MS"
    )
    bench_command.set_defaults(handler=_bench)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the command-line interface."""
    parser = build_parser()
    args = parser.parse_args(argv)
    handler: CommandHandler | None = getattr(args, "handler", None)
    if handler is None:
        parser.print_help()
        return 0
    try:
        return handler(args)
    except (OSError, TypeError, ValueError) as error:
        print(f"voxwright: error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
