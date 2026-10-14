from __future__ import annotations

from pathlib import Path

import pytest

from voxwright.campaign import CampaignArtifact
from voxwright.evaluation import EvaluationRun, score_runs
from voxwright.report_artifacts import (
    ReportBundle,
    ReportFormat,
    create_report_bundle,
    decode_report_bundle,
    encode_report_bundle,
    load_report_bundle,
    report_bundle_digest,
    write_report_bundle,
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


def test_report_bundle_decoder_rejects_shape_version_and_typed_metadata() -> None:
    bundle = create_report_bundle(sample_spec(), ReportFormat.MARKDOWN)
    value = bundle.to_dict()
    value["extra"] = None
    with pytest.raises(ValueError, match="exact report bundle fields"):
        ReportBundle.from_dict(value)
    value = bundle.to_dict()
    value["schema_version"] = True
    with pytest.raises(ValueError, match="unsupported version True"):
        ReportBundle.from_dict(value)
    value = bundle.to_dict()
    value["format"] = "pdf"
    with pytest.raises(ValueError, match="unknown report format"):
        ReportBundle.from_dict(value)
    value = bundle.to_dict()
    value["coverage"]["scenario_count"] = False  # type: ignore[index]
    with pytest.raises(TypeError, match="scenario_count: expected integer"):
        ReportBundle.from_dict(value)


def test_report_bundle_decoder_detects_digest_and_rendered_content_tampering() -> None:
    bundle = create_report_bundle(sample_spec(), ReportFormat.MARKDOWN)
    value = bundle.to_dict()
    value["digest"] = "sha256:" + "0" * 64
    with pytest.raises(ValueError, match="report checksum mismatch"):
        ReportBundle.from_dict(value)
    value = bundle.to_dict()
    value["report"] = bundle.report.replace("1.000000", "0.000000", 1)
    value["digest"] = report_digest(value["report"])  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="does not match its provenance"):
        ReportBundle.from_dict(value)
    value = bundle.to_dict()
    value["coverage"]["scenario_count"] = 2  # type: ignore[index]
    with pytest.raises(ValueError, match="count must match"):
        ReportBundle.from_dict(value)


def test_report_bundle_file_roundtrip_preserves_both_integrity_layers(tmp_path: Path) -> None:
    bundle = create_report_bundle(sample_spec(), ReportFormat.HTML)
    path = tmp_path / "report-bundle.json"
    write_report_bundle(path, bundle)
    restored = load_report_bundle(path)
    assert restored == bundle
    assert restored.digest == report_digest(restored.report)
    assert report_bundle_digest(restored) == report_bundle_digest(bundle)


def test_report_bundle_files_reject_clobbering_truncation_and_empty_input(tmp_path: Path) -> None:
    bundle = create_report_bundle(sample_spec(), ReportFormat.MARKDOWN)
    path = tmp_path / "report-bundle.json"
    write_report_bundle(path, bundle)
    with pytest.raises(FileExistsError, match="output already exists"):
        write_report_bundle(path, bundle)
    path.write_text(encode_report_bundle(bundle).rstrip("\n"), encoding="utf-8")
    with pytest.raises(ValueError, match="missing terminal newline"):
        load_report_bundle(path)
    with pytest.raises(ValueError, match="document is empty"):
        decode_report_bundle("\n")
