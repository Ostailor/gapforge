"""Dataset validation for experiment workspaces."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from gapforge.datasets.loaders import inspect_dataset_file
from gapforge.models import DatasetRecord, DatasetValidationResult, Provenance
from gapforge.state import utc_now_iso


def validate_dataset_record(record: DatasetRecord) -> DatasetValidationResult:
    issues: list[str] = []
    leakage_warnings: list[str] = []
    row_count = 0
    columns: list[str] = []
    sampled_rows: list[dict[str, Any]] = []
    path = Path(record.local_path) if record.local_path else None

    if record.dataset_type in {"fixture", "synthetic"}:
        issues.append(f"Dataset is labeled `{record.dataset_type}`; reports must not present it as real-world evidence.")
    if record.dataset_type == "unknown":
        issues.append("Dataset type is unknown.")
    if not record.license:
        issues.append("Dataset license is unknown.")
    if path is None:
        issues.append("Dataset local path is missing.")
    elif not path.exists():
        issues.append(f"Dataset local path does not exist: {path}")
    else:
        try:
            row_count, columns, sampled_rows = inspect_dataset_file(path)
        except Exception as exc:
            issues.append(str(exc))

    missing_summary = _missing_values_summary(sampled_rows, columns)
    split_integrity = _split_integrity(sampled_rows)
    if "split" not in {column.lower() for column in columns} and row_count > 0:
        leakage_warnings.append("No `split` column found; train/test leakage risk must be reviewed.")
    if split_integrity.startswith("warning"):
        leakage_warnings.append(split_integrity)

    status = _status(issues, leakage_warnings)
    return DatasetValidationResult(
        dataset_id=record.id,
        status=status,
        issues=issues,
        row_count=row_count,
        column_count=len(columns),
        missing_values_summary=missing_summary,
        split_integrity=split_integrity,
        leakage_warnings=leakage_warnings,
        provenance=Provenance(
            created_by_skill="dataset-validation",
            source_ids=[record.id],
            timestamp=utc_now_iso(),
            reasoning_summary="Validated dataset metadata and lightweight local file structure.",
        ),
    )


def render_dataset_validation_markdown(result: DatasetValidationResult) -> str:
    lines = [
        f"# Dataset Validation `{result.dataset_id}`",
        "",
        f"- Status: `{result.status}`",
        f"- Rows: {result.row_count}",
        f"- Columns: {result.column_count}",
        f"- Split integrity: {result.split_integrity or 'not checked'}",
        "",
        "## Issues",
        "",
    ]
    lines.extend([f"- {item}" for item in result.issues] or ["- none"])
    lines.extend(["", "## Leakage Warnings", ""])
    lines.extend([f"- {item}" for item in result.leakage_warnings] or ["- none"])
    lines.extend(["", "## Missing Values", ""])
    lines.extend([f"- `{key}`: {value}" for key, value in result.missing_values_summary.items()] or ["- none"])
    return "\n".join(lines).rstrip() + "\n"


def _missing_values_summary(rows: list[dict[str, Any]], columns: list[str]) -> dict[str, int]:
    summary = {column: 0 for column in columns}
    for row in rows:
        for column in columns:
            value = row.get(column)
            if value is None or value == "":
                summary[column] += 1
    return {key: value for key, value in summary.items() if value}


def _split_integrity(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "not checked"
    split_values = {str(row.get("split", "")).strip().lower() for row in rows if row.get("split", "")}
    if not split_values:
        return "warning: no split values found"
    if len(split_values) == 1:
        return f"warning: only one split present ({next(iter(split_values))})"
    return f"ok: {', '.join(sorted(split_values))}"


def _status(issues: list[str], leakage_warnings: list[str]) -> str:
    invalid_markers = ["does not exist", "Unsupported dataset format", "must be objects", "missing"]
    if any(any(marker in issue for marker in invalid_markers) for issue in issues):
        return "invalid"
    if issues or leakage_warnings:
        return "warning"
    return "valid"
