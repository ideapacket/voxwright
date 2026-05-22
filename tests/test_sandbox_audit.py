from __future__ import annotations

from pathlib import Path

import pytest

from voxwright.identifiers import Identifier
from voxwright.sandbox import PermissionDecision, PermissionPolicy, ToolSandbox
from voxwright.sandbox_audit import (
    AuditSummary,
    audit_entries,
    audit_to_dict,
    decode_audit,
    encode_audit,
    load_audit,
    summarize_audit,
    write_audit,
)

GOLDEN = Path(__file__).parent / "golden" / "sandbox_audit.json"


def test_audit_summary_distinguishes_every_nonexecution_reason() -> None:
    allowed = Identifier("notes.add")
    confirmed = Identifier("messages.send")
    denied = Identifier("home.set-light")
    box = ToolSandbox(
        PermissionPolicy({allowed: PermissionDecision.ALLOW, confirmed: PermissionDecision.CONFIRM})
    )
    box.execute(allowed, {"text": "saved"})
    box.execute(allowed, {"text": "preview"}, dry_run=True)
    box.execute(confirmed, {"recipient": "fixture", "text": "blocked"})
    box.execute(denied, {"room": "study", "on": True})
    assert summarize_audit(box.ledger) == AuditSummary(4, 1, 1, 1, 1)


def test_audit_summary_rejects_tampered_chain() -> None:
    box = ToolSandbox(PermissionPolicy({}))
    box.execute("notes.add", {"text": "blocked"})
    box.ledger.links[0] = box.ledger.links[0].__class__(
        0, box.ledger.links[0].previous, box.ledger.links[0].payload, "sha256:" + "0" * 64
    )
    with pytest.raises(ValueError, match="invalid at index 0"):
        summarize_audit(box.ledger)
    with pytest.raises(ValueError, match="cannot encode invalid"):
        encode_audit(box.ledger)


def test_audit_encoding_preserves_chain_order_and_canonical_bytes() -> None:
    box = ToolSandbox(PermissionPolicy({}))
    box.execute("notes.add", {"text": "blocked"})
    encoded = audit_to_dict(box.ledger)
    assert encoded["schema_version"] == 1
    assert encoded["links"][0]["index"] == 0  # type: ignore[index]
    text = encode_audit(box.ledger)
    assert text.endswith("\n") and " " not in text
    decoded = decode_audit(text)
    assert decoded.links == box.ledger.links
    assert encode_audit(decoded).encode() == text.encode()


def test_audit_decoder_rejects_unknown_versions_and_fields() -> None:
    box = ToolSandbox(PermissionPolicy({}))
    encoded = audit_to_dict(box.ledger)
    encoded["schema_version"] = 2
    with pytest.raises(ValueError, match="unsupported version 2"):
        decode_audit(__import__("json").dumps(encoded))
    encoded = audit_to_dict(box.ledger)
    encoded["unexpected"] = True
    with pytest.raises(ValueError, match="exact sandbox audit fields"):
        decode_audit(__import__("json").dumps(encoded))


def test_audit_decoder_rejects_index_and_payload_shape_drift() -> None:
    box = ToolSandbox(PermissionPolicy({}))
    box.execute("notes.add", {"text": "blocked"})
    encoded = audit_to_dict(box.ledger)
    encoded["links"][0]["index"] = 4  # type: ignore[index]
    with pytest.raises(ValueError, match="expected 0"):
        decode_audit(__import__("json").dumps(encoded))
    encoded = audit_to_dict(box.ledger)
    encoded["links"][0]["payload"].pop("executed")  # type: ignore[index,union-attr]
    with pytest.raises(ValueError, match="exact side-effect fields"):
        decode_audit(__import__("json").dumps(encoded))


def test_audit_decoder_rejects_chain_tampering() -> None:
    box = ToolSandbox(PermissionPolicy({}))
    box.execute("notes.add", {"text": "blocked"})
    encoded = audit_to_dict(box.ledger)
    encoded["links"][0]["digest"] = "sha256:" + "0" * 64  # type: ignore[index]
    with pytest.raises(ValueError, match="chain is invalid at index 0"):
        decode_audit(__import__("json").dumps(encoded))


def test_sandbox_audit_matches_reviewed_golden_bytes() -> None:
    box = ToolSandbox(PermissionPolicy({}))
    box.execute("notes.add", {"text": "blocked"})
    assert encode_audit(box.ledger).encode() == GOLDEN.read_bytes()
    assert decode_audit(GOLDEN.read_text(encoding="utf-8")).links == box.ledger.links


def test_sandbox_audit_files_roundtrip_without_clobbering(tmp_path: Path) -> None:
    box = ToolSandbox(PermissionPolicy({}))
    box.execute("notes.add", {"text": "blocked"})
    path = tmp_path / "audit.json"
    write_audit(path, box.ledger)
    assert load_audit(path).links == box.ledger.links
    with pytest.raises(FileExistsError, match="output already exists"):
        write_audit(path, box.ledger.__class__())


def test_sandbox_audit_loader_detects_truncation(tmp_path: Path) -> None:
    path = tmp_path / "audit.json"
    path.write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="missing terminal newline"):
        load_audit(path)


def test_audit_entry_selection_preserves_verified_ledger_order() -> None:
    allowed = Identifier("notes.add")
    box = ToolSandbox(PermissionPolicy({allowed: PermissionDecision.ALLOW}))
    box.execute(allowed, {"text": "one"})
    box.execute("music.play", {"track": "blocked"})
    box.execute(allowed, {"text": "two"})
    notes = audit_entries(box.ledger, tool_name=allowed)
    assert [item["arguments"] for item in notes] == [{"text": "one"}, {"text": "two"}]
    blocked = audit_entries(box.ledger, executed=False)
    assert [item["tool_name"] for item in blocked] == ["music.play"]


def test_audit_entry_selection_returns_copies_and_rejects_tampering() -> None:
    box = ToolSandbox(PermissionPolicy({}))
    box.execute("notes.add", {"text": "blocked"})
    selected = audit_entries(box.ledger)
    selected[0]["tool_name"] = "changed"
    assert box.ledger.links[0].payload["tool_name"] == "notes.add"  # type: ignore[index]
    box.ledger.links[0] = box.ledger.links[0].__class__(
        0,
        box.ledger.links[0].previous,
        box.ledger.links[0].payload,
        "sha256:" + "0" * 64,
    )
    with pytest.raises(ValueError, match="chain is invalid"):
        audit_entries(box.ledger)
