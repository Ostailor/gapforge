"""v0.4 actual Codex/GPT-5.4 campaign release-gate enforcer."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from gapforge.campaigns import CampaignManager, CampaignState
from gapforge.campaigns.acceptance import accepted_real_agent_output_ids
from gapforge.config import GapForgeConfig
from gapforge.models import CampaignCanaryRecord, ResearchProgramState, ResearchRunState, from_dict
from gapforge.project_memory import ProjectMemoryManager
from gapforge.state import ResearchStateManager


@dataclass(slots=True)
class V04CampaignGateAssessment:
    campaign_id: str
    project_id: str
    mode: str
    accepted_real_campaign: bool = False
    actual_run_attestation: bool = False
    validated_imported_outputs: bool = False
    source_coverage: bool = False
    retrieval_index: bool = False
    novelty_or_refusal: bool = False
    human_review_accepted: bool = False
    campaign_report: bool = False
    explicit_stop_reason: bool = False
    experiment_ready: bool = False
    refusal: bool = False
    full_text_or_manual_pdf: bool = False
    blockers: list[str] = field(default_factory=list)
    blocker_categories: dict[str, list[str]] = field(default_factory=dict)
    next_commands: list[str] = field(default_factory=list)
    fake_vs_real_explanation: str = ""
    task_pack_actual_run_explanation: str = ""


@dataclass(slots=True)
class V04ReleaseGateResult:
    passed: bool
    deterministic_ci_passed: bool
    fake_agent_canary_passed: bool
    accepted_real_campaign_ids: list[str]
    experiment_ready_campaign_present: bool
    refusal_campaign_present: bool
    full_text_campaign_present: bool
    blockers: list[str]
    campaigns: list[V04CampaignGateAssessment]
    accepted_real_campaign_count: int = 0
    missing_campaign_types: list[str] = field(default_factory=list)
    blocker_categories: dict[str, list[str]] = field(default_factory=dict)
    next_commands: list[str] = field(default_factory=list)
    fake_vs_real_explanation: str = ""
    task_pack_actual_run_explanation: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class V04ReleaseGateEnforcer:
    """Machine-check v0.4 actual-run release eligibility."""

    def __init__(self, config: GapForgeConfig) -> None:
        self.config = config
        self.config.ensure_dirs()
        self.project_manager = ProjectMemoryManager(config)
        self.state_manager = ResearchStateManager(config)
        self.campaign_manager = CampaignManager(config)

    def evaluate(self, project_id: str = "") -> V04ReleaseGateResult:
        deterministic_ci_passed = self._deterministic_ci_passed()
        fake_agent_canary_passed = self._fake_agent_canary_passed()
        assessments = self._campaign_assessments(project_id)
        accepted = [item for item in assessments if item.accepted_real_campaign]
        blockers: list[str] = []
        if not deterministic_ci_passed:
            blockers.append("Deterministic CI pass evidence is missing. Write data/release_gate/deterministic_ci.json with passed=true.")
        if not fake_agent_canary_passed:
            blockers.append("Fake-agent campaign canary has not passed.")
        if len(accepted) < 3:
            blockers.append(f"At least 3 accepted real Codex/GPT-5.4 campaigns are required; found {len(accepted)}.")
        experiment_ready = any(item.experiment_ready for item in accepted)
        refusal = any(item.refusal for item in accepted)
        full_text = any(item.full_text_or_manual_pdf for item in accepted)
        if not experiment_ready:
            blockers.append("No accepted real campaign produced an experiment_ready or manuscript_ready direction.")
        if not refusal:
            blockers.append("No accepted real campaign correctly refused a recommendation due to poor coverage or novelty uncertainty.")
        if not full_text:
            blockers.append("No accepted real campaign covered a manual-PDF or full-text workflow.")
        if not assessments:
            blockers.append("No campaigns were found for release-gate evaluation.")
        for assessment in assessments:
            if assessment.blockers and _campaign_has_release_blocking_failures(assessment):
                blockers.extend(f"{assessment.campaign_id}: {item}" for item in assessment.blockers)
        blockers = _dedupe(blockers)
        missing_campaign_types = _missing_campaign_types(
            experiment_ready=experiment_ready,
            refusal=refusal,
            full_text=full_text,
        )
        blocker_categories = _categorize_blockers(blockers)
        next_commands = _next_commands_for_gate(
            blockers=blockers,
            assessments=assessments,
            accepted_count=len(accepted),
            missing_campaign_types=missing_campaign_types,
        )
        return V04ReleaseGateResult(
            passed=not blockers,
            deterministic_ci_passed=deterministic_ci_passed,
            fake_agent_canary_passed=fake_agent_canary_passed,
            accepted_real_campaign_ids=[item.campaign_id for item in accepted],
            experiment_ready_campaign_present=experiment_ready,
            refusal_campaign_present=refusal,
            full_text_campaign_present=full_text,
            blockers=blockers,
            campaigns=assessments,
            accepted_real_campaign_count=len(accepted),
            missing_campaign_types=missing_campaign_types,
            blocker_categories=blocker_categories,
            next_commands=next_commands,
            fake_vs_real_explanation=FAKE_VS_REAL_EXPLANATION,
            task_pack_actual_run_explanation=TASK_PACK_ACTUAL_RUN_EXPLANATION,
        )

    def write_outputs(self, result: V04ReleaseGateResult) -> tuple[Path, Path]:
        from gapforge.release_gate.report import render_v04_release_gate_markdown

        data_dir = self.config.data_dir / "release_gate"
        data_dir.mkdir(parents=True, exist_ok=True)
        json_path = data_dir / "v0.4_latest.json"
        md_path = data_dir / "v0.4_latest.md"
        json_path.write_text(json.dumps(result.to_dict(), indent=2) + "\n", encoding="utf-8")
        md_path.write_text(render_v04_release_gate_markdown(result), encoding="utf-8")
        return json_path, md_path

    def _campaign_assessments(self, project_id: str) -> list[V04CampaignGateAssessment]:
        assessments: list[V04CampaignGateAssessment] = []
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
    ) -> V04CampaignGateAssessment:
        campaign_dir = self.config.project_root / state.campaign.project_id / "campaigns" / state.campaign.id
        ready = any(direction.maturity in {"experiment_ready", "manuscript_ready"} for direction in program.research_directions)
        refusal = _is_refusal_campaign(state, program)
        assessment = V04CampaignGateAssessment(
            campaign_id=state.campaign.id,
            project_id=state.campaign.project_id,
            mode=state.campaign.mode,
            actual_run_attestation=_has_actual_attestation(state),
            validated_imported_outputs=_has_validated_import(state),
            source_coverage=any(run.source_coverage is not None for run in runs),
            retrieval_index=(Path(program.project.root_dir) / "retrieval" / "manifest.json").exists(),
            novelty_or_refusal=refusal or _has_novelty_for_recommendation(program, runs),
            human_review_accepted=any(review.accepted for review in state.human_reviews),
            campaign_report=(campaign_dir / "campaign_report.md").exists(),
            explicit_stop_reason=bool(state.stop_conditions),
            experiment_ready=ready,
            refusal=refusal,
            full_text_or_manual_pdf=_has_full_text_or_pdf(runs),
            fake_vs_real_explanation=FAKE_VS_REAL_EXPLANATION,
            task_pack_actual_run_explanation=TASK_PACK_ACTUAL_RUN_EXPLANATION,
        )
        assessment.blockers = _campaign_blockers(state, runs, assessment)
        assessment.blocker_categories = _categorize_blockers(assessment.blockers)
        assessment.next_commands = _next_commands_for_campaign(state, assessment)
        assessment.accepted_real_campaign = not assessment.blockers
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

    def _deterministic_ci_passed(self) -> bool:
        path = self.config.data_dir / "release_gate" / "deterministic_ci.json"
        if not path.exists():
            return False
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return False
        return bool(isinstance(raw, dict) and raw.get("passed") is True)

    def _fake_agent_canary_passed(self) -> bool:
        root = self.config.data_dir / "campaign_canaries"
        if not root.exists():
            return False
        for path in root.glob("*/record.json"):
            try:
                record = from_dict(CampaignCanaryRecord, json.loads(path.read_text(encoding="utf-8")))
            except (OSError, json.JSONDecodeError, TypeError, ValueError):
                continue
            if record.profile_id == "fake_agent_campaign_regression" and record.accepted and record.status in {"complete", "accepted"}:
                return True
        return False


FAKE_VS_REAL_EXPLANATION = (
    "Fake-agent canaries validate schemas and orchestration only. They never count as actual Codex/GPT-5.4 acceptance. "
    "A real campaign requires validated imported Codex output, actual-run attestation, and human campaign review."
)

TASK_PACK_ACTUAL_RUN_EXPLANATION = (
    "Task-pack or manual-handoff output can count as an actual run only after Codex/GPT-5.4 produced the output, "
    "GapForge validated and imported it, a human attested the agent/model/method, and campaign review accepted it."
)


def _campaign_blockers(
    state: CampaignState,
    runs: list[ResearchRunState],
    assessment: V04CampaignGateAssessment,
) -> list[str]:
    blockers: list[str] = []
    if state.campaign.mode == "fake_agent":
        blockers.append("Fake-agent campaigns cannot count as actual Codex/GPT-5.4 acceptance.")
    if state.campaign.mode not in {"codex_task_pack", "codex_direct", "manual_handoff"}:
        blockers.append("Campaign mode is not an actual Codex/GPT-5.4 pathway.")
    checks = {
        "Actual-run attestation is missing.": assessment.actual_run_attestation,
        "Validated imported agent outputs are missing.": assessment.validated_imported_outputs,
        "Source coverage is missing.": assessment.source_coverage,
        "Retrieval index is missing.": assessment.retrieval_index,
        "Novelty dossier or valid refusal reason is missing.": assessment.novelty_or_refusal,
        "Human review acceptance is missing.": assessment.human_review_accepted,
        "Campaign report is missing.": assessment.campaign_report,
        "Explicit stop reason is missing.": assessment.explicit_stop_reason,
    }
    blockers.extend(message for message, passed in checks.items() if not passed)
    for review in state.human_reviews:
        if review.fake_citation_found:
            blockers.append("Human review found fake citations.")
        if review.unsupported_high_confidence_claim_found:
            blockers.append("Human review found unsupported high-confidence claims.")
        if review.overclaimed_novelty:
            blockers.append("Human review found strict report novelty/readiness overclaim.")
    if _strong_novelty_without_prior_work(runs):
        blockers.append("Strong novelty appears without closest prior work.")
    if any(item for record in state.imports for item in record.issues if "fake citation" in item.lower()):
        blockers.append("Imported agent output reported fake citation issues.")
    return _dedupe(blockers)


def _categorize_blockers(blockers: list[str]) -> dict[str, list[str]]:
    categories: dict[str, list[str]] = {}
    for blocker in blockers:
        category = _blocker_category(blocker)
        categories.setdefault(category, []).append(blocker)
    return categories


def _blocker_category(blocker: str) -> str:
    text = blocker.lower()
    if "fake-agent" in text or "fake agent" in text or "fake-only" in text:
        return "fake_vs_real"
    if "attestation" in text:
        return "missing_attestation"
    if "human review" in text or "human accepted" in text:
        return "missing_human_review"
    if "validated" in text or "imported" in text or "agent output" in text:
        return "missing_validated_import"
    if "source coverage" in text:
        return "missing_source_coverage"
    if "retrieval index" in text:
        return "missing_retrieval_index"
    if "campaign report" in text:
        return "missing_campaign_report"
    if "stop reason" in text:
        return "missing_stop_reason"
    if "experiment_ready" in text or "experiment-ready" in text or "experiment_ready or manuscript_ready" in text:
        return "missing_experiment_ready_campaign"
    if "refused" in text or "refusal" in text or "poor coverage" in text or "novelty uncertainty" in text:
        return "missing_refusal_campaign"
    if "manual-pdf" in text or "full-text" in text:
        return "missing_manual_pdf_full_text_campaign"
    if "3 accepted real" in text or "no campaigns" in text or "zero real" in text:
        return "missing_real_campaigns"
    if "deterministic ci" in text:
        return "missing_deterministic_ci"
    if "fake-agent campaign canary" in text:
        return "missing_fake_canary"
    return "other"


def _missing_campaign_types(*, experiment_ready: bool, refusal: bool, full_text: bool) -> list[str]:
    missing: list[str] = []
    if not experiment_ready:
        missing.append("experiment-ready campaign")
    if not refusal:
        missing.append("refusal campaign")
    if not full_text:
        missing.append("manual PDF/full-text campaign")
    return missing


def _next_commands_for_gate(
    *,
    blockers: list[str],
    assessments: list[V04CampaignGateAssessment],
    accepted_count: int,
    missing_campaign_types: list[str],
) -> list[str]:
    commands: list[str] = []
    categories = set(_categorize_blockers(blockers))
    if not assessments or accepted_count == 0:
        commands.extend(
            [
                "gapforge campaign-canary-run --profile single_task_codex_handoff --real",
                "gapforge codex-handoff --campaign-id <campaign-id> --latest-task --print-prompt",
                "gapforge validate-import-all --campaign-id <campaign-id>",
                'gapforge attest-agent-run --task-id <task-id> --agent codex --model gpt-5.4 --method task_pack --attester "<name>"',
                'gapforge campaign-review --campaign-id <campaign-id> --accept --reviewer "<name>"',
                "gapforge campaign-canary-complete --canary-id <canary-id>",
            ]
        )
    if "missing_attestation" in categories:
        commands.append(
            'gapforge attest-agent-run --task-id <task-id> --agent codex --model gpt-5.4 --method task_pack --attester "<name>"'
        )
    if "missing_human_review" in categories:
        commands.append('gapforge campaign-review --campaign-id <campaign-id> --accept --reviewer "<name>"')
    if "missing_validated_import" in categories:
        commands.extend(
            [
                "gapforge codex-handoff --campaign-id <campaign-id> --latest-task --print-prompt",
                "gapforge validate-import-all --campaign-id <campaign-id>",
            ]
        )
    if "missing_retrieval_index" in categories:
        commands.append("gapforge build-index --project-id <project-id>")
    if "missing_campaign_report" in categories:
        commands.append("gapforge campaign-report --campaign-id <campaign-id>")
    if "missing_stop_reason" in categories:
        commands.append('gapforge campaign-stop --campaign-id <campaign-id> --reason "<explicit stop reason>"')
    if "experiment-ready campaign" in missing_campaign_types:
        commands.append("gapforge campaign-canary-run --profile agentic_low_fpr_collusion --real")
    if "refusal campaign" in missing_campaign_types:
        commands.append("gapforge campaign-canary-run --profile agentic_undercovered_refusal --real")
    if "manual PDF/full-text campaign" in missing_campaign_types:
        commands.append("gapforge campaign-canary-run --profile manual_pdf_codex_reading_handoff --real")
    return _dedupe(commands)


def _next_commands_for_campaign(state: CampaignState, assessment: V04CampaignGateAssessment) -> list[str]:
    commands: list[str] = []
    if state.campaign.mode == "fake_agent":
        commands.append("gapforge campaign-canary-run --profile single_task_codex_handoff --real")
    if not state.campaign.task_ids:
        commands.append(f"gapforge campaign-task --campaign-id {state.campaign.id} --type novelty_reviewer")
    if not assessment.validated_imported_outputs:
        commands.extend(
            [
                f"gapforge codex-handoff --campaign-id {state.campaign.id} --latest-task --print-prompt",
                f"gapforge validate-import-all --campaign-id {state.campaign.id}",
            ]
        )
    task_id = state.campaign.task_ids[-1] if state.campaign.task_ids else "<task-id>"
    if not assessment.actual_run_attestation:
        commands.append(
            f'gapforge attest-agent-run --task-id {task_id} --agent codex --model gpt-5.4 --method task_pack --attester "<name>"'
        )
    if not assessment.human_review_accepted:
        commands.append(f'gapforge campaign-review --campaign-id {state.campaign.id} --accept --reviewer "<name>"')
    if not assessment.source_coverage and state.campaign.run_ids:
        commands.append(f"gapforge coverage --run-id {state.campaign.run_ids[-1]}")
    if not assessment.retrieval_index:
        commands.append(f"gapforge build-index --project-id {state.campaign.project_id}")
    if not assessment.campaign_report:
        commands.append(f"gapforge campaign-report --campaign-id {state.campaign.id}")
    if not assessment.explicit_stop_reason:
        commands.append(f'gapforge campaign-stop --campaign-id {state.campaign.id} --reason "<explicit stop reason>"')
    return _dedupe(commands)


def _has_actual_attestation(state: CampaignState) -> bool:
    return bool(accepted_real_agent_output_ids(state))


def _has_validated_import(state: CampaignState) -> bool:
    return any(record.status in {"applied", "partial", "valid"} and bool(record.accepted_objects) for record in state.imports)


def _has_novelty_for_recommendation(program: ResearchProgramState, runs: list[ResearchRunState]) -> bool:
    if not any(direction.maturity in {"experiment_ready", "manuscript_ready"} for direction in program.research_directions):
        return False
    return any(run.novelty_dossiers or run.novelty_assessments for run in runs)


def _is_refusal_campaign(state: CampaignState, program: ResearchProgramState) -> bool:
    del program
    text = " ".join(condition.reason for condition in state.stop_conditions).lower()
    return any(
        term in text for term in ["poor coverage", "not_ready_poor_coverage", "novelty unknown", "not_ready_novelty_unknown", "refus"]
    )


def _has_full_text_or_pdf(runs: list[ResearchRunState]) -> bool:
    for run in runs:
        if run.paper_sections or run.evidence_spans:
            return True
        if any(artifact.artifact_type == "pdf" and artifact.status == "available" for artifact in run.paper_artifacts):
            return True
        if run.source_coverage and run.source_coverage.papers_with_full_text:
            return True
    return False


def _strong_novelty_without_prior_work(runs: list[ResearchRunState]) -> bool:
    for run in runs:
        for dossier in run.novelty_dossiers:
            if dossier.novelty_strength == "strong" and not dossier.top_prior_work:
                return True
        for assessment in run.novelty_assessments:
            if assessment.novelty_strength == "strong" and not assessment.closest_prior_work:
                return True
    return False


def _campaign_has_release_blocking_failures(assessment: V04CampaignGateAssessment) -> bool:
    """Return whether a campaign's own blockers should fail the global release gate.

    Fake and deterministic campaigns are useful diagnostic context, but they are
    not candidate actual-run campaigns. The top-level gate already fails closed
    when too few accepted real campaigns exist, so old fake regression campaigns
    should not keep the gate failing after the required real Codex campaigns pass.
    """

    return assessment.mode in {"codex_task_pack", "codex_direct", "manual_handoff"}


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value and value not in seen:
            result.append(value)
            seen.add(value)
    return result
