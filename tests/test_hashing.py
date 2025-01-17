"""Tests for digests and hash chains."""

from dataclasses import replace

from voxwright.hashing import (
    EMPTY_DIGEST,
    append_link,
    content_digest,
    object_digest,
    validate_chain,
    verify_digest,
)


def test_sha256_digest_has_explicit_algorithm() -> None:
    assert content_digest(b"") == EMPTY_DIGEST


def test_chain_links_payloads_in_order() -> None:
    first = append_link([], {"event": "start"})
    second = append_link([first], {"event": "finish"})
    assert second.index == 1
    assert second.previous == first.digest
    assert validate_chain([first, second]) is None


def test_modified_payload_breaks_chain_at_modified_link() -> None:
    first = append_link([], {"event": "start"})
    changed = replace(first, payload={"event": "stop"})
    assert validate_chain([changed]) == 0


def test_reordered_links_fail_at_first_position() -> None:
    first = append_link([], {"event": "first"})
    second = append_link([first], {"event": "second"})
    assert validate_chain([second, first]) == 0


def test_truncated_valid_prefix_remains_valid() -> None:
    first = append_link([], {"event": "first"})
    second = append_link([first], {"event": "second"})
    assert validate_chain([first, second]) is None
    assert validate_chain([first]) is None


def test_unknown_digest_algorithm_is_not_accepted() -> None:
    assert not verify_digest(b"voice", "md5:" + "0" * 32)


def test_object_digest_is_independent_of_mapping_order() -> None:
    assert object_digest({"b": 2, "a": 1}) == object_digest({"a": 1, "b": 2})
