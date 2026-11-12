"""Fixture recording/loading for deterministic offline contract tests.

Fixtures are newline-delimited JSON (JSONL): each line is a
``{"call": ..., "result": ...}`` record produced by :class:`RecordingAdapter`.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def record_fixture(path: str | Path, name: str, records: list[dict[str, Any]]) -> Path:
    """Write a JSONL fixture file and return its path."""
    fixture_path = Path(path) / f"{name}.jsonl"
    fixture_path.parent.mkdir(parents=True, exist_ok=True)
    with fixture_path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, default=str) + "\n")
    return fixture_path


def load_fixture(path: str | Path, name: str) -> list[dict[str, Any]]:
    """Read a JSONL fixture file into a list of records."""
    fixture_path = Path(path) / f"{name}.jsonl"
    records: list[dict[str, Any]] = []
    with fixture_path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                records.append(json.loads(line))
    return records
