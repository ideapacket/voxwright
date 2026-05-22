from __future__ import annotations

import pytest

from voxwright.identifiers import Identifier
from voxwright.sandbox import PermissionDecision, PermissionPolicy, ToolSandbox
from voxwright.sandbox_audit import (
    AuditSummary,
    audit_to_dict,
    decode_audit,
    encode_audit,
    summarize_audit,
)


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
