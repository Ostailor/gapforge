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
    create_agent_task_spec,
)
from gapforge.agents.attestation import run_attestation_status
from gapforge.agents.codex_doctor import doctor_codex_task, doctor_to_json, render_codex_doctor_report
from gapforge.agents.codex_handoff_v2 import open_handoff_readme
from gapforge.agents.codex_setup import build_codex_setup_status, render_codex_setup_status, write_codex_setup_report
from gapforge.agents.command_runner import render_codex_command_template, run_command_template, validate_codex_command_template
from gapforge.agents.handoff import write_handoff
from gapforge.agents.output_importer import AgentOutputImporter, discover_output_paths_for_task
from gapforge.agents.repair import (
    create_agent_repair_task,
    find_agent_repair_record,
    import_repair_output,
    render_agent_repair_status,
    repair_from_campaign_validation,
    validate_repair_output,
)
from gapforge.agents.setup import render_real_run_setup
from gapforge.agents.validation import create_actual_run_attestation as create_run_actual_run_attestation
from gapforge.artifact_eval import (
    ArtifactBadgeAssessor,
    ArtifactEvaluationChecklistManager,
    ArtifactEvaluationPackageExporter,
    ArtifactEvaluationSmokeRunner,
)
from gapforge.artifacts.hygiene import (
    ArtifactHygieneAuditor,
    render_artifact_hygiene_report,
    render_gitignore_verification,
    verify_gitignore_patterns,
)
from gapforge.baselines import BaselineRegistry, render_baseline_registry_markdown
from gapforge.benchmarks import (
    BenchmarkCanaryRunner,
    BenchmarkComparisonBuilder,
    BenchmarkRegistry,
    LeaderboardBuilder,
    render_benchmark_canary_profiles,
    render_benchmark_canary_record,
    render_benchmark_comparison,
    render_benchmark_registry_markdown,
    render_leaderboard_report,
)
from gapforge.campaigns import CampaignManager, CampaignState
from gapforge.campaigns.acceptance import (
    campaign_actual_run_status,
    campaign_attestation_statuses,
    campaign_task_attestation_status,
    create_campaign_actual_run_attestation,
)
from gapforge.campaigns.context_builder import inspect_task_context, write_task_context
from gapforge.campaigns.controller import CampaignController
from gapforge.campaigns.import_workflow import expected_campaign_files, find_campaign_task, validate_import_all, write_task_handoff
from gapforge.campaigns.importer import CampaignOutputImporter
from gapforge.campaigns.novelty_loop import CampaignNoveltyLoop
from gapforge.campaigns.outputs import import_campaign_outputs, validate_campaign_outputs
from gapforge.campaigns.reporting import campaign_stop_reason
from gapforge.campaigns.research_synthesis_task import create_research_synthesis_task
from gapforge.campaigns.review import CampaignReviewManager
from gapforge.campaigns.reviewer_loop import CampaignReviewerLoop
from gapforge.campaigns.rollback import rollback_import
from gapforge.campaigns.search_agent import CampaignSearchAgent, write_campaign_search_status
from gapforge.campaigns.task_packs import CAMPAIGN_TASK_OUTPUTS, create_campaign_task_pack
from gapforge.canaries import CampaignCanaryRunManager, CanaryReviewManager, CanaryRunManager, default_canary_profiles
from gapforge.claims.project_sync import ProjectClaimGraphManager
from gapforge.cli_audit import CLICommandAuditor, render_cli_command_audit
from gapforge.compute import check_environment, detect_compute_environments, render_compute_check, render_compute_status
from gapforge.config import GapForgeConfig
from gapforge.dashboard import StaticDashboardBuilder, write_selected_idea_full_report
from gapforge.datasets import DatasetRegistry, render_dataset_registry_markdown, render_dataset_validation_markdown
from gapforge.datasets.cache import clean_dataset_cache, dataset_cache_info, render_dataset_cache_info
from gapforge.datasets.consent import DatasetConsentManager, render_dataset_consent_markdown
from gapforge.datasets.download import DatasetDownloadManager, render_dataset_download_plan, render_dataset_download_record
from gapforge.diagnostics import (
    build_real_run_diagnostic,
    diagnose_canary_markdown,
    diagnose_run_agent_markdown,
    render_real_run_diagnostic_markdown,
    write_real_run_diagnostic,
)
from gapforge.directions.maturation import DirectionMaturationManager
from gapforge.docs_audit import DocsAuditor, render_docs_audit
from gapforge.evals.benchmark import run_evals
from gapforge.experiment_code import (
    ExperimentCodeScaffolderV2,
    ExperimentCodeTaskGenerator,
    ExperimentCodeTaskManager,
    ExperimentRepoScaffolder,
    render_experiment_code_validation,
    render_import_result,
)
from gapforge.experiments.baselines import render_baseline_candidates_markdown
from gapforge.experiments.protocol import ExperimentProtocolBuilder, render_protocol_markdown
from gapforge.experiments.reproducibility import render_reproducibility_checklist
from gapforge.experiments.reproducibility_checker import ReproducibilityChecker, render_reproducibility_check_markdown
from gapforge.experiments.runner import ExperimentRunner, render_run_result
from gapforge.experiments.sweeps import (
    ExperimentSweepManager,
    parse_parameter_specs,
    parse_seed_list,
    render_ablation_plan_markdown,
    render_sweep_status,
)
from gapforge.experiments.workspace import ExperimentWorkspaceManager
from gapforge.export.bibliography import render_bibtex
from gapforge.export.paper_package import PaperPackageExporter
from gapforge.fulltext.downloader import PdfDownloader
from gapforge.fulltext.pdf_parser import FullTextParser
from gapforge.fulltext.structure import FullTextStructureParser
from gapforge.ideas import (
    IDEA_CODEX_TASK_TYPES,
    ConstructiveGapGenerator,
    CrossDomainIdeaTransferEngine,
    IdeaCodexTaskManager,
    IdeaFeedbackManager,
    IdeaMutationEngine,
    IdeaNoveltyLoop,
    IdeaPreferenceManager,
    IdeaSearchController,
    IdeaSeedGenerator,
    IdeaStore,
    IdeaTournamentRunner,
    IdeaYieldMetricCalculator,
    ResearchAgendaManager,
    SelectedIdeaProjectManager,
    TopicPortfolioGenerator,
    render_idea_discovery_report,
)
from gapforge.ingest import ManualIngestor, parse_authors
from gapforge.jobs import JobScheduler, render_job, render_job_queue, render_job_runner_result
from gapforge.llm.base import LLMClient
from gapforge.llm.config import LLMRuntimeConfig
from gapforge.llm.fake import FakeLLMClient
from gapforge.llm.providers import ProviderLLMClient, ProviderUnavailableError, llm_status
from gapforge.llm.transcripts import LLMTranscriptLogger
from gapforge.manuscript import ManuscriptManager
from gapforge.manuscript.anonymization import ManuscriptAnonymizer
from gapforge.manuscript.bibliography import ManuscriptBibliographyManager
from gapforge.manuscript.drastic_rebuttal import DrasticRevisionManager, render_drastic_revision_plan
from gapforge.manuscript.figures import ManuscriptFigureGenerator
from gapforge.manuscript.rebuttal import ManuscriptRebuttalManager
from gapforge.manuscript.reviewer_panel import ManuscriptReviewPanelBuilder, render_manuscript_review_panel_markdown
from gapforge.manuscript.revisions import ManuscriptRevisionManager
from gapforge.manuscript.submission import SubmissionPackageExporter
from gapforge.manuscript.submission_checklist import SubmissionChecklistManager
from gapforge.manuscript.tables import ManuscriptTableGenerator
from gapforge.manuscript.traceability import ManuscriptTraceabilityAuditor
from gapforge.manuscript.venue_rewriter import VenueManuscriptRewriter, rewrite_result_json
from gapforge.manuscript.venues import ManuscriptVenueManager, venue_templates_json
from gapforge.metrics import MetricRegistry, render_metric_registry_markdown, render_statistical_plan_markdown
from gapforge.metrics.low_fpr_power import (
    LowFPRPowerChecker,
    plan_low_fpr,
    render_low_fpr_check_markdown,
    render_low_fpr_plan_markdown,
)
from gapforge.migrations import (
    CompatibilityAuditor,
    MigrationManager,
    build_migration_blocker_report,
    list_historical_migration_fixtures,
    render_compatibility_audit,
    render_compatibility_audit_v2,
    render_migration_blocker_report,
    render_migration_fixtures_list,
    report_to_json,
    write_migration_blocker_report,
)
from gapforge.models import (
    AgentTaskSpec,
    IndexManifest,
    ReplicationManifest,
    ResearchProgramState,
    ResearchRunState,
    ResourceRequest,
    RetrievalResult,
    from_dict,
    to_plain,
)
from gapforge.novelty.recall_gate import (
    assess_campaign_prior_work_recall,
    assess_run_prior_work_recall,
    load_campaign_prior_work_recall_report,
    render_prior_work_recall_report,
)
from gapforge.orchestration.budgets import budget_from_name
from gapforge.orchestrator import Orchestrator
from gapforge.pilots import (
    ExternalPilotReviewManager,
    IdeaGate,
    PilotRunner,
    PilotStore,
    V2IdeaPilotRunner,
    assess_pilot_outcome,
    get_pilot_spec,
    render_idea_gate,
    render_pilot_acceptance,
    render_pilot_document,
    render_pilot_list,
    render_pilot_outcome,
    render_pilot_report,
    render_pilot_status_json,
    render_v2_pilot_status,
)
from gapforge.project_memory import ProjectMemoryManager
from gapforge.real_literature import (
    RealLiteratureCampaignManager,
    RealLiteratureReviewManager,
    build_real_campaign_dry_run,
    default_real_literature_profiles,
    render_real_campaign_dry_run,
    write_real_campaign_dry_run,
)
from gapforge.related_work.matrix import RelatedWorkMatrixBuilder
from gapforge.release_gate import (
    V04ReleaseGateEnforcer,
    V05ReleaseGateEnforcer,
    V06ReleaseGateEnforcer,
    V07ReleaseGateEnforcer,
    V08ReleaseGateEnforcer,
    V09ReleaseGateEnforcer,
    V1ReadinessGate,
    V2ReleaseGateEnforcer,
    V21ReleaseGateEnforcer,
    V22ReleaseGateEnforcer,
    V23ReleaseGateEnforcer,
    V24ReleaseGateEnforcer,
    V25ReleaseGateEnforcer,
    V26ReleaseGateEnforcer,
    render_v04_release_gate_markdown,
    render_v09_release_gate_markdown,
    render_v1_readiness_markdown,
    render_v2_release_gate_markdown,
    render_v21_release_gate_markdown,
    render_v22_release_gate_markdown,
    render_v23_release_gate_markdown,
    render_v24_release_gate_markdown,
    render_v25_release_gate_markdown,
    render_v26_release_gate_markdown,
)
from gapforge.release_gate.v05 import render_v05_release_gate_markdown
from gapforge.release_gate.v06 import render_v06_release_gate_markdown
from gapforge.release_gate.v07 import render_v07_release_gate_markdown
from gapforge.release_gate.v08 import render_v08_release_gate_markdown
from gapforge.replication import (
    ReplicationPackageExporter,
    ReplicationPackageVerifier,
    ReproducibilityMatrixBuilder,
    ReproductionRunner,
    render_replication_package_markdown,
    render_replication_status,
    render_replication_verification_markdown,
    render_reproducibility_matrix_markdown,
    render_reproduction_record_markdown,
)
from gapforge.reporting import write_final_report
from gapforge.results import (
    ErrorAnalysisBuilder,
    ResultAggregator,
    ResultDatabaseBuilder,
    ResultParser,
    ResultStatisticsAnalyzer,
    SliceAnalysisBuilder,
    render_aggregate_results_markdown,
    render_analysis_report_markdown,
    render_error_analysis_report,
    render_error_slice_markdown,
    render_result_summary_markdown,
    render_result_table_markdown,
)
from gapforge.retrieval import build_project_index, build_run_index, search_project_index, search_run_index
from gapforge.retrieval.index_store import RetrievalIndexStore
from gapforge.review.audit import render_human_reviews_markdown
from gapforge.review.edits import HumanReviewEditor
from gapforge.review.queue import ReviewQueueManager, render_review_queue_markdown
from gapforge.review_training import (
    ReviewDatasetBuilder,
    ReviewerEvaluationManager,
    ReviewerTrainingManager,
    ReviewTaxonomyLabeler,
    render_review_labels,
    reviewer_evaluation_json,
    reviewer_training_json,
)
from gapforge.reviewers import (
    DrasticReviewPanelBuilder,
    EmpiricalReviewBuilder,
    ReviewPanelBuilder,
    render_drastic_review_panel,
    render_drastic_review_rerun_result,
    render_empirical_review_markdown,
    render_meta_review_markdown,
    render_rebuttal_plans_markdown,
    render_review_panel_markdown,
)
from gapforge.safety import (
    audit_project_artifacts,
    audit_run_artifacts,
    clean_generated_run_artifacts,
    export_safe_project_bundle,
    render_artifact_audit_markdown,
)
from gapforge.search_strategy import (
    execute_search_strategy,
    plan_search_strategy,
    render_search_rounds_markdown,
    render_search_strategy_markdown,
    save_strategy,
)
from gapforge.selected_benchmark import (
    ArtifactPackageLoader,
    CollusiveAlternativeManager,
    GoNoGoManager,
    HonestNullManager,
    MainAnalysisManager,
    MainDatasetBuilder,
    MainPowerManager,
    MainRunManager,
    MonitorBaselineManager,
    PilotAnalysisManager,
    PilotDatasetBuilder,
    PilotPowerManager,
    PilotRunManager,
    RealBenchmarkExperimentManager,
    RealBenchmarkSearchManager,
    RelatedWorkCompletionManager,
    RelatedWorkCurationManager,
    RelatedWorkMatrixLoader,
    RelatedWorkReadingManager,
    RequiredRelatedWorkSearchManager,
    SelectedBenchmarkCodexTaskManager,
    SelectedBenchmarkExperimentRunner,
    SelectedBenchmarkManager,
    SelectedBenchmarkManuscriptManager,
    SelectedBenchmarkPositioningManager,
    SelectedBenchmarkPriorWorkRefreshManager,
    SelectedBenchmarkRelatedWorkManager,
    SelectedBenchmarkRelatedWorkManuscriptManager,
    SelectedBenchmarkRelatedWorkMatrixV2Manager,
    SelectedBenchmarkReviewerPanelBuilder,
    SelectedBenchmarkVettedMappingManager,
    SelectedBenchmarkWorkspaceManager,
    SelectedMainManuscriptManager,
    SelectedPilotManuscriptManager,
    SelectedVettedBenchmarkExperimentManager,
    SequentialMetricManager,
    SyntheticTraceGenerator,
    VenueArtifactIntegrationManager,
    VenueRevisionPackageManager,
    render_artifact_package_load_result,
    render_artifact_package_repair_record,
    render_collusive_distribution_report,
    render_honest_null_report,
    render_main_power_plan,
    render_main_power_report,
    render_metric_plan,
    render_pilot_power_assessment,
    render_pilot_power_plan,
    render_pilot_trace_dataset_report,
    render_positioning_report,
    render_publication_readiness_review,
    render_real_benchmark_search,
    render_related_work_completion_status,
    render_related_work_curation_report,
    render_related_work_matrix_load_result,
    render_related_work_matrix_repair_record,
    render_related_work_matrix_v2,
    render_related_work_reading_report,
    render_required_related_work_search_report,
    render_selected_main_analysis,
    render_selected_main_status,
    render_selected_paper_package_v24,
    render_selected_prior_work_dossier,
    render_selected_related_work_manuscript_revision,
    render_trace_list,
    render_venue_artifact_integration_report,
    render_venue_revision_package,
)
from gapforge.sources.canonical import canonicalize_project, canonicalize_run, load_merge_report_for_run
from gapforge.sources.coverage import refresh_source_coverage
from gapforge.sources.health import check_sources, render_source_health_markdown, write_source_health_artifacts
from gapforge.sources.http_client import cache_summary
from gapforge.sources.live_diagnostics import (
    render_live_source_diagnostic_markdown,
    run_live_source_diagnostic,
    write_live_source_diagnostic,
)
from gapforge.sources.policies import default_source_policy_profiles, get_source_policy_profile
from gapforge.sources.stopping import refresh_stopping_assessment, render_stopping_assessment_markdown
from gapforge.state import ResearchStateManager
from gapforge.style_corpus import StyleCorpusManager, VenueStyleAnalyzer
from gapforge.venues import VenueProfileManager, get_venue_profile, list_venue_profiles, render_venue_profile, render_venue_profile_list
from gapforge.vetted_benchmarks import (
    BenchmarkAdapterRegistry,
    VettedBenchmarkRegistry,
    render_eligibility_assessment,
    render_real_benchmark_adapter_assessment,
)


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

    subparsers.add_parser("pilot-list", help="List v0.9 external pilot specs, including the low-FPR collusion pilot.")

    pilot_spec_parser = subparsers.add_parser(
        "pilot-spec", help="Print the v0.9 pilot scope, acceptance, or review checklist for a named pilot."
    )
    pilot_spec_parser.add_argument("--name", required=True)
    pilot_spec_parser.add_argument("--document", choices=["spec", "acceptance", "review", "all"], default="spec")

    pilot_run_parser = subparsers.add_parser("pilot-run", help="Run the v0.9 external pilot workflow and create a durable pilot record.")
    pilot_run_parser.add_argument("--name", required=True)

    pilot_status_parser = subparsers.add_parser("pilot-status", help="Print v0.9 pilot status, blockers, artifacts, and acceptance JSON.")
    pilot_status_scope = pilot_status_parser.add_mutually_exclusive_group(required=True)
    pilot_status_scope.add_argument("--pilot-id")
    pilot_status_scope.add_argument("--name")

    pilot_report_parser = subparsers.add_parser("pilot-report", help="Print and write the final durable report for a v0.9 pilot run.")
    pilot_report_parser.add_argument("--pilot-id", required=True)

    v2_pilot_run_parser = subparsers.add_parser("v2-pilot-run", help="Run the v2 idea-discovery pilot workflow.")
    v2_pilot_run_parser.add_argument("--name", required=True)

    v2_pilot_status_parser = subparsers.add_parser("v2-pilot-status", help="Print v2 idea-discovery pilot status JSON.")
    v2_pilot_status_parser.add_argument("--name", required=True)

    v2_pilot_report_parser = subparsers.add_parser("v2-pilot-report", help="Print and write the v2 idea-discovery pilot report.")
    v2_pilot_report_parser.add_argument("--name", required=True)

    pilot_acceptance_parser = subparsers.add_parser("pilot-acceptance", help="Print whether a v0.9 pilot can count for v1 readiness.")
    pilot_acceptance_parser.add_argument("--pilot-id", required=True)

    pilot_review_parser = subparsers.add_parser("pilot-review", help="Capture external or user human review for a v0.9 pilot outcome.")
    pilot_review_parser.add_argument("--pilot-id", required=True)
    pilot_review_parser.add_argument("--reviewer-name", default="human reviewer")
    pilot_review_parser.add_argument(
        "--reviewer-role",
        choices=["user", "domain_expert", "engineer", "external_reviewer", "unknown"],
        default="unknown",
    )
    pilot_review_parser.add_argument("--scope", action="append", default=[])
    pilot_review_parser.add_argument("--novelty-assessment", default="")
    pilot_review_parser.add_argument("--evidence-assessment", default="")
    pilot_review_parser.add_argument("--experiment-assessment", default="")
    pilot_review_parser.add_argument("--manuscript-assessment", default="")
    pilot_review_parser.add_argument("--artifact-assessment", default="")
    pilot_review_parser.add_argument("--major-concern", action="append", default=[])
    pilot_review_parser.add_argument("--required-fix", action="append", default=[])
    pilot_review_parser.add_argument("--notes", default="")
    pilot_review_decision = pilot_review_parser.add_mutually_exclusive_group()
    pilot_review_decision.add_argument("--accept-outcome", action="store_true")
    pilot_review_decision.add_argument("--reject-outcome", action="store_true")
    pilot_review_parser.add_argument("--reason", default="")

    pilot_review_report_parser = subparsers.add_parser("pilot-review-report", help="Print the auditable human review report for a pilot.")
    pilot_review_report_parser.add_argument("--pilot-id", required=True)

    pilot_outcome_parser = subparsers.add_parser(
        "pilot-outcome", help="Classify a v0.9 pilot as direction, refusal, failure, or incomplete."
    )
    pilot_outcome_parser.add_argument("--pilot-id", required=True)
    pilot_outcome_parser.add_argument("--json", action="store_true")

    idea_gate_parser = subparsers.add_parser("idea-gate", help="Select one auditable v0.9 pilot research direction or record refusal.")
    idea_gate_scope = idea_gate_parser.add_mutually_exclusive_group(required=True)
    idea_gate_scope.add_argument("--pilot-id")
    idea_gate_scope.add_argument("--campaign-id")
    idea_gate_parser.add_argument("--json", action="store_true")

    selected_idea_parser = subparsers.add_parser("selected-idea", help="Print the selected pilot direction or v2 idea.")
    selected_idea_scope = selected_idea_parser.add_mutually_exclusive_group(required=True)
    selected_idea_scope.add_argument("--pilot-id")
    selected_idea_scope.add_argument("--project-id")

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

    plan_search_strategy_parser = subparsers.add_parser("plan-search-strategy", help="Plan multi-round live literature searches.")
    plan_search_strategy_parser.add_argument("topic")
    plan_search_strategy_parser.add_argument("--source-profile", default="generic")

    execute_search_strategy_parser = subparsers.add_parser("execute-search-strategy", help="Execute planned search rounds for a run.")
    execute_search_strategy_parser.add_argument("--run-id", required=True)
    execute_search_strategy_parser.add_argument("--strategy-id", required=True)

    search_rounds_parser = subparsers.add_parser("search-rounds", help="Print planned/executed search rounds for a run.")
    search_rounds_parser.add_argument("--run-id", required=True)

    prior_work_recall_parser = subparsers.add_parser("prior-work-recall", help="Run the closest-prior-work recall gate.")
    prior_work_recall_scope = prior_work_recall_parser.add_mutually_exclusive_group(required=True)
    prior_work_recall_scope.add_argument("--run-id")
    prior_work_recall_scope.add_argument("--campaign-id")
    prior_work_recall_parser.add_argument("--gap-id", default="")

    prior_work_recall_report_parser = subparsers.add_parser(
        "prior-work-recall-report", help="Print a campaign prior-work recall gate report."
    )
    prior_work_recall_report_parser.add_argument("--campaign-id", required=True)

    eval_parser = subparsers.add_parser("eval", help="Run offline fixture evaluations.")
    eval_parser.add_argument("--fixture", default=None)
    eval_parser.add_argument("--v2", action="store_true", help="Run v0.2 full-text/evidence/dossier evaluation fixtures.")
    eval_parser.add_argument("--v3", action="store_true", help="Run v0.3 curated real-world-style evaluation fixtures.")
    eval_parser.add_argument("--v4", action="store_true", help="Run v0.4 campaign and agent-behavior evaluation fixtures.")
    eval_parser.add_argument("--v5", action="store_true", help="Run v0.5 real-literature campaign quality evaluation fixtures.")
    eval_parser.add_argument("--v6", action="store_true", help="Run v0.6 experiment execution evaluation fixtures.")
    eval_parser.add_argument("--v7", action="store_true", help="Run v0.7 benchmark and replication evaluation fixtures.")
    eval_parser.add_argument("--v8", action="store_true", help="Run v0.8 manuscript submission evaluation fixtures.")
    eval_parser.add_argument("--v9", action="store_true", help="Run v0.9 pilot and v1-readiness evaluation fixtures.")
    eval_parser.add_argument("--v21", action="store_true", help="Run v2.1 selected benchmark execution evaluation fixtures.")
    eval_parser.add_argument("--v22", action="store_true", help="Run v2.2 pilot benchmark evaluation fixtures.")
    eval_parser.add_argument("--v23", action="store_true", help="Run v2.3 main benchmark decision evaluation fixtures.")
    eval_parser.add_argument("--v24", action="store_true", help="Run v2.4 related-work remediation evaluation fixtures.")
    eval_parser.add_argument("--v25", action="store_true", help="Run v2.5 real benchmark grounding evaluation fixtures.")
    eval_parser.add_argument("--v26", action="store_true", help="Run v2.6 drastic remediation evaluation fixtures.")
    eval_parser.add_argument("--v2-ideas", action="store_true", help="Run v2 Idea Discovery Engine evaluation fixtures.")
    eval_parser.add_argument("--write-report", action="store_true")

    report_parser = subparsers.add_parser("report", help="Write final_report.md or final_report.json.")
    report_parser.add_argument("--run-id", default="latest", help="Run ID to report on, or 'latest' (default).")
    report_parser.add_argument("--format", choices=["markdown", "json"], default="markdown")
    report_parser.add_argument(
        "--strict",
        action="store_true",
        help="Refuse to recommend a top direction when coverage/evidence/novelty gates are weak.",
    )

    dashboard_parser = subparsers.add_parser(
        "dashboard",
        help="Generate a static HTML dashboard for a run, project, workspace, or manuscript.",
    )
    dashboard_scope = dashboard_parser.add_mutually_exclusive_group(required=True)
    dashboard_scope.add_argument("--run-id")
    dashboard_scope.add_argument("--project-id")
    dashboard_scope.add_argument("--workspace-id")
    dashboard_scope.add_argument("--manuscript-id")
    dashboard_parser.add_argument("--open", action="store_true", help="Open the dashboard in the default browser.")
    dashboard_parser.add_argument("--include-actual-runs", action="store_true", help="Include v0.4 actual-run acceptance pages.")
    dashboard_parser.add_argument("--include-experiments", action="store_true", help="Include v0.6 experiment execution pages.")
    dashboard_parser.add_argument("--include-benchmarks", action="store_true", help="Include v0.7 benchmark execution pages.")
    dashboard_parser.add_argument("--include-replication", action="store_true", help="Include v0.7 replication pages.")
    dashboard_parser.add_argument("--include-manuscripts", action="store_true", help="Include v0.8 manuscript readiness pages.")
    dashboard_parser.add_argument("--include-ideas", action="store_true", help="Include v2 idea discovery dashboard pages.")
    dashboard_parser.add_argument(
        "--include-selected-idea",
        action="store_true",
        help="Include v2.1 selected idea execution dashboard pages.",
    )
    dashboard_parser.add_argument(
        "--include-selected-pilot",
        action="store_true",
        help="Include v2.2 selected pilot benchmark dashboard pages.",
    )
    dashboard_parser.add_argument(
        "--include-selected-main",
        action="store_true",
        help="Include v2.3 selected main benchmark dashboard pages.",
    )
    dashboard_parser.add_argument(
        "--include-selected-v24",
        action="store_true",
        help="Include v2.4 selected benchmark related-work remediation dashboard pages.",
    )
    dashboard_parser.add_argument(
        "--include-selected-v25",
        action="store_true",
        help="Include v2.5 real benchmark grounding, venue style, and reviewer calibration dashboard pages.",
    )
    dashboard_parser.add_argument(
        "--include-selected-v26",
        action="store_true",
        help="Include v2.6 drastic remediation and artifact package dashboard pages.",
    )

    selected_idea_full_report_parser = subparsers.add_parser(
        "selected-idea-full-report", help="Write and print the v2.1 selected idea execution report."
    )
    selected_idea_full_report_parser.add_argument("--project-id", required=True)

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

    canonicalize_parser = subparsers.add_parser("canonicalize-papers", help="Canonicalize and merge duplicate paper records.")
    canonicalize_target = canonicalize_parser.add_mutually_exclusive_group(required=True)
    canonicalize_target.add_argument("--run-id")
    canonicalize_target.add_argument("--project-id")

    paper_merge_report_parser = subparsers.add_parser("paper-merge-report", help="Print the paper merge report for a run.")
    paper_merge_report_parser.add_argument("--run-id", required=True)

    source_health_parser = subparsers.add_parser("source-health", help="Check live research source readiness.")
    source_health_parser.add_argument("--source", default=None, help="Optional source name such as arxiv, openreview, or semantic-scholar.")
    source_health_parser.add_argument("--topic", default="machine learning survey", help="Tiny query/topic used for the health probe.")
    source_health_parser.add_argument("--write-report", action="store_true", help="Write ignored data/source_health artifacts.")

    live_source_parser = subparsers.add_parser(
        "live-source-diagnostic", help="Evaluate live source readiness against a source policy profile."
    )
    live_source_parser.add_argument("--topic", required=True)
    live_source_parser.add_argument("--source-profile", default="generic")
    live_source_parser.add_argument("--write-report", action="store_true")

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

    setup_codex_parser = subparsers.add_parser("setup-codex", help="Diagnose Codex/GPT-5.4 setup and recommend an execution mode.")
    setup_codex_parser.add_argument("--json", action="store_true")
    setup_codex_parser.add_argument("--write-report", action="store_true")

    agent_capabilities_parser = subparsers.add_parser("agent-capabilities", help="Show v0.4 AgentClient runtime capabilities.")
    agent_capabilities_parser.add_argument("--json", action="store_true")

    task_handoff_parser = subparsers.add_parser("task-handoff", help="Write HANDOFF.md for a run or campaign agent task.")
    task_handoff_parser.add_argument("--task-id", required=True)

    codex_handoff_parser = subparsers.add_parser("codex-handoff", help="Write a copy-paste-ready Codex/GPT-5.4 handoff bundle.")
    codex_handoff_target = codex_handoff_parser.add_mutually_exclusive_group(required=True)
    codex_handoff_target.add_argument("--task-id")
    codex_handoff_target.add_argument("--campaign-id")
    codex_handoff_parser.add_argument("--latest-task", action="store_true", help="Use the latest task in the campaign.")
    codex_handoff_parser.add_argument("--print-prompt", action="store_true")
    codex_handoff_parser.add_argument("--open", action="store_true")

    codex_doctor_parser = subparsers.add_parser(
        "codex-doctor",
        help="Diagnose Codex task-pack outputs, validation, import, and acceptance state.",
    )
    codex_doctor_target = codex_doctor_parser.add_mutually_exclusive_group(required=True)
    codex_doctor_target.add_argument("--task-id")
    codex_doctor_target.add_argument("--campaign-id")
    codex_doctor_parser.add_argument("--json", action="store_true")

    repair_agent_output_parser = subparsers.add_parser("repair-agent-output", help="Explain how to fix invalid agent output.")
    repair_agent_output_parser.add_argument("--task-id", required=True)
    repair_agent_output_parser.add_argument("--path", action="append", default=[])
    repair_agent_output_parser.add_argument("--latest-invalid", action="store_true")
    repair_agent_output_parser.add_argument("--handoff", action="store_true")
    repair_agent_output_parser.add_argument("--print-prompt", action="store_true")

    repair_status_parser = subparsers.add_parser("repair-status", help="Print an agent repair record.")
    repair_status_parser.add_argument("--repair-id", required=True)

    validate_repair_parser = subparsers.add_parser("validate-repair-output", help="Validate outputs for a generated repair task.")
    validate_repair_parser.add_argument("--repair-id", required=True)

    import_repair_parser = subparsers.add_parser(
        "import-repair-output", help="Import outputs for a generated repair task after validation."
    )
    import_repair_parser.add_argument("--repair-id", required=True)

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
    agent_import_parser.add_argument("--path", action="append", default=[])
    agent_import_parser.add_argument("--all", action="store_true")
    agent_import_parser.add_argument("--allow-partial", action="store_true", default=True)
    agent_import_parser.add_argument("--strict-files", action="store_true")

    agent_validate_parser = subparsers.add_parser("agent-validate-output", help="Validate agent output without importing it.")
    agent_validate_parser.add_argument("--task-id", required=True)
    agent_validate_parser.add_argument("--path", action="append")
    agent_validate_parser.add_argument("--all", action="store_true")
    agent_validate_parser.add_argument("--allow-partial", action="store_true", default=True)
    agent_validate_parser.add_argument("--strict-files", action="store_true")

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

    attestation_status_parser = subparsers.add_parser(
        "attestation-status", help="Show validation/import/attestation/human-review blockers for actual-run tasks."
    )
    attestation_status_scope = attestation_status_parser.add_mutually_exclusive_group(required=True)
    attestation_status_scope.add_argument("--task-id")
    attestation_status_scope.add_argument("--campaign-id")

    actual_run_status_parser = subparsers.add_parser(
        "actual-run-status", help="Report whether a run has auditable actual-agent acceptance."
    )
    actual_run_status_scope = actual_run_status_parser.add_mutually_exclusive_group(required=True)
    actual_run_status_scope.add_argument("--run-id")
    actual_run_status_scope.add_argument("--project-id")
    actual_run_status_scope.add_argument("--campaign-id")

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
    validate_agent_output_parser.add_argument("--all", action="store_true")
    validate_agent_output_parser.add_argument("--allow-partial", action="store_true", default=True)
    validate_agent_output_parser.add_argument("--strict-files", action="store_true")

    import_agent_output_parser = subparsers.add_parser(
        "import-agent-output", help="Import outputs in a Codex task outputs/ dir after validation."
    )
    import_agent_output_parser.add_argument("--task-id", required=True)
    import_agent_output_parser.add_argument("--all", action="store_true")
    import_agent_output_parser.add_argument("--allow-partial", action="store_true", default=True)
    import_agent_output_parser.add_argument("--strict-files", action="store_true")

    list_agent_tasks_parser = subparsers.add_parser("list-agent-tasks", help="List Codex/GPT-5.4 agent task packs for a run.")
    list_agent_tasks_parser.add_argument("--run-id", required=True)

    list_task_outputs_parser = subparsers.add_parser("list-task-outputs", help="List discovered output files for a Codex task.")
    list_task_outputs_parser.add_argument("--task-id", required=True)

    latest_codex_task_parser = subparsers.add_parser("latest-codex-task", help="Print the latest Codex task ID for a campaign.")
    latest_codex_task_parser.add_argument("--campaign-id", required=True)

    codex_run_parser = subparsers.add_parser("codex-run", help="Run a Codex task through direct command or handoff mode.")
    codex_run_parser.add_argument("--task-id", required=True)
    codex_run_parser.add_argument("--direct", action="store_true", help="Prefer the configured direct Codex command path.")
    codex_run_parser.add_argument("--handoff", action="store_true", help="Write explicit handoff instructions instead of running directly.")
    codex_run_parser.add_argument("--require-direct", action="store_true", help="Fail if the direct Codex command path is unavailable.")
    codex_run_parser.add_argument("--dry-run", action="store_true", help="Render the direct command preview without executing it.")
    codex_run_parser.add_argument(
        "--allow-unknown-placeholders",
        action="store_true",
        help="Render unknown command placeholders literally instead of failing validation.",
    )

    codex_command_preview_parser = subparsers.add_parser("codex-command-preview", help="Preview the direct Codex command for a task.")
    codex_command_preview_parser.add_argument("--task-id", required=True)
    codex_command_preview_parser.add_argument("--allow-unknown-placeholders", action="store_true")

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

    campaign_canary_complete_parser = subparsers.add_parser(
        "campaign-canary-complete", help="Check whether a single-task handoff canary has completed acceptance."
    )
    campaign_canary_complete_parser.add_argument("--canary-id", required=True)

    subparsers.add_parser("real-literature-profiles", help="List v0.5 real-literature campaign profiles.")

    real_literature_plan_parser = subparsers.add_parser("real-literature-plan", help="Print a v0.5 real-literature campaign plan.")
    real_literature_plan_parser.add_argument("--profile", required=True)

    real_literature_run_parser = subparsers.add_parser(
        "real-literature-run", help="Create a v0.5 real-literature campaign record from live source diagnostics."
    )
    real_literature_run_parser.add_argument("--profile", required=True)

    real_literature_status_parser = subparsers.add_parser("real-literature-status", help="Print a real-literature campaign record.")
    real_literature_status_parser.add_argument("--record-id", required=True)

    real_campaign_dry_run_parser = subparsers.add_parser(
        "real-campaign-dry-run", help="Preview a broad v0.5 real-literature campaign without network or Codex calls."
    )
    real_campaign_dry_run_parser.add_argument(
        "--profile", default="", help="Real-literature profile ID, for example live_low_fpr_collusion."
    )
    real_campaign_dry_run_parser.add_argument("--topic", default="", help="Custom topic when no profile is used.")
    real_campaign_dry_run_parser.add_argument("--source-profile", default="generic", help="Source policy profile for custom topics.")
    real_campaign_dry_run_parser.add_argument("--write-report", action="store_true", help="Write dry-run JSON/Markdown under data/.")

    real_literature_review_parser = subparsers.add_parser(
        "real-literature-review", help="Render or record v0.5 real-literature research-quality review."
    )
    real_literature_review_parser.add_argument("--campaign-id", required=True)
    real_literature_review_parser.add_argument("--accept-quality", action="store_true")
    real_literature_review_parser.add_argument("--reviewer", default="human")
    real_literature_review_parser.add_argument("--reason", default="")
    real_literature_review_parser.add_argument("--source-quality-score", type=int, default=0)
    real_literature_review_parser.add_argument("--paper-relevance-score", type=int, default=0)
    real_literature_review_parser.add_argument("--prior-work-recall-score", type=int, default=0)
    real_literature_review_parser.add_argument("--evidence-grounding-score", type=int, default=0)
    real_literature_review_parser.add_argument("--novelty-honesty-score", type=int, default=0)
    real_literature_review_parser.add_argument("--gap-importance-score", type=int, default=0)
    real_literature_review_parser.add_argument("--experiment-feasibility-score", type=int, default=0)
    real_literature_review_parser.add_argument("--reviewer-objection-quality-score", type=int, default=0)
    real_literature_review_parser.add_argument("--report-honesty-score", type=int, default=0)
    real_literature_review_parser.add_argument("--missed-obvious-prior-work", action="store_true")
    real_literature_review_parser.add_argument("--fake-citation-found", action="store_true")
    real_literature_review_parser.add_argument("--unsupported-high-confidence-claim-found", action="store_true")
    real_literature_review_parser.add_argument("--overclaimed-novelty", action="store_true")

    real_literature_acceptance_parser = subparsers.add_parser(
        "real-literature-acceptance", help="Print v0.5 real-literature workflow and research-quality acceptance."
    )
    real_literature_acceptance_parser.add_argument("--campaign-id", required=True)

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

    list_projects_parser = subparsers.add_parser("list-projects", aliases=["project-list"], help="List project memory workspaces.")
    list_projects_parser.set_defaults(command="list-projects")

    use_project_parser = subparsers.add_parser("use-project", aliases=["project-use"], help="Set the active project memory workspace.")
    use_project_parser.set_defaults(command="use-project")
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
    campaign_run_parser.add_argument(
        "--real-literature",
        action="store_true",
        help="Use the v0.5 real-literature quality decision policy.",
    )

    campaign_next_parser = subparsers.add_parser("campaign-next", help="Preview the next v0.4 campaign controller action.")
    campaign_next_parser.add_argument("--campaign-id", required=True)
    campaign_next_parser.add_argument(
        "--real-literature",
        action="store_true",
        help="Preview the v0.5 real-literature quality decision policy.",
    )

    campaign_stop_parser = subparsers.add_parser("campaign-stop", help="Pause a campaign with an explicit reason.")
    campaign_stop_parser.add_argument("--campaign-id", required=True)
    campaign_stop_parser.add_argument("--reason", required=True)

    campaign_resume_parser = subparsers.add_parser("campaign-resume", help="Resume a paused campaign.")
    campaign_resume_parser.add_argument("--campaign-id", required=True)

    campaign_task_parser = subparsers.add_parser("campaign-task", help="Create a campaign-level Codex/GPT-5.4 task pack.")
    campaign_task_parser.add_argument("--campaign-id", required=True)
    campaign_task_parser.add_argument("--type", required=True, choices=sorted(CAMPAIGN_TASK_OUTPUTS))

    research_synthesis_task_parser = subparsers.add_parser(
        "research-synthesis-task", help="Create a real-literature Codex research synthesis task pack."
    )
    research_synthesis_task_parser.add_argument("--campaign-id", required=True)

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

    validate_import_all_parser = subparsers.add_parser("validate-import-all", help="Validate and import all discovered task outputs.")
    validate_import_all_target = validate_import_all_parser.add_mutually_exclusive_group(required=True)
    validate_import_all_target.add_argument("--task-id")
    validate_import_all_target.add_argument("--campaign-id")

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
    v4_release_gate_parser.add_argument("--explain", action="store_true")
    v4_release_gate_parser.add_argument("--next-commands", action="store_true")

    v5_release_gate_parser = subparsers.add_parser("v5-release-gate", help="Enforce the v0.5 real-literature quality release gate.")
    v5_release_gate_parser.add_argument("--project-id", default="")
    v5_release_gate_parser.add_argument("--write-report", action="store_true")
    v5_release_gate_parser.add_argument("--json", action="store_true")

    v6_release_gate_parser = subparsers.add_parser("v6-release-gate", help="Enforce the v0.6 empirical validation release gate.")
    v6_release_gate_parser.add_argument("--write-report", action="store_true")
    v6_release_gate_parser.add_argument("--json", action="store_true")

    v7_release_gate_parser = subparsers.add_parser(
        "v7-release-gate", help="Enforce the v0.7 benchmark execution and replication release gate."
    )
    v7_release_gate_parser.add_argument("--write-report", action="store_true")
    v7_release_gate_parser.add_argument("--json", action="store_true")
    v7_release_gate_parser.add_argument(
        "--claim-real",
        action="store_true",
        help="Require opt-in real/local benchmark validation evidence in addition to the fixture benchmark gate.",
    )

    v8_release_gate_parser = subparsers.add_parser(
        "v8-release-gate", help="Enforce the v0.8 manuscript, artifact-evaluation, and rebuttal release gate."
    )
    v8_release_gate_parser.add_argument("--write-report", action="store_true")
    v8_release_gate_parser.add_argument("--json", action="store_true")

    v9_release_gate_parser = subparsers.add_parser("v9-release-gate", help="Enforce the v0.9 external pilot release gate.")
    v9_release_gate_parser.add_argument("--write-report", action="store_true")
    v9_release_gate_parser.add_argument("--json", action="store_true")

    v1_readiness_parser = subparsers.add_parser(
        "v1-readiness", aliases=["v1-gate"], help="Evaluate whether v1 is ready after the v0.9 pilot."
    )
    v1_readiness_parser.set_defaults(command="v1-readiness")
    v1_readiness_parser.add_argument("--write-report", action="store_true")
    v1_readiness_parser.add_argument("--json", action="store_true")
    v1_readiness_parser.add_argument("--explain", action="store_true", help="Print detailed blockers, warnings, and next commands.")
    v1_readiness_parser.add_argument("--next-commands", action="store_true", help="Print only the commands needed to unblock v1.")

    v2_release_gate_parser = subparsers.add_parser("v2-release-gate", help="Enforce the v2 Idea Discovery Engine release gate.")
    v2_release_gate_parser.add_argument("--allow-agenda-only", action="store_true")
    v2_release_gate_parser.add_argument("--write-report", action="store_true")
    v2_release_gate_parser.add_argument("--json", action="store_true")

    v21_release_gate_parser = subparsers.add_parser("v21-release-gate", help="Enforce the v2.1 selected-idea execution release gate.")
    v21_release_gate_parser.add_argument("--write-report", action="store_true")
    v21_release_gate_parser.add_argument("--json", action="store_true")

    v22_release_gate_parser = subparsers.add_parser("v22-release-gate", help="Enforce the v2.2 pilot benchmark release gate.")
    v22_release_gate_parser.add_argument("--write-report", action="store_true")
    v22_release_gate_parser.add_argument("--json", action="store_true")

    v23_release_gate_parser = subparsers.add_parser("v23-release-gate", help="Enforce the v2.3 mature decision release gate.")
    v23_release_gate_parser.add_argument("--write-report", action="store_true")
    v23_release_gate_parser.add_argument("--json", action="store_true")

    v24_release_gate_parser = subparsers.add_parser("v24-release-gate", help="Enforce the v2.4 related-work remediation release gate.")
    v24_release_gate_parser.add_argument("--write-report", action="store_true")
    v24_release_gate_parser.add_argument("--json", action="store_true")

    v25_release_gate_parser = subparsers.add_parser(
        "v25-release-gate", help="Enforce the v2.5 real benchmark and reviewer calibration gate."
    )
    v25_release_gate_parser.add_argument("--write-report", action="store_true")
    v25_release_gate_parser.add_argument("--json", action="store_true")

    v26_release_gate_parser = subparsers.add_parser(
        "v26-release-gate", help="Enforce the v2.6 drastic remediation and artifact package gate."
    )
    v26_release_gate_parser.add_argument("--write-report", action="store_true")
    v26_release_gate_parser.add_argument("--json", action="store_true")

    cli_audit_parser = subparsers.add_parser("cli-audit", help="Audit command grouping, help text, and v1 CLI discoverability.")
    cli_audit_parser.add_argument("--write-report", action="store_true")

    docs_audit_parser = subparsers.add_parser("docs-audit", help="Audit v0.9/v1 documentation usability and overclaim safety.")
    docs_audit_parser.add_argument("--write-report", action="store_true")

    compatibility_audit_parser = subparsers.add_parser("compatibility-audit", help="Audit older project/run load compatibility.")
    compatibility_audit_parser.add_argument("--json", action="store_true")
    compatibility_audit_parser.add_argument("--fixtures", action="store_true", help="Include committed historical migration fixtures.")
    compatibility_audit_parser.add_argument("--v2", action="store_true", help="Run the v1-ready compatibility audit.")
    compatibility_audit_parser.add_argument("--local", action="store_true", help="Include local project/run state in the v2 audit.")
    compatibility_audit_parser.add_argument("--write-report", action="store_true")

    migration_blockers_parser = subparsers.add_parser(
        "migration-blockers", help="Report precise v0.9.1 migration blockers without claiming v1 readiness."
    )
    migration_blockers_parser.add_argument("--json", action="store_true")
    migration_blockers_parser.add_argument("--write-report", action="store_true")

    migration_fixtures_list_parser = subparsers.add_parser("migration-fixtures-list", help="List committed historical migration fixtures.")
    migration_fixtures_list_parser.add_argument("--json", action="store_true")

    migrate_project_parser = subparsers.add_parser("migrate-project", help="Back up and migrate a project to the latest schema.")
    migrate_project_parser.add_argument("--project-id", required=True)
    migrate_project_parser.add_argument("--to-version", default="latest")

    migrate_run_parser = subparsers.add_parser("migrate-run", help="Back up and migrate a run to the latest schema.")
    migrate_run_parser.add_argument("--run-id", required=True)
    migrate_run_parser.add_argument("--to-version", default="latest")

    migrate_all_parser = subparsers.add_parser("migrate-all", help="Back up and migrate all known persisted objects.")
    migrate_all_mode = migrate_all_parser.add_mutually_exclusive_group(required=True)
    migrate_all_mode.add_argument("--dry-run", action="store_true")
    migrate_all_mode.add_argument("--apply", action="store_true")
    migrate_all_parser.add_argument("--to-version", default="latest")

    subparsers.add_parser("migration-report", help="Print the latest compatibility audit and migration records.")

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

    idea_bank_create_parser = subparsers.add_parser("idea-bank-create", help="Create a v2 first-class idea bank for a project.")
    idea_bank_create_parser.add_argument("--project-id", required=True)
    idea_bank_create_parser.add_argument("--root-topic", required=True)

    idea_list_parser = subparsers.add_parser("idea-list", help="List v2 idea candidates for a project.")
    idea_list_parser.add_argument("--project-id", required=True)

    idea_report_parser = subparsers.add_parser("idea-report", help="Write and print a v2 idea candidate report.")
    idea_report_parser.add_argument("--idea-id", required=True)

    idea_review_parser = subparsers.add_parser("idea-review", help="Record or print human review for a v2 idea candidate.")
    idea_review_parser.add_argument("--idea-id", required=True)
    idea_review_parser.add_argument("--reviewer", default="")
    idea_review_parser.add_argument("--status", choices=["accepted", "rejected", "revise", "uncertain"], default="uncertain")
    idea_review_parser.add_argument("--novelty-judgment", default="")
    idea_review_parser.add_argument("--feasibility-judgment", default="")
    idea_review_parser.add_argument("--impact-judgment", default="")
    idea_review_parser.add_argument("--required-fix", action="append", dest="required_fixes", default=[])
    idea_review_parser.add_argument("--notes", default="")

    topic_portfolio_parser = subparsers.add_parser("topic-portfolio", help="Generate a v2 topic variant portfolio.")
    topic_portfolio_parser.add_argument("root_topic", nargs="?")
    topic_portfolio_parser.add_argument("--project-id", default="")

    topic_portfolio_report_parser = subparsers.add_parser("topic-portfolio-report", help="Print a v2 topic portfolio report.")
    topic_portfolio_report_parser.add_argument("--portfolio-id", required=True)

    idea_generate_parser = subparsers.add_parser("idea-generate", help="Generate v2 seed ideas from a topic portfolio and project memory.")
    idea_generate_scope = idea_generate_parser.add_mutually_exclusive_group(required=True)
    idea_generate_scope.add_argument("--project-id")
    idea_generate_scope.add_argument("--portfolio-id")
    idea_generate_parser.add_argument("--max-candidates", type=int, default=50)

    mutate_idea_parser = subparsers.add_parser("mutate-idea", help="Mutate a weak or rejected v2 idea candidate into a new seed.")
    mutate_idea_parser.add_argument("--idea-id", required=True)
    mutate_idea_parser.add_argument("--strategy", default="")

    mutate_rejected_parser = subparsers.add_parser("mutate-rejected-ideas", help="Mutate all rejected ideas retained in a project.")
    mutate_rejected_parser.add_argument("--project-id", required=True)
    mutate_rejected_parser.add_argument("--strategy", default="")

    mutation_report_parser = subparsers.add_parser("mutation-report", help="Print the v2 idea mutation audit report.")
    mutation_report_parser.add_argument("--project-id", required=True)

    constructive_gaps_parser = subparsers.add_parser(
        "constructive-gaps", help="Generate constructive gap candidates for non-method paper forms."
    )
    constructive_gaps_scope = constructive_gaps_parser.add_mutually_exclusive_group(required=True)
    constructive_gaps_scope.add_argument("--project-id")
    constructive_gaps_scope.add_argument("--campaign-id")

    constructive_gap_report_parser = subparsers.add_parser("constructive-gap-report", help="Print the constructive gap candidate report.")
    constructive_gap_report_parser.add_argument("--project-id", required=True)

    transfer_ideas_parser = subparsers.add_parser("transfer-ideas", help="Generate evidence-gated cross-domain idea transfers.")
    transfer_ideas_scope = transfer_ideas_parser.add_mutually_exclusive_group(required=True)
    transfer_ideas_scope.add_argument("--project-id")
    transfer_ideas_scope.add_argument("--topic")

    transfer_report_parser = subparsers.add_parser("transfer-report", help="Print the cross-domain idea transfer report.")
    transfer_report_parser.add_argument("--project-id", required=True)

    idea_codex_task_parser = subparsers.add_parser("idea-codex-task", help="Create a validation-gated Codex idea synthesis task pack.")
    idea_codex_task_parser.add_argument("--project-id", required=True)
    idea_codex_task_parser.add_argument("--type", required=True, choices=sorted(IDEA_CODEX_TASK_TYPES))

    idea_codex_handoff_parser = subparsers.add_parser("idea-codex-handoff", help="Print a Codex idea synthesis task handoff.")
    idea_codex_handoff_parser.add_argument("--task-id", required=True)

    idea_codex_import_parser = subparsers.add_parser("idea-codex-import", help="Validate and import Codex idea synthesis outputs.")
    idea_codex_import_parser.add_argument("--task-id", required=True)

    idea_search_parser = subparsers.add_parser("idea-search", help="Run the active v2 idea search controller.")
    idea_search_parser.add_argument("--project-id", required=True)
    idea_search_parser.add_argument("--max-iterations", type=int, default=5)

    idea_search_status_parser = subparsers.add_parser("idea-search-status", help="Print active v2 idea search status.")
    idea_search_status_parser.add_argument("--project-id", required=True)

    idea_search_decisions_parser = subparsers.add_parser("idea-search-decisions", help="Print persisted active v2 idea search decisions.")
    idea_search_decisions_parser.add_argument("--project-id", required=True)

    idea_novelty_parser = subparsers.add_parser("idea-novelty", help="Run idea-specific novelty and counterevidence assessment.")
    idea_novelty_scope = idea_novelty_parser.add_mutually_exclusive_group(required=True)
    idea_novelty_scope.add_argument("--idea-id")
    idea_novelty_scope.add_argument("--project-id")
    idea_novelty_parser.add_argument("--top-k", type=int, default=10)

    idea_counterevidence_parser = subparsers.add_parser("idea-counterevidence", help="Find and persist counterevidence for an idea.")
    idea_counterevidence_parser.add_argument("--idea-id", required=True)
    idea_counterevidence_parser.add_argument("--top-k", type=int, default=10)

    idea_tournament_parser = subparsers.add_parser("idea-tournament", help="Run transparent tournament scoring for v2 ideas.")
    idea_tournament_parser.add_argument("--project-id", required=True)
    idea_tournament_parser.add_argument("--top-k", type=int, default=5)

    idea_score_report_parser = subparsers.add_parser("idea-score-report", help="Print the latest idea tournament score report.")
    idea_score_report_parser.add_argument("--project-id", required=True)

    idea_preferences_parser = subparsers.add_parser("idea-preferences", help="Save or print human idea preference profile.")
    idea_preferences_parser.add_argument("--project-id", required=True)
    idea_preferences_parser.add_argument("--preferred-contribution-type", action="append", dest="preferred_contribution_types", default=[])
    idea_preferences_parser.add_argument("--preferred-domain", action="append", dest="preferred_domains", default=[])
    idea_preferences_parser.add_argument("--risk-tolerance", default="")
    idea_preferences_parser.add_argument("--time-budget", default="")
    idea_preferences_parser.add_argument("--compute-budget", default="")
    idea_preferences_parser.add_argument("--publication-target", default="")
    idea_preferences_parser.add_argument("--avoid-topic", action="append", dest="avoid_topics", default=[])
    idea_preferences_parser.add_argument("--notes", default="")

    idea_feedback_parser = subparsers.add_parser("idea-feedback", help="Record auditable human feedback for an idea.")
    idea_feedback_parser.add_argument("--idea-id", required=True)
    idea_feedback_parser.add_argument(
        "--action",
        required=True,
        choices=sorted(["upvote", "downvote", "reject", "request_mutation", "request_search", "accept"]),
    )
    idea_feedback_parser.add_argument("--reviewer", default="human")
    idea_feedback_parser.add_argument("--rationale", default="")
    idea_feedback_parser.add_argument("--preferred-mutation", action="append", dest="preferred_mutations", default=[])
    idea_feedback_parser.add_argument("--notes", default="")

    idea_feedback_report_parser = subparsers.add_parser("idea-feedback-report", help="Print the idea feedback audit report.")
    idea_feedback_report_parser.add_argument("--project-id", required=True)

    idea_yield_parser = subparsers.add_parser("idea-yield", help="Compute v2 idea yield metrics for a project.")
    idea_yield_parser.add_argument("--project-id", required=True)
    idea_yield_parser.add_argument("--write-report", action="store_true")

    selected_idea_lock_parser = subparsers.add_parser("selected-idea-lock", help="Lock a v2 selected idea for v2.1 execution.")
    selected_idea_lock_parser.add_argument("--idea-id", required=True)
    selected_idea_lock_parser.add_argument("--locked-by", default="human")
    selected_idea_lock_parser.add_argument(
        "--lock-reason",
        default="Freeze the v2 selected idea as the canonical v2.1 research target.",
    )
    selected_idea_lock_parser.add_argument("--force", action="store_true")

    selected_idea_project_create_parser = subparsers.add_parser(
        "selected-idea-project-create", help="Create a dedicated v2.1 research project from a locked selected idea."
    )
    selected_idea_project_create_parser.add_argument("--idea-id", required=True)
    selected_idea_project_create_parser.add_argument("--locked-by", default="human")
    selected_idea_project_create_parser.add_argument(
        "--lock-reason",
        default="Freeze the v2 selected idea as the canonical v2.1 research target.",
    )
    selected_idea_project_create_parser.add_argument("--force", action="store_true")

    selected_idea_status_parser = subparsers.add_parser("selected-idea-status", help="Print selected v2.1 research project status.")
    selected_idea_status_parser.add_argument("--project-id", required=True)

    selected_benchmark_spec_parser = subparsers.add_parser(
        "selected-benchmark-spec", help="Create the formal selected-idea benchmark specification."
    )
    selected_benchmark_spec_parser.add_argument("--project-id", required=True)

    threat_model_parser = subparsers.add_parser("threat-model", help="Create the selected benchmark collusion threat model.")
    threat_model_parser.add_argument("--benchmark-id", required=True)

    benchmark_task_families_parser = subparsers.add_parser(
        "benchmark-task-families", help="Create task families for the selected benchmark."
    )
    benchmark_task_families_parser.add_argument("--benchmark-id", required=True)

    selected_benchmark_report_parser = subparsers.add_parser(
        "selected-benchmark-report", help="Print the selected benchmark specification report."
    )
    selected_benchmark_report_parser.add_argument("--benchmark-id", required=True)

    selected_vetted_benchmark_map_parser = subparsers.add_parser(
        "selected-vetted-benchmark-map", help="Map selected benchmark protocol to registered vetted benchmarks."
    )
    selected_vetted_benchmark_map_parser.add_argument("--benchmark-id", required=True)
    selected_vetted_benchmark_map_parser.add_argument("--vetted-benchmark-id", default="")

    selected_vetted_benchmark_report_parser = subparsers.add_parser(
        "selected-vetted-benchmark-report", help="Render selected benchmark vetted-benchmark mapping report."
    )
    selected_vetted_benchmark_report_parser.add_argument("--benchmark-id", required=True)

    selected_real_benchmark_search_parser = subparsers.add_parser(
        "selected-real-benchmark-search", help="Search real public benchmark candidates for selected benchmark grounding."
    )
    selected_real_benchmark_search_parser.add_argument("--benchmark-id", required=True)

    selected_real_benchmark_candidates_parser = subparsers.add_parser(
        "selected-real-benchmark-candidates", help="Render real public benchmark candidates for selected benchmark grounding."
    )
    selected_real_benchmark_candidates_parser.add_argument("--benchmark-id", required=True)

    selected_real_benchmark_no_fit_parser = subparsers.add_parser(
        "selected-real-benchmark-no-fit", help="Render selected benchmark real-public-benchmark no-fit report."
    )
    selected_real_benchmark_no_fit_parser.add_argument("--benchmark-id", required=True)

    selected_real_benchmark_adapter_assess_parser = subparsers.add_parser(
        "selected-real-benchmark-adapter-assess", help="Assess adapter feasibility for a real public benchmark candidate."
    )
    selected_real_benchmark_adapter_assess_parser.add_argument("--benchmark-id", required=True)
    selected_real_benchmark_adapter_assess_parser.add_argument("--candidate-id", required=True)

    selected_real_benchmark_adapter_create_parser = subparsers.add_parser(
        "selected-real-benchmark-adapter-create", help="Create an honest adapter for a real public benchmark candidate."
    )
    selected_real_benchmark_adapter_create_parser.add_argument("--benchmark-id", required=True)
    selected_real_benchmark_adapter_create_parser.add_argument("--candidate-id", required=True)

    selected_real_benchmark_adapter_run_parser = subparsers.add_parser(
        "selected-real-benchmark-adapter-run", help="Run a real public benchmark candidate adapter."
    )
    selected_real_benchmark_adapter_run_parser.add_argument("--adapter-id", required=True)

    selected_real_benchmark_experiment_plan_parser = subparsers.add_parser(
        "selected-real-benchmark-experiment-plan",
        help="Plan real public benchmark experiment attempts for the selected benchmark.",
    )
    selected_real_benchmark_experiment_plan_parser.add_argument("--benchmark-id", required=True)

    selected_real_benchmark_experiment_run_parser = subparsers.add_parser(
        "selected-real-benchmark-experiment-run",
        help="Run planned real public benchmark experiment attempts for the selected benchmark.",
    )
    selected_real_benchmark_experiment_run_parser.add_argument("--benchmark-id", required=True)

    selected_real_benchmark_experiment_report_parser = subparsers.add_parser(
        "selected-real-benchmark-experiment-report",
        help="Render real public benchmark experiment attempt report for the selected benchmark.",
    )
    selected_real_benchmark_experiment_report_parser.add_argument("--benchmark-id", required=True)

    selected_venue_artifact_integrate_parser = subparsers.add_parser(
        "selected-venue-artifact-integrate",
        help="Integrate loadable v2.6 artifacts into the venue-shaped selected benchmark manuscript.",
    )
    selected_venue_artifact_integrate_parser.add_argument("--benchmark-id", required=True)

    selected_venue_artifact_report_parser = subparsers.add_parser(
        "selected-venue-artifact-report",
        help="Render selected benchmark venue artifact integration report.",
    )
    selected_venue_artifact_report_parser.add_argument("--benchmark-id", required=True)

    selected_venue_revision_package_parser = subparsers.add_parser(
        "selected-venue-revision-package",
        help="Create a post-review venue revision package for the selected benchmark manuscript.",
    )
    selected_venue_revision_package_parser.add_argument("--benchmark-id", required=True)

    selected_venue_revision_status_parser = subparsers.add_parser(
        "selected-venue-revision-status",
        help="Print selected benchmark venue revision package status.",
    )
    selected_venue_revision_status_parser.add_argument("--benchmark-id", required=True)

    benchmark_adapter_create_parser = subparsers.add_parser(
        "benchmark-adapter-create", help="Create an adapter from a vetted benchmark to a selected benchmark."
    )
    benchmark_adapter_create_parser.add_argument("--selected-benchmark-id", required=True)
    benchmark_adapter_create_parser.add_argument("--vetted-benchmark-id", required=True)

    benchmark_adapter_run_parser = subparsers.add_parser(
        "benchmark-adapter-run", help="Run a vetted benchmark adapter on its registered dataset."
    )
    benchmark_adapter_run_parser.add_argument("--adapter-id", required=True)

    benchmark_adapter_report_parser = subparsers.add_parser("benchmark-adapter-report", help="Render a vetted benchmark adapter report.")
    benchmark_adapter_report_parser.add_argument("--adapter-id", required=True)

    selected_vetted_experiment_plan_parser = subparsers.add_parser(
        "selected-vetted-experiment-plan", help="Plan selected-benchmark experiments on vetted benchmark adapters."
    )
    selected_vetted_experiment_plan_parser.add_argument("--benchmark-id", required=True)

    selected_vetted_experiment_run_parser = subparsers.add_parser(
        "selected-vetted-experiment-run", help="Run a selected-benchmark vetted-adapter experiment plan."
    )
    selected_vetted_experiment_run_parser.add_argument("--plan-id", required=True)

    selected_vetted_experiment_report_parser = subparsers.add_parser(
        "selected-vetted-experiment-report", help="Render a selected-benchmark vetted-adapter experiment report."
    )
    selected_vetted_experiment_report_parser.add_argument("--plan-id", required=True)

    generate_traces_parser = subparsers.add_parser("generate-traces", help="Generate synthetic selected-benchmark traces.")
    generate_traces_parser.add_argument("--benchmark-id", required=True)
    generate_traces_parser.add_argument("--count", type=int, default=100)
    generate_traces_parser.add_argument("--split", default="smoke", choices=["smoke", "pilot"])

    honest_null_scenarios_parser = subparsers.add_parser(
        "honest-null-scenarios", help="Create expanded honest-null pilot scenarios for the selected benchmark."
    )
    honest_null_scenarios_parser.add_argument("--benchmark-id", required=True)

    generate_honest_null_parser = subparsers.add_parser(
        "generate-honest-null", help="Generate expanded honest-null pilot traces for the selected benchmark."
    )
    generate_honest_null_parser.add_argument("--benchmark-id", required=True)
    generate_honest_null_parser.add_argument("--count", type=int, default=300)

    honest_null_report_parser = subparsers.add_parser(
        "honest-null-report", help="Render the selected benchmark honest-null distribution report."
    )
    honest_null_report_parser.add_argument("--benchmark-id", required=True)

    collusive_scenarios_parser = subparsers.add_parser(
        "collusive-scenarios", help="Create expanded collusive pilot scenarios for the selected benchmark."
    )
    collusive_scenarios_parser.add_argument("--benchmark-id", required=True)

    generate_collusive_traces_parser = subparsers.add_parser(
        "generate-collusive-traces", help="Generate expanded collusive pilot traces for the selected benchmark."
    )
    generate_collusive_traces_parser.add_argument("--benchmark-id", required=True)
    generate_collusive_traces_parser.add_argument("--count", type=int, default=150)

    collusive_distribution_report_parser = subparsers.add_parser(
        "collusive-distribution-report", help="Render the selected benchmark collusive alternative distribution report."
    )
    collusive_distribution_report_parser.add_argument("--benchmark-id", required=True)

    build_pilot_trace_dataset_parser = subparsers.add_parser(
        "build-pilot-trace-dataset", help="Build the combined v2.2 pilot trace dataset."
    )
    build_pilot_trace_dataset_parser.add_argument("--benchmark-id", required=True)
    build_pilot_trace_dataset_parser.add_argument("--negative-count", type=int, default=300)
    build_pilot_trace_dataset_parser.add_argument("--positive-count", type=int, default=150)

    pilot_trace_dataset_report_parser = subparsers.add_parser(
        "pilot-trace-dataset-report", help="Render a selected benchmark pilot trace dataset report."
    )
    pilot_trace_dataset_report_parser.add_argument("--dataset-id", required=True)

    build_main_trace_dataset_parser = subparsers.add_parser(
        "build-main-trace-dataset", help="Build or feasibility-gate the selected benchmark main trace dataset."
    )
    build_main_trace_dataset_parser.add_argument("--benchmark-id", required=True)
    build_main_trace_dataset_parser.add_argument("--negative-count", type=int, default=None)
    build_main_trace_dataset_parser.add_argument("--positive-count", type=int, default=None)

    main_trace_dataset_report_parser = subparsers.add_parser(
        "main-trace-dataset-report", help="Render a selected benchmark main trace dataset report."
    )
    main_trace_dataset_report_parser.add_argument("--dataset-id", required=True)

    selected_main_manifest_parser = subparsers.add_parser("selected-main-manifest", help="Create a selected benchmark main run manifest.")
    selected_main_manifest_parser.add_argument("--benchmark-id", required=True)
    selected_main_manifest_parser.add_argument("--dataset-id", required=True)

    selected_main_run_parser = subparsers.add_parser("selected-main-run", help="Run a selected benchmark main manifest.")
    selected_main_run_parser.add_argument("--benchmark-id", required=True)
    selected_main_run_parser.add_argument("--manifest-id", required=True)

    selected_main_status_parser = subparsers.add_parser("selected-main-status", help="Print selected benchmark main execution status.")
    selected_main_status_parser.add_argument("--execution-id", required=True)

    selected_main_analysis_parser = subparsers.add_parser("selected-main-analysis", help="Analyze selected benchmark main run artifacts.")
    selected_main_analysis_parser.add_argument("--execution-id", required=True)

    selected_benchmark_go_no_go_parser = subparsers.add_parser(
        "selected-benchmark-go-no-go", help="Compute the selected benchmark v2.3 go/no-go decision."
    )
    selected_benchmark_go_no_go_parser.add_argument("--benchmark-id", required=True)

    selected_go_no_go_report_parser = subparsers.add_parser(
        "selected-go-no-go-report", help="Print the selected benchmark v2.3 go/no-go report."
    )
    selected_go_no_go_report_parser.add_argument("--benchmark-id", required=True)

    trace_dataset_report_parser = subparsers.add_parser(
        "trace-dataset-report", help="Print a selected-benchmark synthetic trace dataset report."
    )
    trace_dataset_report_parser.add_argument("--dataset-id", required=True)

    trace_list_parser = subparsers.add_parser("trace-list", help="List generated selected-benchmark traces.")
    trace_list_parser.add_argument("--benchmark-id", required=True)

    sequential_metric_plan_parser = subparsers.add_parser(
        "sequential-metric-plan", help="Create the selected benchmark sequential metric plan."
    )
    sequential_metric_plan_parser.add_argument("--benchmark-id", required=True)

    compute_sequential_metrics_parser = subparsers.add_parser(
        "compute-sequential-metrics", help="Compute selected benchmark sequential specificity metrics."
    )
    compute_sequential_metrics_parser.add_argument("--execution-id", required=True)

    low_fpr_audit_check_parser = subparsers.add_parser("low-fpr-audit-check", help="Render a selected benchmark low-FPR audit check.")
    low_fpr_audit_check_parser.add_argument("--execution-id", required=True)

    selected_monitor_baselines_parser = subparsers.add_parser(
        "selected-monitor-baselines", help="Register selected benchmark monitor baselines."
    )
    selected_monitor_baselines_parser.add_argument("--benchmark-id", required=True)

    run_monitor_baseline_parser = subparsers.add_parser("run-monitor-baseline", help="Run one selected benchmark monitor baseline.")
    run_monitor_baseline_parser.add_argument("--benchmark-id", required=True)
    run_monitor_baseline_parser.add_argument("--monitor", required=True)

    monitor_baseline_report_parser = subparsers.add_parser(
        "monitor-baseline-report", help="Print selected benchmark monitor baseline readiness report."
    )
    monitor_baseline_report_parser.add_argument("--benchmark-id", required=True)

    calibrate_monitor_parser = subparsers.add_parser("calibrate-monitor", help="Calibrate a selected benchmark monitor baseline.")
    calibrate_monitor_parser.add_argument("--benchmark-id", required=True)
    calibrate_monitor_parser.add_argument("--monitor", required=True)
    calibrate_monitor_parser.add_argument("--target-alpha", type=float, required=True)

    run_pilot_baselines_parser = subparsers.add_parser("run-pilot-baselines", help="Run required selected benchmark pilot baselines.")
    run_pilot_baselines_parser.add_argument("--benchmark-id", required=True)
    run_pilot_baselines_parser.add_argument("--dataset-id", required=True)

    pilot_baseline_report_parser = subparsers.add_parser(
        "pilot-baseline-report", help="Print selected benchmark pilot baseline readiness report."
    )
    pilot_baseline_report_parser.add_argument("--benchmark-id", required=True)

    selected_baseline_strength_parser = subparsers.add_parser(
        "selected-baseline-strength", help="Assess selected benchmark main-scale baseline strength."
    )
    selected_baseline_strength_parser.add_argument("--benchmark-id", required=True)

    implement_required_baseline_task_parser = subparsers.add_parser(
        "implement-required-baseline-task", help="Restore/register one required selected benchmark main-scale baseline."
    )
    implement_required_baseline_task_parser.add_argument("--benchmark-id", required=True)
    implement_required_baseline_task_parser.add_argument("--baseline", required=True)

    selected_baseline_strength_report_parser = subparsers.add_parser(
        "selected-baseline-strength-report", help="Print selected benchmark baseline strength report."
    )
    selected_baseline_strength_report_parser.add_argument("--benchmark-id", required=True)

    selected_benchmark_workspace_parser = subparsers.add_parser(
        "selected-benchmark-workspace", help="Create a runnable selected benchmark experiment workspace."
    )
    selected_benchmark_workspace_parser.add_argument("--benchmark-id", required=True)

    selected_benchmark_manifest_parser = subparsers.add_parser(
        "selected-benchmark-manifest", help="Create or print a selected benchmark run manifest."
    )
    selected_benchmark_manifest_parser.add_argument("--workspace-id", required=True)
    selected_benchmark_manifest_parser.add_argument("--run-type", default="smoke", choices=["smoke", "pilot"])

    selected_benchmark_run_parser = subparsers.add_parser("selected-benchmark-run", help="Run the selected benchmark smoke or pilot path.")
    selected_benchmark_run_parser.add_argument("--workspace-id", required=True)
    selected_benchmark_run_parser.add_argument("--run-type", default="smoke", choices=["smoke", "pilot"])

    selected_prior_work_parser = subparsers.add_parser("selected-benchmark-prior-work", help="Attach selected benchmark prior-work recall.")
    selected_prior_work_parser.add_argument("--benchmark-id", required=True)

    selected_related_work_parser = subparsers.add_parser(
        "selected-benchmark-related-work", help="Attach selected benchmark related-work matrix."
    )
    selected_related_work_parser.add_argument("--benchmark-id", required=True)

    selected_related_work_complete_parser = subparsers.add_parser(
        "selected-related-work-complete", help="Run selected benchmark related-work completion campaign."
    )
    selected_related_work_complete_parser.add_argument("--benchmark-id", required=True)

    selected_related_work_next_searches_parser = subparsers.add_parser(
        "selected-related-work-next-searches", help="Print next searches for missing selected benchmark related-work categories."
    )
    selected_related_work_next_searches_parser.add_argument("--benchmark-id", required=True)

    selected_related_work_status_parser = subparsers.add_parser(
        "selected-related-work-status", help="Print selected benchmark related-work completion status."
    )
    selected_related_work_status_parser.add_argument("--benchmark-id", required=True)

    selected_related_work_search_plan_parser = subparsers.add_parser(
        "selected-related-work-search-plan", help="Plan executable required related-work search rounds."
    )
    selected_related_work_search_plan_parser.add_argument("--benchmark-id", required=True)

    selected_related_work_search_run_parser = subparsers.add_parser(
        "selected-related-work-search-run", help="Run executable required related-work searches."
    )
    selected_related_work_search_run_parser.add_argument("--benchmark-id", required=True)

    selected_related_work_search_status_parser = subparsers.add_parser(
        "selected-related-work-search-status", help="Print selected benchmark related-work search campaign status."
    )
    selected_related_work_search_status_parser.add_argument("--benchmark-id", required=True)

    selected_related_work_search_report_parser = subparsers.add_parser(
        "selected-related-work-search-report", help="Render selected benchmark related-work search campaign report."
    )
    selected_related_work_search_report_parser.add_argument("--benchmark-id", required=True)

    attach_related_paper_parser = subparsers.add_parser(
        "attach-related-paper", help="Attach a known real paper to a selected benchmark related-work category."
    )
    attach_related_paper_parser.add_argument("--benchmark-id", required=True)
    attach_related_paper_parser.add_argument("--category", required=True)
    attach_related_paper_parser.add_argument("--paper-id", required=True)
    attach_related_paper_parser.add_argument("--relationship", default="background")
    attach_related_paper_parser.add_argument("--curator", default="")
    attach_related_paper_parser.add_argument("--notes", default="")

    reject_related_paper_parser = subparsers.add_parser(
        "reject-related-paper", help="Reject a known selected benchmark related-work paper with a reason."
    )
    reject_related_paper_parser.add_argument("--benchmark-id", required=True)
    reject_related_paper_parser.add_argument("--paper-id", required=True)
    reject_related_paper_parser.add_argument("--reason", required=True)
    reject_related_paper_parser.add_argument("--curator", default="")

    related_work_curation_report_parser = subparsers.add_parser(
        "related-work-curation-report", help="Render selected benchmark related-work curation report."
    )
    related_work_curation_report_parser.add_argument("--benchmark-id", required=True)

    related_work_auto_curate_parser = subparsers.add_parser(
        "related-work-auto-curate", help="Auto-curate accepted papers from selected benchmark related-work search artifacts."
    )
    related_work_auto_curate_parser.add_argument("--benchmark-id", required=True)
    related_work_auto_curate_parser.add_argument("--curator", default="auto-curation")

    read_selected_related_work_parser = subparsers.add_parser(
        "read-selected-related-work", help="Read curated selected benchmark related-work papers for evidence-backed positioning."
    )
    read_selected_related_work_parser.add_argument("--benchmark-id", required=True)
    read_selected_related_work_parser.add_argument("--paper-id", default="")

    selected_related_work_reading_report_parser = subparsers.add_parser(
        "selected-related-work-reading-report", help="Render selected benchmark related-work reading report."
    )
    selected_related_work_reading_report_parser.add_argument("--benchmark-id", required=True)

    selected_prior_work_refresh_parser = subparsers.add_parser(
        "selected-prior-work-refresh", help="Refresh closest-prior-work dossier from curated selected benchmark related work."
    )
    selected_prior_work_refresh_parser.add_argument("--benchmark-id", required=True)

    selected_prior_work_dossier_parser = subparsers.add_parser(
        "selected-prior-work-dossier", help="Render selected benchmark closest-prior-work dossier."
    )
    selected_prior_work_dossier_parser.add_argument("--benchmark-id", required=True)

    selected_positioning_parser = subparsers.add_parser(
        "selected-positioning", help="Build publication-safe selected benchmark contribution positioning."
    )
    selected_positioning_parser.add_argument("--benchmark-id", required=True)

    selected_positioning_report_parser = subparsers.add_parser(
        "selected-positioning-report", help="Render selected benchmark contribution positioning report."
    )
    selected_positioning_report_parser.add_argument("--benchmark-id", required=True)

    selected_related_work_matrix_v2_parser = subparsers.add_parser(
        "selected-related-work-matrix-v2", help="Build and render selected benchmark related-work matrix v2."
    )
    selected_related_work_matrix_v2_parser.add_argument("--benchmark-id", required=True)

    selected_related_work_matrix_load_parser = subparsers.add_parser(
        "selected-related-work-matrix-load", help="Load and validate the selected benchmark manuscript related-work matrix."
    )
    selected_related_work_matrix_load_parser.add_argument("--benchmark-id", required=True)

    selected_related_work_matrix_repair_parser = subparsers.add_parser(
        "selected-related-work-matrix-repair", help="Repair the selected benchmark manuscript related-work matrix load path."
    )
    selected_related_work_matrix_repair_parser.add_argument("--benchmark-id", required=True)

    selected_related_work_matrix_status_parser = subparsers.add_parser(
        "selected-related-work-matrix-status", help="Print selected benchmark manuscript related-work matrix load status."
    )
    selected_related_work_matrix_status_parser.add_argument("--benchmark-id", required=True)

    selected_artifact_package_load_parser = subparsers.add_parser(
        "selected-artifact-package-load", help="Load and validate the selected benchmark manuscript artifact package."
    )
    selected_artifact_package_load_parser.add_argument("--benchmark-id", required=True)

    selected_artifact_package_repair_parser = subparsers.add_parser(
        "selected-artifact-package-repair", help="Repair the selected benchmark manuscript artifact package load path."
    )
    selected_artifact_package_repair_parser.add_argument("--benchmark-id", required=True)

    selected_artifact_package_status_parser = subparsers.add_parser(
        "selected-artifact-package-status", help="Print selected benchmark manuscript artifact package load status."
    )
    selected_artifact_package_status_parser.add_argument("--benchmark-id", required=True)

    selected_must_cite_parser = subparsers.add_parser("selected-must-cite", help="Render selected benchmark must-cite paper list.")
    selected_must_cite_parser.add_argument("--benchmark-id", required=True)

    selected_novelty_report_parser = subparsers.add_parser(
        "selected-benchmark-novelty-report", help="Render selected benchmark conservative novelty positioning."
    )
    selected_novelty_report_parser.add_argument("--benchmark-id", required=True)

    selected_pilot_manifest_parser = subparsers.add_parser(
        "selected-pilot-manifest", help="Create a selected benchmark pilot run manifest."
    )
    selected_pilot_manifest_parser.add_argument("--benchmark-id", required=True)
    selected_pilot_manifest_parser.add_argument("--dataset-id", required=True)

    selected_pilot_run_parser = subparsers.add_parser("selected-pilot-run", help="Execute a selected benchmark pilot manifest.")
    selected_pilot_run_parser.add_argument("--benchmark-id", required=True)
    selected_pilot_run_parser.add_argument("--manifest-id", required=True)

    selected_pilot_status_parser = subparsers.add_parser("selected-pilot-status", help="Print selected benchmark pilot execution status.")
    selected_pilot_status_parser.add_argument("--execution-id", required=True)

    selected_pilot_analysis_parser = subparsers.add_parser("selected-pilot-analysis", help="Analyze a selected benchmark pilot execution.")
    selected_pilot_analysis_parser.add_argument("--execution-id", required=True)

    selected_pilot_report_parser = subparsers.add_parser(
        "selected-pilot-report", help="Print the latest selected benchmark pilot result report."
    )
    selected_pilot_report_parser.add_argument("--benchmark-id", required=True)

    selected_pilot_power_plan_parser = subparsers.add_parser(
        "selected-pilot-power-plan", help="Create and render the selected benchmark pilot power plan."
    )
    selected_pilot_power_plan_parser.add_argument("--benchmark-id", required=True)

    selected_pilot_power_check_parser = subparsers.add_parser(
        "selected-pilot-power-check", help="Check selected benchmark pilot data against alpha targets."
    )
    selected_pilot_power_scope = selected_pilot_power_check_parser.add_mutually_exclusive_group(required=True)
    selected_pilot_power_scope.add_argument("--benchmark-id")
    selected_pilot_power_scope.add_argument("--dataset-id")

    selected_main_power_plan_parser = subparsers.add_parser(
        "selected-main-power-plan", help="Create and render the selected benchmark main-scale power plan."
    )
    selected_main_power_plan_parser.add_argument("--benchmark-id", required=True)

    selected_main_alpha_decision_parser = subparsers.add_parser(
        "selected-main-alpha-decision", help="Record a selected benchmark main-scale alpha decision."
    )
    selected_main_alpha_decision_parser.add_argument("--benchmark-id", required=True)
    selected_main_alpha_decision_parser.add_argument("--alpha", type=float, required=True)

    selected_main_power_report_parser = subparsers.add_parser(
        "selected-main-power-report", help="Print the selected benchmark main-scale power report."
    )
    selected_main_power_report_parser.add_argument("--benchmark-id", required=True)

    selected_benchmark_codex_task_parser = subparsers.add_parser(
        "selected-benchmark-codex-task", help="Create a Codex/GPT-5.4 implementation task pack for the selected benchmark."
    )
    selected_benchmark_codex_task_parser.add_argument("--benchmark-id", required=True)
    selected_benchmark_codex_task_parser.add_argument(
        "--type",
        required=True,
        choices=[
            "implement_trace_generator",
            "implement_monitor_baseline",
            "implement_sequential_metrics",
            "implement_smoke_runner",
            "debug_selected_benchmark",
            "improve_benchmark_report",
        ],
    )

    selected_benchmark_codex_handoff_parser = subparsers.add_parser(
        "selected-benchmark-codex-handoff", help="Print a Codex/GPT-5.4 handoff for a selected-benchmark task pack."
    )
    selected_benchmark_codex_handoff_parser.add_argument("--task-id", required=True)

    selected_benchmark_codex_import_parser = subparsers.add_parser(
        "selected-benchmark-codex-import", help="Validate and import selected-benchmark Codex output into its task workspace."
    )
    selected_benchmark_codex_import_parser.add_argument("--task-id", required=True)

    selected_benchmark_review_parser = subparsers.add_parser("selected-benchmark-review", help="Run the selected benchmark reviewer panel.")
    selected_benchmark_review_parser.add_argument("--benchmark-id", required=True)

    selected_benchmark_fix_list_parser = subparsers.add_parser(
        "selected-benchmark-fix-list", help="Print required fixes from the selected benchmark reviewer panel."
    )
    selected_benchmark_fix_list_parser.add_argument("--benchmark-id", required=True)

    selected_publication_review_parser = subparsers.add_parser(
        "selected-publication-review", help="Run the selected benchmark publication-readiness reviewer panel."
    )
    selected_publication_review_parser.add_argument("--benchmark-id", required=True)
    selected_publication_review_parser.add_argument("--after-related-work", action="store_true")

    selected_publication_fix_list_parser = subparsers.add_parser(
        "selected-publication-fix-list", help="Print selected benchmark publication-readiness fixes."
    )
    selected_publication_fix_list_parser.add_argument("--benchmark-id", required=True)
    selected_publication_fix_list_parser.add_argument("--after-related-work", action="store_true")

    selected_pilot_review_parser = subparsers.add_parser("selected-pilot-review", help="Run the selected benchmark pilot reviewer panel.")
    selected_pilot_review_parser.add_argument("--benchmark-id", required=True)

    selected_pilot_fix_list_parser = subparsers.add_parser(
        "selected-pilot-fix-list", help="Print required fixes from the selected benchmark pilot reviewer panel."
    )
    selected_pilot_fix_list_parser.add_argument("--benchmark-id", required=True)

    selected_pilot_manuscript_parser = subparsers.add_parser(
        "selected-pilot-manuscript", help="Generate the selected benchmark pilot-maturity manuscript."
    )
    selected_pilot_manuscript_parser.add_argument("--benchmark-id", required=True)

    selected_pilot_paper_package_parser = subparsers.add_parser(
        "selected-pilot-paper-package", help="Export the selected benchmark pilot paper package."
    )
    selected_pilot_paper_package_parser.add_argument("--benchmark-id", required=True)

    selected_main_manuscript_parser = subparsers.add_parser(
        "selected-main-manuscript", help="Generate the selected benchmark main/pilot-ready manuscript package."
    )
    selected_main_manuscript_parser.add_argument("--benchmark-id", required=True)

    selected_main_paper_package_parser = subparsers.add_parser(
        "selected-main-paper-package", help="Export the selected benchmark main/pilot-ready paper package."
    )
    selected_main_paper_package_parser.add_argument("--benchmark-id", required=True)

    selected_manuscript_related_work_revise_parser = subparsers.add_parser(
        "selected-manuscript-related-work-revise", help="Revise selected benchmark manuscript related work from v2.4 curation."
    )
    selected_manuscript_related_work_revise_parser.add_argument("--benchmark-id", required=True)

    selected_manuscript_positioning_update_parser = subparsers.add_parser(
        "selected-manuscript-positioning-update", help="Update selected benchmark manuscript positioning from v2.4 novelty evidence."
    )
    selected_manuscript_positioning_update_parser.add_argument("--benchmark-id", required=True)

    selected_paper_package_v24_parser = subparsers.add_parser(
        "selected-paper-package-v24", help="Export the v2.4 selected benchmark paper package after related-work completion."
    )
    selected_paper_package_v24_parser.add_argument("--benchmark-id", required=True)

    selected_benchmark_manuscript_parser = subparsers.add_parser(
        "selected-benchmark-manuscript", help="Generate a manuscript-shaped draft for the selected benchmark."
    )
    selected_benchmark_manuscript_parser.add_argument("--benchmark-id", required=True)

    selected_benchmark_paper_package_parser = subparsers.add_parser(
        "selected-benchmark-paper-package", help="Export the selected benchmark manuscript paper package."
    )
    selected_benchmark_paper_package_parser.add_argument("--benchmark-id", required=True)

    idea_discovery_report_parser = subparsers.add_parser(
        "idea-discovery-report", help="Print and write the consolidated v2 idea discovery report."
    )
    idea_discovery_report_parser.add_argument("--project-id", required=True)

    research_agenda_parser = subparsers.add_parser("research-agenda", help="Create a staged research agenda fallback.")
    research_agenda_parser.add_argument("--project-id", required=True)

    agenda_report_parser = subparsers.add_parser("agenda-report", help="Print a research agenda report.")
    agenda_report_parser.add_argument("--agenda-id", required=True)

    agenda_to_campaigns_parser = subparsers.add_parser("agenda-to-campaigns", help="Create planned campaigns from agenda steps.")
    agenda_to_campaigns_parser.add_argument("--agenda-id", required=True)

    compute_status_parser = subparsers.add_parser("compute-status", help="Inspect local, GPU, Docker, and Slurm compute availability.")
    compute_status_parser.add_argument("--json", action="store_true")

    compute_check_parser = subparsers.add_parser("compute-check", help="Check one compute environment.")
    compute_check_parser.add_argument("--environment", required=True, choices=["local", "docker", "gpu", "gpu_local", "slurm"])

    experiment_workspace_parser = subparsers.add_parser(
        "experiment-workspace-create", help="Create a durable experiment execution workspace."
    )
    experiment_workspace_parser.add_argument("--project-id", required=True)
    experiment_workspace_parser.add_argument("--direction-id", required=True)
    experiment_workspace_parser.add_argument("--campaign-id", default="")
    experiment_workspace_parser.add_argument("--experiment-protocol-id", default="")

    experiment_workspace_status_parser = subparsers.add_parser("experiment-workspace-status", help="Print experiment workspace status.")
    experiment_workspace_status_parser.add_argument("--workspace-id", required=True)

    experiment_manifest_parser = subparsers.add_parser(
        "experiment-manifest-create", help="Create an experiment run manifest without executing it."
    )
    experiment_manifest_parser.add_argument("--workspace-id", required=True)
    experiment_manifest_parser.add_argument("--run-type", default="smoke")
    experiment_manifest_parser.add_argument("--run-name", default="")
    experiment_manifest_parser.add_argument("--dataset-id", action="append", dest="dataset_ids", default=[])
    experiment_manifest_parser.add_argument("--baseline-id", action="append", dest="baseline_ids", default=[])
    experiment_manifest_parser.add_argument("--metric-id", action="append", dest="metric_ids", default=[])
    experiment_manifest_parser.add_argument("--command", dest="run_command", default="")
    experiment_manifest_parser.add_argument("--expected-output", action="append", dest="expected_outputs", default=[])
    experiment_manifest_parser.add_argument("--random-seed", type=int, default=0)
    experiment_manifest_parser.add_argument(
        "--resource-environment", default="local", choices=["local", "docker", "gpu", "gpu_local", "slurm"]
    )
    experiment_manifest_parser.add_argument("--resource-cpus", type=int, default=1)
    experiment_manifest_parser.add_argument("--resource-memory-gb", type=float, default=0.0)
    experiment_manifest_parser.add_argument("--resource-gpus", type=int, default=0)
    experiment_manifest_parser.add_argument("--resource-wall-time-minutes", type=int, default=0)
    experiment_manifest_parser.add_argument("--resource-disk-gb", type=float, default=0.0)

    experiment_runs_parser = subparsers.add_parser("experiment-runs", help="List execution records for an experiment workspace.")
    experiment_runs_parser.add_argument("--workspace-id", required=True)

    experiment_run_parser = subparsers.add_parser("experiment-run", help="Execute an experiment run manifest.")
    experiment_run_parser.add_argument("--workspace-id", required=True)
    experiment_run_scope = experiment_run_parser.add_mutually_exclusive_group(required=True)
    experiment_run_scope.add_argument("--manifest-id")
    experiment_run_scope.add_argument("--run-type")
    experiment_run_parser.add_argument("--timeout-seconds", type=int, default=300)
    experiment_run_parser.add_argument("--dry-run", action="store_true")

    experiment_run_status_parser = subparsers.add_parser("experiment-run-status", help="Print an experiment execution record.")
    experiment_run_status_parser.add_argument("--execution-id", required=True)

    experiment_rerun_parser = subparsers.add_parser("experiment-rerun", help="Rerun the manifest from a previous execution.")
    experiment_rerun_parser.add_argument("--execution-id", required=True)
    experiment_rerun_parser.add_argument("--timeout-seconds", type=int, default=300)
    experiment_rerun_parser.add_argument("--dry-run", action="store_true")

    job_submit_parser = subparsers.add_parser("job-submit", help="Queue an experiment manifest for job-runner execution.")
    job_submit_parser.add_argument("--workspace-id", required=True)
    job_submit_parser.add_argument("--manifest-id", required=True)

    job_status_parser = subparsers.add_parser("job-status", help="Print a queued experiment job.")
    job_status_parser.add_argument("--job-id", required=True)

    job_list_parser = subparsers.add_parser("job-list", help="List jobs for an experiment workspace.")
    job_list_parser.add_argument("--workspace-id", required=True)

    job_cancel_parser = subparsers.add_parser("job-cancel", help="Cancel a queued experiment job.")
    job_cancel_parser.add_argument("--job-id", required=True)

    job_run_next_parser = subparsers.add_parser("job-run-next", help="Run the next queued job.")
    job_run_next_parser.add_argument("--queue-id", required=True)

    sweep_create_parser = subparsers.add_parser("sweep-create", help="Create parameter-sweep manifests from a base manifest.")
    sweep_create_parser.add_argument("--workspace-id", required=True)
    sweep_create_parser.add_argument("--manifest-id", required=True)
    sweep_create_parser.add_argument("--name", default="parameter sweep")
    sweep_create_parser.add_argument("--param", action="append", dest="params", default=[], required=True)
    sweep_create_parser.add_argument("--confirm-large", action="store_true")

    ablation_create_parser = subparsers.add_parser("ablation-create", help="Create an ablation plan for an experiment workspace.")
    ablation_create_parser.add_argument("--workspace-id", required=True)
    ablation_create_parser.add_argument("--manifest-id", default="")
    ablation_create_parser.add_argument("--name", default="ablation plan")
    ablation_create_parser.add_argument("--factor", action="append", dest="factors", default=[])
    ablation_create_parser.add_argument("--control", action="append", dest="controls", default=[])
    ablation_create_parser.add_argument("--comparison", action="append", dest="comparisons", default=[])

    seed_plan_create_parser = subparsers.add_parser("seed-plan-create", help="Create seeded manifests for stochastic experiments.")
    seed_plan_create_parser.add_argument("--workspace-id", required=True)
    seed_plan_create_parser.add_argument("--manifest-id", default="")
    seed_plan_create_parser.add_argument("--seeds", required=True)
    seed_plan_create_parser.add_argument("--rationale", default="")

    sweep_submit_parser = subparsers.add_parser("sweep-submit", help="Submit generated sweep manifests to the job queue.")
    sweep_submit_parser.add_argument("--sweep-id", required=True)

    sweep_status_parser = subparsers.add_parser("sweep-status", help="Print sweep status from queued jobs.")
    sweep_status_parser.add_argument("--sweep-id", required=True)

    parse_results_parser = subparsers.add_parser("parse-results", help="Parse experiment result artifacts into empirical claims.")
    parse_results_parser.add_argument("--execution-id", required=True)

    result_summary_parser = subparsers.add_parser("result-summary", help="Print parsed experiment result summary.")
    result_summary_parser.add_argument("--execution-id", required=True)

    empirical_claims_parser = subparsers.add_parser("empirical-claims", help="Print workspace empirical claim ledger.")
    empirical_claims_parser.add_argument("--workspace-id", required=True)

    results_db_build_parser = subparsers.add_parser("results-db-build", help="Build a workspace result database from executions.")
    results_db_build_parser.add_argument("--workspace-id", required=True)

    results_table_parser = subparsers.add_parser("results-table", help="Print the workspace result table.")
    results_table_parser.add_argument("--workspace-id", required=True)

    results_aggregate_parser = subparsers.add_parser("results-aggregate", help="Aggregate benchmark results across seeds and splits.")
    results_aggregate_parser.add_argument("--workspace-id", required=True)
    results_aggregate_parser.add_argument("--include-smoke", action="store_true")

    results_export_csv_parser = subparsers.add_parser("results-export-csv", help="Export the workspace result table as CSV.")
    results_export_csv_parser.add_argument("--workspace-id", required=True)

    error_analysis_parser = subparsers.add_parser("error-analysis", help="Build an error analysis report from prediction artifacts.")
    error_analysis_parser.add_argument("--execution-id", required=True)

    slice_analysis_parser = subparsers.add_parser("slice-analysis", help="Build a filtered error slice from prediction artifacts.")
    slice_analysis_parser.add_argument("--execution-id", required=True)
    slice_analysis_parser.add_argument("--slice", required=True)

    error_report_parser = subparsers.add_parser("error-report", help="Print workspace error analysis reports.")
    error_report_parser.add_argument("--workspace-id", required=True)

    analyze_results_parser = subparsers.add_parser("analyze-results", help="Analyze parsed experiment metrics with uncertainty.")
    analyze_results_scope = analyze_results_parser.add_mutually_exclusive_group(required=True)
    analyze_results_scope.add_argument("--execution-id")
    analyze_results_scope.add_argument("--workspace-id")

    low_fpr_power_parser = subparsers.add_parser("low-fpr-power-check", help="Check low-FPR experiment sample-size caution.")
    low_fpr_power_parser.add_argument("--workspace-id", required=True)

    low_fpr_plan_parser = subparsers.add_parser("low-fpr-plan", help="Plan negative sample sizes for low-FPR claims.")
    low_fpr_plan_parser.add_argument("--target-fpr", type=float, required=True)
    low_fpr_plan_parser.add_argument("--ci-width", type=float, required=True)
    low_fpr_plan_parser.add_argument("--confidence", type=float, default=0.95)

    low_fpr_check_parser = subparsers.add_parser("low-fpr-check", help="Check low-FPR result artifacts for underpowered claims.")
    low_fpr_check_scope = low_fpr_check_parser.add_mutually_exclusive_group(required=True)
    low_fpr_check_scope.add_argument("--workspace-id")
    low_fpr_check_scope.add_argument("--execution-id")
    low_fpr_check_parser.add_argument("--target-fpr", type=float, default=0.001)
    low_fpr_check_parser.add_argument("--ci-width", type=float, default=0.0005)
    low_fpr_check_parser.add_argument("--confidence", type=float, default=0.95)

    reproducibility_check_parser = subparsers.add_parser(
        "reproducibility-check", help="Audit an experiment workspace or execution for reproducibility artifacts."
    )
    reproducibility_check_scope = reproducibility_check_parser.add_mutually_exclusive_group(required=True)
    reproducibility_check_scope.add_argument("--workspace-id")
    reproducibility_check_scope.add_argument("--execution-id")

    empirical_review_parser = subparsers.add_parser("empirical-review", help="Run an empirical reviewer panel over experiment results.")
    empirical_review_scope = empirical_review_parser.add_mutually_exclusive_group(required=True)
    empirical_review_scope.add_argument("--workspace-id")
    empirical_review_scope.add_argument("--execution-id")

    export_replication_parser = subparsers.add_parser(
        "export-replication-package", help="Export a safe-by-default independent replication package."
    )
    export_replication_parser.add_argument("--workspace-id", required=True)

    verify_replication_parser = subparsers.add_parser(
        "verify-replication-package", help="Verify a replication package manifest and hashes."
    )
    verify_replication_parser.add_argument("--package-path", required=True)

    replication_status_parser = subparsers.add_parser("replication-status", help="Show latest replication package status for a workspace.")
    replication_status_parser.add_argument("--workspace-id", required=True)

    reproduce_parser = subparsers.add_parser("reproduce", help="Attempt reproduction from a replication package.")
    reproduce_parser.add_argument("--package-path", required=True)
    reproduce_parser.add_argument("--dry-run", action="store_true")

    reproduce_status_parser = subparsers.add_parser("reproduce-status", help="Show a recorded reproduction attempt.")
    reproduce_status_parser.add_argument("--reproduction-id", required=True)

    reproducibility_matrix_parser = subparsers.add_parser(
        "reproducibility-matrix", help="Summarize reproduction attempts across compute environments."
    )
    reproducibility_matrix_scope = reproducibility_matrix_parser.add_mutually_exclusive_group(required=True)
    reproducibility_matrix_scope.add_argument("--workspace-id")
    reproducibility_matrix_scope.add_argument("--package-id")

    dataset_register_parser = subparsers.add_parser("dataset-register", help="Register a dataset for an experiment workspace.")
    dataset_register_parser.add_argument("--workspace-id", required=True)
    dataset_register_parser.add_argument("--name", required=True)
    dataset_register_parser.add_argument("--path", required=True)
    dataset_register_parser.add_argument("--dataset-type", default="unknown")
    dataset_register_parser.add_argument("--description", default="")
    dataset_register_parser.add_argument("--source", default="")
    dataset_register_parser.add_argument("--source-url", default="")
    dataset_register_parser.add_argument("--version", default="")
    dataset_register_parser.add_argument("--license", default="")
    dataset_register_parser.add_argument("--intended-use", default="")

    dataset_card_parser = subparsers.add_parser("dataset-card", help="Render a dataset card.")
    dataset_card_parser.add_argument("--dataset-id", required=True)

    dataset_validate_parser = subparsers.add_parser("dataset-validate", help="Validate a registered dataset.")
    dataset_validate_parser.add_argument("--dataset-id", required=True)

    dataset_list_parser = subparsers.add_parser("dataset-list", help="List datasets registered for an experiment workspace.")
    dataset_list_parser.add_argument("--workspace-id", required=True)

    dataset_download_plan_parser = subparsers.add_parser("dataset-download-plan", help="Plan an external dataset download.")
    dataset_download_plan_parser.add_argument("--dataset-id", required=True)

    dataset_download_parser = subparsers.add_parser("dataset-download", help="Download a dataset into the GapForge dataset cache.")
    dataset_download_parser.add_argument("--dataset-id", required=True)
    dataset_download_parser.add_argument("--accept-license", action="store_true")

    subparsers.add_parser("dataset-cache-info", help="Show dataset cache status.")
    subparsers.add_parser("dataset-cache-clean", help="Clean downloaded dataset cache artifacts.")

    dataset_consent_parser = subparsers.add_parser("dataset-consent", help="Record explicit dataset download consent.")
    dataset_consent_parser.add_argument("--dataset-id", required=True)
    dataset_consent_parser.add_argument("--accept", action="store_true", required=True)
    dataset_consent_parser.add_argument("--user", default="")
    dataset_consent_parser.add_argument("--text", default="")

    baseline_register_parser = subparsers.add_parser("baseline-register", help="Register a baseline for an experiment workspace.")
    baseline_register_parser.add_argument("--workspace-id", required=True)
    baseline_register_parser.add_argument("--name", required=True)
    baseline_register_parser.add_argument("--description", default="")
    baseline_register_parser.add_argument("--baseline-type", default="unknown")
    baseline_register_parser.add_argument("--source-paper-id", action="append", dest="source_paper_ids", default=[])
    baseline_register_parser.add_argument("--code-url", default="")
    baseline_register_parser.add_argument("--implementation-path", default="")
    baseline_register_parser.add_argument("--required-for-submission", action="store_true")
    baseline_register_parser.add_argument("--risk-if-missing", default="")

    baseline_from_related_work_parser = subparsers.add_parser(
        "baseline-from-related-work", help="Create baseline records from a direction related-work matrix."
    )
    baseline_from_related_work_parser.add_argument("--project-id", required=True)
    baseline_from_related_work_parser.add_argument("--direction-id", required=True)

    baseline_list_parser = subparsers.add_parser("baseline-list", help="List baselines registered for an experiment workspace.")
    baseline_list_parser.add_argument("--workspace-id", required=True)

    baseline_card_parser = subparsers.add_parser("baseline-card", help="Render a baseline card.")
    baseline_card_parser.add_argument("--baseline-id", required=True)

    metric_register_parser = subparsers.add_parser("metric-register", help="Register a metric for an experiment workspace.")
    metric_register_parser.add_argument("--workspace-id", required=True)
    metric_register_parser.add_argument("--name", required=True)
    metric_register_parser.add_argument("--description", default="")
    metric_register_parser.add_argument("--metric-type", default="custom")
    metric_register_parser.add_argument("--formula", default="")
    metric_register_parser.add_argument("--lower-is-better", action="store_true")
    metric_register_parser.add_argument("--required-input", action="append", dest="required_inputs", default=[])
    metric_register_parser.add_argument("--edge-case", action="append", dest="edge_cases", default=[])

    metric_list_parser = subparsers.add_parser("metric-list", help="List metrics registered for an experiment workspace.")
    metric_list_parser.add_argument("--workspace-id", required=True)

    subparsers.add_parser("benchmark-canary-list", help="List v0.7 benchmark canary profiles.")

    benchmark_canary_run_parser = subparsers.add_parser("benchmark-canary-run", help="Run a v0.7 benchmark canary profile.")
    benchmark_canary_run_parser.add_argument("--profile", required=True)
    benchmark_canary_run_parser.add_argument("--real", action="store_true")
    benchmark_canary_run_parser.add_argument("--accept-download", action="store_true")

    benchmark_register_parser = subparsers.add_parser("benchmark-register", help="Register a benchmark for an experiment workspace.")
    benchmark_register_parser.add_argument("--workspace-id", required=True)
    benchmark_register_parser.add_argument("--name", required=True)
    benchmark_register_parser.add_argument("--description", default="")
    benchmark_register_parser.add_argument("--domain", default="")
    benchmark_register_parser.add_argument("--task-type", default="custom")
    benchmark_register_parser.add_argument("--source-url", default="")
    benchmark_register_parser.add_argument("--dataset-id", action="append", dest="dataset_ids", default=[])
    benchmark_register_parser.add_argument("--baseline-id", action="append", dest="baseline_ids", default=[])
    benchmark_register_parser.add_argument("--metric-id", action="append", dest="metric_ids", default=[])
    benchmark_register_parser.add_argument("--license", default="")
    benchmark_register_parser.add_argument("--expected-split", action="append", dest="expected_splits", default=[])
    benchmark_register_parser.add_argument("--evaluation-protocol", default="")
    benchmark_register_parser.add_argument("--leaderboard-url", default="")
    benchmark_register_parser.add_argument("--paper-id", action="append", dest="paper_ids", default=[])
    benchmark_register_parser.add_argument("--limitation", action="append", dest="limitations", default=[])
    benchmark_register_parser.add_argument("--safety-note", action="append", dest="safety_notes", default=[])

    benchmark_card_parser = subparsers.add_parser("benchmark-card", help="Render a benchmark card.")
    benchmark_card_parser.add_argument("--benchmark-id", required=True)

    benchmark_list_parser = subparsers.add_parser("benchmark-list", help="List benchmarks registered for an experiment workspace.")
    benchmark_list_parser.add_argument("--workspace-id", required=True)

    benchmark_suite_create_parser = subparsers.add_parser("benchmark-suite-create", help="Create a project-level benchmark suite.")
    benchmark_suite_create_parser.add_argument("--project-id", required=True)
    benchmark_suite_create_parser.add_argument("--name", required=True)
    benchmark_suite_create_parser.add_argument("--description", default="")
    benchmark_suite_create_parser.add_argument("--benchmark-id", action="append", dest="benchmark_ids", default=[])
    benchmark_suite_create_parser.add_argument("--required-task", action="append", dest="required_tasks", default=[])
    benchmark_suite_create_parser.add_argument("--optional-task", action="append", dest="optional_tasks", default=[])
    benchmark_suite_create_parser.add_argument("--source-profile", default="generic")

    benchmark_suite_status_parser = subparsers.add_parser("benchmark-suite-status", help="Render benchmark suite status.")
    benchmark_suite_status_parser.add_argument("--suite-id", required=True)

    benchmark_compare_parser = subparsers.add_parser("benchmark-compare", help="Compare internal results for one benchmark.")
    benchmark_compare_parser.add_argument("--workspace-id", required=True)
    benchmark_compare_parser.add_argument("--benchmark-id", required=True)

    leaderboard_report_parser = subparsers.add_parser("leaderboard-report", help="Render an internal benchmark leaderboard report.")
    leaderboard_report_parser.add_argument("--benchmark-id", required=True)

    benchmark_comparison_report_parser = subparsers.add_parser(
        "benchmark-comparison-report", help="Print workspace benchmark comparison reports."
    )
    benchmark_comparison_report_parser.add_argument("--workspace-id", required=True)

    vetted_benchmark_register_parser = subparsers.add_parser(
        "vetted-benchmark-register", help="Register an existing vetted benchmark as a real-grounding option."
    )
    vetted_benchmark_register_parser.add_argument("--name", required=True)
    vetted_benchmark_register_parser.add_argument("--domain", default="")
    vetted_benchmark_register_parser.add_argument("--source", default="")
    vetted_benchmark_register_parser.add_argument("--source-url", default="")
    vetted_benchmark_register_parser.add_argument("--benchmark-type", default="unknown")
    vetted_benchmark_register_parser.add_argument("--task-type", action="append", dest="task_types", default=[])
    vetted_benchmark_register_parser.add_argument("--dataset-id", action="append", dest="dataset_ids", default=[])
    vetted_benchmark_register_parser.add_argument("--metric-id", action="append", dest="metric_ids", default=[])
    vetted_benchmark_register_parser.add_argument("--baseline-id", action="append", dest="baseline_ids", default=[])
    vetted_benchmark_register_parser.add_argument("--paper-id", action="append", dest="paper_ids", default=[])
    vetted_benchmark_register_parser.add_argument("--leaderboard-url", default="")
    vetted_benchmark_register_parser.add_argument("--license", default="")
    vetted_benchmark_register_parser.add_argument("--terms-of-use", default="")
    vetted_benchmark_register_parser.add_argument("--download-required", action="store_true")
    vetted_benchmark_register_parser.add_argument("--authentication-required", action="store_true")
    vetted_benchmark_register_parser.add_argument("--size-estimate", default="")
    vetted_benchmark_register_parser.add_argument("--citation", default="")
    vetted_benchmark_register_parser.add_argument(
        "--vetted-status", choices=["canonical", "widely_used", "emerging", "uncertain"], default="uncertain"
    )
    vetted_benchmark_register_parser.add_argument("--limitation", action="append", dest="limitations", default=[])

    subparsers.add_parser("vetted-benchmark-list", help="List registered vetted benchmarks.")

    vetted_benchmark_card_parser = subparsers.add_parser("vetted-benchmark-card", help="Render a vetted benchmark card.")
    vetted_benchmark_card_parser.add_argument("--benchmark-id", required=True)

    vetted_benchmark_eligibility_parser = subparsers.add_parser(
        "vetted-benchmark-eligibility", help="Assess whether a vetted benchmark fits a selected idea."
    )
    vetted_benchmark_eligibility_parser.add_argument("--benchmark-id", required=True)
    vetted_benchmark_eligibility_parser.add_argument("--idea-id", required=True)

    vetted_benchmark_report_parser = subparsers.add_parser(
        "vetted-benchmark-report", help="Render a project-level vetted benchmark grounding report."
    )
    vetted_benchmark_report_parser.add_argument("--project-id", required=True)

    stats_plan_parser = subparsers.add_parser("stats-plan", help="Create a statistical test plan.")
    stats_plan_scope = stats_plan_parser.add_mutually_exclusive_group(required=True)
    stats_plan_scope.add_argument("--workspace-id")
    stats_plan_scope.add_argument("--experiment-id")

    generate_code_tasks_parser = subparsers.add_parser(
        "generate-code-tasks", help="Generate Codex handoff tasks for experiment implementation."
    )
    generate_code_tasks_parser.add_argument("--campaign-id", required=True)
    generate_code_tasks_parser.add_argument("--direction-id", required=True)

    scaffold_experiment_parser = subparsers.add_parser("scaffold-experiment-repo", help="Create a minimal experiment repository scaffold.")
    scaffold_experiment_parser.add_argument("--campaign-id", required=True)
    scaffold_experiment_parser.add_argument("--direction-id", required=True)

    scaffold_experiment_code_parser = subparsers.add_parser(
        "scaffold-experiment-code", help="Create runnable smoke-test code inside an experiment workspace."
    )
    scaffold_experiment_code_parser.add_argument("--workspace-id", required=True)

    experiment_code_status_parser = subparsers.add_parser("experiment-code-status", help="Print runnable scaffold status.")
    experiment_code_status_parser.add_argument("--workspace-id", required=True)

    experiment_code_validate_parser = subparsers.add_parser("experiment-code-validate", help="Validate runnable experiment scaffold code.")
    experiment_code_validate_parser.add_argument("--workspace-id", required=True)
    experiment_code_validate_parser.add_argument("--no-smoke", action="store_true", help="Check file layout without running smoke tests.")

    experiment_code_task_parser = subparsers.add_parser("experiment-code-task", help="Create a Codex task pack for workspace code.")
    experiment_code_task_parser.add_argument("--workspace-id", required=True)
    experiment_code_task_parser.add_argument(
        "--type",
        required=True,
        choices=[
            "implement_dataset_loader",
            "implement_baseline",
            "implement_metric",
            "implement_experiment_runner",
            "implement_ablation",
            "write_tests",
            "debug_smoke_run",
            "analyze_results",
        ],
    )

    experiment_code_handoff_parser = subparsers.add_parser("experiment-code-handoff", help="Write handoff for an experiment code task.")
    experiment_code_handoff_parser.add_argument("--task-id", required=True)

    experiment_code_import_parser = subparsers.add_parser("experiment-code-import", help="Import validated experiment code task outputs.")
    experiment_code_import_parser.add_argument("--task-id", required=True)

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

    review_dataset_create_parser = subparsers.add_parser(
        "review-dataset-create", help="Create an OpenReview-style review calibration dataset shell."
    )
    review_dataset_create_parser.add_argument("--name", required=True)

    review_dataset_ingest_parser = subparsers.add_parser(
        "review-dataset-ingest", help="Record a guarded public review dataset ingestion request."
    )
    review_dataset_ingest_parser.add_argument("--source", required=True)
    review_dataset_ingest_parser.add_argument("--venue", required=True)
    review_dataset_ingest_parser.add_argument("--year", type=int, required=True)

    subparsers.add_parser("review-dataset-ingest-fixture", help="Ingest the synthetic OpenReview-style review fixture.")

    review_dataset_report_parser = subparsers.add_parser("review-dataset-report", help="Render a review calibration dataset report.")
    review_dataset_report_parser.add_argument("--dataset-id", required=True)

    review_labels_generate_parser = subparsers.add_parser(
        "review-labels-generate", help="Generate heuristic taxonomy labels for a review calibration dataset."
    )
    review_labels_generate_parser.add_argument("--dataset-id", required=True)

    review_taxonomy_report_parser = subparsers.add_parser(
        "review-taxonomy-report", help="Render a review issue taxonomy report for a review calibration dataset."
    )
    review_taxonomy_report_parser.add_argument("--dataset-id", required=True)

    reviewer_train_parser = subparsers.add_parser("reviewer-train", help="Train or calibrate a reviewer rubric/model.")
    reviewer_train_parser.add_argument("--dataset-id", required=True)
    reviewer_train_parser.add_argument(
        "--mode",
        choices=["heuristic", "retrieval_calibrated", "codex_task_pack", "local_model"],
        default="heuristic",
    )

    reviewer_evaluate_parser = subparsers.add_parser("reviewer-evaluate", help="Evaluate a calibrated reviewer model/rubric.")
    reviewer_evaluate_parser.add_argument("--dataset-id", required=True)

    reviewer_calibration_report_parser = subparsers.add_parser(
        "reviewer-calibration-report", help="Render reviewer calibration metrics and limitations."
    )
    reviewer_calibration_report_parser.add_argument("--dataset-id", required=True)

    rebuttal_plan_parser = subparsers.add_parser(
        "rebuttal-plan",
        help="Print the rebuttal plan for a project direction or convert manuscript reviewer objections into action items.",
    )
    rebuttal_plan_parser.add_argument("--project-id")
    rebuttal_plan_parser.add_argument("--direction-id")
    rebuttal_plan_parser.add_argument("--manuscript-id")

    meta_review_parser = subparsers.add_parser("meta-review", help="Print the meta-review for a project direction.")
    meta_review_parser.add_argument("--project-id", required=True)
    meta_review_parser.add_argument("--direction-id", required=True)

    export_package_parser = subparsers.add_parser("export-paper-package", help="Export a manuscript starter kit for a direction.")
    export_package_parser.add_argument("--project-id", required=True)
    export_package_parser.add_argument("--direction-id", required=True)
    export_package_parser.add_argument("--allow-rejected", action="store_true")

    export_package_v2_parser = subparsers.add_parser(
        "export-paper-package-v2", help="Export a v0.6 empirical paper package for a workspace or direction."
    )
    export_package_v2_scope = export_package_v2_parser.add_mutually_exclusive_group(required=True)
    export_package_v2_scope.add_argument("--workspace-id")
    export_package_v2_scope.add_argument("--direction-id")

    manuscript_create_parser = subparsers.add_parser("manuscript-create", help="Create first-class manuscript project state.")
    manuscript_create_parser.add_argument("--project-id", required=True)
    manuscript_create_parser.add_argument("--direction-id", required=True)
    manuscript_create_parser.add_argument("--workspace-id", required=True)
    manuscript_create_parser.add_argument("--title", required=True)
    manuscript_create_parser.add_argument("--campaign-id", default="")
    manuscript_create_parser.add_argument("--short-title", default="")
    manuscript_create_parser.add_argument("--target-venue", default="")

    manuscript_status_parser = subparsers.add_parser("manuscript-status", help="Print manuscript project status.")
    manuscript_status_parser.add_argument("--manuscript-id", required=True)

    manuscript_sections_parser = subparsers.add_parser("manuscript-sections", help="List manuscript sections as JSON.")
    manuscript_sections_parser.add_argument("--manuscript-id", required=True)

    manuscript_report_parser = subparsers.add_parser("manuscript-report", help="Write and print the manuscript traceability report.")
    manuscript_report_parser.add_argument("--manuscript-id", required=True)

    bibliography_build_parser = subparsers.add_parser(
        "bibliography-build", help="Build a manuscript bibliography from known paper records."
    )
    bibliography_build_parser.add_argument("--manuscript-id", required=True)

    bibliography_export_parser = subparsers.add_parser("bibliography-export", help="Export a manuscript bibliography.")
    bibliography_export_parser.add_argument("--manuscript-id", required=True)
    bibliography_export_parser.add_argument("--format", choices=["bibtex"], default="bibtex")

    citation_check_parser = subparsers.add_parser("citation-check", help="Check manuscript citations for unresolved or fake entries.")
    citation_check_parser.add_argument("--manuscript-id", required=True)

    citation_list_parser = subparsers.add_parser("citation-list", help="List manuscript bibliography entries as JSON.")
    citation_list_parser.add_argument("--manuscript-id", required=True)

    manuscript_traceability_parser = subparsers.add_parser("manuscript-traceability", help="Audit manuscript claim traceability.")
    manuscript_traceability_parser.add_argument("--manuscript-id", required=True)

    manuscript_overclaims_parser = subparsers.add_parser("manuscript-overclaims", help="List manuscript overclaim warnings as JSON.")
    manuscript_overclaims_parser.add_argument("--manuscript-id", required=True)

    manuscript_soften_parser = subparsers.add_parser("manuscript-soften-claims", help="Suggest softer wording for unsupported claims.")
    manuscript_soften_parser.add_argument("--manuscript-id", required=True)
    manuscript_soften_parser.add_argument("--dry-run", action="store_true")

    manuscript_table_parser = subparsers.add_parser("manuscript-table", help="Generate an artifact-backed manuscript table.")
    manuscript_table_parser.add_argument("--manuscript-id", required=True)
    manuscript_table_parser.add_argument(
        "--type",
        required=True,
        choices=["result_table", "baseline_comparison", "ablation", "dataset_summary", "reproducibility", "custom"],
    )

    manuscript_figure_parser = subparsers.add_parser("manuscript-figure", help="Generate an artifact-backed manuscript figure.")
    manuscript_figure_parser.add_argument("--manuscript-id", required=True)
    manuscript_figure_parser.add_argument(
        "--type",
        required=True,
        choices=["metric_plot", "error_analysis", "comparison", "power_curve", "custom"],
    )

    manuscript_assets_parser = subparsers.add_parser("manuscript-assets", help="List manuscript figures and tables.")
    manuscript_assets_parser.add_argument("--manuscript-id", required=True)

    subparsers.add_parser("venue-list", help="List built-in manuscript venue templates.")

    subparsers.add_parser("venue-profile-list", help="List built-in conference-style venue profiles.")

    venue_profile_parser = subparsers.add_parser("venue-profile", help="Render a built-in venue profile.")
    venue_profile_parser.add_argument("--venue", required=True)

    manuscript_set_venue_parser = subparsers.add_parser("manuscript-set-venue", help="Assign a venue template to a manuscript.")
    manuscript_set_venue_parser.add_argument("--manuscript-id", required=True)
    manuscript_set_venue_parser.add_argument("--venue", required=True)

    manuscript_set_venue_profile_parser = subparsers.add_parser(
        "manuscript-set-venue-profile", help="Assign a conference-style venue profile to a manuscript."
    )
    manuscript_set_venue_profile_parser.add_argument("--manuscript-id", required=True)
    manuscript_set_venue_profile_parser.add_argument("--venue", required=True)

    style_corpus_add_tex_parser = subparsers.add_parser("style-corpus-add-tex", help="Add a local TeX source to the style corpus.")
    style_corpus_add_tex_parser.add_argument("--path", required=True)
    style_corpus_add_tex_parser.add_argument("--venue", required=True)

    style_corpus_ingest_parser = subparsers.add_parser("style-corpus-ingest", help="Ingest or dry-run a style corpus source.")
    style_corpus_ingest_parser.add_argument("--source", required=True)
    style_corpus_ingest_parser.add_argument("--dry-run", action="store_true")

    subparsers.add_parser("style-corpus-report", help="Render the style corpus report.")

    venue_style_analyze_parser = subparsers.add_parser("venue-style-analyze", help="Analyze venue style corpus patterns.")
    venue_style_analyze_parser.add_argument("--venue", required=True)

    venue_style_recommend_parser = subparsers.add_parser(
        "venue-style-recommend", help="Generate structural venue-style recommendations for a manuscript."
    )
    venue_style_recommend_parser.add_argument("--manuscript-id", required=True)

    venue_style_report_parser = subparsers.add_parser("venue-style-report", help="Render a venue style analysis report.")
    venue_style_report_parser.add_argument("--venue", required=True)

    manuscript_rewrite_for_venue_parser = subparsers.add_parser(
        "manuscript-rewrite-for-venue", help="Rewrite manuscript section structure for a venue profile without bypassing evidence gates."
    )
    manuscript_rewrite_for_venue_parser.add_argument("--manuscript-id", required=True)
    manuscript_rewrite_for_venue_parser.add_argument("--venue", required=True)

    manuscript_style_report_parser = subparsers.add_parser(
        "manuscript-style-report", help="Render the latest venue style revision report for a manuscript."
    )
    manuscript_style_report_parser.add_argument("--manuscript-id", required=True)

    submission_checklist_parser = subparsers.add_parser("submission-checklist", help="Build a venue-aware submission checklist.")
    submission_checklist_parser.add_argument("--manuscript-id", required=True)

    anonymize_manuscript_parser = subparsers.add_parser("anonymize-manuscript", help="Write an anonymized manuscript submission copy.")
    anonymize_manuscript_parser.add_argument("--manuscript-id", required=True)

    anonymization_check_parser = subparsers.add_parser("anonymization-check", help="Scan a manuscript for blind-review identity leaks.")
    anonymization_check_parser.add_argument("--manuscript-id", required=True)

    deanonymize_package_parser = subparsers.add_parser("deanonymize-package", help="Write a non-anonymous manuscript package copy.")
    deanonymize_package_parser.add_argument("--manuscript-id", required=True)

    artifact_eval_package_parser = subparsers.add_parser("artifact-eval-package", help="Export a review-ready artifact evaluation package.")
    artifact_eval_package_parser.add_argument("--manuscript-id", required=True)

    artifact_eval_check_parser = subparsers.add_parser("artifact-eval-check", help="Check an artifact evaluation package.")
    artifact_eval_check_parser.add_argument("--package-id", required=True)

    artifact_badges_parser = subparsers.add_parser("artifact-badges", help="Assess artifact badge eligibility conservatively.")
    artifact_badges_parser.add_argument("--package-id", required=True)

    artifact_eval_smoke_parser = subparsers.add_parser("artifact-eval-smoke", help="Dry-run artifact evaluation package commands.")
    artifact_eval_smoke_parser.add_argument("--package-id", required=True)

    manuscript_review_parser = subparsers.add_parser("manuscript-review", help="Run a full-manuscript reviewer panel.")
    manuscript_review_parser.add_argument("--manuscript-id", required=True)

    manuscript_meta_review_parser = subparsers.add_parser("manuscript-meta-review", help="Print manuscript area-chair meta-review.")
    manuscript_meta_review_parser.add_argument("--manuscript-id", required=True)

    manuscript_fix_list_parser = subparsers.add_parser("manuscript-fix-list", help="Print manuscript reviewer required fixes.")
    manuscript_fix_list_parser.add_argument("--manuscript-id", required=True)

    drastic_review_parser = subparsers.add_parser("drastic-review", help="Run a harsh OpenReview-calibrated reviewer panel.")
    drastic_review_target = drastic_review_parser.add_mutually_exclusive_group(required=True)
    drastic_review_target.add_argument("--manuscript-id")
    drastic_review_target.add_argument("--benchmark-id")

    drastic_review_report_parser = subparsers.add_parser("drastic-review-report", help="Print a harsh reviewer panel report.")
    drastic_review_report_parser.add_argument("--manuscript-id", required=True)

    drastic_review_rerun_parser = subparsers.add_parser(
        "drastic-review-rerun", help="Rerun drastic review and compare previous versus current blockers."
    )
    drastic_review_rerun_parser.add_argument("--manuscript-id", required=True)

    drastic_revision_plan_parser = subparsers.add_parser(
        "drastic-revision-plan", help="Convert drastic review output into concrete manuscript revision tasks."
    )
    drastic_revision_plan_parser.add_argument("--manuscript-id", required=True)

    apply_drastic_revision_parser = subparsers.add_parser(
        "apply-drastic-revision", help="Apply or preview drastic review revision requests and status downgrades."
    )
    apply_drastic_revision_parser.add_argument("--manuscript-id", required=True)
    apply_drastic_revision_parser.add_argument("--dry-run", action="store_true")

    drastic_revision_status_parser = subparsers.add_parser("drastic-revision-status", help="Print drastic revision status.")
    drastic_revision_status_parser.add_argument("--manuscript-id", required=True)

    drastic_revision_close_parser = subparsers.add_parser(
        "drastic-revision-close", help="Close a drastic revision item after rerun evidence supports closure."
    )
    drastic_revision_close_parser.add_argument("--manuscript-id", required=True)
    drastic_revision_close_parser.add_argument("--item-id", required=True)

    drastic_readiness_delta_parser = subparsers.add_parser(
        "drastic-readiness-delta", help="Print the latest drastic review readiness delta."
    )
    drastic_readiness_delta_parser.add_argument("--manuscript-id", required=True)

    revision_plan_parser = subparsers.add_parser("revision-plan", help="Create a manuscript revision plan from rebuttal items.")
    revision_plan_parser.add_argument("--manuscript-id", required=True)

    mark_rebuttal_parser = subparsers.add_parser("mark-rebuttal-item", help="Mark a manuscript rebuttal item status.")
    mark_rebuttal_parser.add_argument("--item-id", required=True)
    mark_rebuttal_parser.add_argument("--status", required=True, choices=["open", "addressed", "rejected", "deferred"])

    revision_status_parser = subparsers.add_parser("revision-status", help="Print manuscript revision status.")
    revision_status_parser.add_argument("--manuscript-id", required=True)

    submission_package_parser = subparsers.add_parser("submission-package", help="Export a gated manuscript submission package.")
    submission_package_parser.add_argument("--manuscript-id", required=True)
    submission_package_parser.add_argument("--type", required=True, choices=["review", "camera_ready", "arxiv", "internal"])

    submission_package_status_parser = subparsers.add_parser("submission-package-status", help="Print submission package status.")
    submission_package_status_parser.add_argument("--package-id", required=True)

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

    artifact_hygiene_parser = subparsers.add_parser(
        "artifact-hygiene", help="Run the v1 artifact hygiene audit for generated/private project artifacts."
    )
    artifact_hygiene_scope = artifact_hygiene_parser.add_mutually_exclusive_group(required=True)
    artifact_hygiene_scope.add_argument("--project-id")
    artifact_hygiene_scope.add_argument("--all", action="store_true")
    artifact_hygiene_parser.add_argument("--write-report", action="store_true")

    subparsers.add_parser("verify-gitignore", help="Verify .gitignore protects generated/private GapForge artifacts.")

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
    if args.command == "pilot-list":
        print(render_pilot_list(), end="")
        return 0
    if args.command == "pilot-spec":
        print(render_pilot_document(config, args.name, args.document), end="")
        return 0
    if args.command == "pilot-run":
        pilot_record = PilotRunner(config).run(args.name)
        print(json.dumps(to_plain(pilot_record), indent=2))
        return 0 if pilot_record.status != "product_failure" else 1
    if args.command == "pilot-status":
        if args.pilot_id:
            pilot_record = PilotStore(config).load_record(args.pilot_id)
            spec = get_pilot_spec(pilot_record.pilot_id)
            print(render_pilot_status_json(config, spec, pilot_id=args.pilot_id), end="")
            return 0
        spec = get_pilot_spec(args.name)
        print(render_pilot_status_json(config, spec), end="")
        return 0
    if args.command == "pilot-report":
        store = PilotStore(config)
        pilot_record = store.load_record(args.pilot_id)
        spec = get_pilot_spec(pilot_record.pilot_id)
        pilot_summary = store.load_acceptance(args.pilot_id)
        store.save_acceptance(pilot_record, pilot_summary)
        pilot_report_text = render_pilot_report(spec, pilot_record, pilot_summary)
        pilot_report_path = store.record_dir(pilot_record.id) / "pilot_report.md"
        pilot_report_path.write_text(pilot_report_text, encoding="utf-8")
        print(pilot_report_text, end="")
        return 0
    if args.command == "v2-pilot-run":
        pilot_record = V2IdeaPilotRunner(config).run(args.name)
        print(json.dumps(to_plain(pilot_record), indent=2))
        return 0 if pilot_record.status != "product_failure" else 1
    if args.command == "v2-pilot-status":
        print(render_v2_pilot_status(config, args.name), end="")
        return 0
    if args.command == "v2-pilot-report":
        print(V2IdeaPilotRunner(config).report(args.name), end="")
        return 0
    if args.command == "pilot-acceptance":
        store = PilotStore(config)
        pilot_record = store.load_record(args.pilot_id)
        pilot_summary = store.load_acceptance(args.pilot_id)
        print(render_pilot_acceptance(pilot_summary), end="")
        return 0 if pilot_record.status != "product_failure" else 1
    if args.command == "pilot-review":
        pilot_review = ExternalPilotReviewManager(config).create_review(
            args.pilot_id,
            reviewer_name=args.reviewer_name,
            reviewer_role=args.reviewer_role,
            review_scope=args.scope,
            novelty_assessment=args.novelty_assessment,
            evidence_assessment=args.evidence_assessment,
            experiment_assessment=args.experiment_assessment,
            manuscript_assessment=args.manuscript_assessment,
            artifact_assessment=args.artifact_assessment,
            major_concerns=args.major_concern,
            accept_outcome=args.accept_outcome,
            reject_outcome=args.reject_outcome,
            reason=args.reason,
            required_fixes=args.required_fix,
            notes=args.notes,
        )
        print(json.dumps(to_plain(pilot_review), indent=2))
        return 0
    if args.command == "pilot-review-report":
        print(ExternalPilotReviewManager(config).render_report(args.pilot_id), end="")
        return 0
    if args.command == "pilot-outcome":
        pilot_record = PilotStore(config).load_record(args.pilot_id)
        pilot_outcome = assess_pilot_outcome(pilot_record, get_pilot_spec(pilot_record.pilot_id))
        print(render_pilot_outcome(pilot_outcome, as_json=args.json), end="")
        return 0 if pilot_outcome.outcome_type != "product_failure" else 1
    if args.command == "idea-gate":
        gate = IdeaGate(config)
        idea_assessment = gate.assess_pilot(args.pilot_id) if args.pilot_id else gate.assess_campaign(args.campaign_id)
        print(render_idea_gate(idea_assessment, as_json=args.json), end="")
        return 0 if idea_assessment.acceptance_status != "rejected" else 1
    if args.command == "selected-idea":
        if getattr(args, "project_id", None):
            selected = IdeaTournamentRunner(config).selected_idea(args.project_id)
            if selected is None:
                print("No idea has been selected.")
            else:
                print(json.dumps(to_plain(selected), indent=2))
            return 0
        idea_assessment = IdeaGate(config).load_assessment(args.pilot_id)
        if not idea_assessment.selected_direction_id:
            print("No selected direction.")
            return 1
        print(idea_assessment.selected_direction_id)
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
    if args.command == "plan-search-strategy":
        strategy = plan_search_strategy(config, args.topic, source_profile=args.source_profile)
        json_path, md_path = save_strategy(config, strategy)
        print(render_search_strategy_markdown(strategy), end="")
        print(f"\nWrote {json_path}")
        print(f"Wrote {md_path}")
        return 0
    if args.command == "execute-search-strategy":
        rounds = execute_search_strategy(config, args.run_id, args.strategy_id)
        print(render_search_rounds_markdown(rounds), end="")
        return 0
    if args.command == "search-rounds":
        state = ResearchStateManager(config).load_run(args.run_id)
        print(render_search_rounds_markdown(state.search_rounds), end="")
        return 0
    if args.command == "prior-work-recall":
        if args.run_id:
            if not args.gap_id:
                parser.error("prior-work-recall with --run-id requires --gap-id")
            recall_assessment = assess_run_prior_work_recall(config, args.run_id, gap_id=args.gap_id)
            print(render_prior_work_recall_report([recall_assessment]), end="")
            return 0
        assessments = assess_campaign_prior_work_recall(config, args.campaign_id)
        print(render_prior_work_recall_report(assessments), end="")
        return 0
    if args.command == "prior-work-recall-report":
        print(load_campaign_prior_work_recall_report(config, args.campaign_id), end="")
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
        report = run_evals(
            fixture=args.fixture,
            output_dir=config.root,
            write_report=True,
            v2=args.v2,
            v3=args.v3,
            v4=args.v4,
            v5=args.v5,
            v6=args.v6,
            v7=args.v7,
            v8=args.v8,
            v9=args.v9,
            v21=args.v21,
            v22=args.v22,
            v23=args.v23,
            v24=args.v24,
            v25=args.v25,
            v26=args.v26,
            v2_ideas=args.v2_ideas,
        )
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
        if args.workspace_id:
            result = dashboard.build_workspace(args.workspace_id)
        elif args.manuscript_id:
            result = dashboard.build_manuscript(args.manuscript_id)
        elif args.project_id:
            result = dashboard.build_project(
                args.project_id,
                include_manuscripts=args.include_manuscripts,
                include_ideas=args.include_ideas,
                include_selected_idea=args.include_selected_idea,
                include_selected_pilot=args.include_selected_pilot,
                include_selected_main=args.include_selected_main,
                include_selected_v24=args.include_selected_v24,
                include_selected_v25=args.include_selected_v25,
                include_selected_v26=args.include_selected_v26,
            )
        else:
            result = dashboard.build_run(args.run_id)
        if args.open:
            dashboard.open(result)
        print(f"Wrote dashboard to {result.index_path}")
        return 0
    if args.command == "selected-idea-full-report":
        path = write_selected_idea_full_report(config, args.project_id)
        print(path.read_text(encoding="utf-8"), end="")
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
    if args.command == "canonicalize-papers":
        if args.run_id is not None:
            canonical_identities, canonical_decisions = canonicalize_run(config, args.run_id)
            print(f"Canonical papers: {len(canonical_identities)}")
            print(f"Merge decisions: {len(canonical_decisions)}")
            print(f"Wrote {Path(config.runs_dir) / args.run_id / 'paper_merge_report.md'}")
            return 0
        project_identities, project_decisions = canonicalize_project(config, args.project_id)
        project = ProjectMemoryManager(config).load_project(args.project_id).project
        print(f"Canonical papers across project runs: {len(project_identities)}")
        print(f"Merge decisions: {len(project_decisions)}")
        print(f"Wrote {Path(project.root_dir) / 'paper_merge_report.md'}")
        return 0
    if args.command == "paper-merge-report":
        print(load_merge_report_for_run(config, args.run_id), end="")
        return 0
    if args.command == "source-health":
        checks = check_sources(config, source_name=args.source, test_query=args.topic)
        if args.write_report:
            source_health_json_path, source_health_md_path = write_source_health_artifacts(config, checks)
            print(f"Wrote source health diagnostics to {source_health_json_path} and {source_health_md_path}.")
            return 0
        print(render_source_health_markdown(checks), end="")
        return 0
    if args.command == "live-source-diagnostic":
        live_source_diagnostic = run_live_source_diagnostic(config, topic=args.topic, source_profile=args.source_profile)
        if args.write_report:
            live_source_json_path, live_source_md_path = write_live_source_diagnostic(config, live_source_diagnostic)
            print(f"Wrote live source diagnostic to {live_source_json_path} and {live_source_md_path}.")
            if not live_source_diagnostic.minimum_coverage_met:
                print("Real-literature campaign validation is blocked until source coverage issues are resolved or recorded as refusal.")
            return 0
        print(render_live_source_diagnostic_markdown(live_source_diagnostic), end="")
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
    if args.command == "setup-codex":
        codex_setup_status = build_codex_setup_status(AgentRuntimeConfig.from_env())
        if args.write_report:
            json_path, markdown_path = write_codex_setup_report(config, codex_setup_status)
            if not args.json:
                print(f"Wrote Codex setup report to {markdown_path}")
                print(f"Wrote Codex setup JSON to {json_path}")
        if args.json:
            print(json.dumps(to_plain(codex_setup_status), indent=2))
        elif not args.write_report:
            print(render_codex_setup_status(codex_setup_status), end="")
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
    if args.command == "codex-handoff":
        handoff_task_id = args.task_id or ""
        if args.campaign_id:
            campaign_state = CampaignManager(config).load_campaign_state(args.campaign_id)
            if not args.latest_task:
                raise ValueError("--campaign-id requires --latest-task for codex-handoff.")
            if not campaign_state.campaign.task_ids:
                raise ValueError(f"Campaign {args.campaign_id} has no agent tasks.")
            handoff_task_id = campaign_state.campaign.task_ids[-1]
        try:
            task_spec = _load_agent_task(config, handoff_task_id)
        except FileNotFoundError:
            campaign_state, pack_dir = find_campaign_task(config, handoff_task_id)
            handoff_path = write_task_handoff(config, handoff_task_id, model=campaign_state.campaign.model or "gpt-5.4")
            prompt_path = pack_dir / "CODEX_PROMPT.md"
            readme_path = pack_dir / "README_FIRST.md"
        else:
            state = ResearchStateManager(config).load_run(task_spec.run_id)
            pack_dir = CodexAgentClient(config, AgentRuntimeConfig(mode="task-pack")).create_task_pack(state, task_spec)
            handoff_path = write_handoff(task_spec, pack_dir, model=AgentRuntimeConfig.from_env().codex_model)
            prompt_path = pack_dir / "CODEX_PROMPT.md"
            readme_path = pack_dir / "README_FIRST.md"
        if args.print_prompt:
            print(prompt_path.read_text(encoding="utf-8"), end="")
        else:
            print(f"Wrote Codex handoff bundle to {pack_dir}")
            print(f"Read first: {readme_path}")
            print(f"Prompt: {prompt_path}")
            print(f"Handoff: {handoff_path}")
            print(f"Outputs directory: {pack_dir / 'outputs'}")
            print(f"Validate/import: {pack_dir / 'VALIDATE_AND_IMPORT.sh'}")
        if args.open:
            open_handoff_readme(readme_path)
        return 0
    if args.command == "codex-doctor":
        codex_doctor_report = doctor_codex_task(config, task_id=args.task_id or "", campaign_id=args.campaign_id or "")
        if args.json:
            print(doctor_to_json(codex_doctor_report), end="")
        else:
            print(render_codex_doctor_report(codex_doctor_report), end="")
        codex_doctor_reports = codex_doctor_report if isinstance(codex_doctor_report, list) else [codex_doctor_report]
        return 0 if all(item.actual_run_eligible or item.blockers for item in codex_doctor_reports) else 1
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
        repair_record, validation, repair_pack_dir = create_agent_repair_task(
            config,
            task_spec,
            paths,
            handoff=args.handoff,
            latest_invalid=args.latest_invalid,
        )
        if repair_record is None:
            print(json.dumps({"task_id": args.task_id, "validation": to_plain(validation), "repair_created": False}, indent=2))
            return 0
        if args.print_prompt and repair_pack_dir is not None:
            print((repair_pack_dir / "REPAIR.md").read_text(encoding="utf-8"), end="")
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
    if args.command == "validate-repair-output":
        repair_record, validation = validate_repair_output(config, args.repair_id)
        print(json.dumps({"repair_record": to_plain(repair_record), "validation": to_plain(validation)}, indent=2))
        return 0 if validation.status in {"valid", "warning"} else 1
    if args.command == "import-repair-output":
        repair_record, validation = import_repair_output(config, args.repair_id)
        print(json.dumps({"repair_record": to_plain(repair_record), "validation": to_plain(validation)}, indent=2))
        return 0 if validation.status in {"valid", "warning"} else 1
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
        state, task_spec = _load_agent_task_with_state(config, args.task_id)
        output_paths = _agent_output_paths_for_cli(state, task_spec, [Path(path) for path in args.path], discover_all=args.all)
        validation = AgentOutputImporter(config).import_outputs(
            task_spec,
            output_paths,
            strict_files=args.strict_files,
        )
        print(json.dumps(to_plain(validation), indent=2))
        return 0 if validation.status in {"valid", "warning"} else 1
    if args.command == "agent-validate-output":
        state, task_spec = _load_agent_task_with_state(config, args.task_id)
        output_paths = _agent_output_paths_for_cli(state, task_spec, [Path(path) for path in args.path or []], discover_all=args.all)
        validation = AgentOutputImporter(config).validate(
            task_spec,
            output_paths,
            strict_files=args.strict_files,
        )
        print(json.dumps(to_plain(validation), indent=2))
        return 0 if validation.status in {"valid", "warning"} else 1
    if args.command == "attest-agent-run":
        try:
            state, task_spec = _load_agent_task_with_state(config, args.task_id)
        except FileNotFoundError:
            campaign_state, _ = find_campaign_task(config, args.task_id)
            attestation = create_campaign_actual_run_attestation(
                campaign_state,
                args.task_id,
                agent_name=args.agent,
                model=args.model,
                execution_method=args.method,
                attester=args.attester,
                statement=args.statement,
            )
            CampaignManager(config).save_campaign_state(campaign_state)
            status = campaign_task_attestation_status(campaign_state, args.task_id)
            print(json.dumps({"attestation": to_plain(attestation), "status": to_plain(status)}, indent=2))
            return _attestation_command_exit(status)
        manager = ResearchStateManager(config)
        attestation = create_run_actual_run_attestation(
            state,
            task_spec,
            agent_name=args.agent,
            model=args.model,
            execution_method=args.method,
            attester=args.attester,
            statement=args.statement,
        )
        manager.save_run(state)
        status = _run_task_attestation_status(state, task_spec)
        print(json.dumps({"attestation": to_plain(attestation), "status": to_plain(status)}, indent=2))
        return _attestation_command_exit(status)
    if args.command == "attestation-status":
        if args.task_id:
            payload = _attestation_status_for_task(config, args.task_id)
        else:
            campaign_state = CampaignManager(config).load_campaign_state(args.campaign_id)
            payload = {
                "campaign_id": args.campaign_id,
                "statuses": [to_plain(status) for status in campaign_attestation_statuses(campaign_state)],
            }
        print(json.dumps(payload, indent=2))
        return 0
    if args.command == "actual-run-status":
        if args.run_id:
            state = ResearchStateManager(config).load_run(args.run_id)
            print(json.dumps(actual_run_status(state), indent=2))
        elif args.campaign_id:
            campaign_state = CampaignManager(config).load_campaign_state(args.campaign_id)
            print(json.dumps(campaign_actual_run_status(campaign_state), indent=2))
        else:
            print(json.dumps(_project_actual_run_status(config, args.project_id), indent=2))
        return 0
    if args.command == "validate-agent-output":
        state, task_spec = _load_agent_task_with_state(config, args.task_id)
        output_paths = _agent_output_paths_for_cli(state, task_spec, [], discover_all=args.all)
        validation = AgentOutputImporter(config).validate(task_spec, output_paths, strict_files=args.strict_files)
        print(json.dumps(to_plain(validation), indent=2))
        return 0 if validation.status in {"valid", "warning"} else 1
    if args.command == "import-agent-output":
        state, task_spec = _load_agent_task_with_state(config, args.task_id)
        output_paths = _agent_output_paths_for_cli(state, task_spec, [], discover_all=args.all)
        validation = AgentOutputImporter(config).import_outputs(task_spec, output_paths, strict_files=args.strict_files)
        print(json.dumps(to_plain(validation), indent=2))
        return 0 if validation.status in {"valid", "warning"} else 1
    if args.command == "list-task-outputs":
        payload = _list_task_outputs_payload(config, args.task_id)
        print(json.dumps(payload, indent=2))
        return 0
    if args.command == "latest-codex-task":
        task_id = _latest_campaign_task_id(config, args.campaign_id)
        print(task_id)
        return 0
    if args.command == "list-agent-tasks":
        state = ResearchStateManager(config).load_run(args.run_id)
        if not state.agent_task_specs:
            print("No agent tasks.")
            return 0
        for task_spec in state.agent_task_specs:
            validations = [item for item in state.agent_validation_results if item.task_spec_id == task_spec.id]
            validation_status_text = validations[-1].status if validations else "not_validated"
            print(f"{task_spec.id}\t{task_spec.skill_name}\t{task_spec.task_type}\t{validation_status_text}")
        return 0
    if args.command == "codex-run":
        try:
            task_spec = _load_agent_task(config, args.task_id)
        except FileNotFoundError:
            payload = _codex_run_campaign_task(
                config,
                args.task_id,
                prefer_direct=args.direct,
                handoff=args.handoff,
                require_direct=args.require_direct,
                dry_run=args.dry_run,
                allow_unknown_placeholders=args.allow_unknown_placeholders,
            )
            print(json.dumps(payload, indent=2))
            return 0 if payload.get("status") in {"complete", "planned", "preview"} else 1
        else:
            codex_run_record = CodexRunner(config, AgentRuntimeConfig.from_env()).run(
                task_spec,
                prefer_direct=args.direct,
                handoff=args.handoff,
                require_direct=args.require_direct,
                dry_run=args.dry_run,
                allow_unknown_placeholders=args.allow_unknown_placeholders,
            )
            print(json.dumps(to_plain(codex_run_record), indent=2))
            return 0 if codex_run_record.status in {"complete", "planned"} else 1
    if args.command == "codex-command-preview":
        try:
            task_spec = _load_agent_task(config, args.task_id)
        except FileNotFoundError:
            preview = _campaign_codex_command_preview(
                config,
                args.task_id,
                allow_unknown_placeholders=args.allow_unknown_placeholders,
            )
        else:
            preview = CodexRunner(config, AgentRuntimeConfig.from_env()).preview(
                task_spec,
                allow_unknown_placeholders=args.allow_unknown_placeholders,
            )
        print(json.dumps(preview, indent=2))
        return 0 if preview["command_template_valid"] else 1
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
    if args.command == "campaign-canary-complete":
        campaign_canary_record = CampaignCanaryRunManager(config).complete(args.canary_id)
        print(json.dumps(to_plain(campaign_canary_record), indent=2))
        return 0 if campaign_canary_record.accepted else 1
    if args.command == "real-literature-profiles":
        for real_literature_profile in default_real_literature_profiles():
            print(
                f"{real_literature_profile.id}\t{real_literature_profile.source_profile}\t"
                f"min_real={real_literature_profile.min_real_papers}\t{real_literature_profile.title}"
            )
        return 0
    if args.command == "real-literature-plan":
        print(RealLiteratureCampaignManager(config).plan(args.profile), end="")
        return 0
    if args.command == "real-literature-run":
        real_literature_record = RealLiteratureCampaignManager(config).run(args.profile)
        print(json.dumps(to_plain(real_literature_record), indent=2))
        return 0
    if args.command == "real-literature-status":
        real_literature_record = RealLiteratureCampaignManager(config).load_record(args.record_id)
        print(json.dumps(to_plain(real_literature_record), indent=2))
        return 0
    if args.command == "real-campaign-dry-run":
        try:
            dry_run_plan = build_real_campaign_dry_run(
                config,
                profile_id=args.profile,
                topic=args.topic,
                source_profile=args.source_profile,
            )
        except (KeyError, ValueError) as exc:
            print(str(exc), file=sys.stderr)
            return 2
        rendered = render_real_campaign_dry_run(dry_run_plan)
        if args.write_report:
            _json_path, md_path = write_real_campaign_dry_run(config, dry_run_plan)
            print(f"Wrote dry-run report: {md_path}")
        print(rendered, end="")
        return 0
    if args.command == "real-literature-review":
        real_literature_review_manager = RealLiteratureReviewManager(config)
        if not args.accept_quality and not any(
            [
                args.missed_obvious_prior_work,
                args.fake_citation_found,
                args.unsupported_high_confidence_claim_found,
                args.overclaimed_novelty,
            ]
        ):
            print(real_literature_review_manager.render_form(args.campaign_id), end="")
            return 0
        real_literature_review, real_literature_summary = real_literature_review_manager.review(
            args.campaign_id,
            reviewer=args.reviewer,
            accept_quality=args.accept_quality,
            reason=args.reason,
            source_quality_score=args.source_quality_score,
            paper_relevance_score=args.paper_relevance_score,
            prior_work_recall_score=args.prior_work_recall_score,
            evidence_grounding_score=args.evidence_grounding_score,
            novelty_honesty_score=args.novelty_honesty_score,
            gap_importance_score=args.gap_importance_score,
            experiment_feasibility_score=args.experiment_feasibility_score,
            reviewer_objection_quality_score=args.reviewer_objection_quality_score,
            report_honesty_score=args.report_honesty_score,
            missed_obvious_prior_work=args.missed_obvious_prior_work,
            fake_citation_found=args.fake_citation_found,
            unsupported_high_confidence_claim_found=args.unsupported_high_confidence_claim_found,
            overclaimed_novelty=args.overclaimed_novelty,
        )
        print(json.dumps({"review": to_plain(real_literature_review), "summary": real_literature_summary}, indent=2))
        return 0 if real_literature_summary["accepted_for_workflow"] else 1
    if args.command == "real-literature-acceptance":
        real_literature_summary = RealLiteratureReviewManager(config).acceptance(args.campaign_id)
        print(json.dumps(real_literature_summary, indent=2))
        return 0 if real_literature_summary["accepted_for_research_quality"] else 1
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
        action = CampaignController(config).next_action(args.campaign_id, real_literature=args.real_literature)
        print(json.dumps(to_plain(action), indent=2))
        return 0
    if args.command == "campaign-run":
        campaign_state = CampaignController(config).run(
            args.campaign_id,
            mode=args.mode,
            max_iterations=args.max_iterations,
            real_literature=args.real_literature,
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
    if args.command == "research-synthesis-task":
        pack_dir = create_research_synthesis_task(config, args.campaign_id)
        print(f"Wrote research synthesis task pack to {pack_dir}")
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
        if args.task_id:
            payload = _validate_import_all_task(config, args.task_id)
        else:
            payload = validate_import_all(config, args.campaign_id)
        print(json.dumps(payload, indent=2))
        return 0 if payload["status"] in {"valid", "warning", "imported", "applied", "partial", "no_tasks_processed"} else 1
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
        reviewer_status_text = reviewer_validation.get("status", "invalid") if isinstance(reviewer_validation, dict) else "invalid"
        return 0 if reviewer_status_text in {"valid", "warning"} else 1
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
        if args.next_commands:
            print("\n".join(gate_result.next_commands))
            return 0 if gate_result.passed else 1
        if args.json:
            print(json.dumps(gate_result.to_dict(), indent=2))
        else:
            print(render_v04_release_gate_markdown(gate_result), end="")
        return 0 if gate_result.passed else 1
    if args.command == "v5-release-gate":
        v5_gate_result = V05ReleaseGateEnforcer(config).evaluate(project_id=args.project_id)
        if args.write_report:
            V05ReleaseGateEnforcer(config).write_outputs(v5_gate_result)
        if args.json:
            print(json.dumps(v5_gate_result.to_dict(), indent=2))
        else:
            print(render_v05_release_gate_markdown(v5_gate_result), end="")
        return 0 if v5_gate_result.passed else 1
    if args.command == "v6-release-gate":
        v6_gate_result = V06ReleaseGateEnforcer(config).evaluate()
        if args.write_report:
            V06ReleaseGateEnforcer(config).write_outputs(v6_gate_result)
        if args.json:
            print(json.dumps(v6_gate_result.to_dict(), indent=2))
        else:
            print(render_v06_release_gate_markdown(v6_gate_result), end="")
        return 0 if v6_gate_result.passed else 1
    if args.command == "v7-release-gate":
        v7_enforcer = V07ReleaseGateEnforcer(config)
        v7_gate_result = v7_enforcer.evaluate(claim_real_benchmark_validation=args.claim_real)
        if args.write_report:
            v7_enforcer.write_outputs(v7_gate_result)
        if args.json:
            print(json.dumps(v7_gate_result.to_dict(), indent=2))
        else:
            print(render_v07_release_gate_markdown(v7_gate_result), end="")
        return 0 if v7_gate_result.passed else 1
    if args.command == "v8-release-gate":
        v8_enforcer = V08ReleaseGateEnforcer(config)
        v8_gate_result = v8_enforcer.evaluate()
        if args.write_report:
            v8_enforcer.write_outputs(v8_gate_result)
        if args.json:
            print(json.dumps(v8_gate_result.to_dict(), indent=2))
        else:
            print(render_v08_release_gate_markdown(v8_gate_result), end="")
        return 0 if v8_gate_result.passed else 1
    if args.command == "v9-release-gate":
        v9_enforcer = V09ReleaseGateEnforcer(config)
        v9_gate_result = v9_enforcer.evaluate()
        if args.write_report:
            v9_enforcer.write_outputs(v9_gate_result)
        if args.json:
            print(json.dumps(v9_gate_result.to_dict(), indent=2))
        else:
            print(render_v09_release_gate_markdown(v9_gate_result), end="")
        return 0 if v9_gate_result.passed else 1
    if args.command == "v1-readiness":
        v1_gate = V1ReadinessGate(config)
        v1_result = v1_gate.evaluate()
        if args.write_report:
            v1_gate.write_outputs(v1_result)
        if args.next_commands:
            print("\n".join(v1_result.next_commands))
            return 0 if v1_result.passed else 1
        if args.json:
            print(json.dumps(v1_result.to_dict(), indent=2))
        else:
            print(render_v1_readiness_markdown(v1_result), end="")
        return 0 if v1_result.passed else 1
    if args.command == "v2-release-gate":
        v2_gate = V2ReleaseGateEnforcer(config)
        v2_result = v2_gate.evaluate(allow_agenda_only=args.allow_agenda_only)
        if args.write_report:
            v2_gate.write_outputs(v2_result)
        if args.json:
            print(json.dumps(v2_result.to_dict(), indent=2))
        else:
            print(render_v2_release_gate_markdown(v2_result), end="")
        return 0 if v2_result.passed else 1
    if args.command == "v21-release-gate":
        v21_gate = V21ReleaseGateEnforcer(config)
        v21_result = v21_gate.evaluate()
        if args.write_report:
            v21_gate.write_outputs(v21_result)
        if args.json:
            print(json.dumps(v21_result.to_dict(), indent=2))
        else:
            print(render_v21_release_gate_markdown(v21_result), end="")
        return 0 if v21_result.passed else 1
    if args.command == "v22-release-gate":
        v22_gate = V22ReleaseGateEnforcer(config)
        v22_result = v22_gate.evaluate()
        if args.write_report:
            v22_gate.write_outputs(v22_result)
        if args.json:
            print(json.dumps(v22_result.to_dict(), indent=2))
        else:
            print(render_v22_release_gate_markdown(v22_result), end="")
        return 0 if v22_result.passed else 1
    if args.command == "v23-release-gate":
        v23_gate = V23ReleaseGateEnforcer(config)
        v23_result = v23_gate.evaluate()
        if args.write_report:
            v23_gate.write_outputs(v23_result)
        if args.json:
            print(json.dumps(v23_result.to_dict(), indent=2))
        else:
            print(render_v23_release_gate_markdown(v23_result), end="")
        return 0 if v23_result.passed else 1
    if args.command == "v24-release-gate":
        v24_gate = V24ReleaseGateEnforcer(config)
        v24_result = v24_gate.evaluate()
        if args.write_report:
            v24_gate.write_outputs(v24_result)
        if args.json:
            print(json.dumps(v24_result.to_dict(), indent=2))
        else:
            print(render_v24_release_gate_markdown(v24_result), end="")
        return 0 if v24_result.passed else 1
    if args.command == "v25-release-gate":
        v25_gate = V25ReleaseGateEnforcer(config)
        v25_result = v25_gate.evaluate()
        if args.write_report:
            v25_gate.write_outputs(v25_result)
        if args.json:
            print(json.dumps(v25_result.to_dict(), indent=2))
        else:
            print(render_v25_release_gate_markdown(v25_result), end="")
        return 0 if v25_result.passed else 1
    if args.command == "v26-release-gate":
        v26_gate = V26ReleaseGateEnforcer(config)
        v26_result = v26_gate.evaluate()
        if args.write_report:
            v26_gate.write_outputs(v26_result)
        if args.json:
            print(json.dumps(v26_result.to_dict(), indent=2))
        else:
            print(render_v26_release_gate_markdown(v26_result), end="")
        return 0 if v26_result.passed else 1
    if args.command == "cli-audit":
        cli_audit = CLICommandAuditor(config).audit(build_parser(), write=args.write_report)
        print(render_cli_command_audit(cli_audit), end="")
        return 0 if not cli_audit.missing_help else 1
    if args.command == "docs-audit":
        docs_audit = DocsAuditor(config).audit(write=args.write_report)
        print(render_docs_audit(docs_audit), end="")
        return 0 if docs_audit.passed else 1
    if args.command == "compatibility-audit":
        if args.v2:
            include_fixtures = args.fixtures or not args.local
            include_local = args.local or not args.fixtures
            audit_v2 = CompatibilityAuditor(config).audit_v2(
                write=args.write_report,
                include_fixtures=include_fixtures,
                include_local=include_local,
            )
            if args.json:
                print(json.dumps(to_plain(audit_v2), indent=2))
            else:
                print(render_compatibility_audit_v2(audit_v2), end="")
            return 0 if audit_v2.status in {"pass", "warning"} else 1
        audit = CompatibilityAuditor(config).audit(write=True, include_fixtures=args.fixtures)
        if args.json:
            print(json.dumps(to_plain(audit), indent=2))
        else:
            print(render_compatibility_audit(audit), end="")
        return 0 if not audit.migration_required and not audit.migration_failures else 1
    if args.command == "migration-fixtures-list":
        fixtures = list_historical_migration_fixtures(config)
        if args.json:
            print(json.dumps([fixture.to_dict() for fixture in fixtures], indent=2))
        else:
            print(render_migration_fixtures_list(fixtures), end="")
        return 0 if fixtures else 1
    if args.command == "migration-blockers":
        migration_blocker_report = build_migration_blocker_report(config)
        if args.write_report:
            write_migration_blocker_report(config, migration_blocker_report)
        if args.json:
            print(report_to_json(migration_blocker_report), end="")
        else:
            print(render_migration_blocker_report(migration_blocker_report), end="")
        return 0 if migration_blocker_report.passed else 1
    if args.command == "migrate-project":
        migration_record = MigrationManager(config).migrate_project(args.project_id, to_version=args.to_version)
        print(json.dumps(to_plain(migration_record), indent=2))
        return 0 if migration_record.status == "migrated" else 1
    if args.command == "migrate-run":
        migration_record = MigrationManager(config).migrate_run(args.run_id, to_version=args.to_version)
        print(json.dumps(to_plain(migration_record), indent=2))
        return 0 if migration_record.status == "migrated" else 1
    if args.command == "migrate-all":
        migration_records = MigrationManager(config).migrate_all(dry_run=args.dry_run, to_version=args.to_version)
        print(json.dumps([to_plain(record) for record in migration_records], indent=2))
        successful_statuses = {"planned", "migrated", "skipped", "warning"}
        return 0 if all(record.status in successful_statuses for record in migration_records) else 1
    if args.command == "migration-report":
        print(MigrationManager(config).report(), end="")
        return 0
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
    if args.command == "idea-bank-create":
        bank = IdeaStore(config).create_bank(project_id=args.project_id, root_topic=args.root_topic)
        print(json.dumps(to_plain(bank), indent=2))
        return 0
    if args.command == "idea-list":
        print(IdeaStore(config).render_bank(args.project_id), end="")
        return 0
    if args.command == "idea-report":
        print(IdeaStore(config).write_idea_report(args.idea_id), end="")
        return 0
    if args.command == "idea-review":
        idea_store = IdeaStore(config)
        if args.reviewer:
            idea_review_record = idea_store.add_review(
                idea_id=args.idea_id,
                reviewer=args.reviewer,
                status=args.status,
                novelty_judgment=args.novelty_judgment,
                feasibility_judgment=args.feasibility_judgment,
                impact_judgment=args.impact_judgment,
                required_fixes=args.required_fixes,
                notes=args.notes,
            )
            print(json.dumps(to_plain(idea_review_record), indent=2))
        else:
            print(idea_store.render_idea_report(args.idea_id), end="")
        return 0
    if args.command == "topic-portfolio":
        generator = TopicPortfolioGenerator(config)
        portfolio = generator.generate(root_topic=args.root_topic or "", project_id=args.project_id)
        print(json.dumps(to_plain(portfolio), indent=2))
        return 0
    if args.command == "topic-portfolio-report":
        print(TopicPortfolioGenerator(config).write_report(args.portfolio_id), end="")
        return 0
    if args.command == "idea-generate":
        idea_generation_result = IdeaSeedGenerator(config).generate(
            project_id=args.project_id or "",
            portfolio_id=args.portfolio_id or "",
            max_candidates=args.max_candidates,
        )
        print(json.dumps(to_plain(idea_generation_result), indent=2))
        return 0
    if args.command == "mutate-idea":
        mutation_result = IdeaMutationEngine(config).mutate_idea(args.idea_id, strategy=args.strategy)
        print(json.dumps(to_plain(mutation_result), indent=2))
        return 0
    if args.command == "mutate-rejected-ideas":
        mutation_results = IdeaMutationEngine(config).mutate_rejected_ideas(args.project_id, strategy=args.strategy)
        print(json.dumps(to_plain(mutation_results), indent=2))
        return 0
    if args.command == "mutation-report":
        print(IdeaMutationEngine(config).write_report(args.project_id), end="")
        return 0
    if args.command == "constructive-gaps":
        constructive_gap_generator = ConstructiveGapGenerator(config)
        if args.project_id:
            constructive_gap_result = constructive_gap_generator.generate_for_project(args.project_id)
        else:
            constructive_gap_result = constructive_gap_generator.generate_for_campaign(args.campaign_id)
        print(json.dumps(to_plain(constructive_gap_result), indent=2))
        return 0
    if args.command == "constructive-gap-report":
        print(ConstructiveGapGenerator(config).write_report(args.project_id), end="")
        return 0
    if args.command == "transfer-ideas":
        transfer_engine = CrossDomainIdeaTransferEngine(config)
        if args.project_id:
            transfer_result = transfer_engine.transfer_for_project(args.project_id)
        else:
            transfer_result = transfer_engine.transfer_for_topic(args.topic)
        print(json.dumps(to_plain(transfer_result), indent=2))
        return 0
    if args.command == "transfer-report":
        print(CrossDomainIdeaTransferEngine(config).write_report(args.project_id), end="")
        return 0
    if args.command == "idea-codex-task":
        task = IdeaCodexTaskManager(config).create_task(args.project_id, args.type)
        print(json.dumps(to_plain(task), indent=2))
        return 0
    if args.command == "idea-codex-handoff":
        print(IdeaCodexTaskManager(config).handoff(args.task_id), end="")
        return 0
    if args.command == "idea-codex-import":
        idea_codex_record = IdeaCodexTaskManager(config).import_outputs(args.task_id)
        print(json.dumps(to_plain(idea_codex_record), indent=2))
        return 0
    if args.command == "idea-search":
        idea_search_result = IdeaSearchController(config).run(args.project_id, max_iterations=args.max_iterations)
        print(json.dumps(to_plain(idea_search_result), indent=2))
        return 0
    if args.command == "idea-search-status":
        print(IdeaSearchController(config).render_status(args.project_id), end="")
        return 0
    if args.command == "idea-search-decisions":
        print(IdeaSearchController(config).render_decisions(args.project_id), end="")
        return 0
    if args.command == "idea-novelty":
        idea_novelty_loop = IdeaNoveltyLoop(config)
        if args.idea_id:
            print(json.dumps(to_plain(idea_novelty_loop.assess_idea(args.idea_id, top_k=args.top_k)), indent=2))
        else:
            print(json.dumps(to_plain(idea_novelty_loop.assess_project(args.project_id, top_k=args.top_k)), indent=2))
        return 0
    if args.command == "idea-counterevidence":
        counterevidence_result = IdeaNoveltyLoop(config).find_counterevidence(args.idea_id, top_k=args.top_k)
        print(json.dumps(to_plain(counterevidence_result), indent=2))
        return 0
    if args.command == "idea-tournament":
        tournament = IdeaTournamentRunner(config).run(args.project_id, top_k=args.top_k)
        print(json.dumps(to_plain(tournament), indent=2))
        return 0
    if args.command == "idea-score-report":
        print(IdeaTournamentRunner(config).write_report(args.project_id), end="")
        return 0
    if args.command == "idea-preferences":
        preferences = IdeaPreferenceManager(config).save_profile(
            project_id=args.project_id,
            preferred_contribution_types=args.preferred_contribution_types,
            preferred_domains=args.preferred_domains,
            risk_tolerance=args.risk_tolerance,
            time_budget=args.time_budget,
            compute_budget=args.compute_budget,
            publication_target=args.publication_target,
            avoid_topics=args.avoid_topics,
            notes=args.notes,
        )
        print(json.dumps(to_plain(preferences), indent=2))
        return 0
    if args.command == "idea-feedback":
        feedback = IdeaFeedbackManager(config).add_feedback(
            idea_id=args.idea_id,
            action=args.action,
            reviewer=args.reviewer,
            rationale=args.rationale,
            preferred_mutations=args.preferred_mutations,
            notes=args.notes,
        )
        print(json.dumps(to_plain(feedback), indent=2))
        return 0
    if args.command == "idea-feedback-report":
        print(IdeaFeedbackManager(config).write_report(args.project_id), end="")
        return 0
    if args.command == "idea-yield":
        idea_yield = IdeaYieldMetricCalculator(config)
        if args.write_report:
            print(idea_yield.write_report(args.project_id), end="")
        else:
            print(json.dumps(to_plain(idea_yield.compute(args.project_id)), indent=2))
        return 0
    if args.command == "selected-idea-lock":
        lock = SelectedIdeaProjectManager(config).lock_selected_idea(
            args.idea_id,
            locked_by=args.locked_by,
            lock_reason=args.lock_reason,
            force=args.force,
        )
        print(json.dumps(to_plain(lock), indent=2))
        return 0
    if args.command == "selected-idea-project-create":
        selected_project = SelectedIdeaProjectManager(config).create_selected_project(
            args.idea_id,
            locked_by=args.locked_by,
            lock_reason=args.lock_reason,
            force=args.force,
        )
        print(json.dumps(to_plain(selected_project), indent=2))
        return 0
    if args.command == "selected-idea-status":
        print(SelectedIdeaProjectManager(config).write_status(args.project_id), end="")
        return 0
    if args.command == "selected-benchmark-spec":
        benchmark_spec = SelectedBenchmarkManager(config).create_spec(args.project_id)
        print(json.dumps(to_plain(benchmark_spec), indent=2))
        return 0
    if args.command == "threat-model":
        threat_model = SelectedBenchmarkManager(config).create_threat_model(args.benchmark_id)
        print(json.dumps(to_plain(threat_model), indent=2))
        return 0
    if args.command == "benchmark-task-families":
        task_families = SelectedBenchmarkManager(config).create_task_families(args.benchmark_id)
        print(json.dumps(to_plain(task_families), indent=2))
        return 0
    if args.command == "selected-benchmark-report":
        print(SelectedBenchmarkManager(config).render_report(args.benchmark_id), end="")
        return 0
    if args.command == "selected-vetted-benchmark-map":
        mapping_report = SelectedBenchmarkVettedMappingManager(config).map_benchmarks(
            args.benchmark_id,
            vetted_benchmark_id=args.vetted_benchmark_id,
        )
        print(json.dumps(to_plain(mapping_report), indent=2))
        return 0
    if args.command == "selected-vetted-benchmark-report":
        print(SelectedBenchmarkVettedMappingManager(config).render_report(args.benchmark_id), end="")
        return 0
    if args.command == "selected-real-benchmark-search":
        real_benchmark_search = RealBenchmarkSearchManager(config).search(args.benchmark_id)
        print(render_real_benchmark_search(real_benchmark_search), end="")
        return 0 if real_benchmark_search.status in {"complete", "no_fit"} else 1
    if args.command == "selected-real-benchmark-candidates":
        print(RealBenchmarkSearchManager(config).render_candidates(args.benchmark_id), end="")
        return 0
    if args.command == "selected-real-benchmark-no-fit":
        print(RealBenchmarkSearchManager(config).render_no_fit_report(args.benchmark_id), end="")
        return 0
    if args.command == "selected-real-benchmark-adapter-assess":
        real_adapter_assessment = SelectedVettedBenchmarkExperimentManager(config).assess_real_candidate(
            args.benchmark_id,
            args.candidate_id,
        )
        print(render_real_benchmark_adapter_assessment(real_adapter_assessment), end="")
        return 0 if real_adapter_assessment.adapter_possible else 1
    if args.command == "selected-real-benchmark-adapter-create":
        real_adapter = SelectedVettedBenchmarkExperimentManager(config).create_real_candidate_adapter(
            args.benchmark_id,
            args.candidate_id,
        )
        print(json.dumps(to_plain(real_adapter), indent=2))
        return 0
    if args.command == "selected-real-benchmark-adapter-run":
        real_adapter_run = SelectedVettedBenchmarkExperimentManager(config).run_real_candidate_adapter(args.adapter_id)
        print(json.dumps(to_plain(real_adapter_run), indent=2))
        return 0 if real_adapter_run.status == "complete" else 1
    if args.command == "selected-real-benchmark-experiment-plan":
        real_benchmark_attempts = RealBenchmarkExperimentManager(config).plan(args.benchmark_id)
        print(json.dumps(to_plain(real_benchmark_attempts), indent=2))
        return 0
    if args.command == "selected-real-benchmark-experiment-run":
        real_benchmark_attempts = RealBenchmarkExperimentManager(config).run(args.benchmark_id)
        print(json.dumps(to_plain(real_benchmark_attempts), indent=2))
        return 0 if not any(attempt.status == "failed" for attempt in real_benchmark_attempts) else 1
    if args.command == "selected-real-benchmark-experiment-report":
        print(RealBenchmarkExperimentManager(config).report(args.benchmark_id), end="")
        return 0
    if args.command == "selected-venue-artifact-integrate":
        venue_artifact_report = VenueArtifactIntegrationManager(config).integrate(args.benchmark_id)
        print(render_venue_artifact_integration_report(venue_artifact_report), end="")
        return 0 if not venue_artifact_report.blockers else 1
    if args.command == "selected-venue-artifact-report":
        print(VenueArtifactIntegrationManager(config).report(args.benchmark_id), end="")
        return 0
    if args.command == "selected-venue-revision-package":
        venue_revision_package = VenueRevisionPackageManager(config).create(args.benchmark_id)
        print(render_venue_revision_package(venue_revision_package), end="")
        return 0 if venue_revision_package.status in {"workshop_candidate", "conference_candidate", "revise_for_reviews"} else 1
    if args.command == "selected-venue-revision-status":
        print(VenueRevisionPackageManager(config).status(args.benchmark_id), end="")
        return 0
    if args.command == "benchmark-adapter-create":
        adapter = BenchmarkAdapterRegistry(config).create_adapter(
            selected_benchmark_id=args.selected_benchmark_id,
            vetted_benchmark_id=args.vetted_benchmark_id,
        )
        print(json.dumps(to_plain(adapter), indent=2))
        return 0
    if args.command == "benchmark-adapter-run":
        adapter_run = BenchmarkAdapterRegistry(config).run_adapter(args.adapter_id)
        print(json.dumps(to_plain(adapter_run), indent=2))
        return 0
    if args.command == "benchmark-adapter-report":
        print(BenchmarkAdapterRegistry(config).render_report(args.adapter_id), end="")
        return 0
    if args.command == "selected-vetted-experiment-plan":
        vetted_experiment_plan = SelectedVettedBenchmarkExperimentManager(config).create_plan(args.benchmark_id)
        print(json.dumps(to_plain(vetted_experiment_plan), indent=2))
        return 0
    if args.command == "selected-vetted-experiment-run":
        vetted_experiment_result = SelectedVettedBenchmarkExperimentManager(config).run_plan(args.plan_id)
        print(json.dumps(to_plain(vetted_experiment_result), indent=2))
        return 0
    if args.command == "selected-vetted-experiment-report":
        print(SelectedVettedBenchmarkExperimentManager(config).render_report(args.plan_id), end="")
        return 0
    if args.command == "generate-traces":
        dataset = SyntheticTraceGenerator(config).generate(args.benchmark_id, count=args.count, split=args.split)
        print(json.dumps(to_plain(dataset), indent=2))
        return 0
    if args.command == "honest-null-scenarios":
        honest_null_scenarios = HonestNullManager(config).create_scenarios(args.benchmark_id)
        print(json.dumps(to_plain(honest_null_scenarios), indent=2))
        return 0
    if args.command == "generate-honest-null":
        honest_null_dataset = HonestNullManager(config).generate(args.benchmark_id, count=args.count)
        print(json.dumps(to_plain(honest_null_dataset), indent=2))
        return 0
    if args.command == "honest-null-report":
        honest_null_report = HonestNullManager(config).report(args.benchmark_id)
        print(render_honest_null_report(honest_null_report), end="")
        return 0
    if args.command == "collusive-scenarios":
        collusive_scenarios = CollusiveAlternativeManager(config).create_scenarios(args.benchmark_id)
        print(json.dumps(to_plain(collusive_scenarios), indent=2))
        return 0
    if args.command == "generate-collusive-traces":
        collusive_dataset = CollusiveAlternativeManager(config).generate(args.benchmark_id, count=args.count)
        print(json.dumps(to_plain(collusive_dataset), indent=2))
        return 0
    if args.command == "collusive-distribution-report":
        collusive_report = CollusiveAlternativeManager(config).report(args.benchmark_id)
        print(render_collusive_distribution_report(collusive_report), end="")
        return 0
    if args.command == "build-pilot-trace-dataset":
        pilot_dataset = PilotDatasetBuilder(config).build(
            args.benchmark_id,
            negative_count=args.negative_count,
            positive_count=args.positive_count,
        )
        print(json.dumps(to_plain(pilot_dataset), indent=2))
        return 0
    if args.command == "pilot-trace-dataset-report":
        pilot_dataset_report = PilotDatasetBuilder(config).report(args.dataset_id)
        print(render_pilot_trace_dataset_report(pilot_dataset_report), end="")
        return 0
    if args.command == "build-main-trace-dataset":
        main_dataset = MainDatasetBuilder(config).build(
            args.benchmark_id,
            negative_count=args.negative_count,
            positive_count=args.positive_count,
        )
        print(json.dumps(to_plain(main_dataset), indent=2))
        return 0
    if args.command == "main-trace-dataset-report":
        print(MainDatasetBuilder(config).render_report(args.dataset_id), end="")
        return 0
    if args.command == "selected-main-manifest":
        main_manifest = MainRunManager(config).create_manifest(args.benchmark_id, args.dataset_id)
        print(json.dumps(to_plain(main_manifest), indent=2))
        return 0
    if args.command == "selected-main-run":
        execution = MainRunManager(config).run(args.benchmark_id, args.manifest_id)
        print(json.dumps(to_plain(execution), indent=2))
        return 0 if execution.status == "complete" else 1
    if args.command == "selected-main-status":
        print(render_selected_main_status(MainRunManager(config).status(args.execution_id)), end="")
        return 0
    if args.command == "selected-main-analysis":
        analysis = MainAnalysisManager(config).analyze(args.execution_id)
        print(render_selected_main_analysis(analysis), end="")
        return 0
    if args.command == "selected-benchmark-go-no-go":
        go_no_go = GoNoGoManager(config).decide(args.benchmark_id)
        print(json.dumps(to_plain(go_no_go), indent=2))
        return 0 if go_no_go.decision == "go_publication_candidate" else 1
    if args.command == "selected-go-no-go-report":
        print(GoNoGoManager(config).report(args.benchmark_id), end="")
        return 0
    if args.command == "trace-dataset-report":
        print(SyntheticTraceGenerator(config).render_dataset_report(args.dataset_id), end="")
        return 0
    if args.command == "trace-list":
        print(render_trace_list(SyntheticTraceGenerator(config).list_traces(args.benchmark_id)), end="")
        return 0
    if args.command == "sequential-metric-plan":
        print(render_metric_plan(SequentialMetricManager(config).create_plan(args.benchmark_id)), end="")
        return 0
    if args.command == "compute-sequential-metrics":
        metric_results = SequentialMetricManager(config).compute(args.execution_id)
        print(json.dumps(to_plain(metric_results), indent=2))
        return 0
    if args.command == "low-fpr-audit-check":
        print(SequentialMetricManager(config).render_low_fpr_audit_check(args.execution_id), end="")
        return 0
    if args.command == "selected-monitor-baselines":
        baselines = MonitorBaselineManager(config).create_baselines(args.benchmark_id)
        print(json.dumps(to_plain(baselines), indent=2))
        return 0
    if args.command == "run-monitor-baseline":
        run = MonitorBaselineManager(config).run_baseline(args.benchmark_id, args.monitor)
        print(json.dumps(to_plain(run), indent=2))
        return 0
    if args.command == "monitor-baseline-report":
        print(MonitorBaselineManager(config).render_report(args.benchmark_id), end="")
        return 0
    if args.command == "calibrate-monitor":
        calibration_record = MonitorBaselineManager(config).calibrate_monitor(
            args.benchmark_id,
            args.monitor,
            target_alpha=args.target_alpha,
        )
        print(json.dumps(to_plain(calibration_record), indent=2))
        return 0
    if args.command == "run-pilot-baselines":
        baseline_runs = MonitorBaselineManager(config).run_pilot_baselines(args.benchmark_id, args.dataset_id)
        print(json.dumps(to_plain(baseline_runs), indent=2))
        return 0
    if args.command == "pilot-baseline-report":
        print(MonitorBaselineManager(config).render_pilot_report(args.benchmark_id), end="")
        return 0
    if args.command == "selected-baseline-strength":
        baseline_strength = MonitorBaselineManager(config).assess_baseline_strength(args.benchmark_id)
        print(json.dumps(to_plain(baseline_strength), indent=2))
        return 0 if baseline_strength.strong_claim_allowed else 1
    if args.command == "implement-required-baseline-task":
        baseline = MonitorBaselineManager(config).implement_required_baseline_task(args.benchmark_id, args.baseline)
        print(json.dumps(to_plain(baseline), indent=2))
        return 0
    if args.command == "selected-baseline-strength-report":
        print(MonitorBaselineManager(config).render_baseline_strength_report(args.benchmark_id), end="")
        return 0
    if args.command == "selected-benchmark-workspace":
        workspace = SelectedBenchmarkWorkspaceManager(config).create_workspace(args.benchmark_id)
        print(json.dumps(to_plain(workspace), indent=2))
        return 0
    if args.command == "selected-benchmark-manifest":
        selected_benchmark_manifest = SelectedBenchmarkWorkspaceManager(config).create_manifest(args.workspace_id, run_type=args.run_type)
        print(json.dumps(to_plain(selected_benchmark_manifest), indent=2))
        return 0
    if args.command == "selected-benchmark-run":
        selected_benchmark_run_result = SelectedBenchmarkExperimentRunner(config).run(args.workspace_id, run_type=args.run_type)
        print(json.dumps(to_plain(selected_benchmark_run_result), indent=2))
        return 0
    if args.command == "selected-benchmark-prior-work":
        related_work_manager = SelectedBenchmarkRelatedWorkManager(config)
        recall = related_work_manager.build_prior_work_recall(args.benchmark_id)
        print(related_work_manager.prior_work_recall_path(args.benchmark_id).with_suffix(".md").read_text(encoding="utf-8"), end="")
        return 0 if not recall.blocking_issues else 1
    if args.command == "selected-benchmark-related-work":
        related_work_manager = SelectedBenchmarkRelatedWorkManager(config)
        related_work_manager.build_related_work_matrix(args.benchmark_id)
        print(related_work_manager.render_related_work_matrix(args.benchmark_id), end="")
        return 0
    if args.command == "selected-related-work-complete":
        completion_manager = RelatedWorkCompletionManager(config)
        completion_status = completion_manager.complete(args.benchmark_id)
        print(
            render_related_work_completion_status(completion_status, completion_manager.next_searches_for_status(completion_status)),
            end="",
        )
        return 0 if not completion_status.blockers else 1
    if args.command == "selected-related-work-next-searches":
        print("\n".join(RelatedWorkCompletionManager(config).next_searches(args.benchmark_id)), end="\n")
        return 0
    if args.command == "selected-related-work-status":
        print(RelatedWorkCompletionManager(config).status_report(args.benchmark_id), end="")
        return 0
    if args.command == "selected-related-work-search-plan":
        campaign = RequiredRelatedWorkSearchManager(config).plan(args.benchmark_id)
        print(render_required_related_work_search_report(campaign), end="")
        return 0
    if args.command == "selected-related-work-search-run":
        campaign = RequiredRelatedWorkSearchManager(config).run(args.benchmark_id)
        print(render_required_related_work_search_report(campaign), end="")
        return 0 if campaign.status == "complete" else 1
    if args.command in {"selected-related-work-search-status", "selected-related-work-search-report"}:
        print(RequiredRelatedWorkSearchManager(config).status_report(args.benchmark_id), end="")
        return 0
    if args.command == "attach-related-paper":
        attachment = RelatedWorkCurationManager(config).attach_paper(
            args.benchmark_id,
            category=args.category,
            paper_id=args.paper_id,
            relationship=args.relationship,
            curator=args.curator,
            notes=args.notes,
        )
        print(json.dumps(to_plain(attachment), indent=2))
        return 0 if attachment.status == "accepted" else 1
    if args.command == "reject-related-paper":
        rejected = RelatedWorkCurationManager(config).reject_paper(
            args.benchmark_id,
            paper_id=args.paper_id,
            reason=args.reason,
            curator=args.curator,
        )
        print(json.dumps([to_plain(attachment) for attachment in rejected], indent=2))
        return 0
    if args.command == "related-work-curation-report":
        curation_report = RelatedWorkCurationManager(config).report(args.benchmark_id)
        print(render_related_work_curation_report(curation_report), end="")
        return 0
    if args.command == "related-work-auto-curate":
        curation_report = RelatedWorkCurationManager(config).auto_curate(args.benchmark_id, curator=args.curator)
        print(render_related_work_curation_report(curation_report), end="")
        return 0 if not curation_report.missing_categories else 1
    if args.command == "read-selected-related-work":
        statuses = RelatedWorkReadingManager(config).read(args.benchmark_id, paper_id=args.paper_id or None)
        print(render_related_work_reading_report(statuses), end="")
        return 0 if statuses else 1
    if args.command == "selected-related-work-reading-report":
        print(RelatedWorkReadingManager(config).report(args.benchmark_id), end="")
        return 0
    if args.command == "selected-prior-work-refresh":
        dossier = SelectedBenchmarkPriorWorkRefreshManager(config).refresh(args.benchmark_id)
        print(render_selected_prior_work_dossier(dossier), end="")
        return 0 if dossier.novelty_status not in {"unknown", "duplicate"} else 1
    if args.command == "selected-prior-work-dossier":
        dossier = SelectedBenchmarkPriorWorkRefreshManager(config).load_or_refresh(args.benchmark_id)
        print(render_selected_prior_work_dossier(dossier), end="")
        return 0
    if args.command == "selected-positioning":
        positioning_report = SelectedBenchmarkPositioningManager(config).build(args.benchmark_id)
        print(render_positioning_report(positioning_report), end="")
        return 0
    if args.command == "selected-positioning-report":
        positioning_report = SelectedBenchmarkPositioningManager(config).load_or_build(args.benchmark_id)
        print(render_positioning_report(positioning_report), end="")
        return 0
    if args.command == "selected-related-work-matrix-v2":
        matrix_v2 = SelectedBenchmarkRelatedWorkMatrixV2Manager(config).build(args.benchmark_id)
        print(render_related_work_matrix_v2(matrix_v2), end="")
        has_direct_solution = any(entry.relationship == "directly solves" for entry in matrix_v2.entries)
        return 0 if not matrix_v2.missing_categories and not has_direct_solution else 1
    if args.command == "selected-related-work-matrix-load":
        load_result = RelatedWorkMatrixLoader(config).load(args.benchmark_id)
        print(render_related_work_matrix_load_result(load_result), end="")
        return 0 if load_result.status in {"loaded", "repaired"} and not load_result.blockers else 1
    if args.command == "selected-related-work-matrix-repair":
        matrix_repair_record = RelatedWorkMatrixLoader(config).repair(args.benchmark_id)
        print(render_related_work_matrix_repair_record(matrix_repair_record), end="")
        return 0 if matrix_repair_record.status == "repaired" else 1
    if args.command == "selected-related-work-matrix-status":
        print(RelatedWorkMatrixLoader(config).status_report(args.benchmark_id), end="")
        return 0
    if args.command == "selected-artifact-package-load":
        artifact_load_result = ArtifactPackageLoader(config).load(args.benchmark_id)
        print(render_artifact_package_load_result(artifact_load_result), end="")
        return 0 if artifact_load_result.status in {"loaded", "repaired"} and not artifact_load_result.blockers else 1
    if args.command == "selected-artifact-package-repair":
        artifact_repair_record = ArtifactPackageLoader(config).repair(args.benchmark_id)
        print(render_artifact_package_repair_record(artifact_repair_record), end="")
        return 0 if artifact_repair_record.status == "repaired" else 1
    if args.command == "selected-artifact-package-status":
        print(ArtifactPackageLoader(config).status_report(args.benchmark_id), end="")
        return 0
    if args.command == "selected-must-cite":
        print(SelectedBenchmarkRelatedWorkMatrixV2Manager(config).must_cite_report(args.benchmark_id), end="")
        return 0
    if args.command == "selected-benchmark-novelty-report":
        from gapforge.selected_benchmark.related_work import render_novelty_positioning

        positioning = SelectedBenchmarkRelatedWorkManager(config).novelty_report(args.benchmark_id)
        print(render_novelty_positioning(positioning), end="")
        return 0 if not positioning.blocking_issues else 1
    if args.command == "selected-pilot-manifest":
        selected_pilot_manifest = PilotRunManager(config).create_manifest(args.benchmark_id, args.dataset_id)
        print(json.dumps(to_plain(selected_pilot_manifest), indent=2))
        return 0
    if args.command == "selected-pilot-run":
        selected_pilot_execution = PilotRunManager(config).run(args.benchmark_id, args.manifest_id)
        print(json.dumps(to_plain(selected_pilot_execution), indent=2))
        return 0
    if args.command == "selected-pilot-status":
        from gapforge.selected_benchmark.pilot_run import render_selected_pilot_status

        selected_pilot_execution = PilotRunManager(config).status(args.execution_id)
        print(render_selected_pilot_status(selected_pilot_execution), end="")
        return 0
    if args.command == "selected-pilot-analysis":
        selected_pilot_analysis = PilotAnalysisManager(config).analyze(args.execution_id)
        print(json.dumps(to_plain(selected_pilot_analysis), indent=2))
        return 0
    if args.command == "selected-pilot-report":
        print(PilotAnalysisManager(config).report(args.benchmark_id), end="")
        return 0
    if args.command == "selected-pilot-power-plan":
        selected_pilot_power_plan = PilotPowerManager(config).create_plan(args.benchmark_id)
        print(render_pilot_power_plan(selected_pilot_power_plan), end="")
        return 0
    if args.command == "selected-pilot-power-check":
        power_manager = PilotPowerManager(config)
        if args.dataset_id:
            selected_pilot_power_assessment = power_manager.check_dataset(args.dataset_id)
        else:
            selected_pilot_power_assessment = power_manager.check_benchmark(args.benchmark_id)
        print(render_pilot_power_assessment(selected_pilot_power_assessment), end="")
        return 0 if not selected_pilot_power_assessment.blockers else 1
    if args.command == "selected-main-power-plan":
        selected_main_power_plan = MainPowerManager(config).create_plan(args.benchmark_id)
        print(render_main_power_plan(selected_main_power_plan), end="")
        return 0
    if args.command == "selected-main-alpha-decision":
        main_power_manager = MainPowerManager(config)
        main_power_manager.decide_alpha(args.benchmark_id, alpha_level=args.alpha)
        main_power_plan = main_power_manager.load_plan(args.benchmark_id)
        main_power_decisions = main_power_manager.load_decisions(args.benchmark_id)
        print(render_main_power_report(main_power_plan, main_power_decisions), end="")
        return 0
    if args.command == "selected-main-power-report":
        print(MainPowerManager(config).report(args.benchmark_id), end="")
        return 0
    if args.command == "selected-benchmark-codex-task":
        selected_benchmark_codex_task = SelectedBenchmarkCodexTaskManager(config).create_task(args.benchmark_id, args.type)
        print(json.dumps(to_plain(selected_benchmark_codex_task), indent=2))
        return 0
    if args.command == "selected-benchmark-codex-handoff":
        print(SelectedBenchmarkCodexTaskManager(config).handoff(args.task_id), end="")
        return 0
    if args.command == "selected-benchmark-codex-import":
        selected_benchmark_codex_import = SelectedBenchmarkCodexTaskManager(config).import_outputs(args.task_id)
        print(json.dumps(to_plain(selected_benchmark_codex_import), indent=2))
        return 0
    if args.command == "selected-benchmark-review":
        selected_benchmark_review = SelectedBenchmarkReviewerPanelBuilder(config).review(args.benchmark_id)
        print(json.dumps(to_plain(selected_benchmark_review), indent=2))
        return 0
    if args.command == "selected-benchmark-fix-list":
        print(SelectedBenchmarkReviewerPanelBuilder(config).fix_list(args.benchmark_id), end="")
        return 0
    if args.command == "selected-publication-review":
        publication_review = SelectedBenchmarkReviewerPanelBuilder(config).publication_review(
            args.benchmark_id,
            after_related_work=args.after_related_work,
        )
        print(render_publication_readiness_review(publication_review), end="")
        return 0 if publication_review.readiness in {"publication_candidate", "workshop_candidate"} else 1
    if args.command == "selected-publication-fix-list":
        print(
            SelectedBenchmarkReviewerPanelBuilder(config).publication_fix_list(
                args.benchmark_id,
                after_related_work=args.after_related_work,
            ),
            end="",
        )
        return 0
    if args.command == "selected-pilot-review":
        from gapforge.selected_benchmark.reviewer import render_pilot_review_panel

        selected_pilot_review = SelectedBenchmarkReviewerPanelBuilder(config).pilot_review(args.benchmark_id)
        print(render_pilot_review_panel(selected_pilot_review), end="")
        return 0
    if args.command == "selected-pilot-fix-list":
        print(SelectedBenchmarkReviewerPanelBuilder(config).pilot_fix_list(args.benchmark_id), end="")
        return 0
    if args.command == "selected-pilot-manuscript":
        selected_pilot_manuscript = SelectedPilotManuscriptManager(config).generate(args.benchmark_id)
        print(json.dumps(to_plain(selected_pilot_manuscript), indent=2))
        return 0
    if args.command == "selected-pilot-paper-package":
        selected_pilot_paper_package = SelectedPilotManuscriptManager(config).paper_package(args.benchmark_id)
        print(json.dumps(to_plain(selected_pilot_paper_package), indent=2))
        return 0
    if args.command == "selected-main-manuscript":
        selected_main_manuscript = SelectedMainManuscriptManager(config).generate(args.benchmark_id)
        print(json.dumps(to_plain(selected_main_manuscript), indent=2))
        return 0
    if args.command == "selected-main-paper-package":
        selected_main_paper_package = SelectedMainManuscriptManager(config).paper_package(args.benchmark_id)
        print(json.dumps(to_plain(selected_main_paper_package), indent=2))
        return 0
    if args.command == "selected-manuscript-related-work-revise":
        related_work_revision = SelectedBenchmarkRelatedWorkManuscriptManager(config).revise_related_work(args.benchmark_id)
        print(render_selected_related_work_manuscript_revision(related_work_revision), end="")
        return 0 if not related_work_revision.missing_categories else 1
    if args.command == "selected-manuscript-positioning-update":
        positioning_revision = SelectedBenchmarkRelatedWorkManuscriptManager(config).update_positioning(args.benchmark_id)
        print(render_selected_related_work_manuscript_revision(positioning_revision), end="")
        return 0
    if args.command == "selected-paper-package-v24":
        package_v24 = SelectedBenchmarkRelatedWorkManuscriptManager(config).paper_package_v24(args.benchmark_id)
        print(render_selected_paper_package_v24(package_v24), end="")
        return 0 if package_v24.publication_readiness in {"publication_candidate", "workshop_candidate"} else 1
    if args.command == "selected-benchmark-manuscript":
        selected_benchmark_manuscript = SelectedBenchmarkManuscriptManager(config).generate(args.benchmark_id)
        print(json.dumps(to_plain(selected_benchmark_manuscript), indent=2))
        return 0
    if args.command == "selected-benchmark-paper-package":
        selected_benchmark_paper_package = SelectedBenchmarkManuscriptManager(config).paper_package(args.benchmark_id)
        print(json.dumps(to_plain(selected_benchmark_paper_package), indent=2))
        return 0
    if args.command == "idea-discovery-report":
        idea_store = IdeaStore(config)
        idea_state = idea_store.load_state(args.project_id)
        portfolios = TopicPortfolioGenerator(config).list_project_portfolios(args.project_id)
        metrics = IdeaYieldMetricCalculator(config).compute(args.project_id)
        try:
            release_gate = V2ReleaseGateEnforcer(config).evaluate()
        except (FileNotFoundError, json.JSONDecodeError, TypeError, ValueError):
            release_gate = None
        discovery_report = render_idea_discovery_report(idea_state, portfolios=portfolios, metrics=metrics, release_gate=release_gate)
        program = ProjectMemoryManager(config).load_project(args.project_id)
        report_path = Path(program.project.root_dir) / "ideas" / "reports" / "idea_discovery_report.md"
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(discovery_report, encoding="utf-8")
        print(discovery_report, end="")
        return 0
    if args.command == "research-agenda":
        agenda = ResearchAgendaManager(config).generate(args.project_id)
        print(json.dumps(to_plain(agenda), indent=2))
        return 0
    if args.command == "agenda-report":
        print(ResearchAgendaManager(config).write_report(args.agenda_id), end="")
        return 0
    if args.command == "agenda-to-campaigns":
        campaigns = ResearchAgendaManager(config).agenda_to_campaigns(args.agenda_id)
        print(json.dumps(to_plain(campaigns), indent=2))
        return 0
    if args.command == "compute-status":
        environments = detect_compute_environments()
        if args.json:
            print(json.dumps(to_plain(environments), indent=2))
        else:
            print(render_compute_status(environments), end="")
        return 0
    if args.command == "compute-check":
        print(render_compute_check(check_environment(args.environment)), end="")
        return 0
    if args.command == "experiment-workspace-create":
        workspace = ExperimentWorkspaceManager(config).create_workspace(
            project_id=args.project_id,
            direction_id=args.direction_id,
            campaign_id=args.campaign_id,
            experiment_protocol_id=args.experiment_protocol_id,
        )
        print(json.dumps(to_plain(workspace), indent=2))
        return 0
    if args.command == "experiment-workspace-status":
        print(ExperimentWorkspaceManager(config).workspace_status_markdown(args.workspace_id), end="")
        return 0
    if args.command == "experiment-manifest-create":
        experiment_manifest = ExperimentWorkspaceManager(config).create_manifest(
            workspace_id=args.workspace_id,
            run_type=args.run_type,
            run_name=args.run_name,
            dataset_ids=args.dataset_ids or None,
            baseline_ids=args.baseline_ids or None,
            metric_ids=args.metric_ids or None,
            command=args.run_command,
            expected_outputs=args.expected_outputs or None,
            random_seed=args.random_seed,
            resource_request=ResourceRequest(
                cpu_count=args.resource_cpus,
                memory_gb=args.resource_memory_gb,
                gpu_count=args.resource_gpus,
                wall_time_minutes=args.resource_wall_time_minutes,
                disk_gb=args.resource_disk_gb,
                environment_type="gpu_local" if args.resource_environment == "gpu" else args.resource_environment,
            ),
        )
        print(json.dumps(to_plain(experiment_manifest), indent=2))
        return 0
    if args.command == "experiment-runs":
        execution_records = ExperimentWorkspaceManager(config).list_execution_records(args.workspace_id)
        print(json.dumps(to_plain(execution_records), indent=2))
        return 0
    if args.command == "experiment-run":
        run_result = ExperimentRunner(config).run(
            workspace_id=args.workspace_id,
            manifest_id=args.manifest_id or "",
            run_type=args.run_type or "",
            timeout_seconds=args.timeout_seconds,
            dry_run=args.dry_run,
        )
        print(render_run_result(run_result), end="")
        return 0 if run_result.execution.status in {"complete", "skipped"} else 1
    if args.command == "experiment-run-status":
        print(ExperimentRunner(config).render_execution_status(args.execution_id), end="")
        return 0
    if args.command == "experiment-rerun":
        run_result = ExperimentRunner(config).rerun(
            args.execution_id,
            timeout_seconds=args.timeout_seconds,
            dry_run=args.dry_run,
        )
        print(render_run_result(run_result), end="")
        return 0 if run_result.execution.status in {"complete", "skipped"} else 1
    if args.command == "job-submit":
        job = JobScheduler(config).submit(workspace_id=args.workspace_id, manifest_id=args.manifest_id)
        print(json.dumps(to_plain(job), indent=2))
        return 0
    if args.command == "job-status":
        print(render_job(JobScheduler(config).get_job(args.job_id)), end="")
        return 0
    if args.command == "job-list":
        job_queue = JobScheduler(config).load_queue(f"queue-{args.workspace_id}")
        print(render_job_queue(job_queue), end="")
        return 0
    if args.command == "job-cancel":
        print(render_job(JobScheduler(config).cancel(args.job_id)), end="")
        return 0
    if args.command == "job-run-next":
        job_result = JobScheduler(config).run_next(args.queue_id)
        print(render_job_runner_result(job_result), end="")
        return 0 if job_result.status == "complete" else 1
    if args.command == "sweep-create":
        sweep = ExperimentSweepManager(config).create_parameter_sweep(
            workspace_id=args.workspace_id,
            base_manifest_id=args.manifest_id,
            name=args.name,
            parameters=parse_parameter_specs(args.params),
            confirm_large=args.confirm_large,
        )
        print(json.dumps(to_plain(sweep), indent=2))
        return 0
    if args.command == "ablation-create":
        ablation_plan = ExperimentSweepManager(config).create_ablation_plan(
            workspace_id=args.workspace_id,
            base_manifest_id=args.manifest_id,
            name=args.name,
            factors=args.factors,
            controls=args.controls,
            expected_comparisons=args.comparisons,
        )
        print(render_ablation_plan_markdown(ablation_plan), end="")
        return 0
    if args.command == "seed-plan-create":
        seed_plan = ExperimentSweepManager(config).create_seed_plan(
            workspace_id=args.workspace_id,
            base_manifest_id=args.manifest_id,
            seeds=parse_seed_list(args.seeds),
            rationale=args.rationale,
        )
        print(json.dumps(to_plain(seed_plan), indent=2))
        return 0
    if args.command == "sweep-submit":
        sweep_queue = ExperimentSweepManager(config).submit_sweep(args.sweep_id)
        print(render_job_queue(sweep_queue), end="")
        return 0
    if args.command == "sweep-status":
        print(render_sweep_status(ExperimentSweepManager(config).sweep_status(args.sweep_id)), end="")
        return 0
    if args.command == "parse-results":
        parsed_result_summary = ResultParser(config).parse_execution(args.execution_id)
        print(render_result_summary_markdown(parsed_result_summary), end="")
        return 0
    if args.command == "result-summary":
        parsed_result_summary = ResultParser(config).load_or_parse_summary(args.execution_id)
        print(render_result_summary_markdown(parsed_result_summary), end="")
        return 0
    if args.command == "empirical-claims":
        print(ResultParser(config).render_empirical_claims(args.workspace_id), end="")
        return 0
    if args.command == "results-db-build":
        result_table = ResultDatabaseBuilder(config).build(args.workspace_id)
        print(render_result_table_markdown(result_table), end="")
        return 0
    if args.command == "results-table":
        result_table = ResultDatabaseBuilder(config).load_or_build(args.workspace_id)
        print(render_result_table_markdown(result_table), end="")
        return 0
    if args.command == "results-aggregate":
        aggregate_results = ResultAggregator(config).aggregate(args.workspace_id, include_smoke=args.include_smoke)
        print(render_aggregate_results_markdown(aggregate_results), end="")
        return 0
    if args.command == "results-export-csv":
        csv_path = ResultDatabaseBuilder(config).export_csv(args.workspace_id)
        print(f"Wrote result CSV: {csv_path}\n", end="")
        return 0
    if args.command == "error-analysis":
        error_report = ErrorAnalysisBuilder(config).analyze_execution(args.execution_id)
        print(render_error_analysis_report(error_report), end="")
        return 0
    if args.command == "slice-analysis":
        error_slice = SliceAnalysisBuilder(config).analyze_slice(args.execution_id, args.slice)
        print(render_error_slice_markdown(error_slice), end="")
        return 0
    if args.command == "error-report":
        print(ErrorAnalysisBuilder(config).render_workspace_report(args.workspace_id), end="")
        return 0
    if args.command == "analyze-results":
        statistics_analyzer = ResultStatisticsAnalyzer(config)
        if args.execution_id:
            statistical_analysis_report = statistics_analyzer.analyze_execution(args.execution_id)
        else:
            statistical_analysis_report = statistics_analyzer.analyze_workspace(args.workspace_id)
        print(render_analysis_report_markdown(statistical_analysis_report), end="")
        return 0
    if args.command == "low-fpr-power-check":
        low_fpr_report = ResultStatisticsAnalyzer(config).low_fpr_power_check(args.workspace_id)
        print(render_analysis_report_markdown(low_fpr_report), end="")
        return 0
    if args.command == "low-fpr-plan":
        low_fpr_plan_result = plan_low_fpr(target_fpr=args.target_fpr, ci_width=args.ci_width, confidence=args.confidence)
        print(render_low_fpr_plan_markdown(low_fpr_plan_result), end="")
        return 0
    if args.command == "low-fpr-check":
        checker = LowFPRPowerChecker(config)
        if args.execution_id:
            check = checker.check_execution(
                args.execution_id,
                target_fpr=args.target_fpr,
                ci_width=args.ci_width,
                confidence=args.confidence,
            )
        else:
            check = checker.check_workspace(
                args.workspace_id,
                target_fpr=args.target_fpr,
                ci_width=args.ci_width,
                confidence=args.confidence,
            )
        print(render_low_fpr_check_markdown(check), end="")
        return 0 if check.status in {"pass", "warning"} else 1
    if args.command == "reproducibility-check":
        reproducibility_checker = ReproducibilityChecker(config)
        if args.execution_id:
            reproducibility_result = reproducibility_checker.check_execution(args.execution_id)
        else:
            reproducibility_result = reproducibility_checker.check_workspace(args.workspace_id)
        print(render_reproducibility_check_markdown(reproducibility_result), end="")
        return 0 if reproducibility_result.status in {"pass", "warning"} else 1
    if args.command == "empirical-review":
        empirical_review_builder = EmpiricalReviewBuilder(config)
        if args.execution_id:
            empirical_review_panel = empirical_review_builder.review_execution(args.execution_id)
        else:
            empirical_review_panel = empirical_review_builder.review_workspace(args.workspace_id)
        print(render_empirical_review_markdown(empirical_review_panel), end="")
        return 0
    if args.command == "export-replication-package":
        replication_exporter = ReplicationPackageExporter(config)
        replication_package = replication_exporter.export_workspace(args.workspace_id)
        manifest = json.loads(Path(replication_package.manifest_path).read_text(encoding="utf-8"))
        print(render_replication_package_markdown(replication_package, from_dict(ReplicationManifest, manifest)), end="")
        return 0
    if args.command == "verify-replication-package":
        verification = ReplicationPackageVerifier(config).verify(args.package_path)
        print(render_replication_verification_markdown(verification), end="")
        return 0 if verification.status in {"pass", "warning"} else 1
    if args.command == "replication-status":
        print(render_replication_status(config, args.workspace_id), end="")
        return 0
    if args.command == "reproduce":
        reproduction = ReproductionRunner(config).reproduce(args.package_path, dry_run=args.dry_run)
        print(render_reproduction_record_markdown(reproduction), end="")
        return 0 if reproduction.status in {"pass", "warning", "planned"} else 1
    if args.command == "reproduce-status":
        reproduction = ReproductionRunner(config).load_record(args.reproduction_id)
        print(render_reproduction_record_markdown(reproduction), end="")
        return 0 if reproduction.status in {"pass", "warning", "planned"} else 1
    if args.command == "reproducibility-matrix":
        matrix_builder = ReproducibilityMatrixBuilder(config)
        if args.workspace_id:
            reproducibility_matrix = matrix_builder.for_workspace(args.workspace_id)
        else:
            reproducibility_matrix = matrix_builder.for_package_id(args.package_id)
        print(render_reproducibility_matrix_markdown(reproducibility_matrix), end="")
        return 0
    if args.command == "dataset-register":
        dataset_record = DatasetRegistry(config).register_dataset(
            workspace_id=args.workspace_id,
            name=args.name,
            path=args.path,
            dataset_type=args.dataset_type,
            description=args.description,
            source=args.source,
            source_url=args.source_url,
            version=args.version,
            license=args.license,
            intended_use=args.intended_use,
        )
        print(json.dumps(to_plain(dataset_record), indent=2))
        return 0
    if args.command == "dataset-card":
        print(DatasetRegistry(config).render_card(args.dataset_id), end="")
        return 0
    if args.command == "dataset-validate":
        dataset_validation = DatasetRegistry(config).validate_dataset(args.dataset_id)
        print(render_dataset_validation_markdown(dataset_validation), end="")
        return 0
    if args.command == "dataset-list":
        dataset_records = DatasetRegistry(config).list_datasets(args.workspace_id)
        print(render_dataset_registry_markdown(dataset_records), end="")
        return 0
    if args.command == "dataset-download-plan":
        plan = DatasetDownloadManager(config).build_plan(args.dataset_id)
        print(render_dataset_download_plan(plan), end="")
        return 0
    if args.command == "dataset-download":
        download_record = DatasetDownloadManager(config).download(args.dataset_id, accept_license=args.accept_license)
        print(render_dataset_download_record(download_record), end="")
        return 0 if download_record.status == "downloaded" else 1
    if args.command == "dataset-cache-info":
        print(render_dataset_cache_info(dataset_cache_info(config)), end="")
        return 0
    if args.command == "dataset-cache-clean":
        print(render_dataset_cache_info(clean_dataset_cache(config)), end="")
        return 0
    if args.command == "dataset-consent":
        consent_record = DatasetConsentManager(config).accept(dataset_id=args.dataset_id, user=args.user, consent_text=args.text)
        print(render_dataset_consent_markdown(consent_record), end="")
        return 0
    if args.command == "baseline-register":
        baseline_record = BaselineRegistry(config).register_baseline(
            workspace_id=args.workspace_id,
            name=args.name,
            description=args.description,
            baseline_type=args.baseline_type,
            source_paper_ids=args.source_paper_ids,
            code_url=args.code_url,
            implementation_path=args.implementation_path,
            required_for_submission=args.required_for_submission,
            risk_if_missing=args.risk_if_missing,
        )
        print(json.dumps(to_plain(baseline_record), indent=2))
        return 0
    if args.command == "baseline-from-related-work":
        baseline_records = BaselineRegistry(config).from_related_work(project_id=args.project_id, direction_id=args.direction_id)
        print(json.dumps(to_plain(baseline_records), indent=2))
        return 0
    if args.command == "baseline-list":
        baseline_records = BaselineRegistry(config).list_baselines(args.workspace_id)
        print(render_baseline_registry_markdown(baseline_records), end="")
        return 0
    if args.command == "baseline-card":
        print(BaselineRegistry(config).render_card(args.baseline_id), end="")
        return 0
    if args.command == "metric-register":
        metric_record = MetricRegistry(config).register_metric(
            workspace_id=args.workspace_id,
            name=args.name,
            description=args.description,
            metric_type=args.metric_type,
            formula=args.formula,
            higher_is_better=not args.lower_is_better,
            required_inputs=args.required_inputs,
            edge_cases=args.edge_cases,
        )
        print(json.dumps(to_plain(metric_record), indent=2))
        return 0
    if args.command == "metric-list":
        metric_records = MetricRegistry(config).list_metrics(args.workspace_id)
        print(render_metric_registry_markdown(metric_records), end="")
        return 0
    if args.command == "benchmark-canary-list":
        print(render_benchmark_canary_profiles(BenchmarkCanaryRunner(config).list_profiles()), end="")
        return 0
    if args.command == "benchmark-canary-run":
        benchmark_canary_record = BenchmarkCanaryRunner(config).run(
            args.profile,
            real=args.real,
            download_consent=args.accept_download,
        )
        print(render_benchmark_canary_record(benchmark_canary_record), end="")
        return 0 if benchmark_canary_record.status in {"passed", "warning", "refused"} else 1
    if args.command == "benchmark-register":
        benchmark_record = BenchmarkRegistry(config).register_benchmark(
            workspace_id=args.workspace_id,
            name=args.name,
            description=args.description,
            domain=args.domain,
            task_type=args.task_type,
            source_url=args.source_url,
            dataset_ids=args.dataset_ids,
            baseline_ids=args.baseline_ids,
            metric_ids=args.metric_ids,
            license=args.license,
            expected_splits=args.expected_splits,
            evaluation_protocol=args.evaluation_protocol,
            leaderboard_url=args.leaderboard_url,
            paper_ids=args.paper_ids,
            limitations=args.limitations,
            safety_notes=args.safety_notes,
        )
        print(json.dumps(to_plain(benchmark_record), indent=2))
        return 0
    if args.command == "benchmark-card":
        print(BenchmarkRegistry(config).render_card(args.benchmark_id), end="")
        return 0
    if args.command == "benchmark-list":
        benchmark_records = BenchmarkRegistry(config).list_benchmarks(args.workspace_id)
        print(render_benchmark_registry_markdown(benchmark_records), end="")
        return 0
    if args.command == "benchmark-suite-create":
        suite = BenchmarkRegistry(config).create_suite(
            project_id=args.project_id,
            name=args.name,
            description=args.description,
            benchmark_ids=args.benchmark_ids,
            required_tasks=args.required_tasks,
            optional_tasks=args.optional_tasks,
            source_profile=args.source_profile,
        )
        print(json.dumps(to_plain(suite), indent=2))
        return 0
    if args.command == "benchmark-suite-status":
        print(BenchmarkRegistry(config).suite_status(args.suite_id), end="")
        return 0
    if args.command == "benchmark-compare":
        comparison = BenchmarkComparisonBuilder(config).compare(workspace_id=args.workspace_id, benchmark_id=args.benchmark_id)
        print(render_benchmark_comparison(comparison), end="")
        return 0
    if args.command == "leaderboard-report":
        leaderboard = LeaderboardBuilder(config).build(args.benchmark_id)
        print(render_leaderboard_report(leaderboard), end="")
        return 0
    if args.command == "benchmark-comparison-report":
        print(BenchmarkComparisonBuilder(config).render_workspace_report(args.workspace_id), end="")
        return 0
    if args.command == "vetted-benchmark-register":
        vetted_record = VettedBenchmarkRegistry(config).register(
            name=args.name,
            domain=args.domain,
            source=args.source,
            source_url=args.source_url,
            benchmark_type=args.benchmark_type,
            task_types=args.task_types,
            dataset_ids=args.dataset_ids,
            metric_ids=args.metric_ids,
            baseline_ids=args.baseline_ids,
            paper_ids=args.paper_ids,
            leaderboard_url=args.leaderboard_url,
            license=args.license,
            terms_of_use=args.terms_of_use,
            download_required=args.download_required,
            authentication_required=args.authentication_required,
            size_estimate=args.size_estimate,
            citation=args.citation,
            vetted_status=args.vetted_status,
            limitations=args.limitations,
        )
        print(json.dumps(to_plain(vetted_record), indent=2))
        return 0
    if args.command == "vetted-benchmark-list":
        print(VettedBenchmarkRegistry(config).render_list(), end="")
        return 0
    if args.command == "vetted-benchmark-card":
        print(VettedBenchmarkRegistry(config).render_card(args.benchmark_id), end="")
        return 0
    if args.command == "vetted-benchmark-eligibility":
        eligibility_assessment = VettedBenchmarkRegistry(config).assess_eligibility(
            benchmark_id=args.benchmark_id,
            selected_idea_id=args.idea_id,
        )
        print(render_eligibility_assessment(eligibility_assessment), end="")
        return 0
    if args.command == "vetted-benchmark-report":
        print(VettedBenchmarkRegistry(config).render_project_report(args.project_id), end="")
        return 0
    if args.command == "stats-plan":
        metric_registry = MetricRegistry(config)
        stats_plan = metric_registry.create_stats_plan(
            workspace_id=args.workspace_id or "",
            experiment_id=args.experiment_id or "",
        )
        metric_records = metric_registry.list_metrics(args.workspace_id) if args.workspace_id else []
        print(render_statistical_plan_markdown(stats_plan, metric_records), end="")
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
    if args.command == "scaffold-experiment-code":
        code_root = ExperimentCodeScaffolderV2(config).scaffold(args.workspace_id)
        print(code_root)
        return 0
    if args.command == "experiment-code-status":
        print(ExperimentCodeScaffolderV2(config).status(args.workspace_id), end="")
        return 0
    if args.command == "experiment-code-validate":
        code_validation = ExperimentCodeScaffolderV2(config).validate(args.workspace_id, run_smoke=not args.no_smoke)
        print(render_experiment_code_validation(code_validation), end="")
        return 0 if code_validation.status in {"valid", "warning"} else 1
    if args.command == "experiment-code-task":
        code_task = ExperimentCodeTaskManager(config).create_task(workspace_id=args.workspace_id, task_type=args.type)
        print(json.dumps(to_plain(code_task), indent=2))
        return 0
    if args.command == "experiment-code-handoff":
        path = ExperimentCodeTaskManager(config).write_handoff(args.task_id)
        print(path)
        return 0
    if args.command == "experiment-code-import":
        import_result = ExperimentCodeTaskManager(config).import_outputs(args.task_id)
        print(render_import_result(import_result), end="")
        return 0 if import_result.status in {"applied", "partial"} else 1
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
    if args.command == "review-dataset-create":
        review_dataset = ReviewDatasetBuilder(config).create(args.name)
        print(json.dumps(to_plain(review_dataset), indent=2))
        return 0
    if args.command == "review-dataset-ingest":
        if args.source != "openreview":
            print("review-dataset-ingest currently supports --source openreview only", file=sys.stderr)
            return 2
        review_dataset = ReviewDatasetBuilder(config).ingest_openreview(venue=args.venue, year=args.year)
        print(json.dumps(to_plain(review_dataset), indent=2))
        return 0
    if args.command == "review-dataset-ingest-fixture":
        review_dataset = ReviewDatasetBuilder(config).ingest_fixture()
        print(json.dumps(to_plain(review_dataset), indent=2))
        return 0
    if args.command == "review-dataset-report":
        print(ReviewDatasetBuilder(config).render_report(args.dataset_id), end="")
        return 0
    if args.command == "review-labels-generate":
        labels = ReviewTaxonomyLabeler(config).generate(args.dataset_id)
        print(render_review_labels(labels), end="")
        return 0
    if args.command == "review-taxonomy-report":
        print(ReviewTaxonomyLabeler(config).render_report(args.dataset_id), end="")
        return 0
    if args.command == "reviewer-train":
        training_run = ReviewerTrainingManager(config).train(args.dataset_id, mode=args.mode)
        print(reviewer_training_json(training_run), end="")
        return 0 if training_run.status in {"complete", "planned", "skipped"} else 1
    if args.command == "reviewer-evaluate":
        evaluation = ReviewerEvaluationManager(config).evaluate(args.dataset_id)
        print(reviewer_evaluation_json(evaluation), end="")
        return 0
    if args.command == "reviewer-calibration-report":
        print(ReviewerEvaluationManager(config).render_report(args.dataset_id), end="")
        return 0
    if args.command == "rebuttal-plan":
        if args.manuscript_id:
            rebuttal_manager = ManuscriptRebuttalManager(config)
            revision = rebuttal_manager.build(args.manuscript_id)
            print(rebuttal_manager.render_markdown(revision), end="")
            return 0
        if not args.project_id or not args.direction_id:
            print("rebuttal-plan requires --manuscript-id or both --project-id and --direction-id", file=sys.stderr)
            return 2
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
    if args.command == "export-paper-package-v2":
        exporter = PaperPackageExporter(config)
        if args.workspace_id:
            package = exporter.export_workspace_v2(args.workspace_id)
        else:
            package = exporter.export_direction_v2(args.direction_id)
        print(
            f"Exported v0.6 paper package {package.id} with {len(package.files)} files "
            f"(readiness={package.readiness}, missing={len(package.missing_requirements)})."
        )
        return 0
    if args.command == "manuscript-create":
        manuscript_state = ManuscriptManager(config).create_manuscript(
            project_id=args.project_id,
            direction_id=args.direction_id,
            workspace_id=args.workspace_id,
            title=args.title,
            campaign_id=args.campaign_id,
            short_title=args.short_title,
            target_venue=args.target_venue,
        )
        print(json.dumps(to_plain(manuscript_state), indent=2))
        return 0
    if args.command == "manuscript-status":
        print(ManuscriptManager(config).status_markdown(args.manuscript_id), end="")
        return 0
    if args.command == "manuscript-sections":
        print(ManuscriptManager(config).sections_json(args.manuscript_id), end="")
        return 0
    if args.command == "manuscript-report":
        print(ManuscriptManager(config).write_report(args.manuscript_id), end="")
        return 0
    if args.command == "bibliography-build":
        bibliography = ManuscriptBibliographyManager(config).build(args.manuscript_id)
        print(json.dumps(to_plain(bibliography), indent=2))
        return 0
    if args.command == "bibliography-export":
        print(ManuscriptBibliographyManager(config).export(args.manuscript_id, export_format=args.format), end="")
        return 0
    if args.command == "citation-check":
        print(ManuscriptBibliographyManager(config).check_markdown(args.manuscript_id), end="")
        return 0
    if args.command == "citation-list":
        print(ManuscriptBibliographyManager(config).citation_list_json(args.manuscript_id), end="")
        return 0
    if args.command == "manuscript-traceability":
        auditor = ManuscriptTraceabilityAuditor(config)
        traceability_report = auditor.audit(args.manuscript_id)
        print(auditor.render_markdown(traceability_report), end="")
        return 0
    if args.command == "manuscript-overclaims":
        print(ManuscriptTraceabilityAuditor(config).overclaims_json(args.manuscript_id), end="")
        return 0
    if args.command == "manuscript-soften-claims":
        print(ManuscriptTraceabilityAuditor(config).soften_claims(args.manuscript_id, dry_run=args.dry_run), end="")
        return 0
    if args.command == "manuscript-table":
        table = ManuscriptTableGenerator(config).generate(args.manuscript_id, args.type)
        print(json.dumps(to_plain(table), indent=2))
        return 0
    if args.command == "manuscript-figure":
        figure = ManuscriptFigureGenerator(config).generate(args.manuscript_id, args.type)
        print(json.dumps(to_plain(figure), indent=2))
        return 0
    if args.command == "manuscript-assets":
        figures = ManuscriptFigureGenerator(config).list_figures(args.manuscript_id)
        tables = ManuscriptTableGenerator(config).list_tables(args.manuscript_id)
        print(json.dumps({"figures": to_plain(figures), "tables": to_plain(tables)}, indent=2))
        return 0
    if args.command == "venue-list":
        print(venue_templates_json(), end="")
        return 0
    if args.command == "venue-profile-list":
        print(render_venue_profile_list(list_venue_profiles()), end="")
        return 0
    if args.command == "venue-profile":
        print(render_venue_profile(get_venue_profile(args.venue)), end="")
        return 0
    if args.command == "manuscript-set-venue":
        manuscript_state = ManuscriptVenueManager(config).set_venue(args.manuscript_id, args.venue)
        print(json.dumps(to_plain(manuscript_state.manuscript), indent=2))
        return 0
    if args.command == "manuscript-set-venue-profile":
        manuscript_state = VenueProfileManager(config).set_profile(args.manuscript_id, args.venue)
        print(json.dumps(to_plain(manuscript_state.manuscript), indent=2))
        return 0
    if args.command == "style-corpus-add-tex":
        ingest_record = StyleCorpusManager(config).add_tex(args.path, args.venue)
        print(json.dumps(to_plain(ingest_record), indent=2))
        return 0 if ingest_record.status != "rejected" else 1
    if args.command == "style-corpus-ingest":
        ingest_record = StyleCorpusManager(config).ingest_source(args.source, dry_run=args.dry_run)
        print(json.dumps(to_plain(ingest_record), indent=2))
        return 0 if ingest_record.status != "rejected" else 1
    if args.command == "style-corpus-report":
        print(StyleCorpusManager(config).render_report(), end="")
        return 0
    if args.command == "venue-style-analyze":
        style_profile = VenueStyleAnalyzer(config).analyze(args.venue)
        print(json.dumps(to_plain(style_profile), indent=2))
        return 0
    if args.command == "venue-style-recommend":
        print(VenueStyleAnalyzer(config).render_recommendations(args.manuscript_id), end="")
        return 0
    if args.command == "venue-style-report":
        print(VenueStyleAnalyzer(config).render_report(args.venue), end="")
        return 0
    if args.command == "manuscript-rewrite-for-venue":
        rewrite_result = VenueManuscriptRewriter(config).rewrite(args.manuscript_id, args.venue)
        print(rewrite_result_json(rewrite_result), end="")
        return 0
    if args.command == "manuscript-style-report":
        print(VenueManuscriptRewriter(config).render_style_report(args.manuscript_id), end="")
        return 0
    if args.command == "submission-checklist":
        checklist_manager = SubmissionChecklistManager(config)
        submission_checklist = checklist_manager.build(args.manuscript_id)
        print(checklist_manager.render_markdown(submission_checklist), end="")
        return 0
    if args.command == "anonymize-manuscript":
        anonymizer = ManuscriptAnonymizer(config)
        anonymization_report = anonymizer.anonymize(args.manuscript_id)
        print(anonymizer.render_markdown(anonymization_report), end="")
        return 0
    if args.command == "anonymization-check":
        anonymizer = ManuscriptAnonymizer(config)
        anonymization_report = anonymizer.check(args.manuscript_id)
        print(anonymizer.render_markdown(anonymization_report), end="")
        return 0
    if args.command == "deanonymize-package":
        anonymizer = ManuscriptAnonymizer(config)
        anonymization_report = anonymizer.deanonymize_package(args.manuscript_id)
        print(anonymizer.render_markdown(anonymization_report), end="")
        return 0
    if args.command == "artifact-eval-package":
        artifact_package = ArtifactEvaluationPackageExporter(config).export(args.manuscript_id)
        print(json.dumps(to_plain(artifact_package), indent=2))
        return 0
    if args.command == "artifact-eval-check":
        artifact_checklist_manager = ArtifactEvaluationChecklistManager(config)
        artifact_checklist = artifact_checklist_manager.check(args.package_id)
        print(artifact_checklist_manager.render_markdown(artifact_checklist), end="")
        return 0
    if args.command == "artifact-badges":
        badge_assessor = ArtifactBadgeAssessor(config)
        badge_assessments = badge_assessor.assess(args.package_id)
        print(badge_assessor.render_markdown(badge_assessments), end="")
        return 0
    if args.command == "artifact-eval-smoke":
        smoke_runner = ArtifactEvaluationSmokeRunner(config)
        smoke_record = smoke_runner.dry_run(args.package_id)
        print(smoke_runner.render_markdown(smoke_record), end="")
        return 0
    if args.command == "manuscript-review":
        reviewer_builder = ManuscriptReviewPanelBuilder(config)
        manuscript_panel = reviewer_builder.review(args.manuscript_id)
        print(render_manuscript_review_panel_markdown(manuscript_panel), end="")
        return 0
    if args.command == "manuscript-meta-review":
        print(ManuscriptReviewPanelBuilder(config).meta_review(args.manuscript_id), end="")
        return 0
    if args.command == "manuscript-fix-list":
        print(ManuscriptReviewPanelBuilder(config).fix_list(args.manuscript_id), end="")
        return 0
    if args.command == "drastic-review":
        drastic_builder = DrasticReviewPanelBuilder(config)
        if args.manuscript_id:
            drastic_panel = drastic_builder.review_manuscript(args.manuscript_id)
        else:
            drastic_panel = drastic_builder.review_benchmark(args.benchmark_id)
        print(render_drastic_review_panel(drastic_panel), end="")
        return 0
    if args.command == "drastic-review-report":
        print(DrasticReviewPanelBuilder(config).render_manuscript_report(args.manuscript_id), end="")
        return 0
    if args.command == "drastic-review-rerun":
        rerun_result = DrasticReviewPanelBuilder(config).rerun_manuscript(args.manuscript_id)
        print(render_drastic_review_rerun_result(rerun_result), end="")
        return 0 if not rerun_result.remaining_blockers else 1
    if args.command == "drastic-revision-plan":
        drastic_revision_manager = DrasticRevisionManager(config)
        drastic_revision_plan = drastic_revision_manager.build(args.manuscript_id)
        print(render_drastic_revision_plan(drastic_revision_plan), end="")
        return 0
    if args.command == "apply-drastic-revision":
        drastic_revision_manager = DrasticRevisionManager(config)
        drastic_revision_plan = drastic_revision_manager.apply(args.manuscript_id, dry_run=args.dry_run)
        print(render_drastic_revision_plan(drastic_revision_plan), end="")
        return 0
    if args.command == "drastic-revision-status":
        print(DrasticRevisionManager(config).status(args.manuscript_id), end="")
        return 0
    if args.command == "drastic-revision-close":
        drastic_revision_plan = DrasticRevisionManager(config).close_item(args.manuscript_id, args.item_id)
        print(render_drastic_revision_plan(drastic_revision_plan), end="")
        return 0
    if args.command == "drastic-readiness-delta":
        print(DrasticRevisionManager(config).readiness_delta(args.manuscript_id), end="")
        return 0
    if args.command == "revision-plan":
        revision_manager = ManuscriptRevisionManager(config)
        revision = revision_manager.build(args.manuscript_id)
        print(revision_manager.render_markdown(revision), end="")
        return 0
    if args.command == "mark-rebuttal-item":
        rebuttal_item = ManuscriptRebuttalManager(config).mark_item(args.item_id, args.status)
        print(json.dumps(to_plain(rebuttal_item), indent=2))
        return 0
    if args.command == "revision-status":
        print(ManuscriptRevisionManager(config).status(args.manuscript_id), end="")
        return 0
    if args.command == "submission-package":
        submission_package = SubmissionPackageExporter(config).export(args.manuscript_id, args.type)
        print(json.dumps(to_plain(submission_package), indent=2))
        return 0
    if args.command == "submission-package-status":
        print(SubmissionPackageExporter(config).status_markdown(args.package_id), end="")
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
    if args.command == "artifact-hygiene":
        hygiene_auditor = ArtifactHygieneAuditor(config)
        if args.all:
            hygiene_reports = hygiene_auditor.audit_all(write=args.write_report)
        else:
            hygiene_report = hygiene_auditor.audit_project(args.project_id, write=args.write_report)
            hygiene_reports = [hygiene_report]
            if args.write_report:
                hygiene_auditor.write_release_gate_report(hygiene_reports)
        print(render_artifact_hygiene_report(hygiene_reports), end="")
        return 0 if hygiene_reports and all(not item.blockers for item in hygiene_reports) else 1
    if args.command == "verify-gitignore":
        gitignore_result = verify_gitignore_patterns(config)
        print(render_gitignore_verification(gitignore_result), end="")
        return 0 if gitignore_result.passed else 1
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
    _, task_spec = _load_agent_task_with_state(config, task_id)
    return task_spec


def _load_agent_task_with_state(config: GapForgeConfig, task_id: str) -> tuple[ResearchRunState, AgentTaskSpec]:
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
                return state, task_spec
    raise FileNotFoundError(f"No agent task found for {task_id}")


def _attestation_status_for_task(config: GapForgeConfig, task_id: str) -> dict[str, object]:
    try:
        state, task_spec = _load_agent_task_with_state(config, task_id)
    except FileNotFoundError:
        campaign_state, _ = find_campaign_task(config, task_id)
        return to_plain(campaign_task_attestation_status(campaign_state, task_id))
    return to_plain(_run_task_attestation_status(state, task_spec))


def _run_task_attestation_status(state: ResearchRunState, task_spec: AgentTaskSpec):
    validations = [item for item in state.agent_validation_results if item.task_spec_id == task_spec.id]
    records = [item for item in state.agent_run_records if item.task_spec_id == task_spec.id]
    attestations = [item for item in state.agent_actual_run_attestations if item.task_spec_id == task_spec.id]
    return run_attestation_status(
        task_spec,
        validations=validations[-1:] if validations else [],
        run_records=records[-1:] if records else [],
        attestations=attestations[-1:] if attestations else [],
    )


def _attestation_command_exit(status) -> int:  # noqa: ANN001
    hard_blockers = (
        "Fake agent",
        "fake agent",
        "Attestation agent must be codex",
        "Attestation model is missing",
        "Attestation model must be gpt-5.4",
    )
    if any(any(token in blocker for token in hard_blockers) for blocker in status.blockers):
        return 1
    return 0 if status.has_attestation else 1


def _agent_output_paths_for_cli(
    state: ResearchRunState,
    task_spec: AgentTaskSpec,
    user_paths: list[Path],
    *,
    discover_all: bool,
) -> list[Path]:
    if discover_all or user_paths:
        return discover_output_paths_for_task(state, task_spec, user_paths=user_paths)
    return []


def _list_task_outputs_payload(config: GapForgeConfig, task_id: str) -> dict[str, object]:
    try:
        state, task_spec = _load_agent_task_with_state(config, task_id)
    except FileNotFoundError:
        campaign_state, pack_dir = find_campaign_task(config, task_id)
        paths = _discover_campaign_output_paths(pack_dir, expected_campaign_files(task_id))
        return {
            "task_id": task_id,
            "kind": "campaign",
            "campaign_id": campaign_state.campaign.id,
            "task_pack": str(pack_dir),
            "outputs_dir": str(pack_dir / "outputs"),
            "repair_outputs_dir": str(pack_dir / "repair_outputs"),
            "expected_files": expected_campaign_files(task_id),
            "existing_outputs": [str(path) for path in paths],
        }
    paths = discover_output_paths_for_task(state, task_spec)
    pack_dir = Path(state.run_dir) / "agent_tasks" / task_id
    from gapforge.agents.schema_validator import expected_output_files

    return {
        "task_id": task_id,
        "kind": "run",
        "run_id": state.run_id,
        "task_pack": str(pack_dir),
        "outputs_dir": str(pack_dir / "outputs"),
        "repair_outputs_dir": str(pack_dir / "repair_outputs"),
        "expected_files": expected_output_files(task_spec),
        "existing_outputs": [str(path) for path in paths],
    }


def _validate_import_all_task(config: GapForgeConfig, task_id: str) -> dict[str, object]:
    try:
        state, task_spec = _load_agent_task_with_state(config, task_id)
    except FileNotFoundError:
        campaign_state, pack_dir = find_campaign_task(config, task_id)
        paths = _discover_campaign_output_paths(pack_dir, expected_campaign_files(task_id))
        if not paths:
            return _no_outputs_payload(
                task_id,
                expected_campaign_files(task_id),
                handoff_command=f"gapforge codex-handoff --task-id {task_id}",
            )
        record = CampaignOutputImporter(config).import_outputs(campaign_state.campaign.id, task_id, paths)
        return {
            "task_id": task_id,
            "kind": "campaign",
            "campaign_id": campaign_state.campaign.id,
            "status": record.status,
            "validation": to_plain(record),
            "outputs": [str(path) for path in paths],
            "next_commands": _post_import_commands(task_id, campaign_id=campaign_state.campaign.id, invalid=record.status == "rejected"),
        }
    paths = discover_output_paths_for_task(state, task_spec)
    if not paths:
        from gapforge.agents.schema_validator import expected_output_files

        return _no_outputs_payload(
            task_id,
            expected_output_files(task_spec),
            handoff_command=f"gapforge codex-handoff --task-id {task_id}",
        )
    validation = AgentOutputImporter(config).import_outputs(task_spec, paths)
    return {
        "task_id": task_id,
        "kind": "run",
        "run_id": state.run_id,
        "status": "imported" if validation.status in {"valid", "warning"} else "invalid",
        "validation": to_plain(validation),
        "outputs": [str(path) for path in paths],
        "next_commands": _post_import_commands(task_id, run_id=state.run_id, invalid=validation.status == "invalid"),
    }


def _campaign_codex_command_preview(
    config: GapForgeConfig,
    task_id: str,
    *,
    allow_unknown_placeholders: bool = False,
) -> dict[str, object]:
    campaign_state, pack_dir = find_campaign_task(config, task_id)
    write_task_handoff(config, task_id, model=campaign_state.campaign.model or AgentRuntimeConfig.from_env().codex_model)
    runtime = AgentRuntimeConfig.from_env()
    outputs_dir = pack_dir / "outputs"
    outputs_dir.mkdir(parents=True, exist_ok=True)
    validation = validate_codex_command_template(
        runtime.command_template,
        task_pack=pack_dir,
        outputs_dir=outputs_dir,
        task_id=task_id,
        run_id="",
        model=runtime.codex_model,
        allow_unknown_placeholders=allow_unknown_placeholders,
    )
    rendered_command = ""
    if runtime.command_template:
        try:
            rendered_command = render_codex_command_template(
                runtime.command_template,
                task_pack=pack_dir,
                outputs_dir=outputs_dir,
                task_id=task_id,
                run_id="",
                model=runtime.codex_model,
                allow_unknown_placeholders=allow_unknown_placeholders,
            )
        except ValueError as exc:
            rendered_command = str(exc)
    return {
        "task_id": task_id,
        "kind": "campaign",
        "campaign_id": campaign_state.campaign.id,
        "cwd": str(runtime.codex_workdir or pack_dir),
        "task_pack": str(pack_dir),
        "outputs_dir": str(outputs_dir),
        "expected_output_files": expected_campaign_files(task_id),
        "command_template_valid": validation.valid,
        "template_validation": to_plain(validation),
        "rendered_command": rendered_command,
        "will_execute": False,
    }


def _codex_run_campaign_task(
    config: GapForgeConfig,
    task_id: str,
    *,
    prefer_direct: bool,
    handoff: bool,
    require_direct: bool,
    dry_run: bool,
    allow_unknown_placeholders: bool = False,
) -> dict[str, object]:
    runtime = AgentRuntimeConfig.from_env()
    campaign_state, pack_dir = find_campaign_task(config, task_id)
    write_task_handoff(config, task_id, model=campaign_state.campaign.model or runtime.codex_model)
    outputs_dir = pack_dir / "outputs"
    if handoff:
        return {
            "task_id": task_id,
            "kind": "campaign",
            "campaign_id": campaign_state.campaign.id,
            "status": "planned",
            "mode": "handoff",
            "task_pack": str(pack_dir),
            "outputs_dir": str(outputs_dir),
            "next_commands": [f"gapforge codex-handoff --task-id {task_id} --print-prompt"],
        }
    if dry_run:
        preview = _campaign_codex_command_preview(config, task_id, allow_unknown_placeholders=allow_unknown_placeholders)
        preview["status"] = "preview"
        return preview
    if require_direct and not runtime.direct_execution_available:
        return {
            "task_id": task_id,
            "kind": "campaign",
            "campaign_id": campaign_state.campaign.id,
            "status": "failed",
            "error": "Direct Codex execution requires GAPFORGE_ENABLE_REAL_RUNS=1 and a valid GAPFORGE_CODEX_COMMAND.",
            "next_commands": [f"gapforge codex-handoff --task-id {task_id} --print-prompt"],
        }
    if not runtime.direct_execution_available and not prefer_direct:
        return {
            "task_id": task_id,
            "kind": "campaign",
            "campaign_id": campaign_state.campaign.id,
            "status": "planned",
            "mode": "handoff",
            "reason": "No direct Codex command is configured.",
            "next_commands": [f"gapforge codex-handoff --task-id {task_id} --print-prompt"],
        }
    if not runtime.direct_execution_available:
        return {
            "task_id": task_id,
            "kind": "campaign",
            "campaign_id": campaign_state.campaign.id,
            "status": "failed",
            "error": "Direct Codex execution is unavailable.",
            "next_commands": ["gapforge setup-codex", f"gapforge codex-handoff --task-id {task_id} --print-prompt"],
        }
    command_result = run_command_template(
        runtime.command_template,
        task_pack=pack_dir,
        outputs_dir=outputs_dir,
        task_id=task_id,
        run_id="",
        model=runtime.codex_model,
        cwd=runtime.codex_workdir or pack_dir,
        timeout_seconds=runtime.codex_timeout_seconds,
        allow_unknown_placeholders=allow_unknown_placeholders,
    )
    outputs = _discover_campaign_output_paths(pack_dir, expected_campaign_files(task_id))
    if not command_result.succeeded:
        return {
            "task_id": task_id,
            "kind": "campaign",
            "campaign_id": campaign_state.campaign.id,
            "status": "failed",
            "command": to_plain(command_result),
            "outputs": [str(path) for path in outputs],
            "next_commands": [f"gapforge codex-doctor --task-id {task_id}", f"gapforge codex-handoff --task-id {task_id} --print-prompt"],
        }
    if not outputs:
        return {
            "task_id": task_id,
            "kind": "campaign",
            "campaign_id": campaign_state.campaign.id,
            "status": "failed",
            "error": f"Codex command completed but did not write expected outputs to {outputs_dir}.",
            "expected_output_files": expected_campaign_files(task_id),
            "command": to_plain(command_result),
            "next_commands": [f"gapforge codex-doctor --task-id {task_id}", f"gapforge codex-handoff --task-id {task_id} --print-prompt"],
        }
    import_payload = _validate_import_all_task(config, task_id)
    return {
        "task_id": task_id,
        "kind": "campaign",
        "campaign_id": campaign_state.campaign.id,
        "status": "complete" if import_payload.get("status") in {"applied", "partial"} else "failed",
        "command": to_plain(command_result),
        "import": import_payload,
        "next_commands": import_payload.get("next_commands", []),
    }


def _discover_campaign_output_paths(pack_dir: Path, expected_files: list[str]) -> list[Path]:
    expected = set(expected_files)
    paths: list[Path] = []
    for directory in (pack_dir / "outputs", pack_dir / "repair_outputs"):
        if not directory.exists():
            continue
        files = [path for path in sorted(directory.iterdir()) if path.is_file()]
        paths.extend([path for path in files if path.name in expected] or files)
    return list(dict.fromkeys(path.resolve() for path in paths if path.exists()))


def _latest_campaign_task_id(config: GapForgeConfig, campaign_id: str) -> str:
    state = CampaignManager(config).load_campaign_state(campaign_id)
    if not state.campaign.task_ids:
        raise ValueError(f"Campaign {campaign_id} has no Codex tasks.")
    return state.campaign.task_ids[-1]


def _no_outputs_payload(task_id: str, expected_files: list[str], *, handoff_command: str) -> dict[str, object]:
    return {
        "task_id": task_id,
        "status": "no_outputs",
        "expected_files": expected_files,
        "next_commands": [
            handoff_command,
            f"gapforge list-task-outputs --task-id {task_id}",
            f"gapforge validate-import-all --task-id {task_id}",
        ],
    }


def _post_import_commands(
    task_id: str,
    *,
    run_id: str = "",
    campaign_id: str = "",
    invalid: bool,
) -> list[str]:
    if invalid:
        return [f"gapforge repair-agent-output --task-id {task_id} --path <bad-output.json> --handoff"]
    commands = [f'gapforge attest-agent-run --task-id {task_id} --agent codex --model gpt-5.4 --method task_pack --attester "<name>"']
    if campaign_id:
        commands.append(f'gapforge campaign-review --campaign-id {campaign_id} --accept --reviewer "<name>"')
    if run_id:
        commands.append(f"gapforge actual-run-status --run-id {run_id}")
    return commands


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


def _project_actual_run_status(config: GapForgeConfig, project_id: str) -> dict[str, object]:
    program = ProjectMemoryManager(config).load_project(project_id)
    campaign_manager = CampaignManager(config)
    campaign_statuses: list[dict[str, object]] = []
    for campaign in program.campaigns:
        try:
            campaign_state = campaign_manager.load_campaign_state(campaign.id)
        except FileNotFoundError:
            continue
        campaign_statuses.append(campaign_actual_run_status(campaign_state))
    accepted = [status for status in campaign_statuses if bool(status.get("accepted_real_campaign")) or bool(status.get("passed"))]
    blockers: list[str] = []
    commands: list[str] = []
    for status in campaign_statuses:
        status_blockers = status.get("blockers", [])
        if isinstance(status_blockers, list):
            blockers.extend(str(blocker) for blocker in status_blockers)
        status_commands = status.get("next_commands", [])
        if isinstance(status_commands, list):
            commands.extend(str(command) for command in status_commands)
    blockers = sorted(set(blockers))
    next_commands = _dedupe_commands(commands)
    if not campaign_statuses:
        blockers.append("No campaigns are recorded for this project.")
        next_commands.append("gapforge campaign-canary-run --profile single_task_codex_handoff --real")
    return {
        "project_id": project_id,
        "passed": bool(accepted),
        "accepted_real_campaign_count": len(accepted),
        "campaign_statuses": campaign_statuses,
        "blockers": blockers,
        "next_commands": next_commands,
        "fake_vs_real_explanation": ("Fake-agent output validates plumbing only and never counts as actual Codex/GPT-5.4 acceptance."),
    }


def _dedupe_commands(commands: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for command in commands:
        if command and command not in seen:
            result.append(command)
            seen.add(command)
    return result


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
