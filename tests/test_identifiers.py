"""Tests for public identifiers."""

from voxwright.identifiers import Identifier, derived_identifier


def test_identifier_preserves_valid_value() -> None:
    assert str(Identifier("session.voice-2")) == "session.voice-2"


def test_derived_identifier_is_seeded() -> None:
    assert derived_identifier("scenario", 7) == derived_identifier("scenario", 7)
    assert derived_identifier("scenario", 7) != derived_identifier("scenario", 8)
