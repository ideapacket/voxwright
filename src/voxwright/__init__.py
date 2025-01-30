"""Offline mechanics for deterministic spoken-language applications."""

from voxwright._version import __version__
from voxwright.events import EventEnvelope, EventKind, envelope_for

__all__ = ["EventEnvelope", "EventKind", "__version__", "envelope_for"]
