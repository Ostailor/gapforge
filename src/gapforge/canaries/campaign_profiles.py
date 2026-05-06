"""v0.4 campaign-level canary profiles."""

from __future__ import annotations

from gapforge.models import CampaignCanaryProfile, Provenance
from gapforge.state import utc_now_iso


def default_campaign_canary_profiles() -> list[CampaignCanaryProfile]:
    now = utc_now_iso()
    return [
        CampaignCanaryProfile(
            id="manual_pdf_codex_reading_handoff",
            title="Manual-PDF fixture Codex reading handoff",
            topic="manual PDF or fixture section Codex reading validation",
            source_profile="generic",
            campaign_mode="manual_handoff",
            budget="small",
            requires_codex=True,
            requires_network=False,
            required_milestones=["reading_ready"],
            expected_stop_reason="manual_handoff_pending",
            expected_artifacts=[
                "campaign_report.md",
                "agent_tasks/*/CAMPAIGN_TASK.md",
                "agent_tasks/*/CODEX_PROMPT.md",
                "agent_tasks/*/VALIDATE_AND_IMPORT.sh",
            ],
            acceptance_criteria=[
                "Canary uses fixture full-text sections and evidence spans when no real local PDF is provided.",
                "Codex writes `paper_notes_patch.json`; `claims_patch.json` and `evidence_spans_patch.json` are optional.",
                "Every paper ID and evidence locator in the reading output resolves to fixture state.",
                "Validated import, Codex/GPT-5.4 attestation, and human review are required before completion.",
            ],
            known_risks=[
                "Fixture sections validate workflow only; they do not prove real literature quality.",
                "A real local PDF workflow still requires separate user-provided PDFs for actual research validation.",
            ],
            provenance=_provenance(now),
        ),
        CampaignCanaryProfile(
            id="manual_pdf_fake_reading_regression",
            title="Manual-PDF fixture fake reading regression",
            topic="manual PDF fixture fake reading validation",
            source_profile="generic",
            campaign_mode="fake_agent",
            budget="small",
            requires_codex=False,
            requires_network=False,
            required_milestones=["reading_ready"],
            expected_stop_reason="fake_not_actual",
            expected_artifacts=["campaign_report.md", "agent_tasks/*/CAMPAIGN_TASK.md", "imports.json"],
            acceptance_criteria=[
                "Fixture reading output validates and imports offline.",
                "Evidence locator validation is exercised without counting fake output as actual Codex/GPT-5.4 work.",
            ],
            known_risks=["This is a CI regression and cannot satisfy actual-run acceptance."],
            provenance=_provenance(now),
        ),
        CampaignCanaryProfile(
            id="single_task_codex_handoff",
            title="Single-task Codex handoff validation",
            topic="single task Codex handoff validation",
            source_profile="generic",
            campaign_mode="manual_handoff",
            budget="small",
            requires_codex=True,
            requires_network=False,
            required_milestones=["novelty_checked"],
            expected_stop_reason="manual_handoff_pending",
            expected_artifacts=[
                "campaign_report.md",
                "agent_tasks/*/CAMPAIGN_TASK.md",
                "agent_tasks/*/CODEX_PROMPT.md",
                "agent_tasks/*/VALIDATE_AND_IMPORT.sh",
            ],
            acceptance_criteria=[
                "A novelty task pack is created from a fixture run with a known paper, gap, and evidence span.",
                "Codex writes `novelty_dossiers_patch.json` with verdict `unknown` or `reject` into the task outputs directory.",
                "The output validates and imports before attestation can count.",
                "Human attestation and campaign review are both recorded before completion.",
            ],
            known_risks=[
                "This canary validates Codex handoff mechanics, not real literature quality.",
                "Task-pack output cannot count as actual-run evidence without user attestation and human review.",
            ],
            provenance=_provenance(now),
        ),
        CampaignCanaryProfile(
            id="single_task_fake_handoff_regression",
            title="Single-task fake handoff regression",
            topic="single task fake handoff validation",
            source_profile="generic",
            campaign_mode="fake_agent",
            budget="small",
            requires_codex=False,
            requires_network=False,
            required_milestones=["novelty_checked"],
            expected_stop_reason="fake_not_actual",
            expected_artifacts=["campaign_report.md", "agent_tasks/*/CAMPAIGN_TASK.md", "imports.json"],
            acceptance_criteria=[
                "A single novelty task validates and imports offline.",
                "Fake attestation is visible but never counted as actual Codex/GPT-5.4 acceptance.",
            ],
            known_risks=["This is a CI regression and cannot satisfy actual-run acceptance."],
            provenance=_provenance(now),
        ),
        CampaignCanaryProfile(
            id="agentic_low_fpr_collusion",
            title="Agentic low-FPR collusion Codex campaign",
            topic="low false positive collusion detection in LLM agents",
            source_profile="ai_safety",
            campaign_mode="codex_task_pack",
            budget="medium",
            requires_codex=True,
            requires_network=True,
            required_milestones=["novelty_checked", "direction_ready", "experiment_ready"],
            expected_artifacts=[
                "campaign_report.md",
                "novelty_dossiers.md",
                "related_work_matrix.md",
                "experiment_protocols.md",
                "final_report.md",
            ],
            acceptance_criteria=[
                "Campaign produces or requests a novelty dossier with closest prior work or explicit unknown status.",
                "Related-work matrix and experiment protocol artifacts are produced before claiming readiness.",
                "Strict report does not overclaim novelty under weak coverage.",
                "Codex/GPT-5.4 outputs are validated, attested, and human reviewed before actual-run acceptance.",
            ],
            known_risks=[
                "Task-pack mode requires manual Codex execution and import.",
                "Source coverage may be incomplete for frontier AI-safety literature.",
            ],
            provenance=_provenance(now),
        ),
        CampaignCanaryProfile(
            id="agentic_monitor_evasion",
            title="Agentic monitor-evasion Codex campaign",
            topic="lexical substitution attacks on LLM monitors",
            source_profile="ai_safety",
            campaign_mode="codex_task_pack",
            budget="medium",
            requires_codex=True,
            requires_network=True,
            required_milestones=["gaps_ready", "novelty_checked"],
            expected_artifacts=["gap_evidence_matrix.md", "novelty_dossiers.md", "campaign_report.md"],
            acceptance_criteria=[
                "Gap evidence matrix links claims to papers or evidence locators.",
                "Novelty dossier lists closest prior work or marks novelty unknown.",
            ],
            known_risks=["Lexical substitution terminology may vary across security and AI-safety literature."],
            provenance=_provenance(now),
        ),
        CampaignCanaryProfile(
            id="agentic_cross_domain_specificity",
            title="Agentic cross-domain specificity Codex campaign",
            topic="medical screening specificity methods for AI safety false-positive control",
            source_profile="medicine+ai_safety",
            campaign_mode="codex_task_pack",
            budget="medium",
            requires_codex=True,
            requires_network=True,
            required_milestones=["gaps_ready", "direction_ready"],
            expected_artifacts=["cross_domain_transfers.md", "related_work_matrix.md", "campaign_report.md"],
            acceptance_criteria=[
                "Transfer candidate is evidence-backed, not a shallow analogy.",
                "Related-work matrix separates medical screening sources from AI-safety target papers.",
            ],
            known_risks=["Medicine source coverage may require sources not yet implemented as first-class connectors."],
            provenance=_provenance(now),
        ),
        CampaignCanaryProfile(
            id="agentic_undercovered_refusal",
            title="Agentic undercovered-topic refusal campaign",
            topic="intentionally sparse undercovered research topic for strict refusal",
            source_profile="generic",
            campaign_mode="deterministic",
            budget="small",
            requires_codex=False,
            requires_network=False,
            required_milestones=["rejected"],
            expected_stop_reason="No useful direction is ready",
            expected_artifacts=["campaign_report.md", "source_coverage.md"],
            acceptance_criteria=[
                "Campaign stops without a paper-ready recommendation.",
                "Coverage weakness is visible in the campaign artifacts.",
            ],
            known_risks=["This canary validates refusal behavior, not research usefulness."],
            provenance=_provenance(now),
        ),
        CampaignCanaryProfile(
            id="manual_pdf_agentic",
            title="Manual PDF agentic full-text campaign",
            topic="manual local PDF workflow with Codex-backed reading",
            source_profile="generic",
            campaign_mode="codex_task_pack",
            budget="small",
            requires_codex=True,
            requires_network=False,
            requires_local_pdf=True,
            required_milestones=["reading_ready"],
            expected_artifacts=["paper_artifacts.json", "paper_sections.json", "evidence_spans.json", "campaign_report.md"],
            acceptance_criteria=[
                "Local PDF ingestion creates a paper artifact.",
                "Full-text evidence spans are available before Codex-backed reading is accepted.",
                "Codex reading output is validation-gated and locator-backed.",
            ],
            known_risks=["No copyrighted PDFs should be committed; OCR is optional."],
            provenance=_provenance(now),
        ),
        CampaignCanaryProfile(
            id="fake_agent_campaign_regression",
            title="Fake-agent campaign regression",
            topic="fake agent campaign regression for CI",
            source_profile="generic",
            campaign_mode="fake_agent",
            budget="small",
            requires_codex=False,
            requires_network=False,
            required_milestones=["reading_ready"],
            expected_artifacts=["campaign_report.md", "agent_tasks/*/CAMPAIGN_TASK.md", "imports.json"],
            acceptance_criteria=[
                "Fake campaign canary runs offline.",
                "Fake output is validated before import.",
                "No fake output is counted as actual Codex/GPT-5.4 acceptance.",
            ],
            known_risks=["This is a CI integration regression and cannot validate real research quality."],
            provenance=_provenance(now),
        ),
    ]


