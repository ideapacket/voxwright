"""Validation and persistence helpers for sandbox side-effect evidence."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from voxwright.core import JSONValue, canonical_json, parse_json
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


AUDIT_FIELDS = frozenset({"schema_version", "links"})
LINK_FIELDS = frozenset({"index", "previous", "payload", "digest"})
PAYLOAD_FIELDS = frozenset({"tool_name", "arguments", "executed", "result"})


def _decode_link(value: JSONValue, expected_index: int) -> ChainLink:
    path = f"$.links[{expected_index}]"
    if not isinstance(value, dict) or set(value) != LINK_FIELDS:
        raise ValueError(f"{path}: expected exact audit link fields")
    index = value["index"]
    previous = value["previous"]
    payload = value["payload"]
    digest = value["digest"]
    if isinstance(index, bool) or not isinstance(index, int) or index != expected_index:
        raise ValueError(f"{path}.index: expected {expected_index}")
    if not isinstance(previous, str) or not isinstance(digest, str):
        raise TypeError(f"{path}: previous and digest must be strings")
    if not isinstance(payload, dict) or set(payload) != PAYLOAD_FIELDS:
        raise ValueError(f"{path}.payload: expected exact side-effect fields")
    if not isinstance(payload["tool_name"], str):
        raise TypeError(f"{path}.payload.tool_name: expected string")
    if not isinstance(payload["arguments"], dict):
        raise TypeError(f"{path}.payload.arguments: expected object")
    if not isinstance(payload["executed"], bool):
        raise TypeError(f"{path}.payload.executed: expected boolean")
    return ChainLink(index, previous, payload, digest)


def audit_from_dict(value: JSONValue) -> SideEffectLedger:
    if not isinstance(value, dict) or set(value) != AUDIT_FIELDS:
        raise ValueError("$: expected exact sandbox audit fields")
    if value["schema_version"] != 1 or isinstance(value["schema_version"], bool):
        raise ValueError(f"$.schema_version: unsupported version {value['schema_version']!r}")
    links = value["links"]
    if not isinstance(links, list):
        raise TypeError("$.links: expected array")
    ledger = SideEffectLedger()
    ledger.links = [_decode_link(item, index) for index, item in enumerate(links)]
    invalid = ledger.validate()
    if invalid is not None:
        raise ValueError(f"side-effect ledger chain is invalid at index {invalid}")
    return ledger


def decode_audit(text: str) -> SideEffectLedger:
    if not text.strip():
        raise ValueError("sandbox audit document is empty")
    return audit_from_dict(parse_json(text))


def load_audit(path: Path) -> SideEffectLedger:
    text = path.read_text(encoding="utf-8")
    if text and not text.endswith("\n"):
        raise ValueError(f"sandbox audit file is missing terminal newline: {path}")
    return decode_audit(text)


def write_audit(path: Path, ledger: SideEffectLedger) -> None:
    try:
        with path.open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(encode_audit(ledger))
    except FileExistsError as error:
        raise FileExistsError(f"sandbox audit output already exists: {path}") from error
