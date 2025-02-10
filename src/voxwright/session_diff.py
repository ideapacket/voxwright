"""Event-by-event comparison of deterministic session replay traces."""

from __future__ import annotations

from dataclasses import dataclass

from voxwright.core import JSONValue
from voxwright.replay import ReplayTrace


@dataclass(frozen=True, slots=True)
class EventDifference:
    """The first differing top-level field for one event position."""

    index: int
    field: str
    left: JSONValue
    right: JSONValue


_FIELDS = ("schema_version", "session_id", "sequence", "at_ms", "kind", "payload")


def diff_traces(left: ReplayTrace, right: ReplayTrace) -> list[EventDifference]:
    """Compare traces in event order, including missing tail events."""
    differences: list[EventDifference] = []
    size = max(len(left.events), len(right.events))
    for index in range(size):
        if index >= len(left.events):
            differences.append(EventDifference(index, "event", None, right.events[index].to_dict()))
            continue
        if index >= len(right.events):
            differences.append(EventDifference(index, "event", left.events[index].to_dict(), None))
            continue
        left_event = left.events[index].to_dict()
        right_event = right.events[index].to_dict()
        for field in _FIELDS:
            if left_event[field] != right_event[field]:
                differences.append(
                    EventDifference(index, field, left_event[field], right_event[field])
                )
                break
    return differences
