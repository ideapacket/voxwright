"""Content digests and tamper-evident hash chains."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from voxwright.core import JSONValue, canonical_bytes

EMPTY_DIGEST = "sha256:" + hashlib.sha256(b"").hexdigest()


def content_digest(data: bytes) -> str:
    """Return an algorithm-qualified SHA-256 digest."""
    return "sha256:" + hashlib.sha256(data).hexdigest()


def object_digest(value: object) -> str:
    """Digest a strict JSON value in canonical form."""
    return content_digest(canonical_bytes(value))


def verify_digest(data: bytes, expected: str) -> bool:
    """Compare a digest without accepting unknown algorithm labels."""
    if not expected.startswith("sha256:") or len(expected) != 71:
        return False
    return content_digest(data) == expected


@dataclass(frozen=True, slots=True)
class ChainLink:
    """One item in a canonical payload hash chain."""

    index: int
    previous: str
    payload: JSONValue
    digest: str

    def unsigned(self) -> dict[str, JSONValue]:
        return {"index": self.index, "previous": self.previous, "payload": self.payload}


def append_link(links: list[ChainLink], payload: JSONValue) -> ChainLink:
    """Construct the next link without mutating the caller's list."""
    previous = links[-1].digest if links else EMPTY_DIGEST
    unsigned: dict[str, JSONValue] = {
        "index": len(links),
        "previous": previous,
        "payload": payload,
    }
    return ChainLink(len(links), previous, payload, object_digest(unsigned))


def validate_chain(links: list[ChainLink]) -> int | None:
    """Return the first invalid index, or ``None`` for a valid chain."""
    previous = EMPTY_DIGEST
    for index, link in enumerate(links):
        if link.index != index or link.previous != previous:
            return index
        if object_digest(link.unsigned()) != link.digest:
            return index
        previous = link.digest
    return None
