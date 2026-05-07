"""v0.4 campaign canary runner."""

from __future__ import annotations

import json
import os
from pathlib import Path

from gapforge.campaigns import CampaignManager
from gapforge.campaigns.acceptance import (
    campaign_task_attestation_status,
    create_campaign_actual_run_attestation,
)
from gapforge.campaigns.controller import CampaignController
from gapforge.campaigns.importer import CampaignOutputImporter
from gapforge.campaigns.task_packs import create_campaign_task_pack
from gapforge.canaries.campaign_profiles import (
    default_campaign_canary_profiles,
    get_campaign_canary_profile,
    render_campaign_canary_plan,
)
from gapforge.config import GapForgeConfig
from gapforge.models import (
    CampaignCanaryProfile,
    CampaignCanaryRecord,
    EvidenceSpan,
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

_SINGLE_TASK_COMPLETION_PROFILES = {
    "single_task_codex_handoff",
    "single_task_fake_handoff_regression",
    "manual_pdf_codex_reading_handoff",
    "manual_pdf_fake_reading_regression",
}
_REAL_SINGLE_TASK_PROFILES = {
    "single_task_codex_handoff",
    "manual_pdf_codex_reading_handoff",
}


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
        if profile.id == "manual_pdf_fake_reading_regression":
            return self._run_manual_pdf_fake_reading(profile)
        if profile.id == "manual_pdf_codex_reading_handoff":
            return self._plan_manual_pdf_codex_reading_handoff(profile)
        if profile.id == "single_task_fake_handoff_regression":
            return self._run_single_task_fake_handoff(profile)
        if profile.id == "single_task_codex_handoff":
            return self._plan_single_task_codex_handoff(profile)
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

    def complete(self, canary_id: str) -> CampaignCanaryRecord:
        record = self.load_record(canary_id)
        profile = get_campaign_canary_profile(record.profile_id)
        if profile.id not in _SINGLE_TASK_COMPLETION_PROFILES:
            record.status = "failed"
            record.accepted = False
            record.failure_reason = "Completion check is only defined for single-task handoff canaries."
            self.save_record(record, profile)
            return record
        if not record.campaign_id:
            record.status = "failed"
            record.failure_reason = "Canary has no campaign ID."
            self.save_record(record, profile)
            return record
        campaign_state = CampaignManager(self.config).load_campaign_state(record.campaign_id)
        task_id = campaign_state.campaign.task_ids[-1] if campaign_state.campaign.task_ids else ""
        if not task_id:
            record.status = "failed"
            record.failure_reason = "Canary campaign has no task ID."
            self.save_record(record, profile)
            return record
        latest_import = next((item for item in reversed(campaign_state.imports) if item.task_id == task_id), None)
        attestation_status = campaign_task_attestation_status(campaign_state, task_id)
        review_accepted = bool(campaign_state.acceptance_summary and campaign_state.acceptance_summary.accepted) or any(
            review.accepted for review in campaign_state.human_reviews
        )
        blockers: list[str] = []
        if latest_import is None or latest_import.status not in {"applied", "partial", "valid"}:
            blockers.append("Validated import is missing.")
        if not attestation_status.has_attestation:
            blockers.append("Codex/GPT-5.4 attestation is missing.")
        if profile.id in _REAL_SINGLE_TASK_PROFILES and not attestation_status.accepted_as_actual_run:
            blockers.extend(attestation_status.blockers)
        if not review_accepted:
            blockers.append("Human campaign review acceptance is missing.")
        blockers = list(dict.fromkeys(blockers))
        passed = not blockers
        record.status = "accepted" if passed else "failed"
        record.accepted = passed
        record.actual_run_status = "accepted" if passed else "not_completed"
        if profile.id == "single_task_fake_handoff_regression":
            record.actual_run_status = "fake_not_actual"
        if profile.id == "manual_pdf_fake_reading_regression":
            record.actual_run_status = "fake_not_actual"
        record.human_review_status = "accepted" if review_accepted else "required"
        record.failure_reason = "; ".join(blockers)
        record.artifacts = _artifact_paths(self._campaign_dir(campaign_state.campaign.project_id, campaign_state.campaign.id))
        self.save_record(record, profile)
        return record

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

    def _plan_manual_pdf_codex_reading_handoff(self, profile: CampaignCanaryProfile) -> CampaignCanaryRecord:
        return self._plan_single_task_handoff(
            profile,
            task_type="deep_reader_batch",
            mode="manual_handoff",
            failure_reason="Awaiting Codex reading output, validation/import, attestation, and campaign review.",
        )

    def _run_manual_pdf_fake_reading(self, profile: CampaignCanaryProfile) -> CampaignCanaryRecord:
        project, campaign_id = self._create_seeded_campaign(profile, mode="fake_agent", novelty_verdict="unknown")
        campaign_manager = CampaignManager(self.config)
        pack_dir = create_campaign_task_pack(self.config, campaign_id, "deep_reader_batch")
        task_id = pack_dir.name
        _write_manual_pdf_reading_output(pack_dir, include_claim=True)
        CampaignOutputImporter(self.config).import_outputs(campaign_id, task_id, [])
        campaign_state = campaign_manager.load_campaign_state(campaign_id)
        create_campaign_actual_run_attestation(
            campaign_state,
            task_id,
            agent_name="fake",
            model="gapforge-fake-agent",
            execution_method="fake",
            attester="CI",
        )
        campaign_manager.save_campaign_state(campaign_state)
        record = self._record_from_campaign(profile, campaign_id, project.project.id)
        imported = any(item.task_id == task_id and item.status in {"applied", "partial", "valid"} for item in campaign_state.imports)
        record.status = "complete" if imported else "failed"
        record.accepted = imported
        record.actual_run_status = "fake_not_actual"
        record.human_review_status = "not_required"
        record.failure_reason = "" if imported else "Fake manual-PDF reading handoff did not import fixture output."
        self.save_record(record, profile)
        return record

    def _plan_single_task_codex_handoff(self, profile: CampaignCanaryProfile) -> CampaignCanaryRecord:
        return self._plan_single_task_handoff(
            profile,
            task_type="novelty_reviewer",
            mode="manual_handoff",
            failure_reason="Awaiting Codex output, validation/import, attestation, and campaign review.",
        )

    def _plan_single_task_handoff(
        self,
        profile: CampaignCanaryProfile,
        *,
        task_type: str,
        mode: str,
        failure_reason: str,
    ) -> CampaignCanaryRecord:
        project, campaign_id = self._create_seeded_campaign(profile, mode=mode, novelty_verdict="unknown")
        campaign_manager = CampaignManager(self.config)
        pack_dir = create_campaign_task_pack(self.config, campaign_id, task_type)
        task_id = pack_dir.name
        campaign_state = campaign_manager.load_campaign_state(campaign_id)
        campaign_state.campaign.status = "paused"
        for step in campaign_state.steps:
            if step.task_spec_id == task_id:
                step.status = "blocked"
                step.blocking_issues = [
                    "Manual Codex handoff pending: awaiting validated import, attestation, and human review.",
                ]
        campaign_manager.save_campaign_state(campaign_state)
        record = self._record_from_campaign(profile, campaign_id, project.project.id)
        record.status = "planned"
        record.actual_run_status = "manual_handoff_pending"
        record.human_review_status = "required"
        record.accepted = False
        record.failure_reason = failure_reason
        self.save_record(record, profile)
        return record

    def _run_single_task_fake_handoff(self, profile: CampaignCanaryProfile) -> CampaignCanaryRecord:
        project, campaign_id = self._create_seeded_campaign(profile, mode="fake_agent", novelty_verdict="unknown")
        campaign_manager = CampaignManager(self.config)
        pack_dir = create_campaign_task_pack(self.config, campaign_id, "novelty_reviewer")
        task_id = pack_dir.name
        _write_single_task_novelty_output(pack_dir, verdict="unknown")
        CampaignOutputImporter(self.config).import_outputs(campaign_id, task_id, [])
        campaign_state = campaign_manager.load_campaign_state(campaign_id)
        create_campaign_actual_run_attestation(
            campaign_state,
            task_id,
            agent_name="fake",
            model="gapforge-fake-agent",
            execution_method="fake",
            attester="CI",
        )
        campaign_manager.save_campaign_state(campaign_state)
        record = self._record_from_campaign(profile, campaign_id, project.project.id)
        imported = any(item.task_id == task_id and item.status in {"applied", "partial", "valid"} for item in campaign_state.imports)
        record.status = "complete" if imported else "failed"
        record.accepted = imported
        record.actual_run_status = "fake_not_actual"
        record.human_review_status = "not_required"
        record.failure_reason = "" if imported else "Fake single-task handoff did not import fixture output."
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
        run.evidence_spans.append(
            EvidenceSpan(
                id="span-1",
                paper_id="paper-1",
                section_id="section-1",
                quote="Synthetic full-text section for campaign canary evidence.",
                locator="paper-1:Abstract:p1",
                evidence_type="claim",
                confidence="medium",
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

    def _campaign_dir(self, project_id: str, campaign_id: str) -> Path:
        return self.config.project_root / project_id / "campaigns" / campaign_id


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
    for filename in ("CAMPAIGN_TASK.md", "CODEX_PROMPT.md", "HANDOFF.md", "README_FIRST.md", "VALIDATE_AND_IMPORT.sh"):
        paths.extend(str(path) for path in (campaign_dir / "agent_tasks").glob(f"*/{filename}") if path.exists())
    return sorted(set(paths))


def _write_single_task_novelty_output(pack_dir: Path, *, verdict: str) -> None:
    outputs_dir = pack_dir / "outputs"
    outputs_dir.mkdir(parents=True, exist_ok=True)
    (outputs_dir / "novelty_dossiers_patch.json").write_text(
        json.dumps(
            {
                "novelty_dossiers": [
                    {
                        "target_id": "gap-1",
                        "idea_summary": "Fixture novelty handoff output for single-task canary.",
                        "top_prior_work": ["paper-1"] if verdict == "reject" else [],
                        "comparison_table": [],
                        "verdict": verdict,
                        "novelty_strength": "unknown",
                        "confidence": "low",
                        "missing_searches": ["fixture-only canary does not establish real novelty"],
                    }
                ]
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def _write_manual_pdf_reading_output(pack_dir: Path, *, include_claim: bool = False, locator: str = "paper-1:Abstract:p1") -> None:
    outputs_dir = pack_dir / "outputs"
    outputs_dir.mkdir(parents=True, exist_ok=True)
    (outputs_dir / "paper_notes_patch.json").write_text(
        json.dumps(
            {
                "paper_notes_patch": [
                    {
                        "paper_id": "paper-1",
                        "source_basis": "fixture full text",
                        "one_sentence_summary": "Fixture section states synthetic full-text evidence for canary validation.",
                        "main_claims": ["Fixture paper provides a synthetic full-text section for workflow validation."],
                        "main_results": [],
                        "limitations": ["Fixture-only section does not establish real literature quality."],
                        "evidence_locators": [locator],
                        "confidence": "medium",
                    }
                ]
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    if include_claim:
        (outputs_dir / "claims_patch.json").write_text(
            json.dumps(
                {
                    "claims_patch": [
                        {
                            "id": "claim-fixture-reading",
                            "paper_id": "paper-1",
                            "text": "Fixture paper contains a synthetic full-text section for workflow validation.",
                            "status": "supported",
                            "confidence": "medium",
                            "evidence_locators": [locator],
                        }
                    ]
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )


def _has_ready_direction(program) -> bool:  # noqa: ANN001
    return any(direction.maturity in {"experiment_ready", "manuscript_ready"} for direction in program.research_directions)
