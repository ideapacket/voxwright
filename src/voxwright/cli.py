"""Command-line entry point."""

from __future__ import annotations

import argparse
from collections.abc import Callable, Sequence
from pathlib import Path

from voxwright import __version__
from voxwright.core import canonical_json
from voxwright.manifests import encode_manifest
from voxwright.scenarios import TaskType, application_scenario, composite_scenario

CommandHandler = Callable[[argparse.Namespace], int]


def _pending(args: argparse.Namespace) -> int:
    raise ValueError(f"command is not implemented: {args.command}")


def _simulate(args: argparse.Namespace) -> int:
    output: Path = args.output
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
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the command-line interface."""
    parser = build_parser()
    args = parser.parse_args(argv)
    handler: CommandHandler | None = getattr(args, "handler", None)
    if handler is None:
        parser.print_help()
        return 0
    return handler(args)


if __name__ == "__main__":
    raise SystemExit(main())
