"""Conservative v0.9 pilot runner."""

from __future__ import annotations

from pathlib import Path

from gapforge.campaigns import CampaignManager
from gapforge.config import GapForgeConfig
from gapforge.models import PilotRunRecord, PilotSpec, Provenance
from gapforge.pilots.reports import render_pilot_acceptance, render_pilot_report
from gapforge.pilots.specs import get_pilot_spec
from gapforge.pilots.status import PilotStore, build_acceptance_summary, classify_record, refresh_artifact_paths
from gapforge.project_memory import ProjectMemoryManager
from gapforge.search_strategy import plan_search_strategy, save_strategy
from gapforge.sources.live_diagnostics import run_live_source_diagnostic, write_live_source_diagnostic
from gapforge.state import utc_now_compact, utc_now_iso


class PilotRunner:
    def __init__(self, config: GapForgeConfig) -> None:
        self.config = config
        self.store = PilotStore(config)

    def run(self, name: str) -> PilotRunRecord:
        spec = get_pilot_spec(name)
        now = utc_now_iso()
        record = PilotRunRecord(
            id=f"pilot-{spec.id}-{utc_now_compact()}",
            pilot_id=spec.id,
            status="running",
            outcome_type="unknown",
            created_at=now,
            updated_at=now,
            provenance=Provenance(
                created_by_skill="pilot-runner",
                source_ids=[spec.id],
                timestamp=now,
                reasoning_summary="Started the v0.9 external pilot runner without assuming success.",
            ),
        )
        self.store.save_record(record)
        try:
            record = self._run_planned_flow(spec, record)
        except Exception as exc:  # pragma: no cover - exercised through product-failure fixture tests.
            record.status = "product_failure"
            record.outcome_type = "product_failure"
            record.blockers.append(f"product_failure: {type(exc).__name__}: {exc}")
        record = refresh_artifact_paths(self.config, spec, record)
        record = classify_record(record, spec)
        self.store.save_record(record)
        self.write_report(spec, record)
        return record

    def write_report(self, spec: PilotSpec, record: PilotRunRecord) -> Path:
        summary = build_acceptance_summary(record)
        self.store.save_acceptance(record, summary)
        record_dir = self.store.record_dir(record.id)
        report = render_pilot_report(spec, record, summary)
        acceptance = render_pilot_acceptance(summary)
        report_path = record_dir / "pilot_report.md"
        report_path.write_text(report, encoding="utf-8")
        (record_dir / "pilot_acceptance.md").write_text(acceptance, encoding="utf-8")
        if record.project_id:
            try:
                program = ProjectMemoryManager(self.config).load_project(record.project_id)
                project_report = Path(program.project.root_dir) / "reports" / "final_pilot_report.md"
                project_report.parent.mkdir(parents=True, exist_ok=True)
                project_report.write_text(report, encoding="utf-8")
                record.artifact_paths["final_pilot_report"] = str(project_report)
                self.store.save_record(record)
            except FileNotFoundError:
                pass
        return report_path

    def _run_planned_flow(self, spec: PilotSpec, record: PilotRunRecord) -> PilotRunRecord:
        project = ProjectMemoryManager(self.config).create_project(spec.project_name, description=spec.topic)
        record.project_id = project.project.id
        record.artifact_paths["project_record"] = str(Path(project.project.root_dir) / "project.json")
        campaign_state = CampaignManager(self.config).create_campaign(
            spec.topic,
            project_id=project.project.id,
            title="v0.9 external pilot: low-FPR collusion",
            mode="codex_task_pack",
            agent_name="codex",
            model="gpt-5.4",
            source_profile=spec.source_profile,
            budget_id="medium",
        )
        record.campaign_id = campaign_state.campaign.id
        campaign_dir = Path(project.project.root_dir) / "campaigns" / campaign_state.campaign.id
        record.artifact_paths["campaign_record"] = str(campaign_dir / "campaign.json")

        diagnostic = run_live_source_diagnostic(self.config, topic=spec.topic, source_profile=spec.source_profile)
        _, diagnostic_md = write_live_source_diagnostic(self.config, diagnostic)
        record.artifact_paths["live_source_diagnostics"] = diagnostic_md

        strategy = plan_search_strategy(self.config, spec.topic, source_profile=spec.source_profile)
        strategy_json, strategy_md = save_strategy(self.config, strategy)
        record.artifact_paths["search_strategy"] = str(strategy_json)
        record.artifact_paths["search_strategy_report"] = str(strategy_md)

        if not diagnostic.minimum_coverage_met:
            record.status = "refusal_ready"
            record.outcome_type = "correct_refusal"
            blockers = diagnostic.blocking_issues or ["Live source coverage gate did not pass."]
            record.blockers.extend(f"research_refusal: {blocker}" for blocker in blockers)
            CampaignManager(self.config).stop_campaign(campaign_state.campaign.id, reason="; ".join(blockers))
            return record

        record.blockers.append(
            "research_refusal: downstream novelty, prior-work, experiment, manuscript, and review gates are not complete"
        )
        return record
