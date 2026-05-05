"""v0.4 campaign canary runner."""

from __future__ import annotations

import json
import os
from pathlib import Path

from gapforge.campaigns import CampaignManager
from gapforge.campaigns.controller import CampaignController
from gapforge.canaries.campaign_profiles import (
    default_campaign_canary_profiles,
    get_campaign_canary_profile,
    render_campaign_canary_plan,
)
from gapforge.config import GapForgeConfig
from gapforge.models import (
    CampaignCanaryProfile,
    CampaignCanaryRecord,
    Gap,
    GapEvidenceMatrix,
    NoveltyDossier,
    Paper,
    PaperNote,
    PaperSection,
    Provenance,
    SourceCoverageReport,
    from_dict,
    to_plain,
)
from gapforge.project_memory import ProjectMemoryManager
from gapforge.retrieval import build_project_index
from gapforge.state import ResearchStateManager, slugify, utc_now_compact, utc_now_iso


class CampaignCanaryRunManager:
    """Run and persist campaign-level canaries."""

    def __init__(self, config: GapForgeConfig) -> None:
        self.config = config
        self.config.ensure_dirs()
        self.root = self.config.data_dir / "campaign_canaries"
        self.root.mkdir(parents=True, exist_ok=True)

    def list_profiles(self) -> list[CampaignCanaryProfile]:
        return default_campaign_canary_profiles()

    def plan(self, profile_id: str) -> str:
        return render_campaign_canary_plan(get_campaign_canary_profile(profile_id))

    def run(self, profile_id: str, *, real: bool = False) -> CampaignCanaryRecord:
        profile = get_campaign_canary_profile(profile_id)
        if profile.requires_codex and not real:
            return self._failed(profile, "Real campaign canary requires --real because it depends on Codex/GPT-5.4.")
        if profile.requires_codex and os.environ.get("GAPFORGE_ENABLE_REAL_RUNS", "0") not in {"1", "true", "TRUE", "yes"}:
            return self._failed(profile, "GAPFORGE_ENABLE_REAL_RUNS=1 is required for real Codex/GPT-5.4 campaign canaries.")
        if profile.requires_local_pdf and not real:
            return self._failed(profile, "Manual PDF campaign canary requires --real and a local PDF workflow.")
        if profile.id == "fake_agent_campaign_regression":
            return self._run_fake_campaign(profile)
        if profile.id == "agentic_undercovered_refusal":
            return self._run_undercovered_refusal(profile)
        return self._plan_real_campaign(profile)

    def load_record(self, canary_id: str) -> CampaignCanaryRecord:
        path = self._record_path(canary_id)
        if not path.exists():
            raise FileNotFoundError(f"No campaign canary record found for {canary_id}")
        return from_dict(CampaignCanaryRecord, json.loads(path.read_text(encoding="utf-8")))

    def save_record(self, record: CampaignCanaryRecord, profile: CampaignCanaryProfile | None = None) -> Path:
        record_dir = self._record_dir(record.id)
        record_dir.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(to_plain(record), indent=2) + "\n"
        (record_dir / "record.json").write_text(payload, encoding="utf-8")
        (record_dir / "campaign_canary_record.json").write_text(payload, encoding="utf-8")
        if profile is not None:
            (record_dir / "plan.md").write_text(render_campaign_canary_plan(profile), encoding="utf-8")
        return record_dir / "record.json"

    def _run_fake_campaign(self, profile: CampaignCanaryProfile) -> CampaignCanaryRecord:
        project, campaign_id = self._create_seeded_campaign(profile, mode="fake_agent", novelty_verdict="unknown")
        campaign_state = CampaignController(self.config).run(campaign_id, mode="fake_agent", max_iterations=1)
        record = self._record_from_campaign(profile, campaign_state.campaign.id, project.project.id)
        record.status = "complete" if campaign_state.imports else "failed"
        record.accepted = record.status == "complete"
        record.actual_run_status = "fake_not_actual"
        record.human_review_status = "not_required"
        if record.status != "complete":
            record.failure_reason = "Fake campaign did not create a validated import."
        self.save_record(record, profile)
        return record

    def _run_undercovered_refusal(self, profile: CampaignCanaryProfile) -> CampaignCanaryRecord:
        project_manager = ProjectMemoryManager(self.config)
        project = project_manager.create_project(f"canary {profile.id}")
        campaign_state = CampaignManager(self.config).create_campaign(
            profile.topic,
            project_id=project.project.id,
            mode=profile.campaign_mode,
            source_profile=profile.source_profile,
            budget_id=profile.budget,
        )
        campaign_state = CampaignController(self.config).run(campaign_state.campaign.id, mode=profile.campaign_mode, max_iterations=2)
        record = self._record_from_campaign(profile, campaign_state.campaign.id, project.project.id)
        refused = bool(campaign_state.stop_conditions) and not _has_ready_direction(project_manager.load_project(project.project.id))
        record.status = "complete" if refused else "failed"
        record.accepted = refused
        record.actual_run_status = "not_applicable"
        record.human_review_status = "not_required"
        record.failure_reason = "" if refused else "Undercovered refusal did not stop without a ready direction."
        self.save_record(record, profile)
        return record

    def _plan_real_campaign(self, profile: CampaignCanaryProfile) -> CampaignCanaryRecord:
        project_manager = ProjectMemoryManager(self.config)
        project = project_manager.create_project(f"canary {profile.id}")
        campaign_state = CampaignManager(self.config).create_campaign(
            profile.topic,
            project_id=project.project.id,
            mode=profile.campaign_mode,
            agent_name=profile.agent_name,
            model=profile.model,
            source_profile=profile.source_profile,
            budget_id=profile.budget,
        )
        campaign_state = CampaignController(self.config).run(campaign_state.campaign.id, mode=profile.campaign_mode, max_iterations=1)
        record = self._record_from_campaign(profile, campaign_state.campaign.id, project.project.id)
        record.status = "planned" if campaign_state.campaign.status == "paused" else "complete"
        record.actual_run_status = "awaiting_attestation_and_human_review"
        record.human_review_status = "required"
        record.accepted = False
        self.save_record(record, profile)
        return record

    def _create_seeded_campaign(self, profile: CampaignCanaryProfile, *, mode: str, novelty_verdict: str):
        project_manager = ProjectMemoryManager(self.config)
        state_manager = ResearchStateManager(self.config)
        project = project_manager.create_project(f"canary {profile.id}")
        run = state_manager.create_run(profile.topic)
        run.papers.append(
            Paper(
                id="paper-1",
                title="Synthetic Campaign Canary Paper",
                authors=["GapForge Fixture"],
                abstract="Synthetic fixture for campaign controller regression.",
                year=2026,
                source="fixture",
            )
        )
        run.paper_sections.append(
            PaperSection(
                id="section-1",
                paper_id="paper-1",
                title="Abstract",
                section_type="abstract",
                text="Synthetic full-text section for campaign canary evidence.",
            )
        )
        run.paper_notes.append(PaperNote(paper_id="paper-1", one_sentence_summary="Synthetic campaign note.", confidence="medium"))
        run.gaps.append(
            Gap(
                id="gap-1",
                description="Synthetic campaign gap requiring novelty review.",
                supporting_paper_ids=["paper-1"],
                risk_that_gap_is_fake="High; fixture only.",
                confidence="medium",
            )
        )
        run.gap_evidence_matrices.append(GapEvidenceMatrix(gap_id="gap-1", papers_supporting=["paper-1"], confidence="medium"))
        run.novelty_dossiers.append(
            NoveltyDossier(
                target_id="gap-1",
                idea_summary="Synthetic novelty state.",
                verdict=novelty_verdict,
                novelty_strength="unknown" if novelty_verdict == "unknown" else "medium",
                confidence="low",
            )
        )
        run.source_coverage = SourceCoverageReport(
            run_id=run.run_id,
            topic=run.topic.text,
            searched_sources=["fixture"],
            papers_by_source={"fixture": 1},
            papers_with_full_text=["paper-1"],
            confidence="medium",
        )
        state_manager.save_run(run)
        project_manager.attach_run(project.project.id, run.run_id)
        program = project_manager.sync_project_memory(project.project.id)
        build_project_index(program)
        campaign = CampaignManager(self.config).create_campaign(
            profile.topic,
            project_id=project.project.id,
            mode=mode,
            source_profile=profile.source_profile,
            budget_id=profile.budget,
        )
        CampaignManager(self.config).attach_run(campaign.campaign.id, run.run_id)
        return project, campaign.campaign.id

    def _record_from_campaign(self, profile: CampaignCanaryProfile, campaign_id: str, project_id: str) -> CampaignCanaryRecord:
        state = CampaignManager(self.config).load_campaign_state(campaign_id)
        campaign_dir = self.config.project_root / project_id / "campaigns" / campaign_id
        artifacts = _artifact_paths(campaign_dir)
        return CampaignCanaryRecord(
            id=f"campaign-canary-{profile.id}-{utc_now_compact()}",
            profile_id=profile.id,
            campaign_id=campaign_id,
            project_id=project_id,
            status=state.campaign.status,
            milestones_reached=[milestone.milestone_type for milestone in state.milestones],
            artifacts=artifacts,
            actual_run_status="not_completed",
            human_review_status="required" if profile.requires_codex else "not_required",
            accepted=False,
            provenance=Provenance(
                created_by_skill="campaign-canary-runner",
                source_ids=[profile.id, campaign_id, project_id],
                timestamp=utc_now_iso(),
                reasoning_summary="Campaign canary executed through v0.4 campaign controller.",
            ),
        )

    def _failed(self, profile: CampaignCanaryProfile, reason: str) -> CampaignCanaryRecord:
        record = CampaignCanaryRecord(
            id=f"campaign-canary-{profile.id}-{utc_now_compact()}",
            profile_id=profile.id,
            status="failed",
            actual_run_status="not_completed",
            human_review_status="not_started",
            accepted=False,
            failure_reason=reason,
            provenance=Provenance(
                created_by_skill="campaign-canary-runner",
                source_ids=[profile.id],
                timestamp=utc_now_iso(),
                reasoning_summary="Campaign canary refused to run because required actual-run conditions were not met.",
            ),
        )
        self.save_record(record, profile)
        return record

    def _record_dir(self, canary_id: str) -> Path:
        return self.root / slugify(canary_id)

    def _record_path(self, canary_id: str) -> Path:
        return self._record_dir(canary_id) / "record.json"


def _artifact_paths(campaign_dir: Path) -> list[str]:
    if not campaign_dir.exists():
        return []
    names = [
        "campaign.json",
        "steps.json",
        "decisions.json",
        "milestones.json",
        "imports.json",
        "campaign_report.md",
    ]
    paths = [str(campaign_dir / name) for name in names if (campaign_dir / name).exists()]
    paths.extend(str(path) for path in (campaign_dir / "agent_tasks").glob("*/CAMPAIGN_TASK.md") if path.exists())
    return sorted(set(paths))


def _has_ready_direction(program) -> bool:  # noqa: ANN001
    return any(direction.maturity in {"experiment_ready", "manuscript_ready"} for direction in program.research_directions)
