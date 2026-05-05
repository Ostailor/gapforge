"""Robust campaign output importer with validation, partial acceptance, and rollback."""

from __future__ import annotations

import json
from pathlib import Path

from gapforge.campaigns import CampaignManager
from gapforge.campaigns.patch_apply import apply_campaign_patch_paths
from gapforge.campaigns.patch_validation import validate_campaign_patch
from gapforge.campaigns.rollback import create_campaign_snapshot
from gapforge.config import GapForgeConfig
from gapforge.models import AgentActualRunAttestation, CampaignImportRecord, Provenance
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
