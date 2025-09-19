"""Tests for deterministic report synthesis."""

from __future__ import annotations

import pytest

from voxwright.campaign import CampaignArtifact, SliceDimension, slice_campaign
from voxwright.evaluation import EvaluationRun, score_runs
from voxwright.events import EventKind, Transcript, envelope_for
from voxwright.identifiers import Identifier
from voxwright.reports import (
    CoverageFacts,
    ReportSpec,
    bar_chart_svg,
    coverage_limitations,
    curve_chart_svg,
    heat_table_svg,
    render_html,
    render_markdown,
    render_slice_markdown,
    report_digest,
    summarize_session,
)


def report_spec(title: str = "Synthetic campaign") -> ReportSpec:
    run = EvaluationRun(
        "run-1",
        "schedule",
        "easy",
        0.1,
        {"title": "lab"},
        {"title": "lab"},
        ("calendar.create",),
        ("calendar.create",),
        True,
        2,
        0,
        0,
        100,
        150,
    )
    campaign = CampaignArtifact("offline", 7, {"adapter": "scripted"}, score_runs((run,)))
    return ReportSpec(title, campaign, CoverageFacts(1, ("schedule",), ("scripted",)))


def test_limitations_are_derived_from_actual_coverage() -> None:
    facts = CoverageFacts(5, ("schedule",), ("scripted",))
    assert coverage_limitations(facts) == (
        "Metrics cover 5 seeded synthetic scenarios with planted truth.",
        "No real speech recording was evaluated.",
        "No actual spoken-model endpoint was evaluated.",
    )


def test_coverage_can_record_explicitly_exercised_interfaces() -> None:
    facts = CoverageFacts(
        1,
        ("music",),
        ("loopback",),
        used_real_audio=True,
        used_model_endpoint=True,
    )
    limitations = coverage_limitations(facts)
    assert len(limitations) == 1
    assert "seeded synthetic" in limitations[0]


def test_empty_coverage_explains_missing_dimensions() -> None:
    limitations = coverage_limitations(CoverageFacts(0, (), ()))
    assert "No task type was represented in this campaign." in limitations
    assert "No adapter execution was represented in this campaign." in limitations


def test_coverage_facts_reject_invalid_counts_and_names() -> None:
    with pytest.raises(ValueError, match="non-negative integer"):
        CoverageFacts(-1, (), ())
    with pytest.raises(ValueError, match="cannot be empty"):
        CoverageFacts(1, ("",), ())
    with pytest.raises(ValueError, match="must be unique"):
        CoverageFacts(1, (), ("scripted", "scripted"))


def test_markdown_report_contains_measured_campaign_values() -> None:
    report = render_markdown(report_spec())
    assert report.startswith("# Synthetic campaign\n")
    assert "| Task success | 1.000000 |" in report
    assert "| False execute | 0 |" in report
    assert "Campaign: `offline`" in report


def test_markdown_report_escapes_hostile_heading_and_metadata() -> None:
    spec = report_spec("[title](bad) <script>|cell")
    report = render_markdown(spec)
    assert "\\[title\\](bad) \\<script\\>\\|cell" in report
    assert "<script>" not in report


def test_report_spec_requires_matching_executed_count() -> None:
    spec = report_spec()
    with pytest.raises(ValueError, match="count must match"):
        ReportSpec(spec.title, spec.campaign, CoverageFacts(2, spec.coverage.task_types, ()))


def test_report_spec_rejects_empty_title() -> None:
    spec = report_spec()
    with pytest.raises(ValueError, match="title cannot be empty"):
        ReportSpec(" ", spec.campaign, spec.coverage)


def test_html_report_is_self_contained_and_measured() -> None:
    report = render_html(report_spec())
    assert report.startswith("<!doctype html>")
    assert "Task success</th><td>1.000000" in report
    assert "Config: <code>sha256:" in report
    assert "http://" not in report and "https://" not in report


def test_html_report_escapes_hostile_user_content() -> None:
    report = render_html(report_spec('<script>alert("x")</script>'))
    assert "<script>" not in report
    assert "&lt;script&gt;" in report
    assert "alert(&quot;x&quot;)" in report


def test_html_report_has_one_complete_document() -> None:
    report = render_html(report_spec())
    assert report.count("<!doctype html>") == 1
    assert report.count("<html") == report.count("</html>") == 1
    assert report.endswith("</body></html>\n")


def test_bar_chart_scales_against_observed_maximum() -> None:
    chart = bar_chart_svg("Latency stages", (("decision", 50.0), ("tool", 100.0)))
    assert '<rect x="140" y="44" width="180.0"' in chart
    assert '<rect x="140" y="74" width="360.0"' in chart
    assert "50.000" in chart and "100.000" in chart


def test_bar_chart_escapes_labels_and_title() -> None:
    chart = bar_chart_svg("<latency>", (("tool<script>", 1.0),))
    assert "<script>" not in chart
    assert "&lt;latency&gt;" in chart
    assert "tool&lt;script&gt;" in chart


def test_bar_chart_validates_empty_and_nonfinite_data() -> None:
    with pytest.raises(ValueError, match="title cannot be empty"):
        bar_chart_svg(" ", (("value", 1.0),))
    with pytest.raises(ValueError, match="at least one"):
        bar_chart_svg("values", ())
    with pytest.raises(ValueError, match="finite and non-negative"):
        bar_chart_svg("values", (("bad", float("nan")),))
    with pytest.raises(ValueError, match="finite and non-negative"):
        bar_chart_svg("values", (("bad", -1.0),))


def test_zero_bar_chart_has_finite_geometry() -> None:
    chart = bar_chart_svg("zero", (("none", 0.0),))
    assert 'width="0.0"' in chart
    assert "nan" not in chart.lower()


