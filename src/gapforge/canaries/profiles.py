"""Built-in canary profiles for v0.3 release validation."""

from __future__ import annotations

from gapforge.models import CanaryRunProfile, Provenance
from gapforge.state import utc_now_iso


def default_canary_profiles() -> list[CanaryRunProfile]:
    now = utc_now_iso()
    return [
        CanaryRunProfile(
            id="low_fpr_collusion_codex",
            title="Codex/GPT-5.4 low-FPR collusion literature canary",
            topic="low false positive collusion detection in LLM agents",
            project_name="v0.3 low-FPR collusion canary",
            source_profile="ai_safety",
            mode="llm_assisted",
            required_steps=[
                "Create or attach project memory.",
                "Run v0.3 search with source policy coverage.",
                "Build retrieval index.",
                "Create Codex task packs for deep reading, gap mining, and novelty.",
                "Import validated Codex outputs.",
                "Generate strict final report.",
                "Record human review.",
            ],
            recommended_commands=[
                'gapforge init-project "v0.3 low-FPR collusion canary"',
                'gapforge run "low false positive collusion detection in LLM agents" --v3 '
                "--project-id v0-3-low-fpr-collusion-canary --source-profile ai_safety "
                "--build-index --deep-novelty --strict-report",
                "gapforge read-llm --run-id {run_id} --agent codex --agent-mode task-pack --model gpt-5.4",
                "gapforge mine-gaps-llm --run-id {run_id} --agent codex --agent-mode task-pack --model gpt-5.4",
                "gapforge novelty-check-llm --run-id {run_id} --gap-id {gap_id} --agent codex --agent-mode task-pack --model gpt-5.4",
                "gapforge import-agent-output --task-id {task_id}",
                "gapforge report --run-id {run_id} --strict",
            ],
            max_papers=50,
            max_expanded_papers=30,
            requires_network=True,
            requires_codex=True,
            requires_human_review=True,
            expected_artifacts=[
                "source_coverage.md",
                "retrieval_index/index_manifest.json",
                "agent_tasks/*/TASK.md",
                "novelty_dossiers.md",
                "final_report.md",
                "human_reviews.md",
            ],
            pass_criteria=[
                "At least one Codex/GPT-5.4 assisted task output is imported after validation.",
                "Strict report remains conservative and does not overclaim novelty.",
                "Novelty dossiers include closest prior work or explicit unknown verdicts.",
                "No unsupported high-confidence claims are present.",
                "Human review is recorded.",
            ],
            known_risks=[
                "Source coverage may remain weak for current frontier literature.",
                "Task-pack mode requires manual Codex execution and output import.",
                "Canary output is not an exhaustive literature review.",
            ],
            provenance=_profile_provenance(now),
        ),
        CanaryRunProfile(
            id="manual_pdf_fulltext_codex",
            title="Manual local-PDF full-text Codex canary",
            topic="manual local PDF workflow",
            project_name="v0.3 manual PDF full-text canary",
            source_profile="generic",
            mode="task_pack",
            required_steps=[
                "Initialize a run.",
                "Add a local PDF with metadata.",
                "Parse full text and sections.",
                "Create Codex deep-reading task pack.",
                "Import validated Codex paper-note/evidence patches.",
                "Generate report with full-text evidence locators.",
            ],
            recommended_commands=[
                'gapforge init-topic "private local PDF full text canary"',
                'gapforge add-pdf --run-id {run_id} /path/to/local.pdf --title "Private fixture" --authors "Author" --year 2024 --parse',
                "gapforge read-llm --run-id {run_id} --paper-id {paper_id} --agent codex --agent-mode task-pack --model gpt-5.4",
                "gapforge import-agent-output --task-id {task_id}",
                "gapforge report --run-id {run_id} --strict",
            ],
            max_papers=5,
            max_expanded_papers=0,
            requires_network=False,
            requires_codex=True,
            requires_human_review=True,
            expected_artifacts=[
                "paper_artifacts.json",
                "paper_sections.json",
                "evidence_spans.json",
                "agent_tasks/*/TASK.md",
                "final_report.md",
            ],
            pass_criteria=[
                "Local PDF artifact is recorded.",
                "Parsed sections preserve page/section locators.",
                "Codex-backed deep reading imports only validated evidence-located patches.",
                "Report distinguishes full-text evidence from abstract-only evidence.",
            ],
            known_risks=["No copyrighted PDF should be committed.", "OCR is optional and may be unavailable."],
            provenance=_profile_provenance(now),
        ),
        CanaryRunProfile(
            id="undercovered_topic_refusal",
            title="Undercovered-topic strict report refusal canary",
            topic="intentionally sparse undercovered research topic",
            project_name="v0.3 undercoverage refusal canary",
            source_profile="generic",
            mode="task_pack",
            required_steps=["Run offline or sparse search.", "Generate strict report.", "Confirm no paper-ready recommendation."],
            recommended_commands=[
                'GAPFORGE_DISABLE_NETWORK=1 gapforge run "intentionally sparse undercovered research topic" '
                "--v3 --max-papers 4 --strict-report",
                "gapforge report --run-id {run_id} --strict",
            ],
            max_papers=4,
            max_expanded_papers=0,
            requires_network=False,
            requires_codex=False,
            requires_human_review=True,
            expected_artifacts=["source_coverage.md", "final_report.md"],
            pass_criteria=[
                "Strict report refuses to recommend a paper-ready direction under poor coverage.",
                "Coverage warnings are visible.",
                "Novelty remains unknown when closest prior work is absent.",
            ],
            known_risks=["This is a refusal/safety canary, not a useful research run."],
            provenance=_profile_provenance(now),
        ),
        CanaryRunProfile(
            id="fake_agent_regression",
            title="Fake AgentClient regression canary",
            topic="fake agent regression for CI",
            project_name="v0.3 fake agent canary",
            source_profile="generic",
            mode="fake",
            required_steps=[
                "Create an offline run.",
                "Create a Codex-compatible task pack.",
                "Run FakeAgentClient.",
                "Validate safe non-conclusive output.",
            ],
            recommended_commands=["GAPFORGE_DISABLE_NETWORK=1 gapforge canary-run --profile fake_agent_regression"],
            max_papers=2,
            max_expanded_papers=0,
            requires_network=False,
            requires_codex=False,
            requires_human_review=False,
            expected_artifacts=["state.json", "agent_tasks.md", "agent_tasks/*/TASK.md", "agent_tasks/*/validation.json"],
            pass_criteria=[
                "Fake canary completes offline.",
                "Agent validation result is valid.",
                "No research conclusion is claimed by fake output.",
            ],
            known_risks=["This does not count as actual Codex/GPT-5.4 validation."],
            provenance=_profile_provenance(now),
        ),
    ]


def get_canary_profile(profile_id: str) -> CanaryRunProfile:
    for profile in default_canary_profiles():
        if profile.id == profile_id:
            return profile
    raise KeyError(f"Unknown canary profile: {profile_id}")


def _profile_provenance(timestamp: str) -> Provenance:
    return Provenance(
        created_by_skill="canary-profile",
        timestamp=timestamp,
        reasoning_summary="Built-in canary profile for repeatable v0.3 validation.",
    )
