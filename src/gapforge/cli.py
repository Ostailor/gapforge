"""Command line interface for GapForge."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from gapforge.agents import (
    AgentRuntimeConfig,
    AgentUnavailableError,
    CodexAgentClient,
    CodexRunner,
    FakeAgentClient,
    actual_run_status,
    agent_capabilities,
    agent_status,
    create_actual_run_attestation,
    create_agent_task_spec,
)
from gapforge.agents.handoff import write_handoff
from gapforge.agents.repair import (
    create_agent_repair_task,
    find_agent_repair_record,
    render_agent_repair_status,
    repair_from_campaign_validation,
)
from gapforge.agents.setup import render_real_run_setup
from gapforge.campaigns import CampaignManager, CampaignState
from gapforge.campaigns.context_builder import inspect_task_context, write_task_context
from gapforge.campaigns.controller import CampaignController
from gapforge.campaigns.import_workflow import expected_campaign_files, find_campaign_task, validate_import_all, write_task_handoff
from gapforge.campaigns.importer import CampaignOutputImporter
from gapforge.campaigns.novelty_loop import CampaignNoveltyLoop
from gapforge.campaigns.outputs import import_campaign_outputs, validate_campaign_outputs
from gapforge.campaigns.reporting import campaign_stop_reason
from gapforge.campaigns.review import CampaignReviewManager
from gapforge.campaigns.reviewer_loop import CampaignReviewerLoop
from gapforge.campaigns.rollback import rollback_import
from gapforge.campaigns.search_agent import CampaignSearchAgent, write_campaign_search_status
from gapforge.campaigns.task_packs import CAMPAIGN_TASK_OUTPUTS, create_campaign_task_pack
from gapforge.canaries import CampaignCanaryRunManager, CanaryReviewManager, CanaryRunManager, default_canary_profiles
from gapforge.claims.project_sync import ProjectClaimGraphManager
from gapforge.config import GapForgeConfig
from gapforge.dashboard import StaticDashboardBuilder
from gapforge.diagnostics import (
    build_real_run_diagnostic,
    diagnose_canary_markdown,
    diagnose_run_agent_markdown,
    render_real_run_diagnostic_markdown,
    write_real_run_diagnostic,
)
from gapforge.directions.maturation import DirectionMaturationManager
from gapforge.evals.benchmark import run_evals
from gapforge.experiment_code import ExperimentCodeTaskGenerator, ExperimentRepoScaffolder
from gapforge.experiments.baselines import render_baseline_candidates_markdown
from gapforge.experiments.protocol import ExperimentProtocolBuilder, render_protocol_markdown
from gapforge.experiments.reproducibility import render_reproducibility_checklist
from gapforge.export.bibliography import render_bibtex
from gapforge.export.paper_package import PaperPackageExporter
from gapforge.fulltext.downloader import PdfDownloader
from gapforge.fulltext.pdf_parser import FullTextParser
from gapforge.fulltext.structure import FullTextStructureParser
from gapforge.ingest import ManualIngestor, parse_authors
from gapforge.llm.base import LLMClient
from gapforge.llm.config import LLMRuntimeConfig
from gapforge.llm.fake import FakeLLMClient
from gapforge.llm.providers import ProviderLLMClient, ProviderUnavailableError, llm_status
from gapforge.llm.transcripts import LLMTranscriptLogger
from gapforge.models import IndexManifest, ResearchProgramState, ResearchRunState, RetrievalResult, to_plain
from gapforge.orchestration.budgets import budget_from_name
from gapforge.orchestrator import Orchestrator
from gapforge.project_memory import ProjectMemoryManager
from gapforge.related_work.matrix import RelatedWorkMatrixBuilder
from gapforge.release_gate import V04ReleaseGateEnforcer, render_v04_release_gate_markdown
from gapforge.reporting import write_final_report
from gapforge.retrieval import build_project_index, build_run_index, search_project_index, search_run_index
from gapforge.retrieval.index_store import RetrievalIndexStore
from gapforge.review.audit import render_human_reviews_markdown
from gapforge.review.edits import HumanReviewEditor
from gapforge.review.queue import ReviewQueueManager, render_review_queue_markdown
from gapforge.reviewers import ReviewPanelBuilder, render_meta_review_markdown, render_rebuttal_plans_markdown, render_review_panel_markdown
from gapforge.safety import (
    audit_project_artifacts,
    audit_run_artifacts,
    clean_generated_run_artifacts,
    export_safe_project_bundle,
    render_artifact_audit_markdown,
)
from gapforge.sources.coverage import refresh_source_coverage
from gapforge.sources.http_client import cache_summary
from gapforge.sources.policies import default_source_policy_profiles, get_source_policy_profile
from gapforge.sources.stopping import refresh_stopping_assessment, render_stopping_assessment_markdown
from gapforge.state import ResearchStateManager


def _add_agent_skill_options(command_parser: argparse.ArgumentParser) -> None:
    command_parser.add_argument("--agent", choices=["codex"], default=None, help="Route this LLM skill through AgentClient.")
    command_parser.add_argument(
        "--agent-mode",
        choices=["task-pack", "manual-handoff", "fake", "codex", "direct"],
        default=None,
        help="AgentClient mode. task-pack writes files only; codex requires GAPFORGE_ENABLE_REAL_RUNS=1.",
    )
    command_parser.add_argument("--model", default="gpt-5.4", help="Agent model label for run records.")
    command_parser.add_argument("--import-output", action="append", default=None, metavar="PATH", help="Validate/import Codex output path.")
    command_parser.add_argument(
        "--validate-only", action="store_true", help="Validate imported Codex output without mutating research state."
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="gapforge",
        description="GapForge: a skills-based research ideation OS for evidence-linked research gaps.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init-topic", help="Create a durable run directory for a topic.")
    init_parser.add_argument("topic")

    run_parser = subparsers.add_parser("run", help="Run the full research loop and write final_report.md.")
    run_parser.add_argument("topic")
    run_parser.add_argument("--max-papers", type=int, default=50)
    run_parser.add_argument("--iterations", type=int, default=1)
    run_parser.add_argument("--sources", default="", help="Comma-separated sources, for example arxiv,crossref,dblp.")
    run_parser.add_argument("--dry-run", action="store_true")
    run_parser.add_argument("--v2", action="store_true", help="Use the v0.2 full-text and prior-work orchestration loop.")
    run_parser.add_argument("--v3", action="store_true", help="Use the v0.3 project-memory and active-research orchestration path.")
    run_parser.add_argument(
        "--mode",
        choices=["deterministic", "prompt-pack", "fake-agent", "llm-assisted"],
        default="deterministic",
        help="v0.3 execution mode. Deterministic is CI-safe; llm-assisted requires explicit LLM/agent configuration.",
    )
    run_parser.add_argument("--agent", choices=["codex", "fake", "none"], default="none", help="Optional v0.3 AgentClient backend.")
    run_parser.add_argument("--model", default="gpt-5.4", help="Model label for Codex/GPT-5.4 agent run records.")
    run_parser.add_argument("--project-id", default="", help="Attach the v0.3 run to a project memory workspace.")
    run_parser.add_argument("--source-profile", default="", help="Source policy profile, for example ai_safety or medicine.")
    run_parser.add_argument("--active", action="store_true", help="Use the v0.3 active loop instead of the staged v0.3 plan.")
    run_parser.add_argument("--download-pdfs", action="store_true", help="Include PDF download before deep reading.")
    run_parser.add_argument("--parse-fulltext", action="store_true", help="Include full-text parsing before deep reading.")
    run_parser.add_argument("--deep-novelty", action="store_true", help="Run closest-prior-work dossiers instead of shallow novelty.")
    run_parser.add_argument("--strict-report", action="store_true", help="Use strict final-report recommendation gating.")
    run_parser.add_argument("--skip-pdf-download", action="store_true", help="Skip v0.2 PDF download while recording coverage warnings.")
    run_parser.add_argument("--max-expanded-papers", type=int, default=30)
    run_parser.add_argument("--llm-reading", action="store_true", help="Use optional LLM-backed deep reading when LLM mode permits it.")
    run_parser.add_argument("--llm-gaps", action="store_true", help="Use optional LLM-backed gap mining when LLM mode permits it.")
    run_parser.add_argument(
        "--llm-novelty", action="store_true", help="Use optional LLM-assisted novelty dossiers when LLM mode permits it."
    )
    run_parser.add_argument("--llm-review", action="store_true", help="Use optional LLM-assisted review panels when LLM mode permits it.")
    run_parser.add_argument("--agent-task-pack", action="store_true", help="Write Codex task packs for selected LLM skill flags.")
    run_parser.add_argument(
        "--require-real-agent",
        action="store_true",
        help="Fail if actual Codex execution is unavailable instead of falling back to task-pack mode.",
    )
    run_parser.add_argument("--build-index", action="store_true", help="Build a v0.3 hybrid retrieval index during the run.")
    run_parser.add_argument("--mature-directions", action="store_true", help="Create and mature project research directions.")
    run_parser.add_argument("--export-package", action="store_true", help="Export paper packages for eligible mature directions.")
    run_parser.add_argument("--dashboard", action="store_true", help="Generate a static dashboard after the run.")
    run_parser.add_argument("--budget", choices=["small", "medium", "large"], default="small", help="v0.3 active-loop budget preset.")
    run_parser.add_argument("--canary-profile", default="", help="Built-in canary profile ID to associate with this v0.3 run.")
    run_parser.add_argument("--record-canary", action="store_true", help="Record this v0.3 run as a canary for human review.")

    active_run_parser = subparsers.add_parser("run-active", help="Run the v0.3 active research loop.")
    active_run_parser.add_argument("topic")
    active_run_parser.add_argument("--project-id", default="")
    active_run_parser.add_argument("--budget", choices=["small", "medium", "large"], default="small")
    active_run_parser.add_argument("--profile", default="", help="Optional source policy profile, for example ai_safety.")

    active_status_parser = subparsers.add_parser("active-status", help="Print active-loop status as JSON.")
    active_status_parser.add_argument("--run-id", required=True)

    active_decisions_parser = subparsers.add_parser("active-decisions", help="Print active-loop decision log.")
    active_decisions_parser.add_argument("--run-id", required=True)

    map_parser = subparsers.add_parser("map", help="Build a field map for a topic or existing run.")
    map_parser.add_argument("topic", nargs="?")
    map_parser.add_argument("--run-id", default=None)

    triage_parser = subparsers.add_parser("triage", help="Rank papers into reading-depth tiers.")
    triage_parser.add_argument("topic", nargs="?")
    triage_parser.add_argument("--run-id", default=None)
    triage_parser.add_argument("--max-tier1", type=int, default=20)

    rank_parser = subparsers.add_parser("rank-papers", help="Rank papers with v0.2 role and diversity scoring.")
    rank_parser.add_argument("--run-id", required=True)
    rank_parser.add_argument("--query-purpose", default="initial_topic")
    rank_parser.add_argument("--recency-preference", choices=["newest", "canonical"], default="newest")
    rank_parser.add_argument("--source-diversity-target", type=int, default=2)
    rank_parser.add_argument("--role-diversity-target", type=int, default=2)

    read_parser = subparsers.add_parser("read", help="Create abstract-aware paper notes for selected papers.")
    read_parser.add_argument("--run-id", default=None)
    read_parser.add_argument("--tier", type=int, default=None)
    read_parser.add_argument("--paper-id", default=None)
    read_parser.add_argument("--fulltext-only", action="store_true")
    read_parser.add_argument("--allow-abstract-only", action=argparse.BooleanOptionalAction, default=True)

    read_llm_parser = subparsers.add_parser("read-llm", help="Run optional locator-grounded LLM deep reading.")
    read_llm_parser.add_argument("--run-id", required=True)
    read_llm_parser.add_argument("--paper-id", default=None)
    read_llm_parser.add_argument("--tier", type=int, default=None)
    read_llm_parser.add_argument("--dry-run-prompts", action="store_true")
    read_llm_parser.add_argument("--fake", action="store_true")
    _add_agent_skill_options(read_llm_parser)

    mine_parser = subparsers.add_parser("mine-gaps", help="Mine evidence-linked research gaps.")
    mine_parser.add_argument("--run-id", required=True)
    mine_parser.add_argument("--min-confidence", choices=["low", "medium", "high"], default="low")
    mine_parser.add_argument("--include-low-confidence", action="store_true")
    mine_parser.add_argument("--force", action="store_true", help="Overwrite locked generated gap artifacts.")

    mine_llm_parser = subparsers.add_parser("mine-gaps-llm", help="Run optional retrieval-grounded LLM gap mining.")
    mine_llm_parser.add_argument("--run-id", required=True)
    mine_llm_parser.add_argument("--fake", action="store_true")
    mine_llm_parser.add_argument("--dry-run-prompts", action="store_true")
    mine_llm_parser.add_argument("--force", action="store_true", help="Ignore automated lock preservation for generated gaps.")
    _add_agent_skill_options(mine_llm_parser)

    analogies_parser = subparsers.add_parser("analogies", help="Generate skeptical cross-domain analogy queries.")
    analogies_parser.add_argument("--run-id", required=True)
    analogies_parser.add_argument("--search", action="store_true")
    analogies_parser.add_argument("--promote-evidence-only", action="store_true")

    novelty_parser = subparsers.add_parser("novelty-check", help="Check candidate gaps against closest prior work.")
    novelty_parser.add_argument("--run-id", default=None)
    novelty_parser.add_argument("--gap-id", default=None)
    novelty_parser.add_argument("--deep", action="store_true")

    novelty_llm_parser = subparsers.add_parser("novelty-check-llm", help="Run optional LLM-assisted novelty dossiers.")
    novelty_llm_parser.add_argument("--run-id", required=True)
    novelty_llm_parser.add_argument("--gap-id", default=None)
    novelty_llm_parser.add_argument("--all", action="store_true")
    novelty_llm_parser.add_argument("--fake", action="store_true")
    novelty_llm_parser.add_argument("--dry-run-prompts", action="store_true")
    _add_agent_skill_options(novelty_llm_parser)

    novelty_dossier_parser = subparsers.add_parser("novelty-dossier", help="Write or refresh a closest-prior-work dossier.")
    novelty_dossier_parser.add_argument("--run-id", required=True)
    novelty_dossier_parser.add_argument("--gap-id", required=True)

    design_all_parser = subparsers.add_parser("design-experiments", help="Convert non-rejected gaps into experiment plans.")
    design_all_parser.add_argument("--run-id", required=True)
    design_all_parser.add_argument("--allow-rejected", action="store_true")
    design_all_parser.add_argument("--force", action="store_true", help="Overwrite locked generated experiment artifacts.")

    design_one_parser = subparsers.add_parser("design-experiment", help="Design an experiment for one gap.")
    design_one_parser.add_argument("--run-id", default=None)
    design_one_parser.add_argument("--gap-id", required=True)
    design_one_parser.add_argument("--allow-rejected", action="store_true")
    design_one_parser.add_argument("--force", action="store_true", help="Overwrite locked generated experiment artifacts.")

    review_parser = subparsers.add_parser("review", help="Simulate serious conference-review objections.")
    review_parser.add_argument("--run-id", default=None)
    review_parser.add_argument("--experiment-id", default=None)
    _add_agent_skill_options(review_parser)

    download_parser = subparsers.add_parser("download-pdfs", help="Download available PDFs for papers in a run.")
    download_parser.add_argument("--run-id", required=True)
    download_parser.add_argument("--paper-id", default=None)
    download_parser.add_argument("--max-papers", type=int, default=None)
    download_parser.add_argument("--skip-existing", action="store_true")

    parse_parser = subparsers.add_parser("parse-fulltext", help="Extract PDF text and sectionize available paper artifacts.")
    parse_parser.add_argument("--run-id", required=True)
    parse_parser.add_argument("--paper-id", default=None)

    parse_structure_parser = subparsers.add_parser(
        "parse-structure",
        help="Extract references, tables, equations, captions, and OCR status.",
    )
    parse_structure_parser.add_argument("--run-id", required=True)

    parse_references_parser = subparsers.add_parser("parse-references", help="Extract parsed references from full-text sections.")
    parse_references_parser.add_argument("--run-id", required=True)

    parse_tables_parser = subparsers.add_parser("parse-tables", help="Extract table-like text and captions from full-text sections.")
    parse_tables_parser.add_argument("--run-id", required=True)

    ocr_status_parser = subparsers.add_parser("ocr-status", help="Record and print optional OCR recommendations.")
    ocr_status_parser.add_argument("--run-id", required=True)

    add_paper_parser = subparsers.add_parser("add-paper", help="Manually add or merge paper metadata into a run.")
    add_paper_parser.add_argument("--run-id", required=True)
    add_paper_parser.add_argument("--title", required=True)
    add_paper_parser.add_argument("--authors", default="")
    add_paper_parser.add_argument("--year", type=int, default=0)
    add_paper_parser.add_argument("--url", default="")
    add_paper_parser.add_argument("--pdf-url", default="")
    add_paper_parser.add_argument("--doi", default="")
    add_paper_parser.add_argument("--arxiv-id", default="")

    add_arxiv_parser = subparsers.add_parser("add-arxiv", help="Add or merge a paper by arXiv ID.")
    add_arxiv_parser.add_argument("--run-id", required=True)
    add_arxiv_parser.add_argument("arxiv_id")

    add_doi_parser = subparsers.add_parser("add-doi", help="Add or merge a paper by DOI.")
    add_doi_parser.add_argument("--run-id", required=True)
    add_doi_parser.add_argument("doi")

    add_pdf_parser = subparsers.add_parser("add-pdf", help="Add a local PDF artifact and optional metadata.")
    add_pdf_parser.add_argument("--run-id", required=True)
    add_pdf_parser.add_argument("pdf_path")
    add_pdf_parser.add_argument("--title", default="")
    add_pdf_parser.add_argument("--authors", default="")
    add_pdf_parser.add_argument("--year", type=int, default=0)
    add_pdf_parser.add_argument("--parse", action="store_true")

    add_url_parser = subparsers.add_parser("add-url", help="Add an arbitrary URL as manually supplied metadata.")
    add_url_parser.add_argument("--run-id", required=True)
    add_url_parser.add_argument("url")

    resume_parser = subparsers.add_parser("resume", help="Resume a previously interrupted run.")
    resume_parser.add_argument("--run-id", required=True)

    status_parser = subparsers.add_parser("status", help="Print orchestrator status as JSON.")
    status_parser.add_argument("--run-id", required=True)

    search_parser = subparsers.add_parser("search", help="Search source connectors and write papers.json.")
    search_parser.add_argument("topic")
    search_parser.add_argument("--max-results", type=int, default=20)
    search_parser.add_argument("--sources", default="", help="Comma-separated sources, for example arxiv,crossref,dblp.")
    search_parser.add_argument("--newest-first", action="store_true", default=True)
    search_parser.add_argument("--date-from", default=None)
    search_parser.add_argument("--date-to", default=None)

    eval_parser = subparsers.add_parser("eval", help="Run offline fixture evaluations.")
    eval_parser.add_argument("--fixture", default=None)
    eval_parser.add_argument("--v2", action="store_true", help="Run v0.2 full-text/evidence/dossier evaluation fixtures.")
    eval_parser.add_argument("--v3", action="store_true", help="Run v0.3 curated real-world-style evaluation fixtures.")
    eval_parser.add_argument("--v4", action="store_true", help="Run v0.4 campaign and agent-behavior evaluation fixtures.")
    eval_parser.add_argument("--write-report", action="store_true")

    report_parser = subparsers.add_parser("report", help="Write final_report.md or final_report.json.")
    report_parser.add_argument("--run-id", default="latest", help="Run ID to report on, or 'latest' (default).")
    report_parser.add_argument("--format", choices=["markdown", "json"], default="markdown")
    report_parser.add_argument(
        "--strict",
        action="store_true",
        help="Refuse to recommend a top direction when coverage/evidence/novelty gates are weak.",
    )

    dashboard_parser = subparsers.add_parser("dashboard", help="Generate a static HTML dashboard for a run or project.")
    dashboard_scope = dashboard_parser.add_mutually_exclusive_group(required=True)
    dashboard_scope.add_argument("--run-id")
    dashboard_scope.add_argument("--project-id")
    dashboard_parser.add_argument("--open", action="store_true", help="Open the dashboard in the default browser.")
    dashboard_parser.add_argument("--include-actual-runs", action="store_true", help="Include v0.4 actual-run acceptance pages.")

    release_gate_dashboard_parser = subparsers.add_parser(
        "release-gate-dashboard", help="Generate a project dashboard and print the release-gate page path."
    )
    release_gate_dashboard_parser.add_argument("--project-id", required=True)

    review_queue_parser = subparsers.add_parser("review-queue", help="Build and print the human review queue.")
    review_queue_scope = review_queue_parser.add_mutually_exclusive_group(required=True)
    review_queue_scope.add_argument("--project-id")
    review_queue_scope.add_argument("--run-id")

    complete_review_item_parser = subparsers.add_parser("complete-review-item", help="Mark a project review queue item completed.")
    complete_review_item_parser.add_argument("--project-id", required=True)
    complete_review_item_parser.add_argument("--item-id", required=True)
    complete_review_item_parser.add_argument("--note", default="")
    complete_review_item_parser.add_argument("--reviewer", default="human")

    dismiss_review_item_parser = subparsers.add_parser(
        "dismiss-review-item", help="Dismiss a project review queue item with an audit note."
    )
    dismiss_review_item_parser.add_argument("--project-id", required=True)
    dismiss_review_item_parser.add_argument("--item-id", required=True)
    dismiss_review_item_parser.add_argument("--reason", required=True)
    dismiss_review_item_parser.add_argument("--reviewer", default="human")

    coverage_parser = subparsers.add_parser("coverage", help="Regenerate source and full-text coverage reports.")
    coverage_parser.add_argument("--run-id", default="latest", help="Run ID to cover, or 'latest' (default).")

    source_policy_parser = subparsers.add_parser("source-policy", help="Inspect or apply a field-specific source policy.")
    source_policy_parser.add_argument("--list", action="store_true", help="List built-in source policy profiles.")
    source_policy_parser.add_argument("--run-id", default=None)
    source_policy_parser.add_argument("--profile", default=None)

    assess_coverage_parser = subparsers.add_parser("assess-coverage", help="Evaluate whether literature coverage is sufficient.")
    assess_coverage_parser.add_argument("--run-id", required=True)
    assess_coverage_parser.add_argument("--profile", default=None)

    next_searches_parser = subparsers.add_parser("next-searches", help="Print policy-recommended next source searches.")
    next_searches_parser.add_argument("--run-id", required=True)

    graph_parser = subparsers.add_parser("build-citation-graph", help="Build citation graph from available paper metadata.")
    graph_parser.add_argument("--run-id", required=True)

    expand_parser = subparsers.add_parser("expand-related-work", help="Run conservative citation/related-work expansion searches.")
    expand_parser.add_argument("--run-id", required=True)
    expand_parser.add_argument("--max-new-papers", type=int, default=30)
    expand_parser.add_argument("--paper-id", default=None)

    list_gaps_parser = subparsers.add_parser("list-gaps", help="List gap candidates with human review status.")
    list_gaps_parser.add_argument("--run-id", required=True)

    approve_gap_parser = subparsers.add_parser("approve-gap", help="Record a human approval for a gap.")
    approve_gap_parser.add_argument("--run-id", required=True)
    approve_gap_parser.add_argument("--gap-id", required=True)
    approve_gap_parser.add_argument("--note", default="")
    approve_gap_parser.add_argument("--reviewer", default="human")

    reject_gap_parser = subparsers.add_parser("reject-gap", help="Record a human rejection for a gap.")
    reject_gap_parser.add_argument("--run-id", required=True)
    reject_gap_parser.add_argument("--gap-id", required=True)
    reject_gap_parser.add_argument("--reason", required=True)
    reject_gap_parser.add_argument("--reviewer", default="human")

    annotate_claim_parser = subparsers.add_parser("annotate-claim", help="Attach a human note to a claim.")
    annotate_claim_parser.add_argument("--run-id", required=True)
    annotate_claim_parser.add_argument("--claim-id", required=True)
    annotate_claim_parser.add_argument("--note", required=True)
    annotate_claim_parser.add_argument("--reviewer", default="human")

    mark_claim_parser = subparsers.add_parser("mark-claim", help="Change a claim status with an audit record.")
    mark_claim_parser.add_argument("--run-id", required=True)
    mark_claim_parser.add_argument("--claim-id", required=True)
    mark_claim_parser.add_argument("--status", choices=["supported", "contested", "uncertain", "falsified"], required=True)
    mark_claim_parser.add_argument("--reviewer", default="human")

    add_evidence_parser = subparsers.add_parser("add-evidence", help="Add manual evidence to a claim.")
    add_evidence_parser.add_argument("--run-id", required=True)
    add_evidence_parser.add_argument("--claim-id", required=True)
    add_evidence_parser.add_argument("--paper-id", required=True)
    add_evidence_parser.add_argument("--quote", required=True)
    add_evidence_parser.add_argument("--locator", default="")
    add_evidence_parser.add_argument("--reviewer", default="human")

    lock_object_parser = subparsers.add_parser("lock-object", help="Lock or unlock a reviewed object against automated overwrite.")
    lock_object_parser.add_argument("--run-id", required=True)
    lock_object_parser.add_argument("--object-type", required=True)
    lock_object_parser.add_argument("--object-id", required=True)
    lock_object_parser.add_argument("--note", default="")
    lock_object_parser.add_argument("--reviewer", default="human")
    lock_object_parser.add_argument("--unlock", action="store_true")
    lock_object_parser.add_argument("--force", action="store_true")

    audit_log_parser = subparsers.add_parser("audit-log", help="Print the human review audit log.")
    audit_log_parser.add_argument("--run-id", required=True)

    prompt_pack_parser = subparsers.add_parser("prompt-pack", help="Write a Codex-readable prompt pack for an optional LLM skill.")
    prompt_pack_parser.add_argument("--run-id", required=True)
    prompt_pack_parser.add_argument("--skill", required=True, choices=["deep-reading", "gap-mining", "novelty-gate", "reviewer-simulation"])
    prompt_pack_parser.add_argument("--gap-id", default=None)

    subparsers.add_parser("agent-status", help="Show optional AgentClient configuration and readiness.")

    subparsers.add_parser("setup-real-run", help="Print setup guidance for real Codex/GPT-5.4 runs.")

    agent_capabilities_parser = subparsers.add_parser("agent-capabilities", help="Show v0.4 AgentClient runtime capabilities.")
    agent_capabilities_parser.add_argument("--json", action="store_true")

    task_handoff_parser = subparsers.add_parser("task-handoff", help="Write HANDOFF.md for a run or campaign agent task.")
    task_handoff_parser.add_argument("--task-id", required=True)

    repair_agent_output_parser = subparsers.add_parser("repair-agent-output", help="Explain how to fix invalid agent output.")
    repair_agent_output_parser.add_argument("--task-id", required=True)
    repair_agent_output_parser.add_argument("--path", action="append", default=[])
    repair_agent_output_parser.add_argument("--handoff", action="store_true")

    repair_status_parser = subparsers.add_parser("repair-status", help="Print an agent repair record.")
    repair_status_parser.add_argument("--repair-id", required=True)

    agent_task_parser = subparsers.add_parser("agent-task", help="Create a Codex/GPT-5.4 task pack for a research skill.")
    agent_task_parser.add_argument("--run-id", required=True)
    agent_task_parser.add_argument(
        "--skill",
        required=True,
        choices=["deep-reading", "gap-mining", "novelty-gate", "reviewer-simulation", "related-work", "manuscript"],
    )
    agent_task_parser.add_argument("--gap-id", default="")
    agent_task_parser.add_argument("--paper-id", default="")
    agent_task_parser.add_argument("--project-id", default="")

    agent_run_parser = subparsers.add_parser("agent-run", help="Run or prepare an existing AgentClient task.")
    agent_run_parser.add_argument("--task-id", required=True)
    agent_run_parser.add_argument("--fake", action="store_true", help="Use FakeAgentClient regardless of environment.")

    agent_import_parser = subparsers.add_parser("agent-import-output", help="Validate and import agent output metadata.")
    agent_import_parser.add_argument("--task-id", required=True)
    agent_import_parser.add_argument("--path", action="append", required=True)

    agent_validate_parser = subparsers.add_parser("agent-validate-output", help="Validate agent output without importing it.")
    agent_validate_parser.add_argument("--task-id", required=True)
    agent_validate_parser.add_argument("--path", action="append")

    attest_agent_run_parser = subparsers.add_parser(
        "attest-agent-run", help="Attest that a validated agent output came from Codex/GPT-5.4."
    )
    attest_agent_run_parser.add_argument("--task-id", required=True)
    attest_agent_run_parser.add_argument("--agent", required=True)
    attest_agent_run_parser.add_argument("--model", required=True)
    attest_agent_run_parser.add_argument(
        "--method",
        required=True,
        choices=["direct", "task_pack", "task-pack", "manual_handoff", "manual-handoff", "fake"],
    )
    attest_agent_run_parser.add_argument("--attester", required=True)
    attest_agent_run_parser.add_argument("--statement", default="")

    actual_run_status_parser = subparsers.add_parser(
        "actual-run-status", help="Report whether a run has auditable actual-agent acceptance."
    )
    actual_run_status_parser.add_argument("--run-id", required=True)

    codex_task_parser = subparsers.add_parser("codex-task", help="Create a Codex-compatible research task pack.")
    codex_task_parser.add_argument("--run-id", required=True)
    codex_task_parser.add_argument(
        "--skill",
        required=True,
        choices=["deep-reading", "gap-mining", "novelty-gate", "reviewer-simulation", "related-work", "manuscript"],
    )
    codex_task_parser.add_argument("--gap-id", default="")
    codex_task_parser.add_argument("--paper-id", default="")
    codex_task_parser.add_argument("--project-id", default="")

    validate_agent_output_parser = subparsers.add_parser("validate-agent-output", help="Validate outputs in a Codex task outputs/ dir.")
    validate_agent_output_parser.add_argument("--task-id", required=True)

    import_agent_output_parser = subparsers.add_parser(
        "import-agent-output", help="Import outputs in a Codex task outputs/ dir after validation."
    )
    import_agent_output_parser.add_argument("--task-id", required=True)

    list_agent_tasks_parser = subparsers.add_parser("list-agent-tasks", help="List Codex/GPT-5.4 agent task packs for a run.")
    list_agent_tasks_parser.add_argument("--run-id", required=True)

    codex_run_parser = subparsers.add_parser("codex-run", help="Run a Codex task through direct command or handoff mode.")
    codex_run_parser.add_argument("--task-id", required=True)
    codex_run_parser.add_argument("--direct", action="store_true", help="Prefer the configured direct Codex command path.")
    codex_run_parser.add_argument("--handoff", action="store_true", help="Write explicit handoff instructions instead of running directly.")
    codex_run_parser.add_argument("--require-direct", action="store_true", help="Fail if the direct Codex command path is unavailable.")

    codex_run_status_parser = subparsers.add_parser("codex-run-status", help="Print a Codex runner AgentRunRecord.")
    codex_run_status_parser.add_argument("--agent-run-id", required=True)

    subparsers.add_parser("canary-list", help="List v0.3 canary run profiles.")

    subparsers.add_parser("campaign-canary-list", help="List v0.4 campaign canary profiles.")

    campaign_canary_plan_parser = subparsers.add_parser("campaign-canary-plan", help="Print a v0.4 campaign canary plan.")
    campaign_canary_plan_parser.add_argument("--profile", required=True)

    campaign_canary_run_parser = subparsers.add_parser("campaign-canary-run", help="Run or record a v0.4 campaign canary.")
    campaign_canary_run_parser.add_argument("--profile", required=True)
    campaign_canary_run_parser.add_argument("--real", action="store_true", help="Allow real Codex/GPT-5.4 campaign canary gates.")

    campaign_canary_status_parser = subparsers.add_parser("campaign-canary-status", help="Print a campaign canary record.")
    campaign_canary_status_parser.add_argument("--canary-id", required=True)

    canary_plan_parser = subparsers.add_parser("canary-plan", help="Print a repeatable canary run plan.")
    canary_plan_parser.add_argument("--profile", required=True)

    canary_run_parser = subparsers.add_parser("canary-run", help="Run or record a v0.3 canary profile.")
    canary_run_parser.add_argument("--profile", required=True)
    canary_run_parser.add_argument("--real", action="store_true", help="Allow real Codex/GPT-5.4 canary execution gate.")

    canary_status_parser = subparsers.add_parser("canary-status", help="Print a canary run record as JSON.")
    canary_status_parser.add_argument("--canary-id", required=True)

    canary_artifacts_parser = subparsers.add_parser("canary-artifacts", help="List artifacts for a canary run record.")
    canary_artifacts_parser.add_argument("--canary-id", required=True)

    canary_review_parser = subparsers.add_parser("canary-review", help="Render or record human review for a canary.")
    canary_review_parser.add_argument("--canary-id", required=True)
    canary_review_parser.add_argument("--reviewer", default="human")
    canary_review_action = canary_review_parser.add_mutually_exclusive_group()
    canary_review_action.add_argument("--accept", action="store_true")
    canary_review_action.add_argument("--reject", action="store_true")
    canary_review_parser.add_argument("--reason", default="")
    canary_review_parser.add_argument("--notes", default="")
    canary_review_parser.add_argument("--source-coverage-score", type=int, default=0)
    canary_review_parser.add_argument("--full-text-grounding-score", type=int, default=0)
    canary_review_parser.add_argument("--citation-grounding-score", type=int, default=0)
    canary_review_parser.add_argument("--novelty-honesty-score", type=int, default=0)
    canary_review_parser.add_argument("--gap-quality-score", type=int, default=0)
    canary_review_parser.add_argument("--experiment-quality-score", type=int, default=0)
    canary_review_parser.add_argument("--uncertainty-visibility-score", type=int, default=0)
    canary_review_parser.add_argument("--fake-citation-found", action="store_true")
    canary_review_parser.add_argument("--unsupported-high-confidence-claim-found", action="store_true")
    canary_review_parser.add_argument("--obvious-prior-work-missed", action="store_true")
    canary_review_parser.add_argument("--strict-report-overclaimed", action="store_true")

    canary_summary_parser = subparsers.add_parser("canary-summary", help="Print canary acceptance summary.")
    canary_summary_parser.add_argument("--canary-id", required=True)

    subparsers.add_parser("real-run-acceptance", help="Report whether v0.3 actual-run acceptance has passed.")

    diagnose_real_run_parser = subparsers.add_parser(
        "diagnose-real-run", help="Explain why actual Codex/GPT-5.4 real-run acceptance is blocked."
    )
    diagnose_real_run_parser.add_argument("--json", action="store_true", help="Print the diagnostic as JSON.")
    diagnose_real_run_parser.add_argument("--write-report", action="store_true", help="Write JSON and Markdown diagnostic artifacts.")

    diagnose_agent_parser = subparsers.add_parser("diagnose-agent", help="Diagnose AgentClient readiness for a run.")
    diagnose_agent_parser.add_argument("--run-id", required=True)

    diagnose_canary_parser = subparsers.add_parser("diagnose-canary", help="Diagnose a canary run record.")
    diagnose_canary_parser.add_argument("--canary-id", required=True)

    init_project_parser = subparsers.add_parser("init-project", help="Create a v0.3 project memory workspace.")
    init_project_parser.add_argument("name")
    init_project_parser.add_argument("--description", default="")

    subparsers.add_parser("list-projects", help="List project memory workspaces.")

    use_project_parser = subparsers.add_parser("use-project", help="Set the active project memory workspace.")
    use_project_parser.add_argument("project_id")

    project_status_parser = subparsers.add_parser("project-status", help="Print project memory status.")
    project_status_parser.add_argument("--project-id", required=True)

    project_report_parser = subparsers.add_parser("project-report", help="Write a project-level memory report.")
    project_report_parser.add_argument("--project-id", required=True)

    campaign_create_parser = subparsers.add_parser("campaign-create", help="Create a v0.4 research campaign.")
    campaign_create_parser.add_argument("topic")
    campaign_create_parser.add_argument("--project-id", required=True)
    campaign_create_parser.add_argument("--title", default="")
    campaign_create_parser.add_argument(
        "--mode",
        default="deterministic",
        choices=["deterministic", "fake_agent", "codex_task_pack", "codex_direct", "manual_handoff"],
    )
    campaign_create_parser.add_argument("--agent-name", default="")
    campaign_create_parser.add_argument("--model", default="")
    campaign_create_parser.add_argument("--source-profile", default="generic")
    campaign_create_parser.add_argument("--budget-id", default="small")

    campaign_status_parser = subparsers.add_parser("campaign-status", help="Print campaign status as JSON.")
    campaign_status_parser.add_argument("--campaign-id", required=True)

    campaign_report_parser = subparsers.add_parser("campaign-report", help="Write a campaign report.")
    campaign_report_parser.add_argument("--campaign-id", required=True)
    campaign_report_parser.add_argument("--format", choices=["markdown", "json"], default="markdown")

    campaign_stop_reason_parser = subparsers.add_parser("campaign-stop-reason", help="Print the normalized campaign stop reason.")
    campaign_stop_reason_parser.add_argument("--campaign-id", required=True)

    campaign_steps_parser = subparsers.add_parser("campaign-steps", help="List campaign steps.")
    campaign_steps_parser.add_argument("--campaign-id", required=True)

    campaign_decisions_parser = subparsers.add_parser("campaign-decisions", help="List campaign decisions.")
    campaign_decisions_parser.add_argument("--campaign-id", required=True)

    campaign_run_parser = subparsers.add_parser("campaign-run", help="Run the v0.4 campaign controller.")
    campaign_run_parser.add_argument("--campaign-id", required=True)
    campaign_run_parser.add_argument(
        "--mode",
        choices=["deterministic", "fake_agent", "codex_task_pack", "codex_direct", "manual_handoff"],
        default=None,
    )
    campaign_run_parser.add_argument("--max-iterations", type=int, default=None)

    campaign_next_parser = subparsers.add_parser("campaign-next", help="Preview the next v0.4 campaign controller action.")
    campaign_next_parser.add_argument("--campaign-id", required=True)

    campaign_stop_parser = subparsers.add_parser("campaign-stop", help="Pause a campaign with an explicit reason.")
    campaign_stop_parser.add_argument("--campaign-id", required=True)
    campaign_stop_parser.add_argument("--reason", required=True)

    campaign_resume_parser = subparsers.add_parser("campaign-resume", help="Resume a paused campaign.")
    campaign_resume_parser.add_argument("--campaign-id", required=True)

    campaign_task_parser = subparsers.add_parser("campaign-task", help="Create a campaign-level Codex/GPT-5.4 task pack.")
    campaign_task_parser.add_argument("--campaign-id", required=True)
    campaign_task_parser.add_argument("--type", required=True, choices=sorted(CAMPAIGN_TASK_OUTPUTS))

    build_task_context_parser = subparsers.add_parser("build-task-context", help="Build retrieval-selected context for a campaign task.")
    build_task_context_parser.add_argument("--campaign-id", required=True)
    build_task_context_parser.add_argument("--task-type", required=True, choices=sorted(CAMPAIGN_TASK_OUTPUTS))
    build_task_context_parser.add_argument("--budget", choices=["small", "medium", "large"], default="medium")

    inspect_task_context_parser = subparsers.add_parser("inspect-task-context", help="Print task_context.json for a campaign task.")
    inspect_task_context_parser.add_argument("--task-id", required=True)

    campaign_validate_parser = subparsers.add_parser("campaign-validate-output", help="Validate campaign task output patches.")
    campaign_validate_parser.add_argument("--campaign-id", required=True)
    campaign_validate_parser.add_argument("--task-id", required=True)
    campaign_validate_parser.add_argument("--path", action="append", default=[])

    campaign_import_parser = subparsers.add_parser("campaign-import-output", help="Import validated campaign task output patches.")
    campaign_import_parser.add_argument("--campaign-id", required=True)
    campaign_import_parser.add_argument("--task-id", required=True)
    campaign_import_parser.add_argument("--path", action="append", default=[])
    campaign_import_parser.add_argument("--dry-run", action="store_true")

    campaign_imports_parser = subparsers.add_parser("campaign-imports", help="List campaign import records.")
    campaign_imports_parser.add_argument("--campaign-id", required=True)

    validate_import_all_parser = subparsers.add_parser("validate-import-all", help="Validate and import all pending campaign task outputs.")
    validate_import_all_parser.add_argument("--campaign-id", required=True)

    campaign_propose_searches_parser = subparsers.add_parser(
        "campaign-propose-searches", help="Create validated campaign literature search requests."
    )
    campaign_propose_searches_parser.add_argument("--campaign-id", required=True)

    campaign_execute_searches_parser = subparsers.add_parser(
        "campaign-execute-searches", help="Execute validated campaign search requests through GapForge sources."
    )
    campaign_execute_searches_parser.add_argument("--campaign-id", required=True)

    campaign_search_status_parser = subparsers.add_parser("campaign-search-status", help="Print campaign search request status.")
    campaign_search_status_parser.add_argument("--campaign-id", required=True)

    novelty_loop_parser = subparsers.add_parser("novelty-loop", help="Run iterative novelty re-search for a campaign.")
    novelty_loop_parser.add_argument("--campaign-id", required=True)
    novelty_loop_parser.add_argument("--gap-id", default="")

    novelty_loop_status_parser = subparsers.add_parser("novelty-loop-status", help="Print novelty re-search loop status.")
    novelty_loop_status_parser.add_argument("--campaign-id", required=True)

    reviewer_loop_parser = subparsers.add_parser("reviewer-loop", help="Run campaign-level reviewer and rebuttal loop.")
    reviewer_loop_parser.add_argument("--campaign-id", required=True)
    reviewer_loop_parser.add_argument("--direction-id", required=True)

    rebuttal_tasks_parser = subparsers.add_parser("rebuttal-tasks", help="Print campaign reviewer rebuttal/fix tasks.")
    rebuttal_tasks_parser.add_argument("--campaign-id", required=True)
    rebuttal_tasks_parser.add_argument("--direction-id", required=True)

    apply_reviewer_fixes_parser = subparsers.add_parser(
        "apply-reviewer-fixes", help="Convert campaign reviewer fixes into decisions and review queue items."
    )
    apply_reviewer_fixes_parser.add_argument("--campaign-id", required=True)
    apply_reviewer_fixes_parser.add_argument("--direction-id", required=True)

    campaign_review_parser = subparsers.add_parser("campaign-review", help="Render or record campaign-level human review.")
    campaign_review_parser.add_argument("--campaign-id", required=True)
    campaign_review_action = campaign_review_parser.add_mutually_exclusive_group()
    campaign_review_action.add_argument("--accept", action="store_true")
    campaign_review_action.add_argument("--reject", action="store_true")
    campaign_review_parser.add_argument("--reviewer", default="human")
    campaign_review_parser.add_argument("--reason", default="")
    campaign_review_parser.add_argument("--notes", default="")
    campaign_review_parser.add_argument("--source-coverage-score", type=int, default=0)
    campaign_review_parser.add_argument("--full-text-grounding-score", type=int, default=0)
    campaign_review_parser.add_argument("--citation-grounding-score", type=int, default=0)
    campaign_review_parser.add_argument("--retrieval-quality-score", type=int, default=0)
    campaign_review_parser.add_argument("--novelty-honesty-score", type=int, default=0)
    campaign_review_parser.add_argument("--gap-quality-score", type=int, default=0)
    campaign_review_parser.add_argument("--related-work-quality-score", type=int, default=0)
    campaign_review_parser.add_argument("--experiment-quality-score", type=int, default=0)
    campaign_review_parser.add_argument("--reviewer-panel-quality-score", type=int, default=0)
    campaign_review_parser.add_argument("--uncertainty-visibility-score", type=int, default=0)
    campaign_review_parser.add_argument("--stop-reason-quality-score", type=int, default=0)
    campaign_review_parser.add_argument("--fake-citation-found", action="store_true")
    campaign_review_parser.add_argument("--unsupported-high-confidence-claim-found", action="store_true")
    campaign_review_parser.add_argument("--obvious-prior-work-missed", action="store_true")
    campaign_review_parser.add_argument("--overclaimed-novelty", action="store_true")

    campaign_acceptance_parser = subparsers.add_parser("campaign-acceptance", help="Print campaign acceptance summary.")
    campaign_acceptance_parser.add_argument("--campaign-id", required=True)

    subparsers.add_parser("v4-actual-run-acceptance", help="Report v0.4 campaign-level actual-run acceptance status.")

    v4_release_gate_parser = subparsers.add_parser("v4-release-gate", help="Enforce the v0.4 actual-run release gate.")
    v4_release_gate_parser.add_argument("--project-id", default="")
    v4_release_gate_parser.add_argument("--write-report", action="store_true")
    v4_release_gate_parser.add_argument("--json", action="store_true")

    rollback_import_parser = subparsers.add_parser("rollback-import", help="Rollback a campaign import by import ID.")
    rollback_import_parser.add_argument("--import-id", required=True)

    attach_run_parser = subparsers.add_parser("attach-run", help="Attach an existing run to a project memory workspace.")
    attach_run_parser.add_argument("--project-id", required=True)
    attach_run_parser.add_argument("--run-id", required=True)

    sync_project_parser = subparsers.add_parser("sync-project-memory", help="Sync attached runs into project memory.")
    sync_project_parser.add_argument("--project-id", required=True)

    build_claim_graph_parser = subparsers.add_parser("build-claim-graph", help="Build a project-level cumulative claim graph.")
    build_claim_graph_parser.add_argument("--project-id", required=True)

    claim_graph_parser = subparsers.add_parser("claim-graph", help="Print the project claim graph report.")
    claim_graph_parser.add_argument("--project-id", required=True)

    contradictions_parser = subparsers.add_parser("contradictions", help="Print unresolved project claim contradictions.")
    contradictions_parser.add_argument("--project-id", required=True)

    resolve_contradiction_parser = subparsers.add_parser(
        "resolve-contradiction", help="Record a human resolution for a claim contradiction."
    )
    resolve_contradiction_parser.add_argument("--project-id", required=True)
    resolve_contradiction_parser.add_argument("--claim-a", required=True)
    resolve_contradiction_parser.add_argument("--claim-b", required=True)
    resolve_contradiction_parser.add_argument("--note", required=True)

    create_direction_parser = subparsers.add_parser("create-direction", help="Create a project research direction from a gap.")
    create_direction_parser.add_argument("--project-id", required=True)
    create_direction_parser.add_argument("--gap-id", required=True)

    list_directions_parser = subparsers.add_parser("list-directions", help="List project research directions.")
    list_directions_parser.add_argument("--project-id", required=True)

    mature_direction_parser = subparsers.add_parser("mature-direction", help="Evaluate and update a direction maturity state.")
    mature_direction_parser.add_argument("--project-id", required=True)
    mature_direction_parser.add_argument("--direction-id", required=True)

    direction_card_parser = subparsers.add_parser("direction-card", help="Print and write a direction card.")
    direction_card_parser.add_argument("--project-id", required=True)
    direction_card_parser.add_argument("--direction-id", required=True)

    reject_direction_parser = subparsers.add_parser("reject-direction", help="Reject a project research direction.")
    reject_direction_parser.add_argument("--project-id", required=True)
    reject_direction_parser.add_argument("--direction-id", required=True)
    reject_direction_parser.add_argument("--reason", required=True)

    related_work_parser = subparsers.add_parser("related-work-matrix", help="Build a structured related-work matrix.")
    related_work_scope = related_work_parser.add_mutually_exclusive_group(required=True)
    related_work_scope.add_argument("--project-id")
    related_work_scope.add_argument("--run-id")
    related_work_parser.add_argument("--direction-id", default="")
    related_work_parser.add_argument("--gap-id", default="")

    must_read_parser = subparsers.add_parser("must-read", help="List must-read papers for a project research direction.")
    must_read_parser.add_argument("--project-id", required=True)
    must_read_parser.add_argument("--direction-id", required=True)

    protocol_parser = subparsers.add_parser("experiment-protocol", help="Generate an executable experiment protocol.")
    protocol_parser.add_argument("--project-id", required=True)
    protocol_parser.add_argument("--direction-id", required=True)

    generate_code_tasks_parser = subparsers.add_parser(
        "generate-code-tasks", help="Generate Codex handoff tasks for experiment implementation."
    )
    generate_code_tasks_parser.add_argument("--campaign-id", required=True)
    generate_code_tasks_parser.add_argument("--direction-id", required=True)

    scaffold_experiment_parser = subparsers.add_parser("scaffold-experiment-repo", help="Create a minimal experiment repository scaffold.")
    scaffold_experiment_parser.add_argument("--campaign-id", required=True)
    scaffold_experiment_parser.add_argument("--direction-id", required=True)

    codex_code_task_parser = subparsers.add_parser("codex-code-task", help="Write a Codex implementation task file.")
    codex_code_task_parser.add_argument("--code-task-id", required=True)

    baselines_parser = subparsers.add_parser("baselines", help="List baseline candidates for a project research direction.")
    baselines_parser.add_argument("--project-id", required=True)
    baselines_parser.add_argument("--direction-id", required=True)

    reproducibility_parser = subparsers.add_parser("reproducibility-checklist", help="Print a reproducibility checklist.")
    reproducibility_parser.add_argument("--run-id", required=True)
    reproducibility_parser.add_argument("--experiment-id", required=True)

    review_panel_parser = subparsers.add_parser("review-panel", help="Build a v0.3 review panel for a project direction.")
    review_panel_parser.add_argument("--project-id", required=True)
    review_panel_parser.add_argument("--direction-id", required=True)

    rebuttal_plan_parser = subparsers.add_parser("rebuttal-plan", help="Print the rebuttal plan for a project direction.")
    rebuttal_plan_parser.add_argument("--project-id", required=True)
    rebuttal_plan_parser.add_argument("--direction-id", required=True)

    meta_review_parser = subparsers.add_parser("meta-review", help="Print the meta-review for a project direction.")
    meta_review_parser.add_argument("--project-id", required=True)
    meta_review_parser.add_argument("--direction-id", required=True)

    export_package_parser = subparsers.add_parser("export-paper-package", help="Export a manuscript starter kit for a direction.")
    export_package_parser.add_argument("--project-id", required=True)
    export_package_parser.add_argument("--direction-id", required=True)
    export_package_parser.add_argument("--allow-rejected", action="store_true")

    export_manuscript_parser = subparsers.add_parser("export-manuscript", help="Export a run-level manuscript starter kit for a gap.")
    export_manuscript_parser.add_argument("--run-id", required=True)
    export_manuscript_parser.add_argument("--gap-id", required=True)
    export_manuscript_parser.add_argument("--allow-rejected", action="store_true")

    export_bib_parser = subparsers.add_parser("export-bib", help="Export BibTeX for a project research direction.")
    export_bib_parser.add_argument("--project-id", required=True)
    export_bib_parser.add_argument("--direction-id", required=True)

    build_index_parser = subparsers.add_parser("build-index", help="Build a v0.3 hybrid retrieval index.")
    build_index_scope = build_index_parser.add_mutually_exclusive_group(required=True)
    build_index_scope.add_argument("--run-id")
    build_index_scope.add_argument("--project-id")

    search_index_parser = subparsers.add_parser("search-index", help="Search a persisted hybrid retrieval index.")
    search_index_scope = search_index_parser.add_mutually_exclusive_group(required=True)
    search_index_scope.add_argument("--run-id")
    search_index_scope.add_argument("--project-id")
    search_index_parser.add_argument("query")
    search_index_parser.add_argument("--top-k", type=int, default=10)

    explain_retrieval_parser = subparsers.add_parser("explain-retrieval", help="Explain hybrid retrieval scores for a query.")
    explain_retrieval_parser.add_argument("--run-id", required=True)
    explain_retrieval_parser.add_argument("query")
    explain_retrieval_parser.add_argument("--top-k", type=int, default=10)

    subparsers.add_parser("llm-status", help="Show optional LLM provider configuration and readiness.")

    llm_test_parser = subparsers.add_parser("llm-test", help="Run a safe LLM smoke test.")
    llm_test_parser.add_argument("--fake", action="store_true", help="Use FakeLLMClient even if provider mode is configured.")
    llm_test_parser.add_argument("--run-id", default=None, help="Optional run for usage/transcript audit artifacts.")

    llm_usage_parser = subparsers.add_parser("llm-usage", help="Print per-run LLM usage JSON.")
    llm_usage_parser.add_argument("--run-id", required=True)

    llm_transcripts_parser = subparsers.add_parser("llm-transcripts", help="Print per-run LLM transcript markdown.")
    llm_transcripts_parser.add_argument("--run-id", required=True)

    audit_artifacts_parser = subparsers.add_parser("audit-artifacts", help="Classify generated artifacts for commit safety.")
    audit_artifacts_scope = audit_artifacts_parser.add_mutually_exclusive_group(required=True)
    audit_artifacts_scope.add_argument("--run-id")
    audit_artifacts_scope.add_argument("--project-id")

    clean_generated_parser = subparsers.add_parser("clean-generated", help="Remove generated/sensitive artifacts from a run.")
    clean_generated_parser.add_argument("--run-id", required=True)

    export_safe_bundle_parser = subparsers.add_parser("export-safe-bundle", help="Export a redacted project bundle without PDFs.")
    export_safe_bundle_parser.add_argument("--project-id", required=True)
    export_safe_bundle_parser.add_argument("--include-pdfs", action="store_true", help="Include PDFs explicitly; unsafe by default.")

    subparsers.add_parser("cache-info", help="Print source cache diagnostics as JSON.")
    subparsers.add_parser("show-state", help="Print latest state.json.")
    subparsers.add_parser("validate-state", help="Validate the latest run state.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    config = GapForgeConfig.from_env_or_cwd()
    orchestrator = Orchestrator(config)

    try:
        return _dispatch(args, config, orchestrator, parser)
    except (FileNotFoundError, ValueError, KeyError, AgentUnavailableError) as exc:
        print(f"gapforge: error: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("gapforge: interrupted", file=sys.stderr)
        return 130


def _dispatch(
    args: argparse.Namespace,
    config: GapForgeConfig,
    orchestrator: Orchestrator,
    parser: argparse.ArgumentParser,
) -> int:
    if args.command == "init-topic":
        state = orchestrator.init_topic(args.topic)
        print(state.run_dir)
        return 0
    if args.command == "run-active":
        state = orchestrator.run_active(
            args.topic,
            budget=budget_from_name(args.budget),
            project_id=args.project_id,
            source_policy_profile=args.profile,
        )
        _print_active_result(state)
        return 0
    if args.command == "active-status":
        state = ResearchStateManager(config).load_run(args.run_id)
        payload = {
            "run_id": state.run_id,
            "status": state.active_loop.status if state.active_loop else "not_started",
            "current_iteration": state.active_loop.current_iteration if state.active_loop else 0,
            "decision_count": len(state.active_loop.decisions) if state.active_loop else 0,
            "coverage_profile": state.coverage_stopping_assessment.profile_id if state.coverage_stopping_assessment else "",
            "enough_for_novelty": state.coverage_stopping_assessment.enough_for_novelty if state.coverage_stopping_assessment else False,
        }
        print(json.dumps(payload, indent=2))
        return 0
    if args.command == "active-decisions":
        state = ResearchStateManager(config).load_run(args.run_id)
        path = Path(state.run_dir) / "active_decisions.md"
        if path.exists():
            print(path.read_text(encoding="utf-8"), end="")
            return 0
        print("No active decisions recorded.")
        return 0
    if args.command == "search":
        state = orchestrator.search(
            args.topic,
            max_results=args.max_results,
            sources=_source_names(args.sources),
            newest_first=args.newest_first,
            date_from=args.date_from,
            date_to=args.date_to,
        )
        print(f"Wrote {len(state.papers)} papers to {Path(state.run_dir) / 'papers.json'}")
        return 0
    if args.command == "map":
        if not args.topic and not args.run_id:
            parser.error("map requires a topic or --run-id")
        state = orchestrator.map_topic(args.topic, run_id=args.run_id)
        clusters = len(state.field_map.clusters) if state.field_map else 0
        print(f"Wrote field map with {clusters} clusters to {Path(state.run_dir) / 'field_map.md'}")
        return 0
    if args.command == "triage":
        if not args.topic and not args.run_id:
            parser.error("triage requires a topic or --run-id")
        state = orchestrator.triage(args.topic, run_id=args.run_id, max_tier1=args.max_tier1)
        decisions = len(state.paper_triage.decisions) if state.paper_triage else 0
        print(f"Wrote {decisions} triage decisions to {Path(state.run_dir) / 'paper_triage.md'}")
        return 0
    if args.command == "rank-papers":
        state = orchestrator.rank_papers_v2(
            run_id=args.run_id,
            query_purpose=args.query_purpose,
            recency_preference=args.recency_preference,
            source_diversity_target=args.source_diversity_target,
            role_diversity_target=args.role_diversity_target,
        )
        ranked = len(state.paper_ranking.decisions) if state.paper_ranking else 0
        print(f"Wrote {ranked} ranked papers to {Path(state.run_dir) / 'paper_ranking.md'}")
        return 0
    if args.command == "read":
        state = orchestrator.read(
            run_id=args.run_id,
            tier=args.tier,
            paper_id=args.paper_id,
            fulltext_only=args.fulltext_only,
            allow_abstract_only=args.allow_abstract_only,
        )
        print(f"Wrote {len(state.paper_notes)} paper notes to {Path(state.run_dir) / 'paper_notes.md'}")
        return 0
    if args.command == "read-llm":
        if _uses_agent_skill(args):
            return _run_agent_skill_command(
                config,
                run_id=args.run_id,
                skill_name="deep-reading",
                agent_mode=args.agent_mode,
                model=args.model,
                import_outputs=args.import_output,
                validate_only=args.validate_only,
                paper_id=args.paper_id or "",
            )
        state = orchestrator.read_llm(
            run_id=args.run_id,
            tier=args.tier,
            paper_id=args.paper_id,
            dry_run_prompts=args.dry_run_prompts,
            fake=args.fake,
        )
        print(f"Wrote LLM deep reading artifacts to {Path(state.run_dir) / 'deep_reading_llm.md'}")
        return 0
    if args.command == "mine-gaps":
        state = orchestrator.mine_gaps(
            run_id=args.run_id,
            min_confidence=args.min_confidence,
            include_low_confidence=args.include_low_confidence or args.min_confidence == "low",
            force=args.force,
        )
        print(f"Wrote {len(state.gaps)} gap candidates to {Path(state.run_dir) / 'gaps.md'}")
        return 0
    if args.command == "mine-gaps-llm":
        if _uses_agent_skill(args):
            return _run_agent_skill_command(
                config,
                run_id=args.run_id,
                skill_name="gap-mining",
                agent_mode=args.agent_mode,
                model=args.model,
                import_outputs=args.import_output,
                validate_only=args.validate_only,
            )
        state = orchestrator.mine_gaps_llm(
            run_id=args.run_id,
            dry_run_prompts=args.dry_run_prompts,
            fake=args.fake,
            force=args.force,
        )
        print(f"Wrote LLM gap mining artifacts to {Path(state.run_dir) / 'gap_mining_llm.md'}")
        return 0
    if args.command == "analogies":
        state = orchestrator.analogies(
            run_id=args.run_id,
            search=args.search,
            promote_evidence_only=args.promote_evidence_only,
        )
        print(f"Wrote {len(state.cross_domain_analogies)} analogies to {Path(state.run_dir) / 'cross_domain_analogies.md'}")
        return 0
    if args.command == "novelty-check":
        state = orchestrator.novelty_check(run_id=args.run_id, gap_id=args.gap_id, deep=args.deep)
        print(f"Wrote {len(state.novelty_assessments)} novelty assessments to {Path(state.run_dir) / 'novelty_gate.md'}")
        return 0
    if args.command == "novelty-check-llm":
        if not args.all and not args.gap_id:
            parser.error("novelty-check-llm requires --gap-id or --all")
        if _uses_agent_skill(args):
            return _run_agent_skill_command(
                config,
                run_id=args.run_id,
                skill_name="novelty-gate",
                agent_mode=args.agent_mode,
                model=args.model,
                import_outputs=args.import_output,
                validate_only=args.validate_only,
                gap_id=args.gap_id or "",
            )
        state = orchestrator.novelty_check_llm(
            run_id=args.run_id,
            gap_id=args.gap_id,
            all_targets=args.all,
            dry_run_prompts=args.dry_run_prompts,
            fake=args.fake,
        )
        print(f"Wrote LLM novelty artifacts to {Path(state.run_dir) / 'novelty_gate_llm.md'}")
        return 0
    if args.command == "novelty-dossier":
        state = orchestrator.novelty_check(run_id=args.run_id, gap_id=args.gap_id, deep=True)
        print(f"Wrote {len(state.novelty_dossiers)} novelty dossiers to {Path(state.run_dir) / 'novelty_dossiers.md'}")
        return 0
    if args.command == "design-experiments":
        state = orchestrator.design_experiments(run_id=args.run_id, allow_rejected=args.allow_rejected, force=args.force)
        print(f"Wrote {len(state.experiments)} experiments to {Path(state.run_dir) / 'experiments.md'}")
        return 0
    if args.command == "design-experiment":
        state = orchestrator.design_experiments(
            run_id=args.run_id,
            gap_id=args.gap_id,
            allow_rejected=args.allow_rejected,
            force=args.force,
        )
        print(f"Wrote {len(state.experiments)} experiments to {Path(state.run_dir) / 'experiments.md'}")
        return 0
    if args.command == "review":
        if _uses_agent_skill(args):
            if args.run_id is None:
                parser.error("review with --agent requires --run-id")
            return _run_agent_skill_command(
                config,
                run_id=args.run_id,
                skill_name="reviewer-simulation",
                agent_mode=args.agent_mode,
                model=args.model,
                import_outputs=args.import_output,
                validate_only=args.validate_only,
            )
        state = orchestrator.review(run_id=args.run_id, experiment_id=args.experiment_id)
        print(f"Wrote {len(state.reviewer_objections)} reviewer objections to {Path(state.run_dir) / 'reviewer_simulation.md'}")
        return 0
    if args.command == "download-pdfs":
        manager = ResearchStateManager(config)
        state = manager.load_run(args.run_id)
        artifacts = PdfDownloader(config.cache_dir).download_for_state(
            state,
            paper_id=args.paper_id,
            max_papers=args.max_papers,
            skip_existing=args.skip_existing,
        )
        manager.save_run(state)
        available = sum(1 for artifact in artifacts if artifact.status == "available")
        failed = sum(1 for artifact in artifacts if artifact.status == "failed")
        skipped = sum(1 for artifact in artifacts if artifact.status == "skipped")
        print(
            f"PDF download complete: {available} available, {failed} failed, {skipped} skipped. "
            f"Coverage: {Path(state.run_dir) / 'full_text_coverage.md'}"
        )
        return 0
    if args.command == "parse-fulltext":
        manager = ResearchStateManager(config)
        state = manager.load_run(args.run_id)
        sections = FullTextParser().parse_for_state(state, paper_id=args.paper_id)
        manager.save_run(state)
        print(
            f"Parsed {len(sections)} paper sections. "
            f"Sections: {Path(state.run_dir) / 'paper_sections.json'} Coverage: {Path(state.run_dir) / 'full_text_coverage.md'}"
        )
        return 0
    if args.command == "parse-structure":
        manager = ResearchStateManager(config)
        state = manager.load_run(args.run_id)
        FullTextStructureParser().parse_all(state)
        manager.save_run(state)
        print(
            f"Parsed structure: {len(state.references)} references, {len(state.tables)} tables, "
            f"{len(state.equations)} equations, {len(state.captions)} captions."
        )
        return 0
    if args.command == "parse-references":
        manager = ResearchStateManager(config)
        state = manager.load_run(args.run_id)
        FullTextStructureParser().parse_references(state)
        manager.save_run(state)
        print(f"Parsed {len(state.references)} references to {Path(state.run_dir) / 'references.json'}")
        return 0
    if args.command == "parse-tables":
        manager = ResearchStateManager(config)
        state = manager.load_run(args.run_id)
        FullTextStructureParser().parse_tables(state)
        manager.save_run(state)
        print(f"Parsed {len(state.tables)} tables and {len(state.captions)} captions to {Path(state.run_dir) / 'tables.json'}")
        return 0
    if args.command == "ocr-status":
        manager = ResearchStateManager(config)
        state = manager.load_run(args.run_id)
        FullTextStructureParser().record_ocr_status(state)
        manager.save_run(state)
        print(Path(state.run_dir, "ocr_status.md").read_text(encoding="utf-8"), end="")
        return 0
    if args.command == "add-paper":
        manager = ResearchStateManager(config)
        state = manager.load_run(args.run_id)
        paper = ManualIngestor(config).add_paper(
            state,
            title=args.title,
            authors=parse_authors(args.authors),
            year=args.year,
            url=args.url,
            pdf_url=args.pdf_url,
            doi=args.doi,
            arxiv_id=args.arxiv_id,
        )
        manager.save_run(state)
        print(f"Added paper {paper.id}. Papers: {Path(state.run_dir) / 'papers.json'}")
        return 0
    if args.command == "add-arxiv":
        manager = ResearchStateManager(config)
        state = manager.load_run(args.run_id)
        paper = ManualIngestor(config).add_arxiv(state, args.arxiv_id)
        manager.save_run(state)
        print(f"Added arXiv paper {paper.id}. Papers: {Path(state.run_dir) / 'papers.json'}")
        return 0
    if args.command == "add-doi":
        manager = ResearchStateManager(config)
        state = manager.load_run(args.run_id)
        paper = ManualIngestor(config).add_doi(state, args.doi)
        manager.save_run(state)
        print(f"Added DOI paper {paper.id}. Papers: {Path(state.run_dir) / 'papers.json'}")
        return 0
    if args.command == "add-pdf":
        manager = ResearchStateManager(config)
        state = manager.load_run(args.run_id)
        title = args.title or Path(args.pdf_path).stem
        paper, artifact = ManualIngestor(config).add_pdf(
            state,
            Path(args.pdf_path),
            title=title,
            authors=parse_authors(args.authors),
            year=args.year,
            parse=args.parse,
        )
        manager.save_run(state)
        print(f"Added PDF artifact {artifact.id} for {paper.id}. Artifacts: {Path(state.run_dir) / 'paper_artifacts.json'}")
        return 0
    if args.command == "add-url":
        manager = ResearchStateManager(config)
        state = manager.load_run(args.run_id)
        paper = ManualIngestor(config).add_url(state, args.url)
        manager.save_run(state)
        print(f"Added URL paper {paper.id}. Papers: {Path(state.run_dir) / 'papers.json'}")
        return 0
    if args.command == "run":
        state = orchestrator.run(
            args.topic,
            max_papers=args.max_papers,
            iterations=args.iterations,
            sources=_source_names(args.sources),
            dry_run=args.dry_run,
            v2=args.v2,
            v3=args.v3,
            project_id=args.project_id,
            source_profile=args.source_profile,
            active=args.active,
            download_pdfs=args.download_pdfs,
            parse_fulltext=args.parse_fulltext,
            deep_novelty=args.deep_novelty,
            strict_report=args.strict_report,
            skip_pdf_download=args.skip_pdf_download,
            max_expanded_papers=args.max_expanded_papers,
            llm_reading=args.llm_reading,
            llm_gaps=args.llm_gaps,
            llm_novelty=args.llm_novelty,
            llm_review=args.llm_review,
            build_index=args.build_index,
            mature_directions=args.mature_directions,
            export_package=args.export_package,
            dashboard=args.dashboard,
            budget=budget_from_name(args.budget),
            run_mode=args.mode,
            agent=args.agent,
            model=args.model,
            agent_task_pack=args.agent_task_pack,
            require_real_agent=args.require_real_agent,
            canary_profile=args.canary_profile,
            record_canary=args.record_canary,
        )
        if args.v3 and args.active and not args.dry_run:
            _print_active_result(state)
        else:
            _print_run_result(state)
        return 1 if state.orchestrator_result is not None and state.orchestrator_result.status == "failed" else 0
    if args.command == "resume":
        state = orchestrator.resume(run_id=args.run_id)
        _print_run_result(state)
        return 0
    if args.command == "status":
        status_result = orchestrator.status(run_id=args.run_id)
        print(json.dumps(to_plain(status_result), indent=2))
        return 0
    if args.command == "eval":
        report = run_evals(fixture=args.fixture, output_dir=config.root, write_report=True, v2=args.v2, v3=args.v3, v4=args.v4)
        target = report.report_path or (config.root / "eval_report.md")
        print(f"Wrote evaluation report to {target}")
        print(f"Overall score: {report.overall_score:.3f}")
        return 0
    if args.command == "report":
        state = _load_report_state(config, args.run_id)
        path = write_final_report(state, output_format=args.format, strict=args.strict)
        print(f"Wrote final report to {path}")
        return 0
    if args.command == "dashboard":
        dashboard = StaticDashboardBuilder(config)
        result = dashboard.build_project(args.project_id) if args.project_id else dashboard.build_run(args.run_id)
        if args.open:
            dashboard.open(result)
        print(f"Wrote dashboard to {result.index_path}")
        return 0
    if args.command == "release-gate-dashboard":
        result = StaticDashboardBuilder(config).build_project(args.project_id)
        path = result.root / "release_gate.html"
        print(f"Wrote release-gate dashboard to {path}")
        return 0
    if args.command == "review-queue":
        queue_manager = ReviewQueueManager(config)
        queue = queue_manager.build_for_project(args.project_id) if args.project_id else queue_manager.build_for_run(args.run_id)
        print(render_review_queue_markdown(queue), end="")
        return 0
    if args.command == "complete-review-item":
        item = ReviewQueueManager(config).complete_project_item(
            args.project_id,
            args.item_id,
            note=args.note,
            reviewer=args.reviewer,
        )
        print(f"Completed review item {item.id}.")
        return 0
    if args.command == "dismiss-review-item":
        item = ReviewQueueManager(config).dismiss_project_item(
            args.project_id,
            args.item_id,
            reason=args.reason,
            reviewer=args.reviewer,
        )
        print(f"Dismissed review item {item.id}.")
        return 0
    if args.command == "coverage":
        manager = ResearchStateManager(config)
        coverage_state = manager.load_latest() if args.run_id == "latest" else manager.load_run(args.run_id)
        if coverage_state is None:
            raise FileNotFoundError('No run state found. Start with `gapforge run "your topic"`.')
        refresh_source_coverage(coverage_state, [str(item) for item in coverage_state.config.get("_coverage_warnings", []) if str(item)])
        refresh_stopping_assessment(coverage_state)
        manager.save_run(coverage_state)
        print(
            f"Wrote coverage reports to {Path(coverage_state.run_dir) / 'source_coverage.md'} "
            f"and {Path(coverage_state.run_dir) / 'full_text_coverage.md'}"
        )
        return 0
    if args.command == "source-policy":
        profiles = default_source_policy_profiles()
        if args.list or not args.run_id:
            for profile_item in profiles.values():
                print(
                    f"{profile_item.id}\t{profile_item.field_name}\trequired={','.join(profile_item.required_sources) or 'none'}\t"
                    f"min_papers={profile_item.minimum_papers}\tmin_full_text={profile_item.minimum_full_text_papers}"
                )
            return 0
        manager = ResearchStateManager(config)
        state = manager.load_run(args.run_id)
        policy_profile = get_source_policy_profile(args.profile) if args.profile else None
        if policy_profile is not None:
            state.config["source_policy_profile"] = policy_profile.id
        refresh_source_coverage(state, [str(item) for item in state.config.get("_coverage_warnings", []) if str(item)])
        assessment = refresh_stopping_assessment(state, profile=policy_profile)
        manager.save_run(state)
        print(render_stopping_assessment_markdown(assessment), end="")
        return 0
    if args.command == "assess-coverage":
        manager = ResearchStateManager(config)
        state = manager.load_run(args.run_id)
        policy_profile = get_source_policy_profile(args.profile) if args.profile else None
        if policy_profile is not None:
            state.config["source_policy_profile"] = policy_profile.id
        refresh_source_coverage(state, [str(item) for item in state.config.get("_coverage_warnings", []) if str(item)])
        assessment = refresh_stopping_assessment(state, profile=policy_profile)
        manager.save_run(state)
        print(render_stopping_assessment_markdown(assessment), end="")
        return 0
    if args.command == "next-searches":
        manager = ResearchStateManager(config)
        state = manager.load_run(args.run_id)
        if state.coverage_stopping_assessment is None:
            refresh_source_coverage(state, [str(item) for item in state.config.get("_coverage_warnings", []) if str(item)])
            refresh_stopping_assessment(state)
            manager.save_run(state)
        next_assessment = state.coverage_stopping_assessment
        if next_assessment is None:
            raise ValueError("Coverage stopping assessment was not generated.")
        if not next_assessment.recommended_queries:
            print("No additional searches recommended by the current source policy.")
            return 0
        print("\n".join(next_assessment.recommended_queries))
        return 0
    if args.command == "build-citation-graph":
        state = orchestrator.build_citation_graph(run_id=args.run_id)
        graph = state.citation_graph
        edge_count = len(graph.edges) if graph else 0
        unresolved = len(graph.unresolved_references) if graph else 0
        print(
            f"Wrote citation graph with {edge_count} edges and {unresolved} unresolved references "
            f"to {Path(state.run_dir) / 'citation_graph.md'}"
        )
        return 0
    if args.command == "expand-related-work":
        before = len(ResearchStateManager(config).load_run(args.run_id).papers)
        state = orchestrator.expand_related_work(
            run_id=args.run_id,
            max_new_papers=args.max_new_papers,
            paper_id=args.paper_id,
        )
        added = max(0, len(state.papers) - before)
        print(f"Expanded related work with {added} new paper(s). Report: {Path(state.run_dir) / 'related_work_expansion.md'}")
        return 0
    if args.command == "list-gaps":
        manager = ResearchStateManager(config)
        state = manager.load_run(args.run_id)
        print(_format_gap_list(state))
        return 0
    if args.command == "approve-gap":
        manager = ResearchStateManager(config)
        state = manager.load_run(args.run_id)
        record = HumanReviewEditor().approve_gap(state, args.gap_id, note=args.note, reviewer=args.reviewer)
        manager.save_run(state)
        print(f"Approved gap {args.gap_id}; audit record {record.id}.")
        return 0
    if args.command == "reject-gap":
        manager = ResearchStateManager(config)
        state = manager.load_run(args.run_id)
        record = HumanReviewEditor().reject_gap(state, args.gap_id, reason=args.reason, reviewer=args.reviewer)
        manager.save_run(state)
        print(f"Rejected gap {args.gap_id}; audit record {record.id}.")
        return 0
    if args.command == "annotate-claim":
        manager = ResearchStateManager(config)
        state = manager.load_run(args.run_id)
        record = HumanReviewEditor().annotate_claim(state, args.claim_id, note=args.note, reviewer=args.reviewer)
        manager.save_run(state)
        print(f"Annotated claim {args.claim_id}; audit record {record.id}.")
        return 0
    if args.command == "mark-claim":
        manager = ResearchStateManager(config)
        state = manager.load_run(args.run_id)
        record = HumanReviewEditor().mark_claim(state, args.claim_id, status=args.status, reviewer=args.reviewer)
        manager.save_run(state)
        print(f"Marked claim {args.claim_id} as {args.status}; audit record {record.id}.")
        return 0
    if args.command == "add-evidence":
        manager = ResearchStateManager(config)
        state = manager.load_run(args.run_id)
        record = HumanReviewEditor().add_evidence(
            state,
            args.claim_id,
            paper_id=args.paper_id,
            quote=args.quote,
            locator=args.locator,
            reviewer=args.reviewer,
        )
        manager.save_run(state)
        print(f"Added evidence to claim {args.claim_id}; audit record {record.id}.")
        return 0
    if args.command == "lock-object":
        manager = ResearchStateManager(config)
        state = manager.load_run(args.run_id)
        editor = HumanReviewEditor()
        if args.unlock:
            record = editor.unlock_object(
                state,
                args.object_type,
                args.object_id,
                note=args.note,
                reviewer=args.reviewer,
            )
            verb = "Unlocked"
        else:
            record = editor.lock_object(
                state,
                args.object_type,
                args.object_id,
                note=args.note,
                reviewer=args.reviewer,
                force=args.force,
            )
            verb = "Locked"
        manager.save_run(state)
        print(f"{verb} {args.object_type}:{args.object_id}; audit record {record.id}.")
        return 0
    if args.command == "audit-log":
        state = ResearchStateManager(config).load_run(args.run_id)
        print(render_human_reviews_markdown(state), end="")
        return 0
    if args.command == "prompt-pack":
        path = orchestrator.write_prompt_pack(run_id=args.run_id, skill_name=args.skill, gap_id=args.gap_id)
        print(f"Wrote prompt pack to {path}")
        return 0
    if args.command == "agent-status":
        print(json.dumps(agent_status(AgentRuntimeConfig.from_env()), indent=2))
        return 0
    if args.command == "setup-real-run":
        print(render_real_run_setup(AgentRuntimeConfig.from_env()), end="")
        return 0
    if args.command == "agent-capabilities":
        capabilities = agent_capabilities(AgentRuntimeConfig.from_env())
        if args.json:
            print(json.dumps(to_plain(capabilities), indent=2))
        else:
            for capability in capabilities:
                availability = "available" if capability.available else "unavailable"
                counts = "can-count" if capability.can_count_as_actual_run else "no-actual-run"
                print(f"{capability.mode}\t{availability}\t{counts}\t{capability.reason}")
        return 0
    if args.command == "task-handoff":
        try:
            task_spec = _load_agent_task(config, args.task_id)
        except FileNotFoundError:
            campaign_state, pack_dir = find_campaign_task(config, args.task_id)
            handoff_path = write_task_handoff(config, args.task_id, model=campaign_state.campaign.model or "gpt-5.4")
            print(f"Wrote campaign handoff to {handoff_path}")
            print(f"Outputs directory: {pack_dir / 'outputs'}")
        else:
            state = ResearchStateManager(config).load_run(task_spec.run_id)
            pack_dir = CodexAgentClient(config, AgentRuntimeConfig(mode="task-pack")).create_task_pack(state, task_spec)
            handoff_path = write_handoff(task_spec, pack_dir, model=AgentRuntimeConfig.from_env().codex_model)
            print(f"Wrote agent handoff to {handoff_path}")
            print(f"Outputs directory: {pack_dir / 'outputs'}")
        return 0
    if args.command == "repair-agent-output":
        paths = [Path(path) for path in args.path]
        try:
            task_spec = _load_agent_task(config, args.task_id)
        except FileNotFoundError:
            campaign_state, pack_dir = find_campaign_task(config, args.task_id)
            campaign_import_record = CampaignOutputImporter(config).validate(campaign_state.campaign.id, args.task_id, paths)
            print(
                repair_from_campaign_validation(
                    args.task_id,
                    campaign_import_record,
                    expected_files=expected_campaign_files(args.task_id),
                    outputs_dir=pack_dir / "outputs",
                ),
                end="",
            )
            return 0 if campaign_import_record.status in {"valid", "applied"} else 1
        repair_record, validation, repair_pack_dir = create_agent_repair_task(config, task_spec, paths, handoff=args.handoff)
        if repair_record is None:
            print(json.dumps({"task_id": args.task_id, "validation": to_plain(validation), "repair_created": False}, indent=2))
            return 0
        print(
            json.dumps(
                {
                    "task_id": args.task_id,
                    "validation": to_plain(validation),
                    "repair_created": True,
                    "repair_record": to_plain(repair_record),
                    "repair_task_pack": str(repair_pack_dir),
                    "handoff": str(repair_pack_dir / "HANDOFF.md") if args.handoff and repair_pack_dir else "",
                },
                indent=2,
            )
        )
        return 0
    if args.command == "repair-status":
        repair_record, run_dir = find_agent_repair_record(config, args.repair_id)
        print(render_agent_repair_status(repair_record, run_dir), end="")
        return 0
    if args.command in {"agent-task", "codex-task"}:
        manager = ResearchStateManager(config)
        state = manager.load_run(args.run_id)
        task_spec = create_agent_task_spec(
            state,
            skill_name=args.skill,
            gap_id=args.gap_id,
            paper_id=args.paper_id,
            project_id=args.project_id,
        )
        state.agent_task_specs.append(task_spec)
        pack_dir = CodexAgentClient(config, AgentRuntimeConfig(mode="task-pack")).create_task_pack(state, task_spec)
        manager.save_run(state)
        print(f"Wrote agent task {task_spec.id} to {pack_dir}")
        return 0
    if args.command == "agent-run":
        task_spec = _load_agent_task(config, args.task_id)
        agent_client = _agent_client_for_command(config, fake=args.fake)
        record = agent_client.run_task(task_spec)
        print(json.dumps(to_plain(record), indent=2))
        return 0
    if args.command == "agent-import-output":
        task_spec = _load_agent_task(config, args.task_id)
        agent_client = CodexAgentClient(config, AgentRuntimeConfig(mode="task-pack"))
        validation = agent_client.import_outputs(task_spec, [Path(path) for path in args.path])
        print(json.dumps(to_plain(validation), indent=2))
        return 0 if validation.status == "valid" else 1
    if args.command == "agent-validate-output":
        task_spec = _load_agent_task(config, args.task_id)
        agent_client = CodexAgentClient(config, AgentRuntimeConfig(mode="task-pack"))
        validation = agent_client.validate_outputs(task_spec, [Path(path) for path in args.path] if args.path else [])
        print(json.dumps(to_plain(validation), indent=2))
        return 0 if validation.status == "valid" else 1
    if args.command == "attest-agent-run":
        task_spec = _load_agent_task(config, args.task_id)
        manager = ResearchStateManager(config)
        state = manager.load_run(task_spec.run_id)
        attestation = create_actual_run_attestation(
            state,
            task_spec,
            agent_name=args.agent,
            model=args.model,
            execution_method=args.method,
            attester=args.attester,
            statement=args.statement,
        )
        manager.save_run(state)
        print(json.dumps(to_plain(attestation), indent=2))
        return 0 if attestation.accepted_as_actual_run else 1
    if args.command == "actual-run-status":
        state = ResearchStateManager(config).load_run(args.run_id)
        print(json.dumps(actual_run_status(state), indent=2))
        return 0
    if args.command == "validate-agent-output":
        task_spec = _load_agent_task(config, args.task_id)
        validation = CodexAgentClient(config, AgentRuntimeConfig(mode="task-pack")).validate_outputs(task_spec, [])
        print(json.dumps(to_plain(validation), indent=2))
        return 0 if validation.status == "valid" else 1
    if args.command == "import-agent-output":
        task_spec = _load_agent_task(config, args.task_id)
        validation = CodexAgentClient(config, AgentRuntimeConfig(mode="task-pack")).import_outputs(task_spec, [])
        print(json.dumps(to_plain(validation), indent=2))
        return 0 if validation.status == "valid" else 1
    if args.command == "list-agent-tasks":
        state = ResearchStateManager(config).load_run(args.run_id)
        if not state.agent_task_specs:
            print("No agent tasks.")
            return 0
        for task_spec in state.agent_task_specs:
            validations = [item for item in state.agent_validation_results if item.task_spec_id == task_spec.id]
            status = validations[-1].status if validations else "not_validated"
            print(f"{task_spec.id}\t{task_spec.skill_name}\t{task_spec.task_type}\t{status}")
        return 0
    if args.command == "codex-run":
        task_spec = _load_agent_task(config, args.task_id)
        codex_run_record = CodexRunner(config, AgentRuntimeConfig.from_env()).run(
            task_spec,
            prefer_direct=args.direct,
            handoff=args.handoff,
            require_direct=args.require_direct,
        )
        print(json.dumps(to_plain(codex_run_record), indent=2))
        return 0 if codex_run_record.status in {"complete", "planned"} else 1
    if args.command == "codex-run-status":
        codex_run_record = CodexRunner(config, AgentRuntimeConfig.from_env()).status(args.agent_run_id)
        print(json.dumps(to_plain(codex_run_record), indent=2))
        return 0
    if args.command == "canary-list":
        for profile in default_canary_profiles():
            print(
                f"{profile.id}\t{profile.mode}\t"
                f"network={str(profile.requires_network).lower()}\t"
                f"codex={str(profile.requires_codex).lower()}\t{profile.title}"
            )
        return 0
    if args.command == "campaign-canary-list":
        for campaign_profile in CampaignCanaryRunManager(config).list_profiles():
            print(
                f"{campaign_profile.id}\t{campaign_profile.campaign_mode}\t"
                f"network={str(campaign_profile.requires_network).lower()}\t"
                f"codex={str(campaign_profile.requires_codex).lower()}\t{campaign_profile.title}"
            )
        return 0
    if args.command == "campaign-canary-plan":
        print(CampaignCanaryRunManager(config).plan(args.profile), end="")
        return 0
    if args.command == "campaign-canary-run":
        campaign_canary_record = CampaignCanaryRunManager(config).run(args.profile, real=args.real)
        print(json.dumps(to_plain(campaign_canary_record), indent=2))
        return 0 if campaign_canary_record.status in {"complete", "planned"} else 1
    if args.command == "campaign-canary-status":
        campaign_canary_record = CampaignCanaryRunManager(config).load_record(args.canary_id)
        print(json.dumps(to_plain(campaign_canary_record), indent=2))
        return 0
    if args.command == "canary-plan":
        print(CanaryRunManager(config).plan(args.profile), end="")
        return 0
    if args.command == "canary-run":
        canary_record = CanaryRunManager(config).run(args.profile, real=args.real)
        print(json.dumps(to_plain(canary_record), indent=2))
        return 0 if canary_record.status in {"complete", "reviewed", "accepted", "planned"} else 1
    if args.command == "canary-status":
        canary_record = CanaryRunManager(config).load_record(args.canary_id)
        print(json.dumps(to_plain(canary_record), indent=2))
        return 0
    if args.command == "canary-artifacts":
        artifact_paths = CanaryRunManager(config).artifact_paths(args.canary_id)
        print("\n".join(artifact_paths) if artifact_paths else "No canary artifacts recorded.")
        return 0
    if args.command == "canary-review":
        review_manager = CanaryReviewManager(config)
        if not args.accept and not args.reject:
            print(review_manager.render_form(args.canary_id), end="")
            return 0
        review, summary = review_manager.review(
            args.canary_id,
            reviewer=args.reviewer,
            accept=args.accept,
            reject=args.reject,
            reason=args.reason,
            notes=args.notes,
            source_coverage_score=args.source_coverage_score,
            full_text_grounding_score=args.full_text_grounding_score,
            citation_grounding_score=args.citation_grounding_score,
            novelty_honesty_score=args.novelty_honesty_score,
            gap_quality_score=args.gap_quality_score,
            experiment_quality_score=args.experiment_quality_score,
            uncertainty_visibility_score=args.uncertainty_visibility_score,
            fake_citation_found=args.fake_citation_found,
            unsupported_high_confidence_claim_found=args.unsupported_high_confidence_claim_found,
            obvious_prior_work_missed=args.obvious_prior_work_missed,
            strict_report_behaved_correctly=not args.strict_report_overclaimed,
        )
        print(json.dumps({"review": to_plain(review), "summary": to_plain(summary)}, indent=2))
        return 0 if summary.passed else 1
    if args.command == "canary-summary":
        summary = CanaryReviewManager(config).summary(args.canary_id)
        print(json.dumps(to_plain(summary), indent=2))
        return 0 if summary.passed else 1
    if args.command == "real-run-acceptance":
        payload = CanaryReviewManager(config).real_run_acceptance()
        print(json.dumps(payload, indent=2))
        return 0 if payload.get("passed") else 1
    if args.command == "diagnose-real-run":
        if args.write_report:
            json_path, markdown_path, diagnostic = write_real_run_diagnostic(config)
            if args.json:
                print(json.dumps(to_plain(diagnostic), indent=2))
            else:
                print(f"Wrote {json_path}")
                print(f"Wrote {markdown_path}")
            return 0
        diagnostic = build_real_run_diagnostic(config)
        if args.json:
            print(json.dumps(to_plain(diagnostic), indent=2))
        else:
            print(render_real_run_diagnostic_markdown(diagnostic), end="")
        return 0
    if args.command == "diagnose-agent":
        print(diagnose_run_agent_markdown(config, args.run_id), end="")
        return 0
    if args.command == "diagnose-canary":
        print(diagnose_canary_markdown(config, args.canary_id), end="")
        return 0
    if args.command == "init-project":
        program = ProjectMemoryManager(config).create_project(args.name, description=args.description)
        print(program.project.root_dir)
        return 0
    if args.command == "list-projects":
        project_manager = ProjectMemoryManager(config)
        projects = project_manager.list_projects()
        active_id = project_manager.active_project_id()
        if not projects:
            print("No projects found.")
            return 0
        for project in projects:
            marker = " *active*" if project.id == active_id else ""
            print(f"{project.id}\t{project.name}\t{project.status}\t{len(project.run_ids)} run(s){marker}")
        return 0
    if args.command == "use-project":
        project = ProjectMemoryManager(config).use_project(args.project_id)
        print(f"Using project {project.id}: {project.name}")
        return 0
    if args.command == "project-status":
        program = ProjectMemoryManager(config).load_project(args.project_id)
        print(json.dumps(_project_status_payload(program), indent=2))
        return 0
    if args.command == "project-report":
        project_manager = ProjectMemoryManager(config)
        program = project_manager.load_project(args.project_id)
        path = project_manager.write_project_report(program)
        print(f"Wrote project report to {path}")
        return 0
    if args.command == "campaign-create":
        campaign_state = CampaignManager(config).create_campaign(
            args.topic,
            project_id=args.project_id,
            title=args.title,
            mode=args.mode,
            agent_name=args.agent_name,
            model=args.model,
            source_profile=args.source_profile,
            budget_id=args.budget_id,
        )
        print(campaign_state.campaign.id)
        return 0
    if args.command == "campaign-status":
        campaign_state = CampaignManager(config).load_campaign_state(args.campaign_id)
        print(json.dumps(_campaign_status_payload(campaign_state), indent=2))
        return 0
    if args.command == "campaign-report":
        path = CampaignManager(config).campaign_report(args.campaign_id, output_format=args.format)
        print(f"Wrote campaign report to {path}")
        return 0
    if args.command == "campaign-stop-reason":
        campaign_manager = CampaignManager(config)
        campaign_state = campaign_manager.load_campaign_state(args.campaign_id)
        program = ProjectMemoryManager(config).load_project(campaign_state.campaign.project_id)
        state_manager = ResearchStateManager(config)
        runs = []
        for run_id in campaign_state.campaign.run_ids:
            try:
                runs.append(state_manager.load_run(run_id))
            except FileNotFoundError:
                continue
        print(json.dumps(campaign_stop_reason(campaign_state, program, runs), indent=2))
        return 0
    if args.command == "campaign-steps":
        campaign_state = CampaignManager(config).load_campaign_state(args.campaign_id)
        print(_format_campaign_steps(campaign_state), end="")
        return 0
    if args.command == "campaign-decisions":
        campaign_state = CampaignManager(config).load_campaign_state(args.campaign_id)
        print(_format_campaign_decisions(campaign_state), end="")
        return 0
    if args.command == "campaign-next":
        action = CampaignController(config).next_action(args.campaign_id)
        print(json.dumps(to_plain(action), indent=2))
        return 0
    if args.command == "campaign-run":
        campaign_state = CampaignController(config).run(
            args.campaign_id,
            mode=args.mode,
            max_iterations=args.max_iterations,
        )
        print(json.dumps(_campaign_status_payload(campaign_state), indent=2))
        return 0 if campaign_state.campaign.status not in {"failed"} else 1
    if args.command == "campaign-stop":
        campaign_state = CampaignManager(config).stop_campaign(args.campaign_id, reason=args.reason)
        print(json.dumps(_campaign_status_payload(campaign_state), indent=2))
        return 0
    if args.command == "campaign-resume":
        campaign_state = CampaignManager(config).resume_campaign(args.campaign_id)
        print(json.dumps(_campaign_status_payload(campaign_state), indent=2))
        return 0
    if args.command == "campaign-task":
        pack_dir = create_campaign_task_pack(config, args.campaign_id, args.type)
        print(f"Wrote campaign task pack to {pack_dir}")
        return 0
    if args.command == "build-task-context":
        path = write_task_context(config, args.campaign_id, args.task_type, budget=args.budget)
        print(str(path))
        return 0
    if args.command == "inspect-task-context":
        print(json.dumps(inspect_task_context(config, args.task_id), indent=2))
        return 0
    if args.command == "campaign-validate-output":
        campaign_validation = validate_campaign_outputs(config, args.campaign_id, args.task_id, [Path(path) for path in args.path])
        print(json.dumps(campaign_validation, indent=2))
        return 0 if campaign_validation["status"] == "valid" else 1
    if args.command == "campaign-import-output":
        campaign_validation = import_campaign_outputs(
            config, args.campaign_id, args.task_id, [Path(path) for path in args.path], dry_run=args.dry_run
        )
        print(json.dumps(campaign_validation, indent=2))
        return 0 if campaign_validation["status"] in {"valid", "applied", "partial"} else 1
    if args.command == "campaign-imports":
        records = CampaignOutputImporter(config).list_imports(args.campaign_id)
        print(json.dumps(to_plain(records), indent=2))
        return 0
    if args.command == "validate-import-all":
        payload = validate_import_all(config, args.campaign_id)
        print(json.dumps(payload, indent=2))
        return 0 if payload["status"] in {"applied", "partial", "no_tasks_processed"} else 1
    if args.command == "campaign-propose-searches":
        batch = CampaignSearchAgent(config).propose_searches(args.campaign_id)
        payload = CampaignSearchAgent(config).status(args.campaign_id)
        write_campaign_search_status(config, args.campaign_id, payload)
        print(json.dumps(to_plain(batch), indent=2))
        return 0 if batch.validation_status in {"valid", "partial"} else 1
    if args.command == "campaign-execute-searches":
        batch = CampaignSearchAgent(config).execute_searches(args.campaign_id)
        payload = CampaignSearchAgent(config).status(args.campaign_id)
        write_campaign_search_status(config, args.campaign_id, payload)
        print(json.dumps(to_plain(batch), indent=2))
        return 0 if batch.validation_status in {"executed", "partial"} else 1
    if args.command == "campaign-search-status":
        payload = CampaignSearchAgent(config).status(args.campaign_id)
        write_campaign_search_status(config, args.campaign_id, payload)
        print(json.dumps(payload, indent=2))
        return 0
    if args.command == "novelty-loop":
        payload = CampaignNoveltyLoop(config).run(args.campaign_id, gap_id=args.gap_id)
        print(json.dumps(payload, indent=2))
        return 0 if payload["stop_reason"] not in {"budget_exhausted"} else 1
    if args.command == "novelty-loop-status":
        payload = CampaignNoveltyLoop(config).status(args.campaign_id)
        print(json.dumps(payload, indent=2))
        return 0
    if args.command == "reviewer-loop":
        payload = CampaignReviewerLoop(config).run(args.campaign_id, args.direction_id)
        print(json.dumps(payload, indent=2))
        reviewer_validation = payload.get("validation", {})
        status = reviewer_validation.get("status", "invalid") if isinstance(reviewer_validation, dict) else "invalid"
        return 0 if status in {"valid", "warning"} else 1
    if args.command == "rebuttal-tasks":
        payload = CampaignReviewerLoop(config).rebuttal_tasks(args.campaign_id, args.direction_id)
        print(json.dumps(payload, indent=2))
        return 0
    if args.command == "apply-reviewer-fixes":
        payload = CampaignReviewerLoop(config).apply_fixes(args.campaign_id, args.direction_id)
        print(json.dumps(payload, indent=2))
        return 0
    if args.command == "campaign-review":
        campaign_review_manager = CampaignReviewManager(config)
        if not args.accept and not args.reject:
            print(campaign_review_manager.render_form(args.campaign_id), end="")
            return 0
        campaign_review, campaign_summary = campaign_review_manager.review(
            args.campaign_id,
            reviewer=args.reviewer,
            accept=args.accept,
            reject=args.reject,
            reason=args.reason,
            notes=args.notes,
            source_coverage_score=args.source_coverage_score,
            full_text_grounding_score=args.full_text_grounding_score,
            citation_grounding_score=args.citation_grounding_score,
            retrieval_quality_score=args.retrieval_quality_score,
            novelty_honesty_score=args.novelty_honesty_score,
            gap_quality_score=args.gap_quality_score,
            related_work_quality_score=args.related_work_quality_score,
            experiment_quality_score=args.experiment_quality_score,
            reviewer_panel_quality_score=args.reviewer_panel_quality_score,
            uncertainty_visibility_score=args.uncertainty_visibility_score,
            stop_reason_quality_score=args.stop_reason_quality_score,
            fake_citation_found=args.fake_citation_found,
            unsupported_high_confidence_claim_found=args.unsupported_high_confidence_claim_found,
            obvious_prior_work_missed=args.obvious_prior_work_missed,
            overclaimed_novelty=args.overclaimed_novelty,
        )
        print(json.dumps({"review": to_plain(campaign_review), "summary": to_plain(campaign_summary)}, indent=2))
        return 0 if campaign_summary.accepted else 1
    if args.command == "campaign-acceptance":
        campaign_summary = CampaignReviewManager(config).summary(args.campaign_id)
        print(json.dumps(to_plain(campaign_summary), indent=2))
        return 0 if campaign_summary.accepted else 1
    if args.command == "v4-actual-run-acceptance":
        payload = CampaignReviewManager(config).v4_actual_run_acceptance()
        print(json.dumps(payload, indent=2))
        return 0 if payload.get("passed") else 1
    if args.command == "v4-release-gate":
        gate_result = V04ReleaseGateEnforcer(config).evaluate(project_id=args.project_id)
        if args.write_report:
            V04ReleaseGateEnforcer(config).write_outputs(gate_result)
        if args.json:
            print(json.dumps(gate_result.to_dict(), indent=2))
        else:
            print(render_v04_release_gate_markdown(gate_result), end="")
        return 0 if gate_result.passed else 1
    if args.command == "rollback-import":
        rollback_record = rollback_import(config, args.import_id)
        print(json.dumps(to_plain(rollback_record), indent=2))
        return 0
    if args.command == "attach-run":
        program = ProjectMemoryManager(config).attach_run(args.project_id, args.run_id)
        print(f"Attached run {args.run_id} to project {program.project.id}.")
        return 0
    if args.command == "sync-project-memory":
        program = ProjectMemoryManager(config).sync_project_memory(args.project_id)
        print(
            f"Synced project {program.project.id}: {len(program.corpus_papers)} corpus papers, "
            f"{len(program.memory_records)} memory records, {len(program.research_directions)} research directions."
        )
        return 0
    if args.command == "build-claim-graph":
        claim_graph = ProjectClaimGraphManager(config).build(args.project_id)
        print(
            f"Built claim graph for {claim_graph.project_id}: {len(claim_graph.nodes)} nodes, "
            f"{len(claim_graph.edges)} edges, {len(claim_graph.unresolved_contradictions)} unresolved contradiction(s)."
        )
        return 0
    if args.command == "claim-graph":
        print(ProjectClaimGraphManager(config).render(args.project_id), end="")
        return 0
    if args.command == "contradictions":
        loaded_claim_graph = ProjectClaimGraphManager(config).load(args.project_id)
        assert loaded_claim_graph is not None
        if not loaded_claim_graph.unresolved_contradictions:
            print("No unresolved contradictions.")
            return 0
        print("\n".join(loaded_claim_graph.unresolved_contradictions))
        return 0
    if args.command == "resolve-contradiction":
        claim_graph = ProjectClaimGraphManager(config).resolve_contradiction(args.project_id, args.claim_a, args.claim_b, args.note)
        print(f"Resolved contradiction note recorded. Unresolved contradictions: {len(claim_graph.unresolved_contradictions)}")
        return 0
    if args.command == "create-direction":
        direction = DirectionMaturationManager(config).create_direction(args.project_id, args.gap_id)
        print(f"Created direction {direction.id} at maturity {direction.maturity}.")
        return 0
    if args.command == "list-directions":
        program = ProjectMemoryManager(config).load_project(args.project_id)
        if not program.research_directions:
            print("No research directions.")
            return 0
        for direction in sorted(program.research_directions, key=lambda item: (-item.readiness_score, item.title)):
            print(f"{direction.id}\t{direction.maturity}\t{direction.readiness_score:.2f}\t{direction.title}")
        return 0
    if args.command == "mature-direction":
        direction = DirectionMaturationManager(config).mature_direction(args.project_id, args.direction_id)
        print(f"Matured direction {direction.id}: {direction.maturity} ({direction.readiness_score:.2f}).")
        return 0
    if args.command == "direction-card":
        direction_manager = DirectionMaturationManager(config)
        card = direction_manager.render_card(args.project_id, args.direction_id)
        direction_manager.write_card(args.project_id, args.direction_id)
        print(card, end="")
        return 0
    if args.command == "reject-direction":
        direction = DirectionMaturationManager(config).reject_direction(args.project_id, args.direction_id, args.reason)
        print(f"Rejected direction {direction.id}: {args.reason}")
        return 0
    if args.command == "related-work-matrix":
        builder = RelatedWorkMatrixBuilder(config)
        if args.project_id:
            if not args.direction_id:
                parser.error("related-work-matrix with --project-id requires --direction-id")
            matrix = builder.build_for_project(args.project_id, args.direction_id)
            print(
                f"Wrote related-work matrix for {matrix.direction_id}: {len(matrix.entries)} entries, "
                f"{len(matrix.must_read_paper_ids)} must-read, {len(matrix.baseline_paper_ids)} baselines."
            )
            return 0
        if not args.gap_id:
            parser.error("related-work-matrix with --run-id requires --gap-id")
        matrix = builder.build_for_run(args.run_id, args.gap_id)
        print(
            f"Wrote related-work matrix for {matrix.direction_id}: {len(matrix.entries)} entries, "
            f"{len(matrix.must_read_paper_ids)} must-read, {len(matrix.baseline_paper_ids)} baselines."
        )
        return 0
    if args.command == "must-read":
        paper_ids = RelatedWorkMatrixBuilder(config).must_read_for_project(args.project_id, args.direction_id)
        print("\n".join(paper_ids) if paper_ids else "No must-read papers recorded.")
        return 0
    if args.command == "experiment-protocol":
        protocol = ExperimentProtocolBuilder(config).build_for_project(args.project_id, args.direction_id)
        print(render_protocol_markdown(protocol), end="")
        return 0
    if args.command == "generate-code-tasks":
        tasks = ExperimentCodeTaskGenerator(config).generate_tasks(
            campaign_id=args.campaign_id,
            direction_id=args.direction_id,
        )
        print(json.dumps(to_plain(tasks), indent=2))
        return 0
    if args.command == "scaffold-experiment-repo":
        scaffold = ExperimentRepoScaffolder(config).scaffold(
            campaign_id=args.campaign_id,
            direction_id=args.direction_id,
        )
        print(json.dumps(to_plain(scaffold), indent=2))
        return 0
    if args.command == "codex-code-task":
        path = ExperimentCodeTaskGenerator(config).write_codex_task(args.code_task_id)
        print(path)
        return 0
    if args.command == "baselines":
        candidates = ExperimentProtocolBuilder(config).baseline_candidates_for_project(args.project_id, args.direction_id)
        print(render_baseline_candidates_markdown(candidates), end="")
        return 0
    if args.command == "reproducibility-checklist":
        checklist = ExperimentProtocolBuilder(config).reproducibility_for_run(args.run_id, args.experiment_id)
        print(render_reproducibility_checklist(checklist), end="")
        return 0
    if args.command == "review-panel":
        panel = ReviewPanelBuilder(config).build_for_project(args.project_id, args.direction_id)
        print(render_review_panel_markdown(panel), end="")
        return 0
    if args.command == "rebuttal-plan":
        review_panel_builder = ReviewPanelBuilder(config)
        review_panel_builder.rebuttal_plan_for_project(args.project_id, args.direction_id)
        program = ProjectMemoryManager(config).load_project(args.project_id)
        panels = [panel for panel in program.review_panels if panel.experiment_or_direction_id == args.direction_id]
        print(render_rebuttal_plans_markdown(panels), end="")
        return 0
    if args.command == "meta-review":
        review_panel_builder = ReviewPanelBuilder(config)
        review_panel_builder.meta_review_for_project(args.project_id, args.direction_id)
        program = ProjectMemoryManager(config).load_project(args.project_id)
        panels = [panel for panel in program.review_panels if panel.experiment_or_direction_id == args.direction_id]
        print(render_meta_review_markdown(panels), end="")
        return 0
    if args.command == "export-paper-package":
        package = PaperPackageExporter(config).export_project_direction(
            args.project_id,
            args.direction_id,
            allow_rejected=args.allow_rejected,
        )
        print(
            f"Exported paper package {package.id} with {len(package.files)} files "
            f"(readiness={package.readiness}, missing={len(package.missing_requirements)})."
        )
        return 0
    if args.command == "export-manuscript":
        package = PaperPackageExporter(config).export_run_gap(args.run_id, args.gap_id, allow_rejected=args.allow_rejected)
        print(
            f"Exported manuscript package {package.id} with {len(package.files)} files "
            f"(readiness={package.readiness}, missing={len(package.missing_requirements)})."
        )
        return 0
    if args.command == "export-bib":
        exporter = PaperPackageExporter(config)
        exporter.export_project_direction(args.project_id, args.direction_id, allow_rejected=True)
        bib_program = ProjectMemoryManager(config).load_project(args.project_id)
        package_dir = Path(bib_program.project.root_dir) / "paper_packages" / args.direction_id
        bib = package_dir / "bibliography.bib"
        if bib.exists():
            print(bib.read_text(encoding="utf-8"), end="")
            return 0
        print(render_bibtex([]), end="")
        return 0
    if args.command == "build-index":
        if args.run_id:
            manager = ResearchStateManager(config)
            state = manager.load_run(args.run_id)
            manifest = build_run_index(state)
            manager.save_run(state)
        else:
            project_manager = ProjectMemoryManager(config)
            program = project_manager.load_project(args.project_id)
            manifest = build_project_index(program)
        print(f"Built {manifest.index_type} retrieval index with {manifest.document_count} documents at {manifest.path}")
        return 0
    if args.command == "search-index":
        results = (
            search_run_index(config, args.run_id, args.query, top_k=args.top_k)
            if args.run_id
            else search_project_index(config, args.project_id, args.query, top_k=args.top_k)
        )
        print(_format_retrieval_results(results))
        return 0
    if args.command == "explain-retrieval":
        results = search_run_index(config, args.run_id, args.query, top_k=args.top_k)
        state = ResearchStateManager(config).load_run(args.run_id)
        manifest = RetrievalIndexStore.for_run(state.run_dir).load_manifest()
        print(_format_retrieval_explanation(manifest, results))
        return 0
    if args.command == "llm-status":
        print(json.dumps(llm_status(LLMRuntimeConfig.from_env()), indent=2))
        return 0
    if args.command == "llm-test":
        llm_run_dir = _run_dir_for_optional_run(config, args.run_id)
        client: LLMClient
        if args.fake:
            client = FakeLLMClient(run_dir=llm_run_dir, skill_name="llm-test")
        else:
            runtime = LLMRuntimeConfig.from_env()
            if runtime.mode != "provider":
                raise ValueError("llm-test without --fake requires GAPFORGE_LLM_MODE=provider")
            client = ProviderLLMClient(config=runtime, run_dir=llm_run_dir, skill_name="llm-test")
        try:
            payload = client.complete_json(
                "Target ID: llm-test\nReturn a conservative novelty-gate JSON object.",
                schema_name="novelty-gate",
                system="You are GapForge. Return valid JSON only.",
            )
        except ProviderUnavailableError as exc:
            print(f"LLM provider unavailable: {exc}", file=sys.stderr)
            return 1
        print(json.dumps(payload, indent=2))
        return 0
    if args.command == "llm-usage":
        run_dir = Path(ResearchStateManager(config).load_run(args.run_id).run_dir)
        path = run_dir / "llm_usage.json"
        print(path.read_text(encoding="utf-8") if path.exists() else json.dumps({"calls": 0, "records": []}, indent=2))
        return 0
    if args.command == "llm-transcripts":
        state = ResearchStateManager(config).load_run(args.run_id)
        print(LLMTranscriptLogger(state.run_dir).render_markdown(), end="")
        return 0
    if args.command == "audit-artifacts":
        classifications = audit_run_artifacts(config, args.run_id) if args.run_id else audit_project_artifacts(config, args.project_id)
        print(render_artifact_audit_markdown(classifications), end="")
        return 0
    if args.command == "clean-generated":
        removed = clean_generated_run_artifacts(config, args.run_id)
        if removed:
            print("\n".join(str(path) for path in removed))
        else:
            print("No generated artifacts removed.")
        return 0
    if args.command == "export-safe-bundle":
        path = export_safe_project_bundle(config, args.project_id, include_pdfs=args.include_pdfs)
        print(f"Exported safe bundle to {path}")
        return 0
    if args.command == "cache-info":
        print(json.dumps(cache_summary(config.cache_dir), indent=2))
        return 0
    if args.command == "show-state":
        raw = ResearchStateManager(config).load_latest_raw()
        print(json.dumps(raw or {"message": "No run state found."}, indent=2))
        return 0
    if args.command == "validate-state":
        validation_result = ResearchStateManager(config).validate_latest()
        if validation_result.ok:
            print("State is valid: no validation issues found.")
            return 0
        print("State is invalid:")
        for issue in validation_result.issues:
            target_text = f" [{issue.object_id}]" if issue.object_id else ""
            print(f"- {issue.severity.upper()} {issue.code}{target_text}: {issue.message}")
        return 1
    parser.error(f"Unknown command: {args.command}")
    return 2


def _agent_client_for_command(config: GapForgeConfig, *, fake: bool):
    if fake:
        return FakeAgentClient(config)
    runtime = AgentRuntimeConfig.from_env()
    if runtime.mode == "fake":
        return FakeAgentClient(config, runtime)
    if runtime.mode in {"task-pack", "manual-handoff", "codex", "direct"}:
        return CodexAgentClient(config, runtime)
    raise AgentUnavailableError("Agent mode is off. Set GAPFORGE_AGENT_MODE=task-pack, manual-handoff, fake, or direct, or pass --fake.")


def _uses_agent_skill(args: argparse.Namespace) -> bool:
    return bool(getattr(args, "agent", None) or getattr(args, "agent_mode", None) or getattr(args, "import_output", None))


def _run_agent_skill_command(
    config: GapForgeConfig,
    *,
    run_id: str,
    skill_name: str,
    agent_mode: str | None,
    model: str,
    import_outputs: list[str] | None,
    validate_only: bool,
    gap_id: str = "",
    paper_id: str = "",
) -> int:
    manager = ResearchStateManager(config)
    state = manager.load_run(run_id)
    mode = agent_mode or ("task-pack" if not import_outputs else "task-pack")
    runtime_env = AgentRuntimeConfig.from_env()
    runtime = AgentRuntimeConfig(
        mode=mode,
        agent_name="fake-agent" if mode == "fake" else "codex",
        codex_model=model or runtime_env.codex_model,
        enable_real_runs=runtime_env.enable_real_runs,
        output_dir=runtime_env.output_dir,
        runner_command=runtime_env.runner_command,
    )
    task_spec = create_agent_task_spec(
        state,
        skill_name=skill_name,
        gap_id=gap_id,
        paper_id=paper_id,
        project_id=str(state.config.get("project_id", "")),
    )
    state.agent_task_specs.append(task_spec)
    pack_dir = CodexAgentClient(config, AgentRuntimeConfig(mode="task-pack", codex_model=runtime.codex_model)).create_task_pack(
        state, task_spec
    )
    manager.save_run(state)

    if import_outputs:
        client = CodexAgentClient(config, AgentRuntimeConfig(mode="task-pack", codex_model=runtime.codex_model))
        paths = [Path(path) for path in import_outputs]
        validation = client.validate_outputs(task_spec, paths) if validate_only else client.import_outputs(task_spec, paths)
        print(json.dumps({"task_id": task_spec.id, "task_pack": str(pack_dir), "validation": to_plain(validation)}, indent=2))
        return 0 if validation.status == "valid" else 1
    if validate_only:
        validation = CodexAgentClient(config, AgentRuntimeConfig(mode="task-pack", codex_model=runtime.codex_model)).validate_outputs(
            task_spec, []
        )
        print(json.dumps({"task_id": task_spec.id, "task_pack": str(pack_dir), "validation": to_plain(validation)}, indent=2))
        return 0 if validation.status == "valid" else 1
    if mode in {"task-pack", "manual-handoff"}:
        print(f"Wrote Codex task pack for {skill_name} to {pack_dir}")
        return 0
    if mode == "fake":
        record = FakeAgentClient(config, runtime).run_task(task_spec)
        print(json.dumps(to_plain(record), indent=2))
        return 0 if record.status == "complete" else 1
    if mode in {"codex", "direct"}:
        record = CodexAgentClient(config, runtime).run_task(task_spec)
        print(json.dumps(to_plain(record), indent=2))
        return 0 if record.status in {"complete", "planned"} else 1
    raise AgentUnavailableError(f"Unsupported agent mode: {mode}")


def _load_agent_task(config: GapForgeConfig, task_id: str):
    manager = ResearchStateManager(config)
    for run_dir in sorted(config.runs_dir.glob("*"), reverse=True):
        if not run_dir.is_dir():
            continue
        try:
            state = manager.load_run(run_dir.name)
        except (FileNotFoundError, ValueError, json.JSONDecodeError):
            continue
        for task_spec in state.agent_task_specs:
            if task_spec.id == task_id:
                return task_spec
    raise FileNotFoundError(f"No agent task found for {task_id}")


def _source_names(raw: str) -> list[str] | None:
    return [name.strip() for name in raw.split(",") if name.strip()] if raw else None


def _format_gap_list(state: ResearchRunState) -> str:
    from gapforge.review.audit import is_locked, is_rejected, latest_action

    if not state.gaps:
        return "No gaps recorded."
    lines = [f"Gaps for {state.run_id}:"]
    for gap in state.gaps:
        action = latest_action(state, "gap", gap.id) or "unreviewed"
        markers = []
        if is_rejected(state, "gap", gap.id):
            markers.append("rejected")
        if is_locked(state, "gap", gap.id):
            markers.append("locked")
        marker_text = f" [{', '.join(markers)}]" if markers else ""
        lines.append(f"- {gap.id}: {gap.title or gap.description} ({gap.confidence}, {gap.novelty_status}, review={action}){marker_text}")
    return "\n".join(lines)


def _load_report_state(config: GapForgeConfig, run_id: str) -> ResearchRunState:
    manager = ResearchStateManager(config)
    if run_id == "latest":
        state = manager.load_latest()
        if state is None:
            raise FileNotFoundError('No run state found. Start with `gapforge run "your topic"`.')
        return state
    return manager.load_run(run_id)


def _run_dir_for_optional_run(config: GapForgeConfig, run_id: str | None) -> Path | None:
    if run_id is None:
        return None
    return Path(ResearchStateManager(config).load_run(run_id).run_dir)


def _project_status_payload(program: ResearchProgramState) -> dict[str, object]:
    project = program.project
    return {
        "project_id": project.id,
        "name": project.name,
        "status": project.status,
        "root_dir": project.root_dir,
        "run_ids": program.run_ids,
        "topic_count": len(program.topics),
        "corpus_paper_count": len(program.corpus_papers),
        "memory_record_count": len(program.memory_records),
        "research_direction_count": len(program.research_directions),
        "campaign_count": len(program.campaigns),
        "active_topic_ids": project.active_topic_ids,
    }


def _campaign_status_payload(campaign_state: CampaignState) -> dict[str, object]:
    campaign = campaign_state.campaign
    return {
        "campaign_id": campaign.id,
        "project_id": campaign.project_id,
        "topic": campaign.topic,
        "title": campaign.title,
        "status": campaign.status,
        "mode": campaign.mode,
        "source_profile": campaign.source_profile,
        "budget_id": campaign.budget_id,
        "run_ids": campaign.run_ids,
        "task_ids": campaign.task_ids,
        "decision_ids": campaign.decision_ids,
        "milestone_ids": campaign.milestone_ids,
        "step_count": len(campaign_state.steps),
        "decision_count": len(campaign_state.decisions),
        "milestone_count": len(campaign_state.milestones),
        "stop_condition_count": len(campaign_state.stop_conditions),
    }


def _format_campaign_steps(campaign_state: CampaignState) -> str:
    lines = [f"Campaign steps for {campaign_state.campaign.id}:"]
    if not campaign_state.steps:
        lines.append("- none")
    for step in campaign_state.steps:
        lines.append(f"- {step.id}\t{step.step_type}\t{step.status}\t{step.name}")
    return "\n".join(lines) + "\n"


def _format_campaign_decisions(campaign_state: CampaignState) -> str:
    lines = [f"Campaign decisions for {campaign_state.campaign.id}:"]
    if not campaign_state.decisions:
        lines.append("- none")
    for decision in campaign_state.decisions:
        lines.append(f"- {decision.id}\titer={decision.iteration}\t{decision.decision_type}\t{decision.status}\t{decision.reason}")
    return "\n".join(lines) + "\n"


def _format_retrieval_results(results: list[RetrievalResult]) -> str:
    if not results:
        return "No retrieval results."
    lines = ["Retrieval results:"]
    for index, result in enumerate(results, start=1):
        title = result.metadata.get("title", "")
        lines.append(f"{index}. {result.score:.3f} `{result.object_type}:{result.object_id}` {title} [{result.document_id}]")
        if result.locator:
            lines.append(f"   Locator: {result.locator}")
        if result.text_snippet:
            lines.append(f"   {result.text_snippet}")
    return "\n".join(lines)


def _format_retrieval_explanation(manifest: IndexManifest, results: list[RetrievalResult]) -> str:
    lines = [
        "Retrieval explanation:",
        f"- Index: `{manifest.id}`",
        f"- Documents: {manifest.document_count}",
        f"- Embedding model: {manifest.embedding_model}",
        "",
    ]
    for index, result in enumerate(results, start=1):
        lines.extend(
            [
                f"{index}. `{result.object_type}:{result.object_id}` score={result.score:.3f}",
                f"   lexical={result.lexical_score:.3f} semantic={result.semantic_score:.3f} rerank={result.rerank_score:.3f}",
                f"   locator={result.locator or 'none'}",
                f"   snippet={result.text_snippet}",
            ]
        )
    if not results:
        lines.append("No retrieval results.")
    return "\n".join(lines)


def _print_run_result(state: ResearchRunState) -> None:
    status = state.orchestrator_result.status if state.orchestrator_result else "unknown"
    report_path = Path(state.run_dir) / "final_report.md"
    suffix = f" Report: {report_path}" if report_path.exists() else ""
    print(f"{_status_verb(status)} run {state.run_id} in {state.run_dir}.{suffix}")


def _print_active_result(state: ResearchRunState) -> None:
    loop_status = state.active_loop.status if state.active_loop else "not_started"
    decisions = len(state.active_loop.decisions) if state.active_loop else 0
    report_path = Path(state.run_dir) / "final_report.md"
    suffix = f" Report: {report_path}" if report_path.exists() else ""
    print(f"Active loop {loop_status} for run {state.run_id} after {decisions} decision(s) in {state.run_dir}.{suffix}")


def _status_verb(status: str) -> str:
    return {
        "complete": "Completed",
        "planned": "Planned",
        "interrupted": "Interrupted",
        "failed": "Failed",
        "running": "Running",
    }.get(status, status.capitalize())


if __name__ == "__main__":
    raise SystemExit(main())
