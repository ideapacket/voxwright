"""Command-line entry point."""

from __future__ import annotations

import argparse
from collections.abc import Sequence

from voxwright import __version__


def build_parser() -> argparse.ArgumentParser:
    """Build the root command parser."""
    parser = argparse.ArgumentParser(
        prog="voxwright",
        description="离线验证语音应用机制的可复现工具箱",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the command-line interface."""
    build_parser().parse_args(argv)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
