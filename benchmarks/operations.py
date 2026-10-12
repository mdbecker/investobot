"""Shared, dependency-free boundary for isolated real workload observations."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable


def noop() -> None:
    pass


@dataclass
class Prepared:
    operation: Callable[[], Any]
    verify: Callable[[Any], dict]
    counts: dict
    input_state_hash: str
    reset: Callable[[], None] = noop
    close: Callable[[], None] = noop
    storage_roots: tuple[Path, ...] = field(default_factory=tuple)
