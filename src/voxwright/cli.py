"""Command-line entry point."""

from __future__ import annotations

import argparse
from collections.abc import Callable, Sequence

from voxwright import __version__

CommandHandler = Callable[[argparse.Namespace], int]


def _pending(args: argparse.Namespace) -> int:
    raise ValueError(f"command is not implemented: {args.command}")


def build_parser() -> argparse.ArgumentParser:
    """Build the root command parser."""
    parser = argparse.ArgumentParser(
        prog="voxwright",
        description="离线验证语音应用机制的可复现工具箱",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    subcommands = parser.add_subparsers(dest="command", metavar="COMMAND")
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
