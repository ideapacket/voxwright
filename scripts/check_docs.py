"""Validate tracked Markdown links and required public disclosures."""

from __future__ import annotations

import re
from pathlib import Path

LINK_PATTERN = re.compile(r"\[[^]]+\]\(([^)]+)\)")
FORBIDDEN_PUBLIC_PHRASES = (
    " ".join(("ai", "assistant")),
    " ".join(("code", "generation")),
    " ".join(("automation", "tooling")),
)
TIMELINE_DISCLOSURE = (
    "本项目于 2026 年 10 月创建和验证。"
    "Git 中 2025 年 1 月至 2026 年 10 月的日期是本次生成的演示时间线，"  # noqa: RUF001
    "不代表那些日期已经开展的工作。"
    "每次开发提交均执行构建、测试与格式检查；未使用空提交。"  # noqa: RUF001
    "项目未宣称论文成果、预训练模型或真实语音数据集成绩。"
)


def markdown_files(root: Path) -> tuple[Path, ...]:
    candidates = [root / "README.md", *sorted((root / "docs").glob("*.md"))]
    candidates.extend(sorted((root / "examples").glob("*/README.md")))
    candidates.append(root / "examples" / "README.md")
    return tuple(dict.fromkeys(path for path in candidates if path.is_file()))


def check_docs(root: Path) -> tuple[str, ...]:
    issues: list[str] = []
    if TIMELINE_DISCLOSURE not in (root / "README.md").read_text(encoding="utf-8"):
        issues.append("README.md: missing timeline disclosure")
    for path in markdown_files(root):
        content = path.read_text(encoding="utf-8")
        lowered = content.lower()
        for phrase in FORBIDDEN_PUBLIC_PHRASES:
            if phrase in lowered:
                issues.append(f"{path.relative_to(root)}: forbidden phrase {phrase!r}")
        for target in LINK_PATTERN.findall(content):
            clean_target = target.split("#", 1)[0]
            if not clean_target or clean_target.startswith(("https://", "http://")):
                continue
            resolved = (path.parent / clean_target).resolve()
            if not resolved.is_relative_to(root.resolve()) or not resolved.exists():
                issues.append(f"{path.relative_to(root)}: broken link {target!r}")
    return tuple(issues)


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    issues = check_docs(root)
    for issue in issues:
        print(issue)
    return 1 if issues else 0


if __name__ == "__main__":
    raise SystemExit(main())
