"""v0.5 real-literature campaign quality release-gate enforcer."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from gapforge.campaigns import CampaignManager, CampaignState
from gapforge.config import GapForgeConfig
from gapforge.models import (
    RealLiteratureCampaignRecord,
    ResearchProgramState,
    ResearchRunState,
    from_dict,
)
from gapforge.project_memory import ProjectMemoryManager
from gapforge.real_literature.review import RealLiteratureReviewManager
from gapforge.release_gate.v04 import V04ReleaseGateEnforcer
from gapforge.state import ResearchStateManager


@dataclass(slots=True)
class V05CampaignQualityAssessment:
    campaign_id: str
    project_id: str
    live_literature_campaign: bool = False
    accepted_for_workflow: bool = False
    accepted_for_research_quality: bool = False
    refusal: bool = False
    experiment_ready: bool = False
    live_source_diagnostic: bool = False
    search_strategy: bool = False
    search_rounds: bool = False
    source_coverage: bool = False
    canonicalized_papers: bool = False
    retrieval_index: bool = False
    prior_work_recall_assessment: bool = False
    novelty_dossier: bool = False
    related_work_matrix: bool = False
    human_research_quality_review: bool = False
    explicit_stop_reason: bool = False
    missing_closest_prior_work: bool = False
    fake_citation_found: bool = False
    unsupported_high_confidence_claim_found: bool = False
    overclaimed_novelty: bool = False
    blockers: list[str] = field(default_factory=list)


@dataclass(slots=True)
class V05ReleaseGateResult:
    passed: bool
    deterministic_ci_passed: bool
    v4_workflow_gate_passed: bool
    live_literature_campaign_count: int
    quality_accepted_campaign_ids: list[str]
    refusal_campaign_present: bool
    experiment_ready_campaign_present: bool
    blockers: list[str]
    campaigns: list[V05CampaignQualityAssessment]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class V05ReleaseGateEnforcer:
    """Machine-check v0.5 real-literature research-quality release eligibility."""

    def __init__(self, config: GapForgeConfig) -> None:
        self.config = config
        self.config.ensure_dirs()
        self.project_manager = ProjectMemoryManager(config)
        self.state_manager = ResearchStateManager(config)
        self.campaign_manager = CampaignManager(config)
        self.real_literature_review_manager = RealLiteratureReviewManager(config)

    def evaluate(self, project_id: str = "") -> V05ReleaseGateResult:
        v4_result = V04ReleaseGateEnforcer(self.config).evaluate(project_id=project_id)
        assessments = self._campaign_assessments(project_id)
        live_campaigns = [item for item in assessments if item.live_literature_campaign]
        quality_accepted = [item for item in live_campaigns if item.accepted_for_research_quality and not item.blockers]
        refusal_present = any(item.refusal for item in quality_accepted)
        experiment_ready_present = any(item.experiment_ready for item in quality_accepted)

        blockers: list[str] = []
        if not v4_result.deterministic_ci_passed:
            blockers.append("Deterministic CI pass evidence is missing.")
        if not v4_result.passed:
            blockers.append("v0.4 workflow release gate has not passed.")
        if len(live_campaigns) < 3:
            blockers.append(f"At least 3 live-literature campaigns must run; found {len(live_campaigns)}.")
        if len(quality_accepted) < 2:
            blockers.append(f"At least 2 campaigns must be accepted for research quality; found {len(quality_accepted)}.")
        if not refusal_present:
            blockers.append("No quality-accepted campaign correctly refused a recommendation.")
        if not experiment_ready_present:
            blockers.append("No quality-accepted campaign produced an experiment-ready direction.")

        for assessment in live_campaigns:
            if assessment.accepted_for_research_quality and assessment.blockers:
                blockers.extend(f"{assessment.campaign_id}: {item}" for item in assessment.blockers)

        blockers = _dedupe(blockers)
        return V05ReleaseGateResult(
            passed=not blockers,
            deterministic_ci_passed=v4_result.deterministic_ci_passed,
            v4_workflow_gate_passed=v4_result.passed,
            live_literature_campaign_count=len(live_campaigns),
            quality_accepted_campaign_ids=[item.campaign_id for item in quality_accepted],
            refusal_campaign_present=refusal_present,
            experiment_ready_campaign_present=experiment_ready_present,
            blockers=blockers,
            campaigns=assessments,
        )

    def write_outputs(self, result: V05ReleaseGateResult) -> tuple[Path, Path]:
        data_dir = self.config.data_dir / "release_gate"
        data_dir.mkdir(parents=True, exist_ok=True)
        json_path = data_dir / "v0.5_latest.json"
        md_path = data_dir / "v0.5_latest.md"
        json_path.write_text(json.dumps(result.to_dict(), indent=2) + "\n", encoding="utf-8")
        md_path.write_text(render_v05_release_gate_markdown(result), encoding="utf-8")
        return json_path, md_path

    def _campaign_assessments(self, project_id: str) -> list[V05CampaignQualityAssessment]:
        assessments: list[V05CampaignQualityAssessment] = []
        for program in self._programs(project_id):
            for campaign in program.campaigns:
                try:
                    state = self.campaign_manager.load_campaign_state(campaign.id)
                except (FileNotFoundError, json.JSONDecodeError, ValueError):
                    continue
                runs = self._runs_for_campaign(state)
                assessments.append(self._assess_campaign(program, state, runs))
        return assessments

    def _assess_campaign(
        self,
        program: ResearchProgramState,
        state: CampaignState,
        runs: list[ResearchRunState],
    ) -> V05CampaignQualityAssessment:
        campaign_dir = self._campaign_dir(state)
        real_records = _real_literature_records_for_campaign(self.config, state.campaign.id)
        reviews = self.real_literature_review_manager.load_reviews(state.campaign.id)
        latest_review = reviews[-1] if reviews else None
        live_literature_campaign = bool(real_records or reviews or (campaign_dir / "real_literature_acceptance.json").exists())
        experiment_ready = _campaign_has_experiment_ready_direction(program)
        refusal = _is_refusal_campaign(state)
        has_novelty = any(run.novelty_dossiers for run in runs)
        assessment = V05CampaignQualityAssessment(
            campaign_id=state.campaign.id,
            project_id=state.campaign.project_id,
            live_literature_campaign=live_literature_campaign,
            accepted_for_workflow=bool(latest_review and latest_review.accepted_for_workflow),
            accepted_for_research_quality=bool(latest_review and latest_review.accepted_for_research_quality),
            refusal=refusal,
            experiment_ready=experiment_ready,
            live_source_diagnostic=bool(
                any(record.live_source_diagnostic_id for record in real_records)
                or (campaign_dir / "live_source_diagnostic.md").exists()
                or (campaign_dir / "live_source_diagnostic.json").exists()
            ),
            search_strategy=any(run.search_strategies for run in runs) or (campaign_dir / "search_strategy.md").exists(),
            search_rounds=any(run.search_rounds for run in runs) or (campaign_dir / "search_rounds.md").exists(),
            source_coverage=any(run.source_coverage is not None for run in runs),
            canonicalized_papers=_has_canonicalized_papers(program, runs),
            retrieval_index=(Path(program.project.root_dir) / "retrieval" / "manifest.json").exists(),
            prior_work_recall_assessment=any(run.prior_work_recall_assessments for run in runs)
            or (campaign_dir / "prior_work_recall.md").exists(),
            novelty_dossier=has_novelty,
            related_work_matrix=bool(program.related_work_matrices) or (Path(program.project.root_dir) / "related_work_matrix.md").exists(),
            human_research_quality_review=bool(latest_review),
            explicit_stop_reason=bool(state.stop_conditions),
            missing_closest_prior_work=_missing_closest_prior_work(program, runs),
            fake_citation_found=bool(latest_review and latest_review.fake_citation_found),
            unsupported_high_confidence_claim_found=bool(latest_review and latest_review.unsupported_high_confidence_claim_found),
            overclaimed_novelty=bool(latest_review and latest_review.overclaimed_novelty),
        )
        assessment.blockers = _quality_campaign_blockers(assessment)
        return assessment

    def _programs(self, project_id: str) -> list[ResearchProgramState]:
        if project_id:
            return [self.project_manager.load_project(project_id)]
        return [self.project_manager.load_project(project.id) for project in self.project_manager.list_projects()]

    def _runs_for_campaign(self, state: CampaignState) -> list[ResearchRunState]:
        runs: list[ResearchRunState] = []
        for run_id in state.campaign.run_ids:
            try:
                runs.append(self.state_manager.load_run(run_id))
            except FileNotFoundError:
                continue
        return runs

    def _campaign_dir(self, state: CampaignState) -> Path:
        return self.config.project_root / state.campaign.project_id / "campaigns" / state.campaign.id


def render_v05_release_gate_markdown(result: V05ReleaseGateResult) -> str:
    lines = [
        "# GapForge v0.5 Real-Literature Quality Release Gate",
        "",
        f"- Passed: {str(result.passed).lower()}",
        f"- Deterministic CI passed: {str(result.deterministic_ci_passed).lower()}",
        f"- v0.4 workflow gate passed: {str(result.v4_workflow_gate_passed).lower()}",
        f"- Live-literature campaigns: {result.live_literature_campaign_count}",
        f"- Quality-accepted campaigns: {len(result.quality_accepted_campaign_ids)}",
        f"- Refusal campaign present: {str(result.refusal_campaign_present).lower()}",
        f"- Experiment-ready campaign present: {str(result.experiment_ready_campaign_present).lower()}",
        "",
        "## Blocking Failures",
        "",
    ]
    lines.extend([f"- {item}" for item in result.blockers] or ["- none"])
    lines.extend(["", "## Campaign Assessments", ""])
    for campaign in result.campaigns:
        if not campaign.live_literature_campaign:
            continue
        lines.extend(
            [
                f"### `{campaign.campaign_id}`",
                "",
                f"- Project: `{campaign.project_id}`",
                f"- Accepted for workflow: {str(campaign.accepted_for_workflow).lower()}",
                f"- Accepted for research quality: {str(campaign.accepted_for_research_quality).lower()}",
                f"- Refusal: {str(campaign.refusal).lower()}",
                f"- Experiment-ready: {str(campaign.experiment_ready).lower()}",
                f"- Live source diagnostic: {str(campaign.live_source_diagnostic).lower()}",
                f"- Search strategy: {str(campaign.search_strategy).lower()}",
                f"- Search rounds: {str(campaign.search_rounds).lower()}",
                f"- Source coverage: {str(campaign.source_coverage).lower()}",
                f"- Canonicalized papers: {str(campaign.canonicalized_papers).lower()}",
                f"- Retrieval index: {str(campaign.retrieval_index).lower()}",
                f"- Prior-work recall: {str(campaign.prior_work_recall_assessment).lower()}",
                f"- Novelty dossier: {str(campaign.novelty_dossier).lower()}",
                f"- Related-work matrix: {str(campaign.related_work_matrix).lower()}",
                f"- Explicit stop reason: {str(campaign.explicit_stop_reason).lower()}",
                "",
                "Blockers:",
                "",
            ]
        )
        lines.extend([f"- {item}" for item in campaign.blockers] or ["- none"])
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _quality_campaign_blockers(assessment: V05CampaignQualityAssessment) -> list[str]:
    blockers: list[str] = []
    required = {
        "Live source diagnostic is missing.": assessment.live_source_diagnostic,
        "Search strategy is missing.": assessment.search_strategy,
        "Search rounds are missing.": assessment.search_rounds,
        "Source coverage is missing.": assessment.source_coverage,
        "Canonicalized papers are missing.": assessment.canonicalized_papers,
        "Retrieval index is missing.": assessment.retrieval_index,
        "Prior-work recall assessment is missing.": assessment.prior_work_recall_assessment,
        "Novelty dossier is missing.": assessment.novelty_dossier,
        "Related-work matrix is missing.": assessment.related_work_matrix,
        "Human research-quality review is missing.": assessment.human_research_quality_review,
        "Explicit stop reason is missing.": assessment.explicit_stop_reason,
    }
    blockers.extend(message for message, present in required.items() if not present)
    if assessment.fake_citation_found:
        blockers.append("Human research-quality review found fake citations.")
    if assessment.unsupported_high_confidence_claim_found:
        blockers.append("Human research-quality review found unsupported high-confidence claims.")
    if assessment.overclaimed_novelty:
        blockers.append("Human research-quality review found overclaimed novelty.")
    if assessment.missing_closest_prior_work:
        blockers.append("Recommended direction is missing closest prior work.")
    return _dedupe(blockers)


def _real_literature_records_for_campaign(config: GapForgeConfig, campaign_id: str) -> list[RealLiteratureCampaignRecord]:
    root = config.data_dir / "real_literature"
    if not root.exists():
        return []
    records: list[RealLiteratureCampaignRecord] = []
    for path in root.glob("*/record.json"):
        try:
            record = from_dict(RealLiteratureCampaignRecord, json.loads(path.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            continue
        if record.campaign_id == campaign_id:
            records.append(record)
    return records


def _campaign_has_experiment_ready_direction(program: ResearchProgramState) -> bool:
    return any(direction.maturity in {"experiment_ready", "manuscript_ready"} for direction in program.research_directions)


def _is_refusal_campaign(state: CampaignState) -> bool:
    text = " ".join(" ".join([condition.reason, *condition.evidence]) for condition in state.stop_conditions).lower()
    return any(
        term in text
        for term in (
            "refusal",
            "poor coverage",
            "insufficient",
            "not_ready",
            "not ready",
            "novelty unknown",
            "refused",
        )
    )


def _has_canonicalized_papers(program: ResearchProgramState, runs: list[ResearchRunState]) -> bool:
    root = Path(program.project.root_dir)
    identities_path = root / "canonical_paper_identities.json"
    if identities_path.exists():
        try:
            raw = json.loads(identities_path.read_text(encoding="utf-8"))
            if isinstance(raw, list) and raw:
                return True
        except json.JSONDecodeError:
            pass
    report_path = root / "paper_merge_report.md"
    if report_path.exists():
        text = report_path.read_text(encoding="utf-8").lower()
        if "no project paper canonicalization" not in text:
            return True
    for run in runs:
        identities_path = Path(run.run_dir) / "canonical_paper_identities.json"
        if identities_path.exists():
            try:
                raw = json.loads(identities_path.read_text(encoding="utf-8"))
                if isinstance(raw, list) and raw:
                    return True
            except json.JSONDecodeError:
                pass
        report_path = Path(run.run_dir) / "paper_merge_report.md"
        if report_path.exists():
            text = report_path.read_text(encoding="utf-8").lower()
            if "canonical papers:" in text and "no run paper canonicalization" not in text:
                return True
    return False


def _missing_closest_prior_work(program: ResearchProgramState, runs: list[ResearchRunState]) -> bool:
    ready = _campaign_has_experiment_ready_direction(program)
    if not ready:
        return False
    for run in runs:
        for dossier in run.novelty_dossiers:
            if dossier.top_prior_work:
                return False
        for assessment in run.prior_work_recall_assessments:
            if assessment.top_prior_work_ids:
                return False
    return True


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value and value not in seen:
            result.append(value)
            seen.add(value)
    return result
