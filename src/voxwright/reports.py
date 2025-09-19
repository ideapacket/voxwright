"""Deterministic Markdown, HTML, and SVG reports for executed campaigns."""

from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass
from html import escape
from itertools import pairwise

from voxwright.campaign import CampaignArtifact, CampaignSlice
from voxwright.events import EventEnvelope
from voxwright.hashing import content_digest


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


def render_html(spec: ReportSpec, *, charts: tuple[str, ...] = ()) -> str:
    """Render a self-contained, escaped HTML campaign summary."""
    metrics = spec.campaign.metrics
    limitations = "".join(
        f"<li>{escape(item)}</li>" for item in coverage_limitations(spec.coverage)
    )
    rows = (
        ("Task success", metrics.task_success),
        ("Slot accuracy", metrics.slots.accuracy),
        ("Tool F1", metrics.tools.f1),
        ("Repair rate", metrics.efficiency.repair_rate),
        ("Latency adherence", metrics.efficiency.latency_adherence),
    )
    metric_rows = "".join(
        f"<tr><th>{escape(name)}</th><td>{value:.6f}</td></tr>" for name, value in rows
    )
    for chart in charts:
        lowered = chart.lower()
        if (
            not chart.startswith("<svg ")
            or not chart.endswith("</svg>")
            or "<script" in lowered
            or "onload=" in lowered
        ):
            raise ValueError("report charts must be safe complete SVG documents")
    chart_section = "".join(f"<figure>{chart}</figure>" for chart in charts)
    return (
        '<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f"<title>{escape(spec.title)}</title>"
        "<style>body{font:16px system-ui;max-width:900px;margin:auto;padding:2rem}"
        "table{border-collapse:collapse}th,td{border:1px solid #bbb;padding:.4rem}</style>"
        "</head><body>"
        f"<h1>{escape(spec.title)}</h1>"
        "<p><strong>离线合成评估:</strong> 指标来自植入真值, 不代表真实模型质量。</p>"
        f"<p>Campaign: <code>{escape(spec.campaign.name)}</code>; Seed: "
        f"<code>{spec.campaign.seed}</code>; Config: "
        f"<code>{escape(spec.campaign.config_digest)}</code></p>"
        f"<table><tbody>{metric_rows}</tbody></table>{chart_section}"
        f"<h2>局限</h2><ul>{limitations}</ul>"
        "</body></html>\n"
    )


def bar_chart_svg(title: str, values: tuple[tuple[str, float], ...]) -> str:
    """Render a deterministic horizontal SVG bar chart without plotting dependencies."""
    if not title.strip():
        raise ValueError("bar chart title cannot be empty")
    if not values:
        raise ValueError("bar chart requires at least one value")
    if any(not label.strip() for label, _ in values):
        raise ValueError("bar chart labels cannot be empty")
    if any(not math.isfinite(value) or value < 0 for _, value in values):
        raise ValueError("bar chart values must be finite and non-negative")
    maximum = max(value for _, value in values) or 1.0
    height = 52 + len(values) * 30
    elements = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 560 {height}" role="img">',
        f"<title>{escape(title)}</title>",
        f'<text x="12" y="24" font-size="16">{escape(title)}</text>',
    ]
    for index, (label, value) in enumerate(values):
        y = 44 + index * 30
        width = round(360 * value / maximum, 3)
        elements.extend(
            (
                f'<text x="12" y="{y + 15}" font-size="12">{escape(label)}</text>',
                f'<rect x="140" y="{y}" width="{width}" height="18" fill="#3568a8"/>',
                f'<text x="508" y="{y + 15}" font-size="12">{value:.3f}</text>',
            )
        )
    elements.append("</svg>")
    return "".join(elements)


