"""Canary run management and execution."""

from __future__ import annotations

import json
import os
from pathlib import Path

from gapforge.agents import AgentRuntimeConfig, FakeAgentClient, create_agent_task_spec
from gapforge.canaries.planner import render_canary_plan
from gapforge.canaries.profiles import default_canary_profiles, get_canary_profile
from gapforge.canaries.review_checklist import render_review_checklist
from gapforge.config import GapForgeConfig
from gapforge.models import CanaryRunProfile, CanaryRunRecord, Provenance, to_plain
from gapforge.state import ResearchStateManager, utc_now_compact, utc_now_iso


class CanaryRunManager:
    def __init__(self, config: GapForgeConfig) -> None:
        self.config = config
        self.config.ensure_dirs()
        self.root = self.config.data_dir / "canaries"
        self.root.mkdir(parents=True, exist_ok=True)

    def list_profiles(self) -> list[CanaryRunProfile]:
        return default_canary_profiles()

    def plan(self, profile_id: str) -> str:
        return render_canary_plan(get_canary_profile(profile_id))

    def run(self, profile_id: str, *, real: bool = False) -> CanaryRunRecord:
        profile = get_canary_profile(profile_id)
        if profile.requires_codex and not real:
            record = self._new_record(profile, status="failed")
            record.validation_summary = {
                "reason": "Real Codex/GPT-5.4 canary requires --real and GAPFORGE_ENABLE_REAL_RUNS=1.",
                "counts_as_actual_run": False,
            }
            self.save_record(record, profile)
            return record
        if profile.requires_codex and os.environ.get("GAPFORGE_ENABLE_REAL_RUNS", "0") not in {"1", "true", "TRUE", "yes"}:
            record = self._new_record(profile, status="failed")
            record.validation_summary = {
                "reason": "GAPFORGE_ENABLE_REAL_RUNS=1 is required for real Codex/GPT-5.4 canaries.",
                "counts_as_actual_run": False,
            }
            self.save_record(record, profile)
            return record
        if profile.id == "fake_agent_regression":
            return self._run_fake_agent_regression(profile)
        record = self._new_record(profile, status="planned" if real else "failed")
        record.validation_summary = {
            "reason": "Profile is represented as a repeatable plan; direct real-agent execution is not automated here.",
            "counts_as_actual_run": False,
            "manual_private_workflow_required": True,
        }
        self.save_record(record, profile)
        return record

    def load_record(self, canary_id: str) -> CanaryRunRecord:
        path = self._record_path(canary_id)
        if not path.exists():
            raise FileNotFoundError(f"No canary record found for {canary_id}")
        from gapforge.models import from_dict

        return from_dict(CanaryRunRecord, json.loads(path.read_text(encoding="utf-8")))

    def artifact_paths(self, canary_id: str) -> list[str]:
        record = self.load_record(canary_id)
        paths = list(record.artifact_paths)
        record_dir = self._record_dir(canary_id)
        paths.extend(
            str(path)
            for path in [
                record_dir / "record.json",
                record_dir / "canary_record.json",
                record_dir / "human_review.json",
                record_dir / "acceptance_summary.json",
                record_dir / "review_report.md",
                record_dir / "plan.md",
                record_dir / "review_checklist.md",
            ]
            if path.exists()
        )
        return sorted(set(paths))

    def save_record(self, record: CanaryRunRecord, profile: CanaryRunProfile | None = None) -> Path:
        record_dir = self._record_dir(record.id)
        record_dir.mkdir(parents=True, exist_ok=True)
        profile = profile or get_canary_profile(record.profile_id)
        payload = json.dumps(to_plain(record), indent=2) + "\n"
        (record_dir / "record.json").write_text(payload, encoding="utf-8")
        (record_dir / "canary_record.json").write_text(payload, encoding="utf-8")
        (record_dir / "plan.md").write_text(render_canary_plan(profile), encoding="utf-8")
        (record_dir / "review_checklist.md").write_text(render_review_checklist(profile, record), encoding="utf-8")
        return record_dir / "record.json"

    def _run_fake_agent_regression(self, profile: CanaryRunProfile) -> CanaryRunRecord:
        record = self._new_record(profile, status="running")
        manager = ResearchStateManager(self.config)
        state = manager.create_run(profile.topic)
        task = create_agent_task_spec(state, skill_name="novelty-gate", instructions="Run the fake AgentClient regression canary.")
        state.agent_task_specs.append(task)
        manager.save_run(state)
        run_record = FakeAgentClient(self.config, AgentRuntimeConfig(mode="fake")).run_task(task)
        state = manager.load_run(state.run_id)
        validation = state.agent_validation_results[-1] if state.agent_validation_results else None
        record.run_id = state.run_id
        record.status = (
            "complete" if validation is not None and validation.status == "valid" and run_record.status == "complete" else "failed"
        )
        record.command_log = [
            f'gapforge init-topic "{profile.topic}"',
            f"gapforge codex-task --run-id {state.run_id} --skill novelty-gate",
            f"gapforge agent-run --task-id {task.id} --fake",
        ]
        record.artifact_paths = [
            state.run_dir,
            str(Path(state.run_dir) / "agent_tasks.md"),
            str(Path(state.run_dir) / "agent_tasks" / task.id / "TASK.md"),
            str(Path(state.run_dir) / "agent_tasks" / task.id / "validation.json"),
        ]
        record.validation_summary = {
            "fake_agent_status": run_record.status,
            "validation_status": validation.status if validation is not None else "missing",
            "counts_as_actual_run": False,
            "pass_criteria_met": record.status == "complete",
        }
        record.completed_at = utc_now_iso()
        record.provenance.reasoning_summary = "Fake canary executed offline through AgentClient task-pack validation."
        self.save_record(record, profile)
        return record

    def _new_record(self, profile: CanaryRunProfile, *, status: str) -> CanaryRunRecord:
        now = utc_now_iso()
        return CanaryRunRecord(
            id=f"canary-{profile.id}-{utc_now_compact()}",
            profile_id=profile.id,
            status=status,
            started_at=now,
            completed_at=now if status in {"failed", "planned"} else "",
            provenance=Provenance(
                created_by_skill="canary-runner",
                source_ids=[profile.id],
                timestamp=now,
                reasoning_summary="Canary run record created from a built-in v0.3 validation profile.",
            ),
        )

    def _record_dir(self, canary_id: str) -> Path:
        return self.root / canary_id

    def _record_path(self, canary_id: str) -> Path:
        return self._record_dir(canary_id) / "record.json"
