"""Deterministic fake AgentClient for CI and offline tests."""

from __future__ import annotations

import json
from pathlib import Path

from gapforge.agents.base import AgentRuntimeConfig
from gapforge.agents.records import append_run_record, append_validation_result, output_dir_for_task, utc_now_iso, write_task_pack
from gapforge.agents.schema_validator import TASK_OUTPUTS, expected_output_files
from gapforge.agents.validation import validate_agent_outputs
from gapforge.config import GapForgeConfig
from gapforge.models import AgentRunRecord, AgentTaskSpec, AgentValidationResult, Provenance, ResearchRunState, to_plain
from gapforge.state import ResearchStateManager, utc_now_compact


class FakeAgentClient:
    """Offline fake agent that writes deterministic, non-conclusive outputs."""

    def __init__(self, config: GapForgeConfig, runtime: AgentRuntimeConfig | None = None) -> None:
        self.config = config
        self.runtime = runtime or AgentRuntimeConfig(mode="fake", agent_name="fake-agent", codex_model="gapforge-fake-agent")
        self.state_manager = ResearchStateManager(config)

    def create_task_pack(self, state: ResearchRunState, task_spec: AgentTaskSpec) -> Path:
        return write_task_pack(state, task_spec)

    def run_task(self, task_spec: AgentTaskSpec) -> AgentRunRecord:
        state = self.state_manager.load_run(task_spec.run_id)
        pack_dir = self.create_task_pack(state, task_spec)
        outputs_dir = output_dir_for_task(state, task_spec)
        output_paths = _write_fake_outputs(task_spec, outputs_dir)
        validation = self.validate_outputs(task_spec, output_paths)
        append_validation_result(state, validation)
        record = AgentRunRecord(
            id=f"agent-run-{utc_now_compact()}-{task_spec.id}",
            agent_name="fake-agent",
            model="gapforge-fake-agent",
            task_spec_id=task_spec.id,
            run_id=task_spec.run_id,
            project_id=task_spec.project_id,
            status="complete" if validation.status == "valid" else "failed",
            started_at=utc_now_iso(),
            completed_at=utc_now_iso(),
            output_paths=[str(path) for path in output_paths],
            validation_result_id=validation.id,
            usage_summary={"mode": "fake", "task_pack": str(pack_dir)},
            provenance=Provenance(
                created_by_skill="fake-agent",
                source_ids=[task_spec.id],
                timestamp=utc_now_iso(),
                reasoning_summary="Deterministic fake agent produced safe non-conclusive output for CI.",
            ),
        )
        append_run_record(state, record)
        self.state_manager.save_run(state)
        return record

    def import_outputs(self, task_spec: AgentTaskSpec, output_paths: list[Path]) -> AgentValidationResult:
        state = self.state_manager.load_run(task_spec.run_id)
        validation = self.validate_outputs(task_spec, output_paths)
        append_validation_result(state, validation)
        record = AgentRunRecord(
            id=f"agent-import-{utc_now_compact()}-{task_spec.id}",
            agent_name="fake-agent",
            model="gapforge-fake-agent",
            task_spec_id=task_spec.id,
            run_id=task_spec.run_id,
            project_id=task_spec.project_id,
            status="imported" if validation.status == "valid" else "rejected",
            started_at=utc_now_iso(),
            completed_at=utc_now_iso(),
            output_paths=[str(path.expanduser().resolve()) for path in output_paths],
            validation_result_id=validation.id,
            error="; ".join(validation.issues) if validation.status != "valid" else "",
            usage_summary={"mode": "fake-import"},
            provenance=Provenance(
                created_by_skill="fake-agent-import",
                source_ids=[task_spec.id],
                timestamp=utc_now_iso(),
                reasoning_summary="Recorded validation-gated fake agent import metadata.",
            ),
        )
        append_run_record(state, record)
        self.state_manager.save_run(state)
        return validation

    def validate_outputs(self, task_spec: AgentTaskSpec, output_paths: list[Path]) -> AgentValidationResult:
        state = self.state_manager.load_run(task_spec.run_id)
        return validate_agent_outputs(state, task_spec, output_paths)


def _write_fake_outputs(task_spec: AgentTaskSpec, outputs_dir: Path) -> list[Path]:
    paths: list[Path] = []
    for filename in expected_output_files(task_spec):
        path = outputs_dir / filename
        if path.suffix.lower() == ".md":
            path.write_text("# Manuscript Outline\n\nFakeAgentClient did not generate manuscript claims.\n", encoding="utf-8")
        else:
            contract = TASK_OUTPUTS.get(task_spec.task_type, {}).get(filename, {})
            top_key = str(contract.get("top_key", "items"))
            path.write_text(json.dumps(_fake_payload(task_spec, top_key), indent=2) + "\n", encoding="utf-8")
        paths.append(path)
    return paths


def _fake_payload(task_spec: AgentTaskSpec, top_key: str) -> dict[str, object]:
    return {
        "task_spec_id": task_spec.id,
        "status": "non_conclusive",
        "confidence": "low",
        top_key: [],
        "missing_searches": ["fake agent performs no live research"],
        "evidence_locators": [],
        "public_reasoning_summary": "FakeAgentClient does not make research claims.",
        "task_spec": to_plain(task_spec),
    }
