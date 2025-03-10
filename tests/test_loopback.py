"""Tests for bounded local loopback adapter mechanics."""

from __future__ import annotations

from collections.abc import Iterator

import pytest

import voxwright.loopback as loopback
from voxwright.events import EventEnvelope, EventKind
from voxwright.identifiers import Identifier


def event() -> EventEnvelope:
    return EventEnvelope(Identifier("session-1"), 0, 0, EventKind.FINAL_TRANSCRIPT, {"text": "hi"})


def transport_from(responses: list[loopback.LoopbackResponse]) -> loopback.LoopbackTransport:
    iterator: Iterator[loopback.LoopbackResponse] = iter(responses)

    def transport(request: dict[str, object], timeout_ms: int) -> loopback.LoopbackResponse:
        assert request["schema_version"] == 1
        assert timeout_ms == 25
        return next(iterator)

    return transport  # type: ignore[return-value]


def test_loopback_returns_successful_local_response() -> None:
    adapter = loopback.LoopbackAdapter(
        transport_from([loopback.LoopbackResponse(200, (event(),))]), timeout_ms=25
    )
    adapter.observe([event()])
    assert adapter.act().events == (event(),)
    assert adapter.attempts == 1


def test_loopback_validates_bounded_config() -> None:
    with pytest.raises(ValueError, match="must be positive"):
        loopback.LoopbackAdapter(
            lambda request, timeout: loopback.LoopbackResponse(200), timeout_ms=0
        )
