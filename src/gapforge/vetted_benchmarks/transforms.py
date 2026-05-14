"""Transparent transformations from vetted benchmark rows into trace-like units."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from gapforge.datasets.loaders import inspect_dataset_file
from gapforge.models import DatasetRecord
from gapforge.vetted_benchmarks.adapters import BenchmarkAdapter
from gapforge.vetted_benchmarks.sources import VettedBenchmarkRecord

TEXT_COLUMNS = ("trace", "trajectory", "conversation", "messages", "transcript", "prompt", "input", "question", "text", "content")
LABEL_COLUMNS = ("label", "labels", "target", "class", "y", "outcome")
SPLIT_COLUMNS = ("split", "partition", "fold")
COLLUSION_TERMS = ("collusion", "collusive", "covert coordination", "cartel")


def dataset_input_schema(dataset: DatasetRecord) -> dict[str, Any]:
    path = Path(dataset.local_path)
    schema: dict[str, Any] = {
        "dataset_id": dataset.id,
        "dataset_type": dataset.dataset_type,
        "local_path": dataset.local_path,
        "license": dataset.license,
        "split_names": dataset.split_names,
    }
    if path.exists():
        try:
            row_count, columns, _rows = inspect_dataset_file(path)
            schema.update({"row_count": row_count, "columns": columns, "format": path.suffix.lower().lstrip(".") or "unknown"})
        except Exception as exc:
            schema.update({"columns": [], "format": path.suffix.lower().lstrip(".") or "unknown", "inspection_error": str(exc)})
    return schema


def trace_like_output_schema() -> dict[str, Any]:
    return {
        "adapter_id": "string",
        "source_dataset_id": "string",
        "claim_guardrail": "string",
        "examples": [
            {
                "id": "string",
                "trace_like_unit": {
                    "steps": [{"round": "integer", "agent_id": "string", "message": "string", "action": "string"}],
                    "original_label": "source label value",
                    "original_split": "source split value",
                    "metadata": "source row metadata",
                },
                "original_label": "source label value",
                "original_split": "source split value",
            }
        ],
    }


def transform_dataset_to_trace_units(
    *,
    adapter: BenchmarkAdapter,
    dataset: DatasetRecord,
    vetted_benchmark: VettedBenchmarkRecord,
) -> tuple[dict[str, Any], list[str]]:
    path = Path(dataset.local_path)
    rows = _load_rows(path)
    warnings = _transformation_warnings(rows, vetted_benchmark)
    text_column = _first_present(rows, TEXT_COLUMNS)
    label_column = _first_present(rows, LABEL_COLUMNS)
    split_column = _first_present(rows, SPLIT_COLUMNS)
    examples = [
        _trace_like_example(
            adapter=adapter,
            dataset=dataset,
            row=row,
            row_index=index,
            text_column=text_column,
            label_column=label_column,
            split_column=split_column,
        )
        for index, row in enumerate(rows)
    ]
    manifest = {
        "adapter_id": adapter.id,
        "source_dataset_id": dataset.id,
        "vetted_benchmark_id": adapter.vetted_benchmark_id,
        "selected_benchmark_id": adapter.selected_benchmark_id,
        "claim_guardrail": (
            "Adapted examples are not real collusion traces unless the source benchmark explicitly contains real collusion traces."
        ),
        "transformation_description": adapter.transformation_description,
        "preserved_fields": {
            "label_column": label_column or "",
            "split_column": split_column or "",
            "original_labels_preserved": bool(label_column),
            "original_splits_preserved": bool(split_column),
        },
        "warnings": warnings,
        "examples": examples,
    }
    return manifest, warnings


def _trace_like_example(
    *,
    adapter: BenchmarkAdapter,
    dataset: DatasetRecord,
    row: dict[str, Any],
    row_index: int,
    text_column: str,
    label_column: str,
    split_column: str,
) -> dict[str, Any]:
    message = _message_from_row(row, text_column)
    original_label = row.get(label_column, "") if label_column else ""
    original_split = row.get(split_column, "") if split_column else ""
    return {
        "id": f"{adapter.id}:{dataset.id}:{row_index}",
        "trace_like_unit": {
            "steps": [
                {
                    "round": 0,
                    "agent_id": "vetted_benchmark_source",
                    "message": message,
                    "action": "",
                }
            ],
            "original_label": original_label,
            "original_split": original_split,
            "metadata": {
                "source_row_index": row_index,
                "source_dataset_id": dataset.id,
                "source_columns": sorted(str(key) for key in row),
                "original_row": row,
            },
        },
        "original_label": original_label,
        "original_split": original_split,
    }


def _transformation_warnings(rows: list[dict[str, Any]], vetted_benchmark: VettedBenchmarkRecord) -> list[str]:
    warnings: list[str] = []
    record_text = " ".join(
        [
            vetted_benchmark.name,
            vetted_benchmark.domain,
            vetted_benchmark.benchmark_type,
            " ".join(vetted_benchmark.task_types),
            " ".join(vetted_benchmark.limitations),
        ]
    ).lower()
    if not any(term in record_text for term in COLLUSION_TERMS):
        warnings.append("Adapted examples must not be described as real collusion traces; source benchmark is not collusion-labeled.")
    if not _first_present(rows, TEXT_COLUMNS):
        warnings.append("No trace, transcript, prompt, input, or text column was found; row serialization may destroy task meaning.")
    if not _first_present(rows, LABEL_COLUMNS):
        warnings.append("No standard label column was found; original labels cannot be preserved for monitor evaluation.")
    if not _first_present(rows, SPLIT_COLUMNS):
        warnings.append("No standard split column was found; original train/test splits cannot be preserved.")
    if not rows:
        warnings.append("Source dataset has no rows available for adapter conversion.")
    return warnings


def _load_rows(path: Path) -> list[dict[str, Any]]:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        with path.open(newline="", encoding="utf-8") as handle:
            return [dict(row) for row in csv.DictReader(handle)]
    if suffix == ".jsonl":
        rows = []
        with path.open(encoding="utf-8") as handle:
            for line in handle:
                if line.strip():
                    item = json.loads(line)
                    if not isinstance(item, dict):
                        raise ValueError("JSONL adapter source rows must be objects.")
                    rows.append(item)
        return rows
    if suffix == ".json":
        raw = json.loads(path.read_text(encoding="utf-8"))
        items = raw["rows"] if isinstance(raw, dict) and isinstance(raw.get("rows"), list) else raw
        if not isinstance(items, list):
            raise ValueError("JSON adapter source must be a list of objects or an object with a rows list.")
        if not all(isinstance(item, dict) for item in items):
            raise ValueError("JSON adapter source rows must be objects.")
        return list(items)
    raise ValueError(f"Unsupported adapter dataset format: {suffix or path.name}")


def _first_present(rows: list[dict[str, Any]], candidates: tuple[str, ...]) -> str:
    if not rows:
        return ""
    lower_to_original = {str(key).lower(): str(key) for row in rows[:20] for key in row}
    for candidate in candidates:
        if candidate in lower_to_original:
            return lower_to_original[candidate]
    return ""


def _message_from_row(row: dict[str, Any], text_column: str) -> str:
    if text_column:
        value = row.get(text_column, "")
        return value if isinstance(value, str) else json.dumps(value, sort_keys=True)
    return json.dumps(row, sort_keys=True)