def test_curve_chart_maps_normalized_points_deterministically() -> None:
    chart = curve_chart_svg("Success", ((0.0, 0.0), (0.5, 0.5), (1.0, 1.0)))
    assert 'points="40.0,220.0 280.0,130.0 520.0,40.0"' in chart
    assert "<title>Success</title>" in chart


def test_curve_chart_accepts_repeated_x_coordinates() -> None:
    chart = curve_chart_svg("Repair", ((0.0, 0.2), (0.0, 0.3)))
    assert 'points="40.0,184.0 40.0,166.0"' in chart


def test_curve_chart_rejects_unordered_or_unbounded_points() -> None:
    with pytest.raises(ValueError, match="ordered by x"):
        curve_chart_svg("bad", ((1.0, 0.5), (0.0, 0.5)))
    with pytest.raises(ValueError, match="bounded y"):
        curve_chart_svg("bad", ((0.0, 1.1),))
    with pytest.raises(ValueError, match="at least one point"):
        curve_chart_svg("bad", ())


def test_curve_chart_escapes_hostile_title() -> None:
    chart = curve_chart_svg("<curve>", ((0.0, 0.0),))
    assert "<curve>" not in chart
    assert "&lt;curve&gt;" in chart


def test_html_report_embeds_validated_inline_charts() -> None:
    chart = bar_chart_svg("Latency", (("tool", 10.0),))
    report = render_html(report_spec(), charts=(chart,))
    assert f"<figure>{chart}</figure>" in report
    assert report.count("<svg ") == 1


def test_html_report_rejects_arbitrary_chart_markup() -> None:
    with pytest.raises(ValueError, match="safe complete SVG"):
        render_html(report_spec(), charts=("<script>alert(1)</script>",))
    with pytest.raises(ValueError, match="safe complete SVG"):
        render_html(report_spec(), charts=("<svg><script>bad</script></svg>",))


def test_charted_html_is_byte_deterministic() -> None:
    charts = (
        bar_chart_svg("Latency", (("tool", 10.0),)),
        curve_chart_svg("Success", ((0.0, 0.5), (1.0, 1.0))),
    )
    first = render_html(report_spec(), charts=charts)
    second = render_html(report_spec(), charts=charts)
    assert first.encode() == second.encode()


def test_heat_table_encodes_normalized_slice_values() -> None:
    chart = heat_table_svg("Task slices", (("music", 0.0), ("schedule", 1.0)))
    assert "rgb(235,235,255)" in chart
    assert "rgb(85,85,255)" in chart
    assert "music" in chart and "1.000" in chart


def test_heat_table_escapes_labels_and_title() -> None:
    chart = heat_table_svg("<slices>", (("<music>", 0.5),))
    assert "<slices>" not in chart and "<music>" not in chart
    assert "&lt;slices&gt;" in chart and "&lt;music&gt;" in chart


def test_heat_table_rejects_invalid_cells() -> None:
    with pytest.raises(ValueError, match="title cannot be empty"):
        heat_table_svg(" ", (("slice", 0.5),))
    with pytest.raises(ValueError, match="at least one cell"):
        heat_table_svg("Slices", ())
    with pytest.raises(ValueError, match="between 0 and 1"):
        heat_table_svg("Slices", (("slice", 1.01),))
    with pytest.raises(ValueError, match="between 0 and 1"):
        heat_table_svg("Slices", (("", 0.5),))


def test_slice_markdown_reports_independently_scored_groups() -> None:
    base = report_spec().campaign.metrics
    run_a = EvaluationRun("a", "schedule", "easy", 0.0, {}, {}, (), (), True, 1, 0, 0, 1, 2)
    run_b = EvaluationRun("b", "music", "easy", 0.0, {}, {}, (), (), False, 1, 0, 0, 1, 2)
    slices = slice_campaign((run_a, run_b), SliceDimension.TASK_TYPE)
    table = render_slice_markdown(slices)
    assert "| music | 1 | 0.000000 |" in table
    assert "| schedule | 1 | 1.000000 |" in table
    assert base.run_count == 1


def test_slice_markdown_escapes_hostile_labels() -> None:
    item = EvaluationRun("a", "<script>|x", "easy", 0.0, {}, {}, (), (), True, 1, 0, 0, 1, 2)
    table = render_slice_markdown(slice_campaign((item,), SliceDimension.TASK_TYPE))
    assert "<script>" not in table
    assert "\\<script\\>\\|x" in table


def test_slice_markdown_rejects_no_slices() -> None:
    with pytest.raises(ValueError, match="at least one slice"):
        render_slice_markdown(())


def test_report_digest_tracks_exact_rendered_bytes() -> None:
    report = render_markdown(report_spec())
    assert report_digest(report) == report_digest(render_markdown(report_spec()))
    assert report_digest(report + "\n") != report_digest(report)


def test_report_digest_is_algorithm_qualified() -> None:
    digest = report_digest("offline report\n")
    assert digest.startswith("sha256:") and len(digest) == 71


def test_report_digest_rejects_empty_content() -> None:
    with pytest.raises(ValueError, match="nonempty content"):
        report_digest("")


def event(sequence: int, at_ms: int, kind: EventKind = EventKind.FINAL_TRANSCRIPT):
    return envelope_for(Identifier("session-1"), sequence, at_ms, kind, Transcript("hello", 1.0))


def test_session_summary_counts_ordered_event_kinds() -> None:
    summary = summarize_session(
        (event(0, 10), event(1, 25, EventKind.PARTIAL_TRANSCRIPT), event(2, 40))
    )
    assert (summary.session_id, summary.event_count, summary.duration_ms) == ("session-1", 3, 30)
    assert summary.kinds == (("final-transcript", 2), ("partial-transcript", 1))