def get_campaign_canary_profile(profile_id: str) -> CampaignCanaryProfile:
    for profile in default_campaign_canary_profiles():
        if profile.id == profile_id:
            return profile
    raise KeyError(f"Unknown campaign canary profile: {profile_id}")


def render_campaign_canary_plan(profile: CampaignCanaryProfile) -> str:
    commands = _recommended_commands(profile)
    lines = [
        f"# Campaign Canary Plan: {profile.id}",
        "",
        f"- Title: {profile.title}",
        f"- Topic: {profile.topic}",
        f"- Source profile: {profile.source_profile}",
        f"- Campaign mode: {profile.campaign_mode}",
        f"- Agent/model: {profile.agent_name}/{profile.model}",
        f"- Budget: {profile.budget}",
        f"- Requires Codex/GPT-5.4: {str(profile.requires_codex).lower()}",
        f"- Requires network: {str(profile.requires_network).lower()}",
        f"- Requires local PDF: {str(profile.requires_local_pdf).lower()}",
        "",
        "## Recommended Commands",
        "",
    ]
    lines.extend(f"```bash\n{command}\n```" for command in commands)
    lines.extend(["", "## Required Milestones", ""])
    lines.extend(f"- `{milestone}`" for milestone in profile.required_milestones)
    lines.extend(["", "## Expected Artifacts", ""])
    lines.extend(f"- `{artifact}`" for artifact in profile.expected_artifacts)
    if profile.expected_stop_reason:
        lines.extend(["", "## Expected Stop Reason", "", f"- {profile.expected_stop_reason}"])
    lines.extend(["", "## Acceptance Criteria", ""])
    lines.extend(f"- {criterion}" for criterion in profile.acceptance_criteria)
    lines.extend(["", "## Known Risks", ""])
    lines.extend(f"- {risk}" for risk in profile.known_risks)
    return "\n".join(lines).rstrip() + "\n"


