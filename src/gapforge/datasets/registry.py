"""Workspace-scoped dataset registry."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from gapforge.config import GapForgeConfig
from gapforge.datasets.cards import default_dataset_card, render_dataset_card_markdown, render_dataset_registry_markdown
from gapforge.datasets.validation import render_dataset_validation_markdown, validate_dataset_record
from gapforge.experiments.workspace import ExperimentWorkspaceManager
from gapforge.models import DatasetCard, DatasetRecord, DatasetValidationResult, Provenance, from_dict, to_plain
from gapforge.state import slugify, utc_now_iso


class DatasetRegistry:
    """Register, render, and validate datasets used by an experiment workspace."""

    def __init__(self, config: GapForgeConfig) -> None:
        self.config = config
        self.workspace_manager = ExperimentWorkspaceManager(config)

    def register_dataset(
        self,
        *,
        workspace_id: str,
        name: str,
        path: str | Path,
        dataset_type: str = "unknown",
        description: str = "",
        source: str = "",
        source_url: str = "",
        version: str = "",
        license: str = "",
        intended_use: str = "",
        limitations: list[str] | None = None,
        safety_notes: list[str] | None = None,
    ) -> DatasetRecord:
        workspace = self.workspace_manager.load_workspace(workspace_id)
        data_dir = Path(workspace.root_dir) / "data"
        data_dir.mkdir(parents=True, exist_ok=True)
        dataset_id = _unique_dataset_id(data_dir, name)
        resolved = Path(path).resolve()
        record = DatasetRecord(
            id=dataset_id,
            name=name,
            description=description,
            dataset_type=dataset_type,
            source=source,
            source_url=source_url,
            local_path=str(resolved),
            version=version,
            license=license,
            intended_use=intended_use,
            limitations=limitations or [],
            safety_notes=safety_notes or _default_safety_notes(dataset_type),
            provenance=Provenance(
                created_by_skill="dataset-registry",
                source_ids=[workspace_id, str(resolved)],
                timestamp=utc_now_iso(),
                reasoning_summary="Registered a dataset for experiment execution. Registration does not imply readiness.",
            ),
        )
        record.size_summary, record.schema_summary, record.split_names = _summarize_dataset(record)
        self._write_record(workspace_id, record)
        card = default_dataset_card(record)
        self._write_card(workspace_id, record, card)
        self._write_registry_markdown(workspace_id)
        return record

    def list_datasets(self, workspace_id: str) -> list[DatasetRecord]:
        data_dir = self._data_dir(workspace_id)
        if not data_dir.exists():
            return []
        return [
            from_dict(DatasetRecord, json.loads(path.read_text(encoding="utf-8")))
            for path in sorted(data_dir.glob("dataset-*.record.json"))
        ]

    def load_dataset(self, dataset_id: str) -> DatasetRecord:
        for project_dir in self.config.project_root.glob("*"):
            for path in (project_dir / "experiment_workspaces").glob("*/data/dataset-*.record.json"):
                record = from_dict(DatasetRecord, json.loads(path.read_text(encoding="utf-8")))
                if record.id == dataset_id:
                    return record
        raise FileNotFoundError(f"No dataset registered with id {dataset_id}")

    def render_card(self, dataset_id: str) -> str:
        record = self.load_dataset(dataset_id)
        card = self._load_or_create_card(record)
        return render_dataset_card_markdown(record, card)

    def validate_dataset(self, dataset_id: str) -> DatasetValidationResult:
        record = self.load_dataset(dataset_id)
        result = validate_dataset_record(record)
        workspace_id = _workspace_id_from_record(record)
        validation_dir = self._data_dir(workspace_id) / "validations"
        validation_dir.mkdir(parents=True, exist_ok=True)
        (validation_dir / f"{record.id}.validation.json").write_text(json.dumps(to_plain(result), indent=2) + "\n", encoding="utf-8")
        (validation_dir / f"{record.id}.validation.md").write_text(render_dataset_validation_markdown(result), encoding="utf-8")
        return result

    def update_local_path(self, dataset_id: str, local_path: str | Path) -> DatasetRecord:
        record = self.load_dataset(dataset_id)
        workspace_id = _workspace_id_from_record(record)
        record.local_path = str(Path(local_path).resolve())
        self._write_record(workspace_id, record)
        self._write_registry_markdown(workspace_id)
        return record

    def _write_record(self, workspace_id: str, record: DatasetRecord) -> None:
        path = self._data_dir(workspace_id) / f"{record.id}.record.json"
        path.write_text(json.dumps(to_plain(record), indent=2) + "\n", encoding="utf-8")

    def _write_card(self, workspace_id: str, record: DatasetRecord, card: DatasetCard) -> None:
        data_dir = self._data_dir(workspace_id)
        cards_dir = data_dir / "cards"
        cards_dir.mkdir(parents=True, exist_ok=True)
        (cards_dir / f"{record.id}.card.json").write_text(json.dumps(to_plain(card), indent=2) + "\n", encoding="utf-8")
        (cards_dir / f"{record.id}.card.md").write_text(render_dataset_card_markdown(record, card), encoding="utf-8")

    def _load_or_create_card(self, record: DatasetRecord) -> DatasetCard:
        workspace_id = _workspace_id_from_record(record)
        card_path = self._data_dir(workspace_id) / "cards" / f"{record.id}.card.json"
        if card_path.exists():
            return from_dict(DatasetCard, json.loads(card_path.read_text(encoding="utf-8")))
        card = default_dataset_card(record)
        self._write_card(workspace_id, record, card)
        return card

    def _write_registry_markdown(self, workspace_id: str) -> None:
        records = self.list_datasets(workspace_id)
        (self._data_dir(workspace_id) / "dataset_registry.md").write_text(render_dataset_registry_markdown(records), encoding="utf-8")

    def _data_dir(self, workspace_id: str) -> Path:
        workspace = self.workspace_manager.load_workspace(workspace_id)
        data_dir = Path(workspace.root_dir) / "data"
        data_dir.mkdir(parents=True, exist_ok=True)
        return data_dir


def _summarize_dataset(record: DatasetRecord) -> tuple[str, str, list[str]]:
    from gapforge.datasets.loaders import inspect_dataset_file

    path = Path(record.local_path)
    if not path.exists():
        return "missing local file", "unknown", []
    try:
        row_count, columns, rows = inspect_dataset_file(path)
    except Exception:
        return f"{path.stat().st_size} bytes", "unknown", []
    split_names = sorted({str(row.get("split", "")).strip() for row in rows if row.get("split", "")})
    return f"{row_count} rows, {len(columns)} columns", ", ".join(columns) or "no columns", split_names


def _unique_dataset_id(data_dir: Path, name: str) -> str:
    base = f"dataset-{slugify(name)}"
    digest = hashlib.sha1(name.encode("utf-8")).hexdigest()[:6]
    candidate = f"{base}-{digest}"
    suffix = 2
    while (data_dir / f"{candidate}.record.json").exists():
        candidate = f"{base}-{digest}-{suffix}"
        suffix += 1
    return candidate


def _workspace_id_from_record(record: DatasetRecord) -> str:
    return record.provenance.source_ids[0] if record.provenance.source_ids else ""


def _default_safety_notes(dataset_type: str) -> list[str]:
    if dataset_type == "real":
        return ["Real datasets should not be committed by default; audit license, privacy, and access constraints."]
    if dataset_type == "synthetic":
        return ["Synthetic data must stay clearly labeled and cannot support real-world empirical claims alone."]
    if dataset_type == "fixture":
        return ["Fixture data is for tests and workflow validation only."]
    return ["Dataset risk review is incomplete."]
