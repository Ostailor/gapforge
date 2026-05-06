"""Lightweight tabular dataset loaders for validation."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any


def inspect_dataset_file(path: Path) -> tuple[int, list[str], list[dict[str, Any]]]:
    """Return row count, column names, and sampled rows for CSV/JSON/JSONL datasets."""

    suffix = path.suffix.lower()
    if suffix == ".csv":
        return _inspect_csv(path)
    if suffix == ".jsonl":
        return _inspect_jsonl(path)
    if suffix == ".json":
        return _inspect_json(path)
    raise ValueError(f"Unsupported dataset format for lightweight validation: {suffix or path.name}")


def _inspect_csv(path: Path) -> tuple[int, list[str], list[dict[str, Any]]]:
    rows: list[dict[str, Any]] = []
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        columns = list(reader.fieldnames or [])
        count = 0
        for row in reader:
            count += 1
            if len(rows) < 100:
                rows.append(dict(row))
    return count, columns, rows


def _inspect_jsonl(path: Path) -> tuple[int, list[str], list[dict[str, Any]]]:
    rows: list[dict[str, Any]] = []
    columns: set[str] = set()
    count = 0
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            item = json.loads(line)
            if not isinstance(item, dict):
                raise ValueError("JSONL dataset rows must be objects.")
            count += 1
            columns.update(str(key) for key in item)
            if len(rows) < 100:
                rows.append(item)
    return count, sorted(columns), rows


def _inspect_json(path: Path) -> tuple[int, list[str], list[dict[str, Any]]]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(raw, dict) and isinstance(raw.get("rows"), list):
        items = raw["rows"]
    elif isinstance(raw, list):
        items = raw
    else:
        raise ValueError("JSON dataset must be a list of objects or an object with a rows list.")
    rows: list[dict[str, Any]] = []
    columns: set[str] = set()
    for item in items:
        if not isinstance(item, dict):
            raise ValueError("JSON dataset rows must be objects.")
        columns.update(str(key) for key in item)
        if len(rows) < 100:
            rows.append(item)
    return len(items), sorted(columns), rows
