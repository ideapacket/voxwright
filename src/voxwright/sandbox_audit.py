"""Validation and persistence helpers for sandbox side-effect evidence."""

from __future__ import annotations

from dataclasses import dataclass

from voxwright.core import JSONValue, canonical_json
from voxwright.hashing import ChainLink
from voxwright.sandbox import SideEffectLedger


@dataclass(frozen=True, slots=True)
class AuditSummary:
    total: int
    executed: int
    denied: int
    confirmation_required: int
    dry_runs: int


def summarize_audit(ledger: SideEffectLedger) -> AuditSummary:
    """Count verified audit dispositions without inferring execution from tool output."""
    invalid = ledger.validate()
    if invalid is not None:
        raise ValueError(f"side-effect ledger chain is invalid at index {invalid}")
    executed = denied = confirmation_required = dry_runs = 0
    for index, link in enumerate(ledger.links):
        payload = link.payload
        if not isinstance(payload, dict) or not isinstance(payload.get("executed"), bool):
            raise ValueError(f"side-effect ledger payload is invalid at index {index}")
        result = payload.get("result")
        if payload["executed"]:
            executed += 1
        elif result == "denied":
            denied += 1
        elif result == "confirmation-required":
            confirmation_required += 1
        elif isinstance(result, dict) and result.get("dry_run") is True:
            dry_runs += 1
    return AuditSummary(len(ledger.links), executed, denied, confirmation_required, dry_runs)


def _link_to_dict(link: ChainLink) -> dict[str, JSONValue]:
    return {
        "index": link.index,
        "previous": link.previous,
        "payload": link.payload,
        "digest": link.digest,
    }


def audit_to_dict(ledger: SideEffectLedger) -> dict[str, JSONValue]:
    """Encode a ledger only when its complete chain is intact."""
    invalid = ledger.validate()
    if invalid is not None:
        raise ValueError(f"cannot encode invalid side-effect ledger at index {invalid}")
    return {"schema_version": 1, "links": [_link_to_dict(link) for link in ledger.links]}


def encode_audit(ledger: SideEffectLedger) -> str:
    return canonical_json(audit_to_dict(ledger)) + "\n"
