"""Shared, dependency-free boundary for isolated real workload observations."""

import json
import os
import re
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable


def noop() -> None:
    pass


def retain_native(case_id, value):
    """Retain synthetic native results outside timing, including failed oracles."""
    destination = os.environ.get('INVEST_PERF_NATIVE_OUTPUT')
    if destination:
        root = Path(destination)
        root.mkdir(parents=True, exist_ok=True)
        (root / (case_id + '.json')).write_text(json.dumps(value, sort_keys=True, default=str))


def evidence(value):
    """Keep financial/source facts; label generated IDs and omit ingestion clocks."""
    identities = {}
    def walk(item):
        if isinstance(item, dict):
            return {key: walk(cell) for key, cell in sorted(item.items())
                    if key not in {'created_at', 'updated_at', 'recorded_at', 'imported_at',
                                   'retrieval_timestamp', 'retrieved_at', 'source_age_seconds'}}
        if isinstance(item, list):
            return [walk(cell) for cell in item]
        if isinstance(item, str) and re.fullmatch(r'[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}', item):
            return identities.setdefault(item, f'generated-identity-{len(identities)}')
        return item
    return walk(value)


@dataclass
class Prepared:
    operation: Callable[[], Any]
    verify: Callable[[Any], dict]
    counts: dict
    input_state_hash: str
    reset: Callable[[], None] = noop
    close: Callable[[], None] = noop
    storage_roots: tuple[Path, ...] = field(default_factory=tuple)
    connection: sqlite3.Connection | None = None
