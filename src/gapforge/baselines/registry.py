"""Workspace-scoped baseline registry."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from gapforge.baselines.cards import default_baseline_card, render_baseline_card_markdown, render_baseline_registry_markdown
from gapforge.baselines.selection import baseline_record_from_related_work
from gapforge.config import GapForgeConfig
from gapforge.experiments.workspace import ExperimentWorkspaceManager
from gapforge.models import BaselineCard, BaselineRecord, Provenance, RelatedWorkMatrix, from_dict, to_plain
from gapforge.project_memory import ProjectMemoryManager
from gapforge.related_work.matrix import RelatedWorkMatrixBuilder
from gapforge.state import slugify, utc_now_iso


class BaselineRegistry:
    """Register and select baselines for experiment workspaces."""

    def __init__(self, config: GapForgeConfig) -> None:
        self.config = config
        self.workspace_manager = ExperimentWorkspaceManager(config)
        self.project_manager = ProjectMemoryManager(config)

    def register_baseline(
        self,
        *,
        workspace_id: str,
        name: str,
        description: str = "",
        baseline_type: str = "unknown",
        source_paper_ids: list[str] | None = None,
        related_work_entry_ids: list[str] | None = None,
        code_available: bool = False,
        code_url: str = "",
        implementation_path: str = "",
        required_for_submission: bool = False,
        risk_if_missing: str = "",
        expected_inputs: list[str] | None = None,
        expected_outputs: list[str] | None = None,
    ) -> BaselineRecord:
        self.workspace_manager.load_workspace(workspace_id)
        record = BaselineRecord(
            id=_unique_baseline_id(self._baseline_dir(workspace_id), name),
            name=name,
            description=description,
            baseline_type=baseline_type,
            source_paper_ids=source_paper_ids or [],
            related_work_entry_ids=related_work_entry_ids or [],
            code_available=code_available,
            code_url=code_url,
            implementation_path=implementation_path,
            required_for_submission=required_for_submission,
            risk_if_missing=risk_if_missing,
            expected_inputs=expected_inputs or [],
            expected_outputs=expected_outputs or [],
            provenance=Provenance(
                created_by_skill="baseline-registry",
                source_ids=[workspace_id, *(source_paper_ids or [])],
                timestamp=utc_now_iso(),
                reasoning_summary="Registered an explicit experiment baseline.",
            ),
        )
        return self._persist_record(workspace_id, record)

    def from_related_work(self, *, project_id: str, direction_id: str) -> list[BaselineRecord]:
        program = self.project_manager.load_project(project_id)
        matrix = next((item for item in program.related_work_matrices if item.direction_id == direction_id), None)
        if matrix is None:
            matrix = RelatedWorkMatrixBuilder(self.config).build_for_project(project_id, direction_id)
            program = self.project_manager.load_project(project_id)
        workspace_ids = [item.id for item in program.experiment_workspaces if item.direction_id == direction_id]
        if not workspace_ids:
            workspace = self.workspace_manager.create_workspace(project_id=project_id, direction_id=direction_id)
            workspace_ids = [workspace.id]
        records = [
            _record
            for entry in _baseline_entries(matrix)
            for _record in [baseline_record_from_related_work(entry, corpus_papers=program.corpus_papers)]
        ]
        persisted: list[BaselineRecord] = []
        for workspace_id in workspace_ids:
            for record in records:
                persisted.append(self._persist_record(workspace_id, record))
            self._write_registry_markdown(workspace_id)
        return persisted

    def list_baselines(self, workspace_id: str) -> list[BaselineRecord]:
        baseline_dir = self._baseline_dir(workspace_id)
        if not baseline_dir.exists():
            return []
        return [
            from_dict(BaselineRecord, json.loads(path.read_text(encoding="utf-8")))
            for path in sorted(baseline_dir.glob("baseline-*.record.json"))
        ]

    def load_baseline(self, baseline_id: str) -> BaselineRecord:
        for project_dir in self.config.project_root.glob("*"):
            for path in (project_dir / "experiment_workspaces").glob("*/baselines/baseline-*.record.json"):
                record = from_dict(BaselineRecord, json.loads(path.read_text(encoding="utf-8")))
                if record.id == baseline_id:
                    return record
        raise FileNotFoundError(f"No baseline registered with id {baseline_id}")

    def render_card(self, baseline_id: str) -> str:
        record = self.load_baseline(baseline_id)
        card = self._load_or_create_card(record)
        return render_baseline_card_markdown(record, card)

    def readiness_blockers(self, workspace_id: str) -> list[str]:
        workspace = self.workspace_manager.load_workspace(workspace_id)
        records = self.list_baselines(workspace_id)
        blockers: list[str] = []
        if not records:
            blockers.append("No explicit baseline records are registered for this experiment workspace.")
        program = self.project_manager.load_project(workspace.project_id)
        matrix = _matrix_for_direction(program.related_work_matrices, workspace.direction_id)
        if matrix is not None:
            registered_paper_ids = {paper_id for record in records for paper_id in record.source_paper_ids}
            missing = [paper_id for paper_id in matrix.baseline_paper_ids if paper_id not in registered_paper_ids]
            blockers.extend(f"Required related-work baseline `{paper_id}` is not registered." for paper_id in missing)
        required = [record for record in records if record.required_for_submission]
        blockers.extend(
            f"Required baseline `{record.id}` has no implementation path or code URL yet."
            for record in required
            if not record.code_available and not record.code_url and not record.implementation_path
        )
        return blockers

    def _persist_record(self, workspace_id: str, record: BaselineRecord) -> BaselineRecord:
        baseline_dir = self._baseline_dir(workspace_id)
        existing = next(
            (
                item
                for item in self.list_baselines(workspace_id)
                if set(item.source_paper_ids) & set(record.source_paper_ids) or item.name.lower() == record.name.lower()
            ),
            None,
        )
        if existing is not None:
            record.id = existing.id
        (baseline_dir / f"{record.id}.record.json").write_text(json.dumps(to_plain(record), indent=2) + "\n", encoding="utf-8")
        card = default_baseline_card(record)
        self._write_card(workspace_id, record, card)
        self._write_registry_markdown(workspace_id)
        return record

    def _write_card(self, workspace_id: str, record: BaselineRecord, card: BaselineCard) -> None:
        cards_dir = self._baseline_dir(workspace_id) / "cards"
        cards_dir.mkdir(parents=True, exist_ok=True)
        (cards_dir / f"{record.id}.card.json").write_text(json.dumps(to_plain(card), indent=2) + "\n", encoding="utf-8")
        (cards_dir / f"{record.id}.card.md").write_text(render_baseline_card_markdown(record, card), encoding="utf-8")

    def _load_or_create_card(self, record: BaselineRecord) -> BaselineCard:
        workspace_id = _workspace_id_from_record(record)
        card_path = self._baseline_dir(workspace_id) / "cards" / f"{record.id}.card.json"
        if card_path.exists():
            return from_dict(BaselineCard, json.loads(card_path.read_text(encoding="utf-8")))
        card = default_baseline_card(record)
        self._write_card(workspace_id, record, card)
        return card

    def _write_registry_markdown(self, workspace_id: str) -> None:
        records = self.list_baselines(workspace_id)
        (self._baseline_dir(workspace_id) / "baseline_registry.md").write_text(render_baseline_registry_markdown(records), encoding="utf-8")

    def _baseline_dir(self, workspace_id: str) -> Path:
        workspace = self.workspace_manager.load_workspace(workspace_id)
        baseline_dir = Path(workspace.root_dir) / "baselines"
        baseline_dir.mkdir(parents=True, exist_ok=True)
        return baseline_dir


def _baseline_entries(matrix: RelatedWorkMatrix):
    return [entry for entry in matrix.entries if entry.baseline_candidate or entry.paper_id in matrix.baseline_paper_ids]


def _matrix_for_direction(matrices: list[RelatedWorkMatrix], direction_id: str) -> RelatedWorkMatrix | None:
    return next((item for item in matrices if item.direction_id == direction_id), None)


def _unique_baseline_id(baseline_dir: Path, name: str) -> str:
    base = f"baseline-{slugify(name)}"
    digest = hashlib.sha1(name.encode("utf-8")).hexdigest()[:6]
    candidate = f"{base}-{digest}"
    suffix = 2
    while (baseline_dir / f"{candidate}.record.json").exists():
        candidate = f"{base}-{digest}-{suffix}"
        suffix += 1
    return candidate


def _workspace_id_from_record(record: BaselineRecord) -> str:
    return record.provenance.source_ids[0] if record.provenance.source_ids else ""
