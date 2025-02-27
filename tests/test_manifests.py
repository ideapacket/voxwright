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
