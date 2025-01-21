"""Validated and reproducible identifiers for public artifacts."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

_IDENTIFIER = re.compile(r"^[a-z][a-z0-9]*(?:[._-][a-z0-9]+)*$")


@dataclass(frozen=True, order=True, slots=True)
class Identifier:
    """A compact lowercase identifier safe in JSON and filenames."""

    value: str

    def __post_init__(self) -> None:
        if len(self.value) > 64:
            raise ValueError("identifier exceeds 64 characters")
        if not _IDENTIFIER.fullmatch(self.value):
            raise ValueError(f"invalid identifier: {self.value!r}")

    def __str__(self) -> str:
        return self.value


def derived_identifier(namespace: str, seed: int) -> Identifier:
    """Derive a stable identifier from a validated namespace and integer seed."""
    prefix = Identifier(namespace).value
    if seed < 0:
        raise ValueError("seed cannot be negative")
    suffix = hashlib.blake2s(f"{prefix}:{seed}".encode(), digest_size=6).hexdigest()
    return Identifier(f"{prefix}-{suffix}")
