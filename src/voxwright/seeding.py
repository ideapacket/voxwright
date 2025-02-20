"""Small hash-derived streams for reproducible synthetic choices."""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from dataclasses import dataclass
from typing import TypeVar

T = TypeVar("T")


@dataclass(slots=True)
class SeedStream:
    """A deterministic choice stream independent of global random state."""

    seed: int
    namespace: str = "voxwright"
    counter: int = 0

    def __post_init__(self) -> None:
        if isinstance(self.seed, bool) or self.seed < 0:
            raise ValueError("seed must be a non-negative integer")
        if not self.namespace:
            raise ValueError("seed namespace cannot be empty")
        if self.counter < 0:
            raise ValueError("seed counter cannot be negative")

    def next_int(self) -> int:
        """Return the next unsigned 64-bit value in this named stream."""
        material = f"{self.namespace}:{self.seed}:{self.counter}".encode()
        self.counter += 1
        return int.from_bytes(hashlib.sha256(material).digest()[:8], "big")

    def choose(self, values: Sequence[T]) -> T:
        """Choose an item without mutating the input sequence."""
        if not values:
            raise ValueError("cannot choose from an empty sequence")
        return values[self.next_int() % len(values)]

    def chance(self, probability: float) -> bool:
        """Make a quantized probability decision with stable integer arithmetic."""
        if not 0.0 <= probability <= 1.0:
            raise ValueError("probability must be between 0 and 1")
        threshold = round(probability * 1_000_000)
        return self.next_int() % 1_000_000 < threshold

    def shuffled(self, values: Sequence[T]) -> list[T]:
        """Return a deterministically shuffled copy using Fisher-Yates swaps."""
        result = list(values)
        for index in range(len(result) - 1, 0, -1):
            swap = self.next_int() % (index + 1)
            result[index], result[swap] = result[swap], result[index]
        return result