def _recommended_commands(profile: CampaignCanaryProfile) -> list[str]:
    real_flag = " --real" if profile.requires_codex else ""
    commands = [
        f"gapforge campaign-canary-plan --profile {profile.id}",
        f"gapforge campaign-canary-run --profile {profile.id}{real_flag}",
        "gapforge campaign-status --campaign-id {campaign_id}",
        "gapforge campaign-report --campaign-id {campaign_id}",
        "gapforge campaign-canary-status --canary-id {canary_id}",
    ]
    if profile.id in {"single_task_codex_handoff", "manual_pdf_codex_reading_handoff"}:
        commands.extend(
            [
                "gapforge codex-handoff --campaign-id {campaign_id} --latest-task --print-prompt",
                "gapforge validate-import-all --campaign-id {campaign_id}",
                'gapforge attest-agent-run --task-id {task_id} --agent codex --model gpt-5.4 --method task_pack --attester "<name>"',
                'gapforge campaign-review --campaign-id {campaign_id} --accept --reviewer "<name>"',
                "gapforge campaign-canary-complete --canary-id {canary_id}",
            ]
        )
    return commands


def _provenance(timestamp: str) -> Provenance:
    return Provenance(
        created_by_skill="campaign-canary-profile",
        timestamp=timestamp,
        reasoning_summary="Built-in v0.4 campaign canary profile with explicit pass/fail criteria.",
    )
