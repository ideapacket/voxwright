"""Verifiable bundles for deterministic campaign reports and their provenance."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from voxwright.reports import ReportSpec, render_html, render_markdown, report_digest


class ReportFormat(str, Enum):
    MARKDOWN = "markdown"
    HTML = "html"


def _render(spec: ReportSpec, format: ReportFormat, charts: tuple[str, ...]) -> str:
    if format is ReportFormat.HTML:
        return render_html(spec, charts=charts)
    if charts:
        raise ValueError("markdown report bundles cannot carry SVG charts")
    return render_markdown(spec)


@dataclass(frozen=True, slots=True)
class ReportBundle:
    """Rendered bytes bound to the facts used to create them."""

    spec: ReportSpec
    format: ReportFormat
    charts: tuple[str, ...]
    report: str
    schema_version: int = 1

    def __post_init__(self) -> None:
        if self.schema_version != 1:
            raise ValueError(f"unsupported report bundle version: {self.schema_version}")
        expected = _render(self.spec, self.format, self.charts)
        if self.report != expected:
            raise ValueError("report bundle content does not match its provenance")

    @property
    def digest(self) -> str:
        return report_digest(self.report)


def create_report_bundle(
    spec: ReportSpec,
    format: ReportFormat,
    *,
    charts: tuple[str, ...] = (),
) -> ReportBundle:
    return ReportBundle(spec, format, charts, _render(spec, format, charts))
