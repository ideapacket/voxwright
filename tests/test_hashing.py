"""Tests for digests and hash chains."""

from voxwright.hashing import EMPTY_DIGEST, append_link, content_digest, validate_chain


def test_sha256_digest_has_explicit_algorithm() -> None:
    assert content_digest(b"") == EMPTY_DIGEST


def test_chain_links_payloads_in_order() -> None:
    first = append_link([], {"event": "start"})
    second = append_link([first], {"event": "finish"})
    assert second.index == 1
    assert second.previous == first.digest
    assert validate_chain([first, second]) is None