def curve_chart_svg(title: str, points: tuple[tuple[float, float], ...]) -> str:
    """Render an ordered normalized success or repair curve as SVG."""
    if not title.strip():
        raise ValueError("curve chart title cannot be empty")
    if not points:
        raise ValueError("curve chart requires at least one point")
    if any(
        not math.isfinite(x) or not math.isfinite(y) or x < 0 or not 0.0 <= y <= 1.0
        for x, y in points
    ):
        raise ValueError("curve points require finite non-negative x and bounded y")
    if any(right[0] < left[0] for left, right in pairwise(points)):
        raise ValueError("curve points must be ordered by x")
    maximum_x = max(x for x, _ in points) or 1.0
    coordinates = " ".join(
        f"{round(40 + 480 * x / maximum_x, 3)},{round(220 - 180 * y, 3)}" for x, y in points
    )
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 560 250" role="img">'
        f"<title>{escape(title)}</title>"
        '<path d="M40 20V220H530" fill="none" stroke="#333"/>'
        f'<polyline points="{coordinates}" fill="none" stroke="#b54747" stroke-width="3"/>'
        "</svg>"
    )


def heat_table_svg(title: str, cells: tuple[tuple[str, float], ...]) -> str:
    """Render labeled normalized values as an accessible SVG heat table."""
    if not title.strip():
        raise ValueError("heat table title cannot be empty")
    if not cells:
        raise ValueError("heat table requires at least one cell")
    if any(
        not label.strip() or not math.isfinite(value) or not 0.0 <= value <= 1.0
        for label, value in cells
    ):
        raise ValueError("heat table cells require labels and values between 0 and 1")
    height = 40 + len(cells) * 32
    output = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 440 {height}" role="img">',
        f"<title>{escape(title)}</title>",
    ]
    for index, (label, value) in enumerate(cells):
        y = 10 + index * 32
        shade = round(235 - 150 * value)
        output.extend(
            (
                f'<rect x="160" y="{y}" width="200" height="26" fill="rgb({shade},{shade},255)"/>',
                f'<text x="8" y="{y + 18}" font-size="12">{escape(label)}</text>',
                f'<text x="368" y="{y + 18}" font-size="12">{value:.3f}</text>',
            )
        )
    output.append("</svg>")
    return "".join(output)


def render_slice_markdown(slices: tuple[CampaignSlice, ...]) -> str:
    """Render campaign slice metrics as a stable Markdown table fragment."""
    if not slices:
        raise ValueError("slice table requires at least one slice")
    rows = [
        "| Dimension | Slice | Runs | Success | Slot accuracy | Tool F1 |",
        "| --- | --- | ---: | ---: | ---: | ---: |",
    ]
    rows.extend(
        f"| {_markdown_text(item.dimension.value)} | {_markdown_text(item.label)} | "
        f"{item.metrics.run_count} | {item.metrics.task_success:.6f} | "
        f"{item.metrics.slots.accuracy:.6f} | {item.metrics.tools.f1:.6f} |"
        for item in slices
    )
    return "\n".join(rows) + "\n"


def report_digest(report: str) -> str:
    """Digest the exact UTF-8 bytes of a completed deterministic report."""
    if not report:
        raise ValueError("report digest requires nonempty content")
    return content_digest(report.encode("utf-8"))


@dataclass(frozen=True, slots=True)
class SessionSummary:
    session_id: str
    event_count: int
    duration_ms: int
    kinds: tuple[tuple[str, int], ...]


def summarize_session(events: tuple[EventEnvelope, ...]) -> SessionSummary:
    """Summarize one ordered recorded session without interpreting dialogue quality."""
    if not events:
        raise ValueError("session summary requires at least one event")
    session_id = events[0].session_id
    for index, event in enumerate(events):
        if event.session_id != session_id:
            raise ValueError("session summary events must share a session id")
        if event.sequence != index:
            raise ValueError("session summary events must have contiguous sequence numbers")
        if index and event.at_ms < events[index - 1].at_ms:
            raise ValueError("session summary event times cannot move backwards")
    counts = Counter(event.kind.value for event in events)
    return SessionSummary(
        str(session_id),
        len(events),
        events[-1].at_ms - events[0].at_ms,
        tuple(sorted(counts.items())),
    )
