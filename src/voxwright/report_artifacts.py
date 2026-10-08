"""Verifiable bundles for deterministic campaign reports and their provenance."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from voxwright.campaign import CampaignArtifact
from voxwright.core import JSONValue, canonical_json, ensure_json_value, parse_json
from voxwright.reports import (
    CoverageFacts,
    ReportSpec,
    render_html,
    render_markdown,
    report_digest,
)


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

    def to_dict(self) -> dict[str, JSONValue]:
        coverage = self.spec.coverage
        return {
            "schema_version": self.schema_version,
            "format": self.format.value,
            "title": self.spec.title,
            "campaign": self.spec.campaign.to_dict(),
            "coverage": {
                "scenario_count": coverage.scenario_count,
                "task_types": list(coverage.task_types),
                "adapter_names": list(coverage.adapter_names),
                "used_real_audio": coverage.used_real_audio,
                "used_model_endpoint": coverage.used_model_endpoint,
            },
            "charts": list(self.charts),
            "report": self.report,
            "digest": self.digest,
        }

    @classmethod
    def from_dict(cls, value: JSONValue) -> ReportBundle:
        data = ensure_json_value(value)
        fields = {
            "schema_version",
            "format",
            "title",
            "campaign",
            "coverage",
            "charts",
            "report",
            "digest",
        }
        if not isinstance(data, dict) or set(data) != fields:
            raise ValueError("$: expected exact report bundle fields")
        version = data["schema_version"]
        if isinstance(version, bool) or not isinstance(version, int) or version != 1:
            raise ValueError(f"$.schema_version: unsupported version {version!r}")
        title = data["title"]
        format_text = data["format"]
        report = data["report"]
        digest = data["digest"]
        if not all(isinstance(item, str) for item in (title, format_text, report, digest)):
            raise TypeError("report bundle title, format, report, and digest must be strings")
        try:
            format = ReportFormat(format_text)
        except ValueError as error:
            raise ValueError(f"$.format: unknown report format {format_text!r}") from error
        charts = data["charts"]
        if not isinstance(charts, list) or any(not isinstance(item, str) for item in charts):
            raise TypeError("$.charts: expected string array")
        coverage = data["coverage"]
        coverage_fields = {
            "scenario_count",
            "task_types",
            "adapter_names",
            "used_real_audio",
            "used_model_endpoint",
        }
        if not isinstance(coverage, dict) or set(coverage) != coverage_fields:
            raise ValueError("$.coverage: expected exact coverage fields")
        scenario_count = coverage["scenario_count"]
        task_types = coverage["task_types"]
        adapter_names = coverage["adapter_names"]
        used_real_audio = coverage["used_real_audio"]
        used_model_endpoint = coverage["used_model_endpoint"]
        if isinstance(scenario_count, bool) or not isinstance(scenario_count, int):
            raise TypeError("$.coverage.scenario_count: expected integer")
        if not isinstance(task_types, list) or any(
            not isinstance(item, str) for item in task_types
        ):
            raise TypeError("$.coverage.task_types: expected string array")
        if not isinstance(adapter_names, list) or any(
            not isinstance(item, str) for item in adapter_names
        ):
            raise TypeError("$.coverage.adapter_names: expected string array")
        if not isinstance(used_real_audio, bool) or not isinstance(used_model_endpoint, bool):
            raise TypeError("$.coverage usage flags must be booleans")
        if not isinstance(data["campaign"], dict):
            raise TypeError("$.campaign: expected object")
        campaign = CampaignArtifact.from_dict(data["campaign"])
        facts = CoverageFacts(
            scenario_count,
            tuple(task_types),
            tuple(adapter_names),
            used_real_audio,
            used_model_endpoint,
        )
        if report_digest(report) != digest:
            raise ValueError("$.digest: report checksum mismatch")
        return cls(ReportSpec(title, campaign, facts), format, tuple(charts), report, version)


def create_report_bundle(
    spec: ReportSpec,
    format: ReportFormat,
    *,
    charts: tuple[str, ...] = (),
) -> ReportBundle:
    return ReportBundle(spec, format, charts, _render(spec, format, charts))


def encode_report_bundle(bundle: ReportBundle) -> str:
    return canonical_json(bundle.to_dict()) + "\n"


def decode_report_bundle(text: str) -> ReportBundle:
    if not text.strip():
        raise ValueError("report bundle document is empty")
    return ReportBundle.from_dict(parse_json(text))
