"""Deterministic Markdown, HTML, and SVG reports for executed campaigns."""

from __future__ import annotations

from dataclasses import dataclass

from voxwright.campaign import CampaignArtifact


@dataclass(frozen=True, slots=True)
class CoverageFacts:
    """Facts about what an offline campaign actually exercised."""

    scenario_count: int
    task_types: tuple[str, ...]
    adapter_names: tuple[str, ...]
    used_real_audio: bool = False
    used_model_endpoint: bool = False

    def __post_init__(self) -> None:
        if isinstance(self.scenario_count, bool) or self.scenario_count < 0:
            raise ValueError("coverage scenario count must be a non-negative integer")
        for label, values in (("task type", self.task_types), ("adapter", self.adapter_names)):
            if any(not value.strip() for value in values):
                raise ValueError(f"coverage {label} names cannot be empty")
            if len(set(values)) != len(values):
                raise ValueError(f"coverage {label} names must be unique")


def coverage_limitations(facts: CoverageFacts) -> tuple[str, ...]:
    """Generate honest limitations directly from recorded coverage facts."""
    items = [f"Metrics cover {facts.scenario_count} seeded synthetic scenarios with planted truth."]
    if not facts.used_real_audio:
        items.append("No real speech recording was evaluated.")
    if not facts.used_model_endpoint:
        items.append("No actual spoken-model endpoint was evaluated.")
    if not facts.task_types:
        items.append("No task type was represented in this campaign.")
    if not facts.adapter_names:
        items.append("No adapter execution was represented in this campaign.")
    return tuple(items)


@dataclass(frozen=True, slots=True)
class ReportSpec:
    title: str
    campaign: CampaignArtifact
    coverage: CoverageFacts

    def __post_init__(self) -> None:
        if not self.title.strip():
            raise ValueError("report title cannot be empty")
        if self.coverage.scenario_count != self.campaign.metrics.run_count:
            raise ValueError("report coverage count must match campaign metrics")


def _markdown_text(value: str) -> str:
    escaped = value.replace("\\", "\\\\")
    for marker in ("`", "*", "_", "[", "]", "<", ">", "|"):
        escaped = escaped.replace(marker, f"\\{marker}")
    return escaped.replace("\r", " ").replace("\n", " ")


def render_markdown(spec: ReportSpec) -> str:
    """Render a deterministic campaign summary without invented measurements."""
    metrics = spec.campaign.metrics
    lines = [
        f"# {_markdown_text(spec.title)}",
        "",
        "> 本报告仅汇总离线合成场景及植入真值, 不代表真实语音模型质量。",
        "",
        "## 运行元数据",
        "",
        f"- Campaign: `{_markdown_text(spec.campaign.name)}`",
        f"- Seed: `{spec.campaign.seed}`",
        f"- Config digest: `{spec.campaign.config_digest}`",
        f"- Runs: `{metrics.run_count}`",
        "",
        "## 指标",
        "",
        "| 指标 | 值 |",
        "| --- | ---: |",
        f"| Task success | {metrics.task_success:.6f} |",
        f"| Slot accuracy | {metrics.slots.accuracy:.6f} |",
        f"| Tool F1 | {metrics.tools.f1:.6f} |",
        f"| Repair rate | {metrics.efficiency.repair_rate:.6f} |",
        f"| False execute | {metrics.efficiency.false_execute_count} |",
        f"| Latency adherence | {metrics.efficiency.latency_adherence:.6f} |",
        "",
        "## 局限",
        "",
    ]
    lines.extend(f"- {_markdown_text(item)}" for item in coverage_limitations(spec.coverage))
    return "\n".join(lines) + "\n"
