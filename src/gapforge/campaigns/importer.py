"""Robust campaign output importer with validation, partial acceptance, and rollback."""

from __future__ import annotations

import json
from pathlib import Path

from gapforge.campaigns import CampaignManager
from gapforge.campaigns.patch_apply import apply_campaign_patch_paths
from gapforge.campaigns.patch_validation import validate_campaign_patch
from gapforge.campaigns.rollback import create_campaign_snapshot
from gapforge.config import GapForgeConfig
from gapforge.models import AgentActualRunAttestation, CampaignImportRecord, Provenance, ResearchDirection
from gapforge.project_memory import ProjectMemoryManager
from gapforge.state import utc_now_iso


class CampaignOutputImporter:
    def __init__(self, config: GapForgeConfig) -> None:
        self.config = config
        self.manager = CampaignManager(config)

    def validate(self, campaign_id: str, task_id: str, paths: list[Path]) -> CampaignImportRecord:
        state = self.manager.load_campaign_state(campaign_id)
        record = validate_campaign_patch(self.config, state, task_id, paths)
        self._write_validation(campaign_id, task_id, record)
        return record

    def import_outputs(
        self,
        campaign_id: str,
        task_id: str,
        paths: list[Path],
        *,
        dry_run: bool = False,
        attestation: AgentActualRunAttestation | None = None,
    ) -> CampaignImportRecord:
        state = self.manager.load_campaign_state(campaign_id)
        record = validate_campaign_patch(self.config, state, task_id, paths)
        snapshot_path = create_campaign_snapshot(self.config, state, record.id)
        record.rollback_snapshot_path = str(snapshot_path)
        if dry_run:
            record.status = "partial" if record.accepted_objects and record.rejected_objects else record.status
            record.issues.append("Dry run: no campaign state was mutated.")
            self._write_validation(campaign_id, task_id, record)
            return record

        if record.accepted_objects:
            apply_campaign_patch_paths(state, record.id, record.accepted_objects)
            self._apply_project_synthesis_patches(state, record)
            record.status = "partial" if record.rejected_objects or record.issues else "applied"
        else:
            record.status = "rejected"

        if attestation is not None:
            record.accepted_objects.append(
                {
                    "type": "agent_actual_run_attestation",
                    "id": attestation.id,
                    "accepted": attestation.accepted_as_actual_run,
                }
            )

        step = _step_for_task(state, task_id)
        if step is not None:
            if record.status in {"applied", "valid"}:
                step.status = "complete"
            elif record.status == "partial":
                step.status = "blocked"
            else:
                step.status = "failed"
            step.completed_at = utc_now_iso()
            step.blocking_issues = record.issues
            step.output_artifacts = [item["source_path"] for item in record.accepted_objects if item.get("source_path")]

        record.created_at = record.created_at or utc_now_iso()
        record.provenance = Provenance(
            created_by_skill="campaign-importer",
            source_ids=[campaign_id, task_id],
            timestamp=utc_now_iso(),
            reasoning_summary="Validated campaign output patches, applied accepted portions, and recorded rollback snapshot.",
        )
        state.imports.append(record)
        self.manager.save_campaign_state(state)
        self._write_validation(campaign_id, task_id, record)
        if record.status == "rejected":
            self._write_failed_step_diagnostic(campaign_id, task_id)
        return record

    def _apply_project_synthesis_patches(self, state, record: CampaignImportRecord) -> None:  # noqa: ANN001
        files = {item["source_path"] for item in record.accepted_objects if item.get("type") == "file" and item.get("source_path")}
        direction_paths = [Path(path) for path in files if Path(path).name == "research_directions_patch.json"]
        if not direction_paths:
            return
        project_manager = ProjectMemoryManager(self.config)
        program = project_manager.load_project(state.campaign.project_id)
        existing = {direction.id for direction in program.research_directions}
        for path in direction_paths:
            payload = json.loads(path.read_text(encoding="utf-8"))
            for item in _items(payload.get("research_directions_patch")):
                direction_id = str(item.get("id") or item.get("direction_id") or "").strip()
                if not direction_id or direction_id in existing:
                    continue
                program.research_directions.append(
                    ResearchDirection(
                        id=direction_id,
                        project_id=program.project.id,
                        title=str(item.get("title") or direction_id),
                        summary=str(item.get("summary") or ""),
                        linked_gap_ids=[str(value) for value in item.get("linked_gap_ids", []) if value],
                        linked_hypothesis_ids=[str(value) for value in item.get("linked_hypothesis_ids", []) if value],
                        linked_experiment_ids=[str(value) for value in item.get("linked_experiment_ids", []) if value],
                        linked_novelty_dossier_ids=[str(value) for value in item.get("linked_novelty_dossier_ids", []) if value],
                        supporting_paper_ids=[str(value) for value in item.get("supporting_paper_ids", []) if value],
                        counterevidence_paper_ids=[str(value) for value in item.get("counterevidence_paper_ids", []) if value],
                        maturity=str(item.get("maturity") or "candidate"),
                        readiness_score=float(item.get("readiness_score") or 0.0),
                        blocking_issues=[str(value) for value in item.get("blocking_issues", []) if value],
                        next_actions=[str(value) for value in item.get("next_actions", []) if value],
                        provenance=Provenance(
                            created_by_skill="campaign-importer",
                            source_ids=[record.id, path.name],
                            timestamp=utc_now_iso(),
                            reasoning_summary="Imported validated Codex research synthesis direction.",
                        ),
                    )
                )
                existing.add(direction_id)
        project_manager.save_project(program)

    def list_imports(self, campaign_id: str) -> list[CampaignImportRecord]:
        return self.manager.load_campaign_state(campaign_id).imports

    def _write_validation(self, campaign_id: str, task_id: str, record: CampaignImportRecord) -> None:
        from gapforge.campaigns.task_packs import campaign_task_pack_dir

        validation_path = campaign_task_pack_dir(self.config, campaign_id, task_id) / "validation.json"
        validation_path.write_text(json.dumps(_record_payload(record), indent=2) + "\n", encoding="utf-8")

    def _write_failed_step_diagnostic(self, campaign_id: str, task_id: str) -> None:
        from gapforge.campaigns.import_workflow import _write_campaign_diagnostic

        _write_campaign_diagnostic(self.config, campaign_id, task_id)


def _record_payload(record: CampaignImportRecord) -> dict[str, object]:
    from gapforge.models import to_plain

    payload = to_plain(record)
    if record.status in {"valid", "applied"}:
        payload["status"] = "valid" if record.status == "valid" else "applied"
    return payload


def _step_for_task(state, task_id: str):  # noqa: ANN001,ANN201
    matches = [step for step in state.steps if step.task_spec_id == task_id]
    return matches[-1] if matches else None


def _items(value):  # noqa: ANN001,ANN201
    if isinstance(value, dict):
        return [value]
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    return []
