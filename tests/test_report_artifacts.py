from __future__ import annotations

import pytest

from voxwright.campaign import CampaignArtifact
from voxwright.evaluation import EvaluationRun, score_runs
from voxwright.report_artifacts import (
    ReportBundle,
    ReportFormat,
    create_report_bundle,
    decode_report_bundle,
    encode_report_bundle,
)
from voxwright.reports import CoverageFacts, ReportSpec, bar_chart_svg, report_digest


def sample_spec() -> ReportSpec:
    run = EvaluationRun(
        "bundle-run",
        "notes",
        "easy",
        0.0,
        {"text": "synthetic note"},
        {"text": "synthetic note"},
        ("notes.add",),
        ("notes.add",),
        True,
        1,
        0,
        0,
        20,
        50,
    )
    campaign = CampaignArtifact("bundle-campaign", 11, {"adapter": "scripted"}, score_runs((run,)))
    return ReportSpec("Synthetic bundle", campaign, CoverageFacts(1, ("notes",), ("scripted",)))


def test_report_bundle_binds_rendered_content_to_provenance() -> None:
    bundle = create_report_bundle(sample_spec(), ReportFormat.MARKDOWN)
    assert bundle.report.startswith("# Synthetic bundle\n")
    assert bundle.digest == report_digest(bundle.report)
    assert bundle.spec.campaign.seed == 11


def test_html_bundle_retains_validated_charts_in_order() -> None:
    charts = (
        bar_chart_svg("Latency", (("tool", 5.0),)),
        bar_chart_svg("Success", (("notes", 1.0),)),
    )
    bundle = create_report_bundle(sample_spec(), ReportFormat.HTML, charts=charts)
    assert bundle.charts == charts
    assert bundle.report.index("Latency") < bundle.report.index("Success")


def test_report_bundle_rejects_content_or_format_drift() -> None:
    bundle = create_report_bundle(sample_spec(), ReportFormat.HTML)
    with pytest.raises(ValueError, match="does not match its provenance"):
        ReportBundle(bundle.spec, bundle.format, bundle.charts, bundle.report + "tampered")
    with pytest.raises(ValueError, match="cannot carry SVG charts"):
        create_report_bundle(
            sample_spec(), ReportFormat.MARKDOWN, charts=(bar_chart_svg("x", (("x", 1.0),)),)
        )


def test_report_bundle_codec_restores_full_provenance_and_content() -> None:
    chart = bar_chart_svg("Latency", (("tool", 5.0),))
    bundle = create_report_bundle(sample_spec(), ReportFormat.HTML, charts=(chart,))
    restored = ReportBundle.from_dict(bundle.to_dict())
    assert restored == bundle
    encoded = encode_report_bundle(bundle)
    assert decode_report_bundle(encoded) == bundle
    assert encode_report_bundle(decode_report_bundle(encoded)) == encoded
