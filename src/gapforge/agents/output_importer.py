"""Validation-gated import of Codex agent patch outputs."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from gapforge.agents.records import append_run_record, append_validation_result, task_pack_dir, utc_now_iso
from gapforge.agents.schema_validator import expected_output_files, validate_task_outputs
from gapforge.config import GapForgeConfig
from gapforge.models import (
    AgentRunRecord,
    AgentTaskSpec,
    AgentValidationResult,
    Claim,
    EvidenceSpan,
    Gap,
    GapEvidenceMatrix,
    NoveltyAssessment,
    NoveltyDossier,
    PaperNote,
    Provenance,
    RejectedIdea,
    RelatedWorkMatrix,
    ResearchRunState,
    ReviewerObjection,
    ReviewerSimulationSummary,
    from_dict,
    to_plain,
)
from gapforge.state import ResearchStateManager, utc_now_compact


class AgentOutputImporter:
    def __init__(self, config: GapForgeConfig, *, agent_name: str = "codex", model: str = "gpt-5.4") -> None:
        self.config = config
        self.agent_name = agent_name
        self.model = model
        self.state_manager = ResearchStateManager(config)

    def validate(self, task_spec: AgentTaskSpec, output_paths: list[Path] | None = None) -> AgentValidationResult:
        state = self.state_manager.load_run(task_spec.run_id)
        validation = validate_task_outputs(state, task_spec, output_paths)
        _write_validation(task_spec, state, validation)
        return validation

    def import_outputs(self, task_spec: AgentTaskSpec, output_paths: list[Path] | None = None) -> AgentValidationResult:
        state = self.state_manager.load_run(task_spec.run_id)
        before = state.to_dict()
        validation = validate_task_outputs(state, task_spec, output_paths)
        append_validation_result(state, validation)
        if validation.status == "valid":
            _apply_patches(state, task_spec, validation.accepted_output_paths)
        record = AgentRunRecord(
            id=f"agent-import-{utc_now_compact()}-{task_spec.id}",
            agent_name=self.agent_name,
            model=self.model,
            task_spec_id=task_spec.id,
            run_id=task_spec.run_id,
            project_id=task_spec.project_id,
            status="imported" if validation.status == "valid" else "rejected",
            started_at=utc_now_iso(),
            completed_at=utc_now_iso(),
            output_paths=validation.accepted_output_paths if validation.status == "valid" else validation.rejected_output_paths,
            validation_result_id=validation.id,
            error="; ".join(validation.issues) if validation.status != "valid" else "",
            usage_summary={
                "validated_import": validation.status == "valid",
                "mutated_state": validation.status == "valid",
                "state_changed": before != state.to_dict(),
            },
            provenance=Provenance(
                created_by_skill="agent-output-importer",
                source_ids=[task_spec.id],
                timestamp=utc_now_iso(),
                reasoning_summary="Imported agent patch outputs only after strict validation passed.",
            ),
        )
        append_run_record(state, record)
        _write_validation(task_spec, state, validation)
        self.state_manager.save_run(state)
        return validation


def output_paths_for_task(state: ResearchRunState, task_spec: AgentTaskSpec) -> list[Path]:
    output_dir = task_pack_dir(state, task_spec) / "outputs"
    return [output_dir / filename for filename in expected_output_files(task_spec)]


def _apply_patches(state: ResearchRunState, task_spec: AgentTaskSpec, accepted_paths: list[str]) -> None:
    for raw_path in accepted_paths:
        path = Path(raw_path)
        if path.suffix.lower() != ".json" or not path.exists():
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        if task_spec.task_type == "deep_reading":
            _merge_list(state.paper_notes, _items(payload, "paper_notes", PaperNote), key="paper_id")
            _merge_list(state.claims, _items(payload, "claims", Claim), key="id")
            _merge_list(state.evidence_spans, _items(payload, "evidence_spans", EvidenceSpan), key="id")
        elif task_spec.task_type == "gap_mining":
            _merge_list(state.gaps, _items(payload, "gaps", Gap), key="id")
            _merge_list(state.gap_evidence_matrices, _items(payload, "gap_evidence_matrices", GapEvidenceMatrix), key="gap_id")
            _merge_list(state.claims, _items(payload, "claims", Claim), key="id")
        elif task_spec.task_type == "novelty":
            _merge_list(state.novelty_dossiers, _items(payload, "novelty_dossiers", NoveltyDossier), key="target_id")
            _merge_list(
                state.novelty_assessments, _items(payload, "novelty_assessments", NoveltyAssessment), key="target_gap_or_hypothesis_id"
            )
            _merge_list(state.rejected_ideas, _items(payload, "rejected_ideas", RejectedIdea), key="id")
        elif task_spec.task_type == "reviewer":
            _merge_list(state.reviewer_objections, _items(payload, "reviewer_objections", ReviewerObjection), key="id")
            _merge_list(state.reviewer_summaries, _items(payload, "reviewer_summaries", ReviewerSimulationSummary), key="experiment_id")
        elif task_spec.task_type == "related_work":
            _merge_list(state.related_work_matrices, _items(payload, "related_work_matrices", RelatedWorkMatrix), key="direction_id")


def _items(payload: dict[str, Any], key: str, model: type[Any]) -> list[Any]:
    return [from_dict(model, item) for item in payload.get(key, []) if isinstance(item, dict)]


def _merge_list(existing: list[Any], incoming: list[Any], *, key: str) -> None:
    positions = {getattr(item, key): index for index, item in enumerate(existing)}
    for item in incoming:
        item_key = getattr(item, key)
        if item_key in positions:
            existing[positions[item_key]] = item
        else:
            positions[item_key] = len(existing)
            existing.append(item)


def _write_validation(task_spec: AgentTaskSpec, state: ResearchRunState, validation: AgentValidationResult) -> None:
    path = task_pack_dir(state, task_spec) / "validation.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(to_plain(validation), indent=2) + "\n", encoding="utf-8")
