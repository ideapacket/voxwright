"""Tests for synthetic scenario manifests."""

from __future__ import annotations

import json

import pytest

import voxwright.manifests as manifests
import voxwright.scenarios as scenarios


def campaign() -> list[scenarios.SyntheticScenario]:
    return [
        scenarios.schedule_scenario(1),
        scenarios.application_scenario(scenarios.TaskType.MUSIC, 2),
        scenarios.adversarial_scenario(3),
    ]


def test_manifest_roundtrips_complete_scenario_truth(tmp_path: object) -> None:
    path = tmp_path / "campaign.jsonl"  # type: ignore[operator]
    manifests.write_manifest(path, campaign())
    assert manifests.read_manifest(path) == campaign()


def test_manifest_bytes_replay_for_same_campaign() -> None:
    assert manifests.encode_manifest(campaign()) == manifests.encode_manifest(campaign())
    assert manifests.encode_manifest(campaign()).count("\n") == 3


def test_manifest_checksum_detects_transcript_tampering(tmp_path: object) -> None:
    path = tmp_path / "campaign.jsonl"  # type: ignore[operator]
    entry = json.loads(manifests.encode_manifest(campaign()[:1]))
    entry["scenario"]["transcript"] = "tampered"
    path.write_text(json.dumps(entry) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="checksum mismatch"):
        manifests.read_manifest(path)


def test_manifest_rejects_truncated_last_line(tmp_path: object) -> None:
    path = tmp_path / "campaign.jsonl"  # type: ignore[operator]
    path.write_text(manifests.encode_manifest(campaign()).rstrip(), encoding="utf-8")
    with pytest.raises(ValueError, match="incomplete line"):
        manifests.read_manifest(path)


def test_manifest_entry_has_golden_top_level_contract() -> None:
    entry = manifests.manifest_entry(scenarios.schedule_scenario(7))
    assert list(entry) == ["schema_version", "scenario", "checksum"]
    assert entry["schema_version"] == 1
    assert str(entry["checksum"]).startswith("sha256:")
    assert set(entry["scenario"]) == {
        "scenario_id",
        "seed",
        "persona",
        "transcript",
        "goals",
        "difficulty",
        "noise_rate",
        "adversarial",
    }


def test_manifest_line_order_matches_input_campaign(tmp_path: object) -> None:
    path = tmp_path / "campaign.jsonl"  # type: ignore[operator]
    expected = campaign()
    manifests.write_manifest(path, expected)
    actual = manifests.read_manifest(path)
    assert [item.scenario_id for item in actual] == [item.scenario_id for item in expected]


def test_empty_manifest_is_a_valid_empty_campaign(tmp_path: object) -> None:
    path = tmp_path / "empty.jsonl"  # type: ignore[operator]
    manifests.write_manifest(path, [])
    assert path.read_bytes() == b""
    assert manifests.read_manifest(path) == []


def test_manifest_decoder_rejects_invalid_nested_shapes() -> None:
    value = manifests.scenario_to_dict(scenarios.schedule_scenario(1))
    persona = value["persona"]
    assert isinstance(persona, dict)
    persona["quirks"] = "not-an-array"
    with pytest.raises(ValueError, match="quirks must be an array"):
        manifests._scenario_from_dict(value)

    value = manifests.scenario_to_dict(scenarios.schedule_scenario(1))
    goals = value["goals"]
    assert isinstance(goals, list) and isinstance(goals[0], dict)
    goals[0]["slots"] = []
    with pytest.raises(ValueError, match="invalid shapes"):
        manifests._scenario_from_dict(value)
