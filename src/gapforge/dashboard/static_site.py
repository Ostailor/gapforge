"""Dependency-free static HTML dashboards for runs and projects."""

from __future__ import annotations

import html
import json
import webbrowser
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from gapforge.campaigns import CampaignState
from gapforge.config import GapForgeConfig
from gapforge.manuscript.citations import suspicious_citation_string
from gapforge.models import (
    AgentActualRunAttestation,
    CampaignAcceptanceSummary,
    CampaignBudget,
    CampaignCanaryRecord,
    CampaignDecision,
    CampaignHumanReview,
    CampaignImportRecord,
    CampaignMilestone,
    CampaignStep,
    CampaignStopCondition,
    EvidenceSpan,
    Gap,
    HumanReviewRecord,
    NoveltyDossier,
    Paper,
    RejectedIdea,
    ResearchCampaign,
    ResearchProgramState,
    ResearchRunState,
    ReviewPanel,
    ReviewQueue,
    SearchRound,
    SourceCoverageReport,
    from_dict,
    to_plain,
)
from gapforge.project_memory import ProjectMemoryManager
from gapforge.release_gate.v08 import V08ReleaseGateEnforcer
from gapforge.state import ResearchStateManager

PAGES = [
    ("index.html", "Overview"),
    ("papers.html", "Papers"),
    ("gaps.html", "Gaps"),
    ("directions.html", "Directions"),
    ("novelty.html", "Novelty"),
    ("evidence.html", "Evidence"),
    ("coverage.html", "Coverage"),
    ("reviews.html", "Reviews"),
    ("campaigns.html", "Campaigns"),
    ("actual_runs.html", "Actual Runs"),
    ("canaries.html", "Canaries"),
    ("agent_tasks.html", "Agent Tasks"),
    ("imports.html", "Imports"),
    ("human_reviews.html", "Human Reviews"),
    ("release_gate.html", "Release Gate"),
    ("live_sources.html", "Live Sources"),
    ("search_strategy.html", "Search Strategy"),
    ("search_rounds.html", "Search Rounds"),
    ("prior_work_recall.html", "Prior-Work Recall"),
    ("real_literature_quality.html", "Real Literature Quality"),
    ("v5_release_gate.html", "v5 Release Gate"),
    ("experiment_workspaces.html", "Experiment Workspaces"),
    ("experiment_runs.html", "Experiment Runs"),
    ("datasets.html", "Datasets"),
    ("baselines.html", "Baselines"),
    ("metrics.html", "Metrics"),
    ("results.html", "Results"),
    ("reproducibility.html", "Reproducibility"),
    ("empirical_reviews.html", "Empirical Reviews"),
    ("benchmarks.html", "Benchmarks"),
    ("benchmark_suites.html", "Benchmark Suites"),
    ("jobs.html", "Jobs"),
    ("sweeps.html", "Sweeps"),
    ("result_tables.html", "Result Tables"),
    ("error_analysis.html", "Error Analysis"),
    ("leaderboard.html", "Leaderboard"),
    ("replication_packages.html", "Replication Packages"),
    ("reproduction_matrix.html", "Reproduction Matrix"),
    ("v7_release_gate.html", "v7 Release Gate"),
    ("manuscripts.html", "Manuscripts"),
    ("manuscript_sections.html", "Manuscript Sections"),
    ("bibliography.html", "Bibliography"),
    ("traceability.html", "Traceability"),
    ("figures_tables.html", "Figures/Tables"),
    ("submission_checklist.html", "Submission Checklist"),
    ("artifact_evaluation.html", "Artifact Evaluation"),
    ("reviewer_panel.html", "Reviewer Panel"),
    ("rebuttal.html", "Rebuttal"),
    ("submission_packages.html", "Submission Packages"),
    ("v8_release_gate.html", "v8 Release Gate"),
]


@dataclass(slots=True)
class DashboardResult:
    root: Path
    index_path: Path
    pages: list[Path]


class StaticDashboardBuilder:
    """Write a small static dashboard under a run or project directory."""

    def __init__(self, config: GapForgeConfig) -> None:
        self.config = config
        self.state_manager = ResearchStateManager(config)
        self.project_manager = ProjectMemoryManager(config)

    def build_run(self, run_id: str) -> DashboardResult:
        state = self.state_manager.load_latest() if run_id == "latest" else self.state_manager.load_run(run_id)
        if state is None:
            raise FileNotFoundError("No run state found.")
        context = _DashboardContext.from_run(state)
        return _write_dashboard(Path(state.run_dir) / "dashboard", context)

    def build_project(self, project_id: str, *, include_manuscripts: bool = False) -> DashboardResult:
        program = self.project_manager.load_project(project_id)
        states = [self.state_manager.load_run(run_id) for run_id in program.run_ids]
        context = _DashboardContext.from_project(program, states, include_manuscripts=include_manuscripts, config=self.config)
        return _write_dashboard(Path(program.project.root_dir) / "dashboard", context)

    def build_workspace(self, workspace_id: str) -> DashboardResult:
        workspace_dir = _find_experiment_workspace_dir(self.config.project_root, workspace_id)
        context = _DashboardContext.from_workspace(workspace_dir)
        return _write_dashboard(workspace_dir / "dashboard", context)

    def build_manuscript(self, manuscript_id: str) -> DashboardResult:
        manuscript_root = _find_manuscript_root(self.config.project_root, manuscript_id)
        context = _DashboardContext.from_manuscript(manuscript_root, self.config)
        return _write_dashboard(manuscript_root / "dashboard", context)

    def open(self, result: DashboardResult) -> None:
        webbrowser.open(result.index_path.resolve().as_uri())


class _DashboardContext:
    def __init__(
        self,
        *,
        title: str,
        subtitle: str,
        base_dir: Path,
        papers: list[Paper],
        gaps: list[Gap],
        directions: list[dict[str, Any]],
        novelty_dossiers: list[NoveltyDossier],
        evidence_spans: list[EvidenceSpan],
        coverage_reports: list[SourceCoverageReport],
        rejected_ideas: list[RejectedIdea],
        human_reviews: list[HumanReviewRecord],
        review_panels: list[ReviewPanel],
        review_queue: ReviewQueue | None,
        artifact_links: list[tuple[str, str]],
        campaigns: list[ResearchCampaign] | None = None,
        campaign_states: list[CampaignState] | None = None,
        canary_records: list[CampaignCanaryRecord] | None = None,
        run_states: list[ResearchRunState] | None = None,
        experiments: dict[str, list[dict[str, Any]]] | None = None,
        manuscripts: dict[str, Any] | None = None,
    ) -> None:
        self.title = title
        self.subtitle = subtitle
        self.base_dir = base_dir
        self.papers = papers
        self.gaps = gaps
        self.directions = directions
        self.novelty_dossiers = novelty_dossiers
        self.evidence_spans = evidence_spans
        self.coverage_reports = coverage_reports
        self.rejected_ideas = rejected_ideas
        self.human_reviews = human_reviews
        self.review_panels = review_panels
        self.review_queue = review_queue
        self.artifact_links = artifact_links
        self.campaigns = campaigns or []
        self.campaign_states = campaign_states or []
        self.canary_records = canary_records or []
        self.run_states = run_states or []
        self.experiments = experiments or _empty_experiment_context()
        self.manuscripts = manuscripts or _empty_manuscript_context()

    @classmethod
    def from_run(cls, state: ResearchRunState) -> _DashboardContext:
        return cls(
            title=f"GapForge Run: {state.run_id}",
            subtitle=state.topic.text,
            base_dir=Path(state.run_dir),
            papers=state.papers,
            gaps=state.gaps,
            directions=[],
            novelty_dossiers=state.novelty_dossiers,
            evidence_spans=state.evidence_spans,
            coverage_reports=[state.source_coverage] if state.source_coverage is not None else [],
            rejected_ideas=state.rejected_ideas,
            human_reviews=state.human_reviews,
            review_panels=[],
            review_queue=state.review_queue,
            artifact_links=_run_artifact_links(state),
            campaigns=[],
            campaign_states=[],
            canary_records=[],
            run_states=[state],
            experiments=_load_experiment_context(Path(state.run_dir)),
            manuscripts=_empty_manuscript_context(),
        )

    @classmethod
    def from_project(
        cls,
        program: ResearchProgramState,
        states: list[ResearchRunState],
        *,
        include_manuscripts: bool = False,
        config: GapForgeConfig | None = None,
    ) -> _DashboardContext:
        coverage_reports = [state.source_coverage for state in states if state.source_coverage is not None]
        campaign_states = _load_campaign_states(program)
        experiments = _load_experiment_context(Path(program.project.root_dir))
        experiments["benchmark_suites"] = [to_plain(suite) for suite in program.benchmark_suites]
        return cls(
            title=f"GapForge Project: {program.project.name}",
            subtitle=program.project.description or program.project.id,
            base_dir=Path(program.project.root_dir),
            papers=[paper for state in states for paper in state.papers],
            gaps=[gap for state in states for gap in state.gaps],
            directions=[
                {
                    "id": direction.id,
                    "title": direction.title,
                    "maturity": direction.maturity,
                    "readiness_score": direction.readiness_score,
                    "blocking_issues": direction.blocking_issues,
                    "next_actions": direction.next_actions,
                    "supporting_paper_ids": direction.supporting_paper_ids,
                }
                for direction in program.research_directions
            ],
            novelty_dossiers=[dossier for state in states for dossier in state.novelty_dossiers],
            evidence_spans=[span for state in states for span in state.evidence_spans],
            coverage_reports=coverage_reports,
            rejected_ideas=[idea for state in states for idea in state.rejected_ideas],
            human_reviews=[review for state in states for review in state.human_reviews],
            review_panels=program.review_panels,
            review_queue=program.review_queue,
            artifact_links=_project_artifact_links(program),
            campaigns=program.campaigns,
            campaign_states=campaign_states,
            canary_records=_load_campaign_canaries(Path(program.project.root_dir).parents[1] / "data", program.project.id),
            run_states=states,
            experiments=experiments,
            manuscripts=_load_project_manuscript_context(Path(program.project.root_dir), config)
            if include_manuscripts and config is not None
            else _empty_manuscript_context(),
        )

    @classmethod
    def from_workspace(cls, workspace_dir: Path) -> _DashboardContext:
        workspace = _read_json_if_exists(workspace_dir / "workspace.json")
        title = f"GapForge Experiment Workspace: {workspace.get('id', workspace_dir.name)}"
        subtitle = str(workspace.get("direction_id") or workspace.get("project_id") or workspace_dir)
        return cls(
            title=title,
            subtitle=subtitle,
            base_dir=workspace_dir,
            papers=[],
            gaps=[],
            directions=[],
            novelty_dossiers=[],
            evidence_spans=[],
            coverage_reports=[],
            rejected_ideas=[],
            human_reviews=[],
            review_panels=[],
            review_queue=None,
            artifact_links=_workspace_artifact_links(workspace_dir),
            campaigns=[],
            campaign_states=[],
            canary_records=[],
            run_states=[],
            experiments=_load_experiment_context(workspace_dir),
            manuscripts=_empty_manuscript_context(),
        )

    @classmethod
    def from_manuscript(cls, manuscript_root: Path, config: GapForgeConfig) -> _DashboardContext:
        state = _read_json_if_exists(manuscript_root / "manuscript.json")
        manuscript = state.get("manuscript", {}) if isinstance(state.get("manuscript"), dict) else {}
        title = str(manuscript.get("title") or manuscript_root.name)
        subtitle = str(manuscript.get("project_id") or manuscript.get("target_venue") or manuscript_root)
        return cls(
            title=f"GapForge Manuscript: {title}",
            subtitle=subtitle,
            base_dir=manuscript_root,
            papers=[],
            gaps=[],
            directions=[],
            novelty_dossiers=[],
            evidence_spans=[],
            coverage_reports=[],
            rejected_ideas=[],
            human_reviews=[],
            review_panels=[],
            review_queue=None,
            artifact_links=_manuscript_artifact_links(manuscript_root),
            campaigns=[],
            campaign_states=[],
            canary_records=[],
            run_states=[],
            experiments=_empty_experiment_context(),
            manuscripts=_load_manuscript_context([manuscript_root], config),
        )


def _write_dashboard(root: Path, context: _DashboardContext) -> DashboardResult:
    root.mkdir(parents=True, exist_ok=True)
    pages = {
        "index.html": _render_index(context),
        "papers.html": _render_papers(context),
        "gaps.html": _render_gaps(context),
        "directions.html": _render_directions(context),
        "novelty.html": _render_novelty(context),
        "evidence.html": _render_evidence(context),
        "coverage.html": _render_coverage(context),
        "reviews.html": _render_reviews(context),
        "campaigns.html": _render_campaigns(context),
        "actual_runs.html": _render_actual_runs(context),
        "canaries.html": _render_canaries(context),
        "agent_tasks.html": _render_agent_tasks(context),
        "imports.html": _render_imports(context),
        "human_reviews.html": _render_human_reviews(context),
        "release_gate.html": _render_release_gate(context),
        "live_sources.html": _render_live_sources(context),
        "search_strategy.html": _render_search_strategy(context),
        "search_rounds.html": _render_search_rounds(context),
        "prior_work_recall.html": _render_prior_work_recall(context),
        "real_literature_quality.html": _render_real_literature_quality(context),
        "v5_release_gate.html": _render_v5_release_gate(context),
        "experiment_workspaces.html": _render_experiment_workspaces(context),
        "experiment_runs.html": _render_experiment_runs(context),
        "datasets.html": _render_experiment_datasets(context),
        "baselines.html": _render_experiment_baselines(context),
        "metrics.html": _render_experiment_metrics(context),
        "results.html": _render_experiment_results(context),
        "reproducibility.html": _render_experiment_reproducibility(context),
        "empirical_reviews.html": _render_experiment_reviews(context),
        "benchmarks.html": _render_benchmarks(context),
        "benchmark_suites.html": _render_benchmark_suites(context),
        "jobs.html": _render_jobs(context),
        "sweeps.html": _render_sweeps(context),
        "result_tables.html": _render_result_tables(context),
        "error_analysis.html": _render_error_analysis(context),
        "leaderboard.html": _render_leaderboard(context),
        "replication_packages.html": _render_replication_packages(context),
        "reproduction_matrix.html": _render_reproduction_matrix(context),
        "v7_release_gate.html": _render_v7_release_gate(context),
        "manuscripts.html": _render_manuscripts(context),
        "manuscript_sections.html": _render_manuscript_sections(context),
        "bibliography.html": _render_manuscript_bibliography(context),
        "traceability.html": _render_manuscript_traceability(context),
        "figures_tables.html": _render_manuscript_figures_tables(context),
        "submission_checklist.html": _render_manuscript_submission_checklist(context),
        "artifact_evaluation.html": _render_manuscript_artifact_evaluation(context),
        "reviewer_panel.html": _render_manuscript_reviewer_panel(context),
        "rebuttal.html": _render_manuscript_rebuttal(context),
        "submission_packages.html": _render_manuscript_submission_packages(context),
        "v8_release_gate.html": _render_v8_release_gate(context),
    }
    written = []
    for filename, body in pages.items():
        path = root / filename
        path.write_text(_page(context, filename, body), encoding="utf-8")
        written.append(path)
    return DashboardResult(root=root, index_path=root / "index.html", pages=written)


def _page(context: _DashboardContext, current: str, body: str) -> str:
    nav = " ".join(
        f'<a class="{"active" if filename == current else ""}" href="{_e(filename)}">{_e(label)}</a>' for filename, label in PAGES
    )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{_e(context.title)}</title>
  <style>
    :root {{ color-scheme: light dark; --border: #c8c8c8; --muted: #666; --bg-soft: rgba(127,127,127,.08); }}
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; margin: 0; line-height: 1.45; }}
    header {{ padding: 24px 32px 12px; border-bottom: 1px solid var(--border); }}
    main {{ padding: 20px 32px 40px; max-width: 1200px; }}
    nav {{ display: flex; flex-wrap: wrap; gap: 8px; margin-top: 16px; }}
    nav a {{ color: inherit; text-decoration: none; padding: 6px 10px; border: 1px solid var(--border); border-radius: 6px; }}
    nav a.active {{ background: var(--bg-soft); font-weight: 700; }}
    h1 {{ margin: 0; font-size: 1.8rem; }}
    h2 {{ margin-top: 28px; }}
    .muted {{ color: var(--muted); }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 12px; }}
    .card {{ border: 1px solid var(--border); border-radius: 6px; padding: 12px; background: var(--bg-soft); }}
    table {{ width: 100%; border-collapse: collapse; margin: 12px 0 20px; }}
    th, td {{ border-bottom: 1px solid var(--border); padding: 8px; text-align: left; vertical-align: top; }}
    th {{ background: var(--bg-soft); }}
    code {{ white-space: nowrap; }}
    .warning {{ border-left: 4px solid #b26a00; padding-left: 10px; }}
    .search {{ width: min(420px, 100%); padding: 8px; margin: 12px 0; }}
  </style>
  <script>
    function filterRows(q) {{
      q = q.toLowerCase();
      document.querySelectorAll('[data-filter]').forEach(function(row) {{
        row.style.display = row.getAttribute('data-filter').toLowerCase().includes(q) ? '' : 'none';
      }});
    }}
  </script>
</head>
<body>
  <header>
    <h1>{_e(context.title)}</h1>
    <div class="muted">{_e(context.subtitle)}</div>
    <nav>{nav}</nav>
  </header>
  <main>
    {body}
  </main>
</body>
</html>
"""


def _render_index(context: _DashboardContext) -> str:
    warnings = _coverage_warnings(context.coverage_reports)
    return "\n".join(
        [
            '<div class="grid">',
            _metric("Papers", len(context.papers)),
            _metric("Gaps", len(context.gaps)),
            _metric("Directions", len(context.directions)),
            _metric("Evidence Spans", len(context.evidence_spans)),
            _metric("Open Review Items", len(_open_queue_items(context.review_queue))),
            _metric("Human Reviews", len(context.human_reviews)),
            _metric("Rejected Ideas", len(context.rejected_ideas)),
            "</div>",
            "<h2>Coverage Warnings</h2>",
            _list(warnings, css_class="warning"),
            "<h2>Top Directions</h2>",
            _direction_cards(context.directions[:5]),
            "<h2>Rejected Ideas</h2>",
            _rejected_ideas(context.rejected_ideas),
            "<h2>Markdown Artifacts</h2>",
            _artifact_links(context.artifact_links),
        ]
    )


def _render_papers(context: _DashboardContext) -> str:
    rows = [
        [
            _code(paper.id),
            _e(paper.title),
            _e("; ".join(paper.authors)),
            str(paper.year),
            _e(paper.source),
            _link(paper.url, "url") if paper.url else "",
            _e(", ".join(paper.roles)),
        ]
        for paper in context.papers
    ]
    return _filter_box() + _table(["ID", "Title", "Authors", "Year", "Source", "URL", "Roles"], rows)


def _render_gaps(context: _DashboardContext) -> str:
    rows = [
        [
            _code(gap.id),
            _e(gap.title or gap.description),
            _e(gap.type),
            _e(gap.confidence),
            _e(gap.novelty_status),
            _e(", ".join(gap.supporting_paper_ids or gap.linked_paper_ids)),
            _e(gap.risk_that_gap_is_fake),
        ]
        for gap in context.gaps
    ]
    return _filter_box() + _table(["ID", "Gap", "Type", "Confidence", "Novelty", "Papers", "Risk"], rows)


def _render_directions(context: _DashboardContext) -> str:
    if not context.directions:
        return "<p>No project directions are available for this dashboard.</p>"
    rows = [
        [
            _code(str(direction["id"])),
            _e(str(direction["title"])),
            _e(str(direction["maturity"])),
            f"{float(direction['readiness_score']):.2f}",
            _e("; ".join(direction["blocking_issues"])),
            _e("; ".join(direction["next_actions"])),
            _e(", ".join(direction["supporting_paper_ids"])),
        ]
        for direction in context.directions
    ]
    return _filter_box() + _table(["ID", "Title", "Maturity", "Readiness", "Blocking Issues", "Next Actions", "Papers"], rows)


def _render_novelty(context: _DashboardContext) -> str:
    rows = [
        [
            _code(dossier.target_id),
            _e(dossier.idea_summary),
            _e(dossier.verdict),
            _e(dossier.novelty_strength),
            _e(dossier.confidence),
            _e(", ".join(dossier.top_prior_work)),
            _e("; ".join(dossier.missing_searches)),
            _e(dossier.decisive_difference_needed),
        ]
        for dossier in context.novelty_dossiers
    ]
    return _filter_box() + _table(
        ["Target", "Idea", "Verdict", "Strength", "Confidence", "Closest Prior Work", "Missing Searches", "Decisive Difference"],
        rows,
    )


def _render_evidence(context: _DashboardContext) -> str:
    rows = [
        [
            _code(span.id),
            _code(span.paper_id),
            _code(span.section_id),
            _e(span.evidence_type),
            _e(span.confidence),
            _e(span.locator),
            _e(span.quote),
        ]
        for span in context.evidence_spans
    ]
    return _filter_box() + _table(["ID", "Paper", "Section", "Type", "Confidence", "Locator", "Quote"], rows)


def _render_coverage(context: _DashboardContext) -> str:
    sections = []
    for index, coverage in enumerate(context.coverage_reports, start=1):
        sections.extend(
            [
                f"<h2>Coverage Report {index}</h2>",
                '<div class="grid">',
                _metric("Sources", len(coverage.searched_sources)),
                _metric("Full Text Papers", len(coverage.papers_with_full_text)),
                _metric("Abstract Only", len(coverage.papers_abstract_only)),
                _metric("Fallback Papers", coverage.fallback_paper_count),
                "</div>",
                "<h3>Warnings</h3>",
                _list(coverage.coverage_warnings or coverage.missing_source_types, css_class="warning"),
                "<h3>Queries</h3>",
                _table(
                    ["Query", "Purpose", "Sources", "Results", "Failures"],
                    [
                        [
                            _e(record.query),
                            _e(record.purpose),
                            _e(", ".join(record.source_names)),
                            _e(", ".join(record.result_paper_ids)),
                            _e("; ".join(record.failure_messages)),
                        ]
                        for record in coverage.query_records
                    ],
                ),
            ]
        )
    return "\n".join(sections) if sections else "<p>No source coverage report is available.</p>"


def _render_reviews(context: _DashboardContext) -> str:
    parts = ["<h2>Review Queue</h2>"]
    parts.append(_review_queue_table(context.review_queue))
    parts.append("<h2>Human Review Decisions</h2>")
    parts.append(
        _table(
            ["ID", "Object", "Action", "Reviewer", "Note"],
            [
                [
                    _code(review.id),
                    _e(f"{review.object_type}:{review.object_id}"),
                    _e(review.action),
                    _e(review.reviewer),
                    _e(review.note),
                ]
                for review in context.human_reviews
            ],
        )
    )
    parts.extend(["<h2>Review Panels</h2>"])
    for panel in context.review_panels:
        parts.extend(
            [
                f"<h3>{_code(panel.experiment_or_direction_id)}</h3>",
                f"<p><strong>Decision risk:</strong> {_e(panel.decision_risk)}</p>",
                f"<p>{_e(panel.area_chair_summary)}</p>",
                _table(
                    ["Reviewer", "Role", "Score", "Fatal Flaws", "Required Fixes", "Evidence"],
                    [
                        [
                            _code(review.reviewer_id),
                            _e(review.role),
                            f"{review.score:.1f}",
                            _e("; ".join(review.fatal_flaws)),
                            _e("; ".join(review.required_fixes)),
                            _e(", ".join(review.evidence_or_prior_work)),
                        ]
                        for review in panel.reviewer_reviews
                    ],
                ),
            ]
        )
    parts.extend(["<h2>Rejected Ideas</h2>", _rejected_ideas(context.rejected_ideas)])
    return "\n".join(parts)


def _render_campaigns(context: _DashboardContext) -> str:
    rows = [
        [
            _code(campaign.id),
            _e(campaign.status),
            _e(campaign.mode),
            _e(campaign.agent_name or "none"),
            _e(campaign.model or "none"),
            _e(campaign.source_profile),
            str(len(campaign.run_ids)),
            str(len(campaign.task_ids)),
        ]
        for campaign in context.campaigns
    ]
    return _filter_box() + _table(["ID", "Status", "Mode", "Agent", "Model", "Source Profile", "Runs", "Tasks"], rows)


def _render_actual_runs(context: _DashboardContext) -> str:
    rows = []
    for state in context.campaign_states:
        real_imports = _real_import_records(state.imports)
        fake = state.campaign.mode == "fake_agent"
        summary = state.acceptance_summary
        rows.append(
            [
                _code(state.campaign.id),
                _e("fake" if fake else "real-capable" if _campaign_requires_actual_run(state.campaign) else "deterministic"),
                _e(state.campaign.mode),
                _e(state.campaign.agent_name or "none"),
                _e(state.campaign.model or "none"),
                str(len(real_imports)),
                str(_attested_output_count(state.imports)),
                _e("eligible" if summary and summary.release_gate_eligible else "not eligible"),
                _e("; ".join(summary.blocking_failures) if summary else _default_actual_run_blocker(state)),
            ]
        )
    return (
        "<p><strong>Fake-agent success is not actual-run acceptance.</strong> Actual-run acceptance requires attested "
        "Codex/GPT-5.4 output, validated import, and human campaign review.</p>"
        + _filter_box()
        + _table(
            [
                "Campaign",
                "Run Type",
                "Mode",
                "Agent",
                "Model",
                "Accepted Real Imports",
                "Attested Outputs",
                "Release Gate",
                "Blockers",
            ],
            rows,
        )
    )


def _render_canaries(context: _DashboardContext) -> str:
    rows = [
        [
            _code(record.id),
            _code(record.profile_id),
            _code(record.campaign_id),
            _e(record.status),
            _e(record.actual_run_status),
            _e(record.human_review_status),
            _e("accepted" if record.accepted else "not accepted"),
            _e(record.failure_reason),
        ]
        for record in context.canary_records
    ]
    return _filter_box() + _table(
        ["ID", "Profile", "Campaign", "Status", "Actual Run", "Human Review", "Accepted", "Failure/Blocker"], rows
    )


def _render_agent_tasks(context: _DashboardContext) -> str:
    rows = []
    for state in context.campaign_states:
        for step in state.steps:
            if not step.task_spec_id:
                continue
            rows.append(
                [
                    _code(step.task_spec_id),
                    _code(state.campaign.id),
                    _e(step.step_type),
                    _e(step.status),
                    _e("fake" if state.campaign.mode == "fake_agent" else state.campaign.mode),
                    _e("; ".join(step.blocking_issues)),
                    _e(", ".join(step.output_artifacts)),
                ]
            )
    return _filter_box() + _table(["Task", "Campaign", "Step Type", "Status", "Mode", "Blockers", "Outputs"], rows)


def _render_imports(context: _DashboardContext) -> str:
    rows = []
    for state in context.campaign_states:
        for record in state.imports:
            rows.append(
                [
                    _code(record.id),
                    _code(state.campaign.id),
                    _code(record.task_id),
                    _e(record.status),
                    _e(
                        "real-attested"
                        if _record_has_actual_attestation(record)
                        else "fake"
                        if state.campaign.mode == "fake_agent"
                        else "unattested"
                    ),
                    str(len(record.accepted_objects)),
                    str(len(record.rejected_objects)),
                    _e("; ".join(record.issues)),
                ]
            )
    return _filter_box() + _table(
        ["Import", "Campaign", "Task", "Status", "Actual-Run Label", "Accepted Objects", "Rejected Objects", "Issues"], rows
    )


def _render_human_reviews(context: _DashboardContext) -> str:
    campaign_rows = []
    for state in context.campaign_states:
        for review in state.human_reviews:
            campaign_rows.append(
                [
                    _code(review.id),
                    _code(state.campaign.id),
                    _e(review.reviewer),
                    _e("accepted" if review.accepted else "rejected/not accepted"),
                    _e(str(review.fake_citation_found)),
                    _e(str(review.unsupported_high_confidence_claim_found)),
                    _e(str(review.overclaimed_novelty)),
                    _e("; ".join(review.reasons + review.required_fixes + ([review.notes] if review.notes else []))),
                ]
            )
    run_rows = [
        [_code(review.id), _e(f"{review.object_type}:{review.object_id}"), _e(review.action), _e(review.reviewer), _e(review.note)]
        for review in context.human_reviews
    ]
    return "\n".join(
        [
            "<h2>Campaign Human Reviews</h2>",
            _filter_box(),
            _table(
                [
                    "Review",
                    "Campaign",
                    "Reviewer",
                    "Accepted",
                    "Fake Citation",
                    "Unsupported High Confidence",
                    "Overclaimed Novelty",
                    "Notes/Fixes",
                ],
                campaign_rows,
            ),
            "<h2>Run-Level Human Reviews</h2>",
            _table(["Review", "Object", "Action", "Reviewer", "Note"], run_rows),
        ]
    )


def _render_release_gate(context: _DashboardContext) -> str:
    eligible = [state for state in context.campaign_states if state.acceptance_summary and state.acceptance_summary.release_gate_eligible]
    blockers = _release_gate_blockers(context)
    status = "PASSED" if eligible and not blockers else "NOT PASSED"
    css = "card" if status == "PASSED" else "card warning"
    fake_warnings = [
        f"`{state.campaign.id}` is fake-agent only and cannot count as actual-run acceptance."
        for state in context.campaign_states
        if state.campaign.mode == "fake_agent"
    ]
    return "\n".join(
        [
            f'<div class="{css}"><h2>v0.4 Actual-Run Release Gate: {_e(status)}</h2>'
            f"<p>Eligible real campaigns: {_e(str(len(eligible)))}</p></div>",
            "<h2>Fake vs Real</h2>",
            "<p>Fake-agent canaries validate schemas and orchestration only. They never count as actual Codex/GPT-5.4 acceptance. "
            "Task-pack or handoff output counts only after validated import, human attestation, and campaign review.</p>",
            "<h2>Fake Run Warnings</h2>",
            _list(fake_warnings, css_class="warning"),
            "<h2>Acceptance Blockers</h2>",
            _list(blockers, css_class="warning"),
            "<h2>Suggested Next Commands</h2>",
            _list(_release_gate_next_commands(context, blockers), css_class="warning"),
            "<h2>Eligible Campaigns</h2>",
            _table(
                ["Campaign", "Mode", "Agent", "Model", "Accepted Real Imports"],
                [
                    [
                        _code(state.campaign.id),
                        _e(state.campaign.mode),
                        _e(state.campaign.agent_name or "codex"),
                        _e(state.campaign.model or "gpt-5.4"),
                        _e(", ".join(state.acceptance_summary.accepted_real_agent_outputs) if state.acceptance_summary else ""),
                    ]
                    for state in eligible
                ],
            ),
            "<h2>All Campaign Gate Summaries</h2>",
            _table(
                ["Campaign", "Accepted", "Attestation", "Release Eligible", "Blockers"],
                [
                    [
                        _code(state.campaign.id),
                        _e(str(state.acceptance_summary.accepted if state.acceptance_summary else False)),
                        _e(str(state.acceptance_summary.actual_run_attestation_present if state.acceptance_summary else False)),
                        _e(str(state.acceptance_summary.release_gate_eligible if state.acceptance_summary else False)),
                        _e("; ".join(state.acceptance_summary.blocking_failures) if state.acceptance_summary else "No acceptance summary."),
                    ]
                    for state in context.campaign_states
                ],
            ),
        ]
    )


def _render_live_sources(context: _DashboardContext) -> str:
    rows: list[list[str]] = []
    for state in context.campaign_states:
        diagnostic = _campaign_live_source_diagnostic(context, state)
        checks = diagnostic.get("source_health_checks", diagnostic.get("checks", []))
        for check in checks if isinstance(checks, list) else []:
            if not isinstance(check, dict):
                continue
            rows.append(
                [
                    _code(state.campaign.id),
                    _e(str(check.get("source_name", ""))),
                    _e(str(check.get("status", ""))),
                    _e(str(check.get("test_query", ""))),
                    _e(str(check.get("result_count", 0))),
                    _e(str(check.get("latency_ms", ""))),
                    _e(str(check.get("warning", ""))),
                    _e(str(check.get("error", ""))),
                ]
            )
    if not rows:
        for coverage in context.coverage_reports:
            for source in coverage.searched_sources:
                rows.append(
                    ["run coverage", _e(source), _e(coverage.confidence), "", "", "", _e("; ".join(coverage.coverage_warnings)), ""]
                )
    return "\n".join(
        [
            "<p><strong>Fallback and fixture counts must be treated as quality blockers when they dominate collected papers.</strong></p>",
            _filter_box(),
            _table(["Campaign", "Source", "Status", "Test Query", "Results", "Latency", "Warning", "Error"], rows),
        ]
    )


def _render_search_strategy(context: _DashboardContext) -> str:
    rows: list[list[str]] = []
    for run in context.run_states:
        for strategy in run.search_strategies:
            rows.append(
                [
                    _code(run.run_id),
                    _code(strategy.id),
                    _e(strategy.source_profile),
                    str(len(strategy.primary_queries)),
                    str(len(strategy.survey_queries)),
                    str(len(strategy.benchmark_queries)),
                    str(len(strategy.closest_prior_work_queries)),
                    _e("; ".join(strategy.primary_queries[:3])),
                    _e(", ".join(strategy.expected_sources)),
                ]
            )
    for state in context.campaign_states:
        raw_strategy = _campaign_json(context, state, "search_strategy.json")
        if raw_strategy:
            rows.append(
                [
                    _code(state.campaign.id),
                    _code(str(raw_strategy.get("id", ""))),
                    _e(str(raw_strategy.get("source_profile", ""))),
                    str(len(_as_list(raw_strategy.get("primary_queries")))),
                    str(len(_as_list(raw_strategy.get("survey_queries")))),
                    str(len(_as_list(raw_strategy.get("benchmark_queries")))),
                    str(len(_as_list(raw_strategy.get("closest_prior_work_queries")))),
                    _e("; ".join(map(str, _as_list(raw_strategy.get("primary_queries"))[:3]))),
                    _e(", ".join(map(str, _as_list(raw_strategy.get("expected_sources"))))),
                ]
            )
    return _filter_box() + _table(
        ["Scope", "Strategy", "Profile", "Primary", "Survey", "Benchmark", "Prior Work", "Example Queries", "Expected Sources"],
        rows,
    )


def _render_search_rounds(context: _DashboardContext) -> str:
    rows: list[list[str]] = []
    for run in context.run_states:
        for round_item in run.search_rounds:
            rows.append(_search_round_row(run.run_id, round_item))
    for state in context.campaign_states:
        raw_rounds = _campaign_json_list(context, state, "search_rounds.json")
        for item in raw_rounds:
            rows.append(
                [
                    _code(state.campaign.id),
                    _code(str(item.get("id", ""))),
                    _e(str(item.get("round_type", ""))),
                    _e(str(item.get("status", ""))),
                    _e(", ".join(map(str, _as_list(item.get("sources"))))),
                    str(len(_as_list(item.get("result_paper_ids")))),
                    _e("; ".join(map(str, _as_list(item.get("failures"))))),
                ]
            )
    return _filter_box() + _table(["Scope", "Round", "Type", "Status", "Sources", "Results", "Failures"], rows)


def _render_prior_work_recall(context: _DashboardContext) -> str:
    rows: list[list[str]] = []
    for run in context.run_states:
        for assessment in run.prior_work_recall_assessments:
            rows.append(
                [
                    _code(run.run_id),
                    _code(assessment.target_id),
                    _e(str(assessment.novelty_allowed)),
                    _e(str(assessment.likely_duplicate)),
                    _e(assessment.recall_confidence),
                    _e(", ".join(assessment.completed_query_rounds)),
                    _e(", ".join(assessment.missing_required_searches)),
                    _e(", ".join(assessment.top_prior_work_ids)),
                    _e("; ".join(assessment.blocking_issues)),
                ]
            )
    for state in context.campaign_states:
        raw = _campaign_json(context, state, "prior_work_recall.json")
        items = raw if isinstance(raw, list) else [raw] if raw else []
        for item in items:
            if not isinstance(item, dict):
                continue
            rows.append(
                [
                    _code(state.campaign.id),
                    _code(str(item.get("target_id", ""))),
                    _e(str(item.get("novelty_allowed", ""))),
                    _e(str(item.get("likely_duplicate", ""))),
                    _e(str(item.get("recall_confidence", ""))),
                    _e(", ".join(map(str, _as_list(item.get("completed_query_rounds"))))),
                    _e(", ".join(map(str, _as_list(item.get("missing_required_searches"))))),
                    _e(", ".join(map(str, _as_list(item.get("top_prior_work_ids"))))),
                    _e("; ".join(map(str, _as_list(item.get("blocking_issues"))))),
                ]
            )
    return (
        "<p>Missing prior-work search rounds cap novelty and should be visible before any recommendation.</p>"
        + _filter_box()
        + _table(
            [
                "Scope",
                "Target",
                "Novelty Allowed",
                "Duplicate",
                "Confidence",
                "Completed Rounds",
                "Missing Rounds",
                "Top Prior Work",
                "Blockers",
            ],
            rows,
        )
    )


def _render_real_literature_quality(context: _DashboardContext) -> str:
    rows: list[list[str]] = []
    for state in context.campaign_states:
        reviews = _campaign_json_list(context, state, "real_literature_reviews.json")
        acceptance = _campaign_json(context, state, "real_literature_acceptance.json")
        latest = reviews[-1] if reviews else {}
        rows.append(
            [
                _code(state.campaign.id),
                _e(str(latest.get("reviewer", ""))),
                _e("accepted" if latest.get("accepted_for_workflow") else "not accepted"),
                _e("accepted" if latest.get("accepted_for_research_quality") else "rejected/not accepted"),
                _e(str(latest.get("fake_citation_found", False))),
                _e(str(latest.get("unsupported_high_confidence_claim_found", False))),
                _e(str(latest.get("missed_obvious_prior_work", False))),
                _e(str(latest.get("overclaimed_novelty", False))),
                _e("; ".join(map(str, _as_list(acceptance.get("blocking_failures"))))),
            ]
        )
    return (
        "<p><strong>Workflow acceptance is separate from research-quality acceptance.</strong> "
        "A workflow-accepted but quality-rejected campaign is not research validation.</p>"
        + _filter_box()
        + _table(
            [
                "Campaign",
                "Reviewer",
                "Workflow Acceptance",
                "Research Quality",
                "Fake Citation",
                "Unsupported High Confidence",
                "Missed Prior Work",
                "Overclaimed Novelty",
                "Blockers",
            ],
            rows,
        )
    )


def _render_v5_release_gate(context: _DashboardContext) -> str:
    quality_rows = []
    quality_accepted = 0
    refusal_count = 0
    experiment_ready = 0
    for state in context.campaign_states:
        acceptance = _campaign_json(context, state, "real_literature_acceptance.json")
        accepted_quality = bool(acceptance.get("accepted_for_research_quality"))
        quality_accepted += int(accepted_quality)
        is_refusal = bool(acceptance.get("is_refusal_campaign")) or _state_refusal(state)
        refusal_count += int(accepted_quality and is_refusal)
        ready = any(direction.get("maturity") in {"experiment_ready", "manuscript_ready"} for direction in context.directions)
        experiment_ready += int(accepted_quality and ready)
        quality_rows.append(
            [
                _code(state.campaign.id),
                _e(str(accepted_quality)),
                _e(str(is_refusal)),
                _e(str(ready)),
                _e("; ".join(map(str, _as_list(acceptance.get("blocking_failures"))))),
            ]
        )
    blockers = []
    if len(context.campaign_states) < 3:
        blockers.append("Fewer than 3 campaigns are available for v0.5 quality release gating.")
    if quality_accepted < 2:
        blockers.append("Fewer than 2 campaigns are accepted for research quality.")
    if refusal_count < 1:
        blockers.append("No quality-accepted refusal campaign is visible.")
    if experiment_ready < 1:
        blockers.append("No quality-accepted experiment-ready campaign is visible.")
    status = "PASSED" if not blockers else "NOT PASSED"
    return "\n".join(
        [
            f'<div class="{"card" if not blockers else "card warning"}"><h2>v0.5 Real-Literature Quality Gate: {_e(status)}</h2>'
            f"<p>Quality accepted: {_e(str(quality_accepted))}</p></div>",
            "<h2>Blockers</h2>",
            _list(blockers, css_class="warning"),
            "<h2>Campaign Quality Summaries</h2>",
            _table(["Campaign", "Quality Accepted", "Refusal", "Experiment Ready", "Blockers"], quality_rows),
        ]
    )


def _render_experiment_workspaces(context: _DashboardContext) -> str:
    rows = [
        [
            _code(str(workspace.get("id", ""))),
            _code(str(workspace.get("project_id", ""))),
            _code(str(workspace.get("campaign_id", ""))),
            _code(str(workspace.get("direction_id", ""))),
            _code(str(workspace.get("experiment_protocol_id", ""))),
            _e(str(workspace.get("status", ""))),
            _e(str(workspace.get("root_dir", ""))),
            _e(_paper_package_status(context, str(workspace.get("id", "")))),
        ]
        for workspace in context.experiments["workspaces"]
    ]
    return _filter_box() + _table(["Workspace", "Project", "Campaign", "Direction", "Protocol", "Status", "Root", "Paper Package"], rows)


def _render_experiment_runs(context: _DashboardContext) -> str:
    manifest_rows = [
        [
            _code(str(manifest.get("workspace_id", ""))),
            _code(str(manifest.get("id", ""))),
            _e(str(manifest.get("run_name", ""))),
            _e(str(manifest.get("run_type", ""))),
            _e(", ".join(map(str, _as_list(manifest.get("dataset_ids"))))),
            _e(", ".join(map(str, _as_list(manifest.get("baseline_ids"))))),
            _e(", ".join(map(str, _as_list(manifest.get("metric_ids"))))),
            _e(", ".join(map(str, _as_list(manifest.get("expected_outputs"))))),
        ]
        for manifest in context.experiments["manifests"]
    ]
    execution_rows = [
        [
            _code(str(record.get("workspace_id", ""))),
            _code(str(record.get("id", ""))),
            _code(str(record.get("manifest_id", ""))),
            _e(str(record.get("status", ""))),
            _e(str(record.get("returncode", ""))),
            _e(str(record.get("failure_reason", ""))),
            _e(str(record.get("stdout_path", ""))),
            _e(str(record.get("stderr_path", ""))),
            _e(", ".join(map(str, _as_list(record.get("result_artifact_ids"))))),
        ]
        for record in context.experiments["executions"]
    ]
    failed = [str(record.get("id", "")) for record in context.experiments["executions"] if _execution_failed(record)]
    return "\n".join(
        [
            "<h2>Run Manifests</h2>",
            _filter_box(),
            _table(
                ["Workspace", "Manifest", "Name", "Type", "Datasets", "Baselines", "Metrics", "Expected Outputs"],
                manifest_rows,
            ),
            "<h2>Execution Records</h2>",
            "<p>Log file paths are shown, but log contents are not embedded in the dashboard.</p>",
            _table(
                [
                    "Workspace",
                    "Execution",
                    "Manifest",
                    "Status",
                    "Return Code",
                    "Failure Reason",
                    "Stdout Path",
                    "Stderr Path",
                    "Artifacts",
                ],
                execution_rows,
            ),
            "<h2>Failed Runs</h2>",
            _list(failed, css_class="warning"),
        ]
    )


def _render_experiment_datasets(context: _DashboardContext) -> str:
    rows = [
        [
            _code(str(record.get("workspace_id", ""))),
            _code(str(record.get("id", ""))),
            _e(str(record.get("name", ""))),
            _e(str(record.get("dataset_type", ""))),
            _e(str(record.get("license", ""))),
            _e(str(record.get("size_summary", ""))),
            _e(", ".join(map(str, _as_list(record.get("split_names"))))),
            _e(str(record.get("intended_use", ""))),
            _e("; ".join(map(str, _as_list(record.get("limitations")) + _as_list(record.get("safety_notes"))))),
        ]
        for record in context.experiments["datasets"]
    ]
    warnings = [
        f"`{record.get('id', '')}` is {record.get('dataset_type')} data and cannot establish real empirical acceptance by itself."
        for record in context.experiments["datasets"]
        if str(record.get("dataset_type", "")) in {"fixture", "synthetic", "generated"}
    ]
    return (
        _filter_box()
        + _table(["Workspace", "Dataset", "Name", "Type", "License", "Size", "Splits", "Use", "Risks"], rows)
        + "<h2>Fixture/Synthetic Warnings</h2>"
        + _list(warnings, css_class="warning")
    )


def _render_experiment_baselines(context: _DashboardContext) -> str:
    rows = [
        [
            _code(str(record.get("workspace_id", ""))),
            _code(str(record.get("id", ""))),
            _e(str(record.get("name", ""))),
            _e(str(record.get("baseline_type", ""))),
            _e(str(record.get("code_available", ""))),
            _e(
                str(record.get("implementation_path", "") or str(record.get("code_url", ""))),
            ),
            _e(str(record.get("required_for_submission", ""))),
            _e(str(record.get("risk_if_missing", ""))),
        ]
        for record in context.experiments["baselines"]
    ]
    return _filter_box() + _table(
        ["Workspace", "Baseline", "Name", "Type", "Code Available", "Implementation", "Required", "Risk If Missing"], rows
    )


def _render_experiment_metrics(context: _DashboardContext) -> str:
    rows = [
        [
            _code(str(record.get("workspace_id", ""))),
            _code(str(record.get("id", ""))),
            _e(str(record.get("name", ""))),
            _e(str(record.get("metric_type", ""))),
            _e(str(record.get("higher_is_better", ""))),
            _e(str(record.get("formula", ""))),
            _e("; ".join(map(str, _as_list(record.get("edge_cases"))))),
        ]
        for record in context.experiments["metrics"]
    ]
    return _filter_box() + _table(["Workspace", "Metric", "Name", "Type", "Higher Is Better", "Formula", "Edge Cases"], rows)


def _render_experiment_results(context: _DashboardContext) -> str:
    artifact_rows = [
        [
            _code(str(artifact.get("workspace_id", ""))),
            _code(str(artifact.get("id", ""))),
            _code(str(artifact.get("execution_id", ""))),
            _e(str(artifact.get("artifact_type", ""))),
            _e(str(artifact.get("sha256", ""))),
            _e(str(artifact.get("safe_to_commit", ""))),
            _e(str(artifact.get("summary", ""))),
            _e(str(artifact.get("path", ""))),
        ]
        for artifact in context.experiments["artifacts"]
    ]
    metric_rows = [
        [
            _code(str(result.get("workspace_id", ""))),
            _code(str(result.get("execution_id", ""))),
            _code(str(result.get("id", ""))),
            _code(str(result.get("metric_id", ""))),
            _e(str(result.get("value", ""))),
            _e(str(result.get("sample_size", ""))),
            _e(", ".join(map(str, _as_list(result.get("confidence_interval"))))),
            _code(str(result.get("raw_artifact_id", ""))),
        ]
        for result in context.experiments["metric_results"]
    ]
    claim_rows = [
        [
            _code(str(claim.get("workspace_id", ""))),
            _code(str(claim.get("execution_id", ""))),
            _code(str(claim.get("id", ""))),
            _e(str(claim.get("status", ""))),
            _e(str(claim.get("confidence", ""))),
            _e(str(claim.get("text", ""))),
            _e(", ".join(map(str, _as_list(claim.get("metric_result_ids"))))),
            _e("; ".join(map(str, _as_list(claim.get("limitations"))))),
        ]
        for claim in context.experiments["empirical_claims"]
    ]
    fake_warnings = _fake_result_warnings(context)
    return "\n".join(
        [
            "<h2>Result Artifacts</h2>",
            _filter_box(),
            _table(["Workspace", "Artifact", "Execution", "Type", "SHA256", "Safe To Commit", "Summary", "Path"], artifact_rows),
            "<h2>Metric Results</h2>",
            _table(["Workspace", "Execution", "Metric Result", "Metric", "Value", "Sample Size", "CI", "Artifact"], metric_rows),
            "<h2>Empirical Claims</h2>",
            _table(["Workspace", "Execution", "Claim", "Status", "Confidence", "Text", "Metric Results", "Limitations"], claim_rows),
            "<h2>Fixture/Synthetic Result Warnings</h2>",
            _list(fake_warnings, css_class="warning"),
        ]
    )


def _render_experiment_reproducibility(context: _DashboardContext) -> str:
    rows: list[list[str]] = []
    blocker_items: list[str] = []
    for result in context.experiments["reproducibility"]:
        checks = result.get("checks", {})
        rows.append(
            [
                _code(str(result.get("workspace_id", ""))),
                _code(str(result.get("execution_id", ""))),
                _e(str(result.get("status", ""))),
                _e("; ".join(f"{key}: {value}" for key, value in checks.items()) if isinstance(checks, dict) else ""),
                _e("; ".join(map(str, _as_list(result.get("blockers"))))),
                _e("; ".join(map(str, _as_list(result.get("warnings"))))),
            ]
        )
        blocker_items.extend(f"`{result.get('workspace_id', '')}`: {item}" for item in _as_list(result.get("blockers")))
    return (
        _filter_box()
        + _table(["Workspace", "Execution", "Status", "Checks", "Blockers", "Warnings"], rows)
        + "<h2>Reproducibility Blockers</h2>"
        + _list(blocker_items, css_class="warning")
    )


def _render_experiment_reviews(context: _DashboardContext) -> str:
    rows = [
        [
            _code(str(panel.get("workspace_id", ""))),
            _code(str(panel.get("execution_id", ""))),
            _e(str(len(_as_list(panel.get("reviewer_reviews"))))),
            _e(str(panel.get("area_chair_summary", ""))),
            _e("; ".join(map(str, _as_list(panel.get("fatal_flaws"))))),
            _e("; ".join(map(str, _as_list(panel.get("required_fixes"))))),
            _e("; ".join(map(str, _as_list(panel.get("result_claim_softening_recommendations"))))),
        ]
        for panel in context.experiments["empirical_reviews"]
    ]
    return _filter_box() + _table(
        ["Workspace", "Execution", "Reviews", "Area Chair Summary", "Fatal Flaws", "Required Fixes", "Claim Softening"], rows
    )


def _render_benchmarks(context: _DashboardContext) -> str:
    rows = [
        [
            _code(str(record.get("workspace_id", ""))),
            _code(str(record.get("id", ""))),
            _e(str(record.get("name", ""))),
            _e(str(record.get("domain", ""))),
            _e(str(record.get("task_type", ""))),
            _e(", ".join(map(str, _as_list(record.get("dataset_ids"))))),
            _e(", ".join(map(str, _as_list(record.get("baseline_ids"))))),
            _e(", ".join(map(str, _as_list(record.get("metric_ids"))))),
            _e("; ".join(map(str, _as_list(record.get("limitations")) + _as_list(record.get("safety_notes"))))),
        ]
        for record in context.experiments["benchmarks"]
    ]
    canary_rows = [
        [
            _code(str(record.get("workspace_id", ""))),
            _code(str(record.get("profile_id", ""))),
            _e(str(record.get("status", ""))),
            _e(str(record.get("execution_status", ""))),
            _e("; ".join(map(str, _as_list(record.get("warnings"))))),
            _e("; ".join(map(str, _as_list(record.get("issues"))))),
        ]
        for record in context.experiments["benchmark_canaries"]
    ]
    failures = [
        f"`{record.get('profile_id', '')}` status `{record.get('status', '')}`: "
        f"{'; '.join(map(str, _as_list(record.get('issues')))) or 'failure path recorded'}"
        for record in context.experiments["benchmark_canaries"]
        if str(record.get("status", "")) in {"failed", "warning", "refused"}
    ]
    return "\n".join(
        [
            "<h2>Benchmark Records</h2>",
            _filter_box(),
            _table(["Workspace", "Benchmark", "Name", "Domain", "Task", "Datasets", "Baselines", "Metrics", "Limitations"], rows),
            "<h2>Benchmark Canaries</h2>",
            _table(["Workspace", "Profile", "Status", "Execution", "Warnings", "Issues"], canary_rows),
            "<h2>Failures and Warnings</h2>",
            _list(failures, css_class="warning"),
        ]
    )


def _render_benchmark_suites(context: _DashboardContext) -> str:
    rows = [
        [
            _code(str(suite.get("id", ""))),
            _e(str(suite.get("name", ""))),
            _e(str(suite.get("source_profile", ""))),
            _e(", ".join(map(str, _as_list(suite.get("benchmark_ids"))))),
            _e(", ".join(map(str, _as_list(suite.get("required_tasks"))))),
            _e(", ".join(map(str, _as_list(suite.get("optional_tasks"))))),
        ]
        for suite in context.experiments["benchmark_suites"]
    ]
    return _filter_box() + _table(["Suite", "Name", "Source Profile", "Benchmarks", "Required Tasks", "Optional Tasks"], rows)


def _render_jobs(context: _DashboardContext) -> str:
    rows = [
        [
            _code(str(job.get("workspace_id", ""))),
            _code(str(job.get("id", ""))),
            _code(str(job.get("manifest_id", ""))),
            _e(str(job.get("environment_id", ""))),
            _e(str(job.get("status", ""))),
            _code(str(job.get("execution_id", ""))),
            _e(", ".join(map(str, _as_list(job.get("logs"))))),
        ]
        for job in context.experiments["jobs"]
    ]
    result_rows = [
        [
            _code(str(result.get("workspace_id", ""))),
            _code(str(result.get("job_id", ""))),
            _e(str(result.get("status", ""))),
            _e(str(result.get("returncode", ""))),
            _e(str(result.get("error", ""))),
            _e(", ".join(map(str, _as_list(result.get("result_paths"))))),
        ]
        for result in context.experiments["job_results"]
    ]
    return "\n".join(
        [
            "<p>Job log paths are shown, but stdout/stderr contents are not embedded.</p>",
            "<h2>Jobs</h2>",
            _filter_box(),
            _table(["Workspace", "Job", "Manifest", "Environment", "Status", "Execution", "Log Paths"], rows),
            "<h2>Runner Results</h2>",
            _table(["Workspace", "Job", "Status", "Return Code", "Error", "Result Paths"], result_rows),
        ]
    )


def _render_sweeps(context: _DashboardContext) -> str:
    sweep_rows = [
        [
            _code(str(record.get("workspace_id", ""))),
            _code(str(record.get("id", ""))),
            _e(str(record.get("name", ""))),
            _code(str(record.get("base_manifest_id", ""))),
            _e(str(record.get("status", ""))),
            str(len(_as_list(record.get("generated_manifest_ids")))),
        ]
        for record in context.experiments["sweeps"]
    ]
    ablation_rows = [
        [
            _code(str(record.get("workspace_id", ""))),
            _code(str(record.get("id", ""))),
            _e(str(record.get("name", ""))),
            _e(", ".join(map(str, _as_list(record.get("factors"))))),
            _e(", ".join(map(str, _as_list(record.get("controls"))))),
            str(len(_as_list(record.get("generated_manifest_ids")))),
        ]
        for record in context.experiments["ablation_plans"]
    ]
    seed_rows = [
        [
            _code(str(record.get("workspace_id", ""))),
            _code(str(record.get("id", ""))),
            _e(", ".join(map(str, _as_list(record.get("seeds"))))),
            str(len(_as_list(record.get("generated_manifest_ids")))),
            _e(str(record.get("rationale", ""))),
        ]
        for record in context.experiments["seed_plans"]
    ]
    return "\n".join(
        [
            "<h2>Parameter Sweeps</h2>",
            _filter_box(),
            _table(["Workspace", "Sweep", "Name", "Base Manifest", "Status", "Generated Manifests"], sweep_rows),
            "<h2>Ablations</h2>",
            _table(["Workspace", "Ablation", "Name", "Factors", "Controls", "Generated Manifests"], ablation_rows),
            "<h2>Seed Plans</h2>",
            _table(["Workspace", "Seed Plan", "Seeds", "Generated Manifests", "Rationale"], seed_rows),
        ]
    )


def _render_result_tables(context: _DashboardContext) -> str:
    rows: list[list[str]] = []
    failed: list[str] = []
    for table in context.experiments["result_tables"]:
        for row in _as_list(table.get("rows")):
            if not isinstance(row, dict):
                continue
            rows.append(
                [
                    _code(str(table.get("workspace_id", ""))),
                    _code(str(row.get("execution_id", ""))),
                    _code(str(row.get("benchmark_id", ""))),
                    _code(str(row.get("baseline_id", ""))),
                    _code(str(row.get("metric_id", ""))),
                    _e(str(row.get("run_type", ""))),
                    _e(str(row.get("value", ""))),
                    _code(str(row.get("artifact_id", ""))),
                ]
            )
        failed.extend(map(str, _as_list(table.get("failed_execution_ids"))))
    aggregate_rows = []
    for payload in context.experiments["aggregate_results"]:
        aggregates = payload if isinstance(payload, list) else _as_list(payload.get("items"))
        for aggregate in aggregates:
            if not isinstance(aggregate, dict):
                continue
            aggregate_rows.append(
                [
                    _code(str(aggregate.get("workspace_id", ""))),
                    _code(str(aggregate.get("id", ""))),
                    _code(str(aggregate.get("metric_id", ""))),
                    _code(str(aggregate.get("baseline_id", ""))),
                    _e(str(aggregate.get("n", ""))),
                    _e(str(aggregate.get("mean", ""))),
                    _e(str(aggregate.get("std", ""))),
                ]
            )
    return "\n".join(
        [
            "<h2>Result Table Rows</h2>",
            _filter_box(),
            _table(["Workspace", "Execution", "Benchmark", "Baseline", "Metric", "Run Type", "Value", "Artifact"], rows),
            "<h2>Aggregate Results</h2>",
            _table(["Workspace", "Aggregate", "Metric", "Baseline", "N", "Mean", "Std"], aggregate_rows),
            "<h2>Failed Runs Excluded From Aggregates</h2>",
            _list(failed, css_class="warning"),
        ]
    )


def _render_error_analysis(context: _DashboardContext) -> str:
    rows = [
        [
            _code(str(report.get("workspace_id", ""))),
            _code(str(report.get("execution_id", ""))),
            _e("; ".join(map(str, _as_list(report.get("top_error_types"))))),
            _e(str(len(_as_list(report.get("slices"))))),
            _e("; ".join(map(str, _as_list(report.get("limitations"))))),
        ]
        for report in context.experiments["error_analysis"]
    ]
    return _filter_box() + _table(["Workspace", "Execution", "Top Error Types", "Slices", "Limitations"], rows)


def _render_leaderboard(context: _DashboardContext) -> str:
    comparison_rows = [
        [
            _code(str(comparison.get("workspace_id", ""))),
            _code(str(comparison.get("benchmark_id", ""))),
            str(len(_as_list(comparison.get("baseline_results")))),
            str(len(_as_list(comparison.get("proposed_method_results")))),
            _e("; ".join(map(str, _as_list(comparison.get("missing_baselines"))))),
            _e("; ".join(map(str, _as_list(comparison.get("limitations"))))),
        ]
        for comparison in context.experiments["benchmark_comparisons"]
    ]
    leaderboard_rows = []
    for report in context.experiments["leaderboards"]:
        for row in _as_list(report.get("rows")):
            if not isinstance(row, dict):
                continue
            leaderboard_rows.append(
                [
                    _code(str(report.get("workspace_id", ""))),
                    _code(str(report.get("benchmark_id", ""))),
                    _e(str(row.get("method", ""))),
                    _code(str(row.get("metric_id", ""))),
                    _e(str(row.get("value", ""))),
                    _e(str(row.get("run_type", ""))),
                    _e(str(row.get("source", ""))),
                ]
            )
    return "\n".join(
        [
            "<h2>Benchmark Comparisons</h2>",
            _filter_box(),
            _table(["Workspace", "Benchmark", "Baseline Rows", "Proposed Rows", "Missing Baselines", "Limitations"], comparison_rows),
            "<h2>Leaderboard Rows</h2>",
            _table(["Workspace", "Benchmark", "Method", "Metric", "Value", "Run Type", "Source"], leaderboard_rows),
        ]
    )


def _render_replication_packages(context: _DashboardContext) -> str:
    package_rows = [
        [
            _code(str(package.get("workspace_id", ""))),
            _code(str(package.get("id", ""))),
            _e(str(package.get("safe_to_share", ""))),
            _e(", ".join(map(str, _as_list(package.get("execution_ids"))))),
            _e("; ".join(map(str, _as_list(package.get("missing_requirements"))))),
            _e(str(package.get("manifest_path", ""))),
        ]
        for package in context.experiments["replication_packages"]
    ]
    verification_rows = [
        [
            _code(str(verification.get("workspace_id", ""))),
            _code(str(verification.get("package_id", ""))),
            _e(str(verification.get("status", ""))),
            _e("; ".join(f"{key}: {value}" for key, value in verification.get("checks", {}).items())),
            _e("; ".join(map(str, _as_list(verification.get("blockers"))))),
        ]
        for verification in context.experiments["replication_verifications"]
    ]
    return "\n".join(
        [
            "<h2>Replication Packages</h2>",
            _filter_box(),
            _table(["Workspace", "Package", "Safe To Share", "Executions", "Missing Requirements", "Manifest"], package_rows),
            "<h2>Verification Attempts</h2>",
            _table(["Workspace", "Package", "Status", "Checks", "Blockers"], verification_rows),
        ]
    )


def _render_reproduction_matrix(context: _DashboardContext) -> str:
    matrix_rows = [
        [
            _code(str(matrix.get("workspace_id", ""))),
            _code(str(matrix.get("package_id", ""))),
            _e(", ".join(map(str, _as_list(matrix.get("environments"))))),
            _e(str(matrix.get("pass_count", ""))),
            _e(str(matrix.get("warning_count", ""))),
            _e(str(matrix.get("fail_count", ""))),
            _e("; ".join(map(str, _as_list(matrix.get("differences"))))),
        ]
        for matrix in context.experiments["reproducibility_matrices"]
    ]
    reproduction_rows = [
        [
            _code(str(record.get("workspace_id", ""))),
            _code(str(record.get("id", ""))),
            _code(str(record.get("package_id", ""))),
            _e(str(record.get("environment", ""))),
            _e(str(record.get("status", ""))),
            _e("; ".join(map(str, _as_list(record.get("errors"))))),
        ]
        for record in context.experiments["reproductions"]
    ]
    return "\n".join(
        [
            "<p>No single environment result should be generalized to all compute settings.</p>",
            "<h2>Reproducibility Matrix</h2>",
            _filter_box(),
            _table(["Workspace", "Package", "Environments", "Pass", "Warning", "Fail", "Differences"], matrix_rows),
            "<h2>Reproduction Attempts</h2>",
            _table(["Workspace", "Reproduction", "Package", "Environment", "Status", "Errors"], reproduction_rows),
        ]
    )


def _render_v7_release_gate(context: _DashboardContext) -> str:
    if not context.experiments["v7_release_gate"]:
        return "<p>No v0.7 release-gate report is available. Run <code>gapforge v7-release-gate --write-report</code>.</p>"
    latest = context.experiments["v7_release_gate"][-1]
    requirements = latest.get("requirements", {})
    real_requirements = latest.get("real_benchmark_requirements", {})
    rows = [[_code(str(key)), _e(str(value))] for key, value in requirements.items()] if isinstance(requirements, dict) else []
    real_rows = (
        [[_code(str(key)), _e(str(value))] for key, value in real_requirements.items()] if isinstance(real_requirements, dict) else []
    )
    return "\n".join(
        [
            f'<div class="{"card" if latest.get("passed") else "card warning"}">'
            f"<h2>v0.7 Benchmark Release Gate: {_e('PASSED' if latest.get('passed') else 'NOT PASSED')}</h2>"
            f"<p>Fixture gate passed: {_e(str(latest.get('fixture_gate_passed', False)))}</p>"
            f"<p>Real benchmark claimed: {_e(str(latest.get('real_benchmark_claimed', False)))}</p></div>",
            "<h2>Fixture Requirements</h2>",
            _table(["Requirement", "Passed"], rows),
            "<h2>Real Benchmark Claim Requirements</h2>",
            _table(["Requirement", "Passed"], real_rows),
            "<h2>Blockers</h2>",
            _list([str(item) for item in _as_list(latest.get("blockers"))], css_class="warning"),
            "<h2>Warnings</h2>",
            _list([str(item) for item in _as_list(latest.get("warnings"))], css_class="warning"),
        ]
    )


def _render_manuscripts(context: _DashboardContext) -> str:
    states = context.manuscripts["states"]
    rows = []
    for state in states:
        manuscript = _dict(state.get("manuscript"))
        manuscript_id = str(manuscript.get("id", ""))
        rows.append(
            [
                _code(manuscript_id),
                _e(str(manuscript.get("title", ""))),
                _code(str(manuscript.get("project_id", ""))),
                _code(str(manuscript.get("direction_id", ""))),
                _e(str(manuscript.get("target_venue", ""))),
                _e(str(manuscript.get("status", ""))),
                str(len(_as_list(state.get("sections")))),
                str(len(_as_list(state.get("claim_uses")))),
                _e("; ".join(_manuscript_blockers(context, manuscript_id))),
            ]
        )
    return "\n".join(
        [
            "<p>Manuscript readiness is summarized from manuscript metadata and generated audit artifacts. "
            "Missing reports remain visible as missing.</p>",
            _filter_box(),
            _table(["Manuscript", "Title", "Project", "Direction", "Venue", "Status", "Sections", "Claims", "Visible Blockers"], rows),
        ]
    )


def _render_manuscript_sections(context: _DashboardContext) -> str:
    section_rows = [
        [
            _code(str(section.get("manuscript_id", ""))),
            _code(str(section.get("id", ""))),
            _e(str(section.get("section_type", ""))),
            _e(str(section.get("title", ""))),
            _e(str(section.get("status", ""))),
            _e(", ".join(map(str, _as_list(section.get("source_claim_ids"))))),
            _e(", ".join(map(str, _as_list(section.get("source_paper_ids"))))),
            _e(", ".join(map(str, _as_list(section.get("source_result_ids"))))),
            _e(", ".join(map(str, _as_list(section.get("source_artifact_ids"))))),
            _e("; ".join(map(str, _as_list(section.get("warnings"))))),
        ]
        for section in context.manuscripts["sections"]
    ]
    claim_rows = [
        [
            _code(str(claim.get("manuscript_id", ""))),
            _code(str(claim.get("section_id", ""))),
            _code(str(claim.get("claim_id", ""))),
            _e(str(claim.get("use_type", ""))),
            _e(str(claim.get("support_status", ""))),
            _e(str(claim.get("claim_text", ""))),
            _e(", ".join(map(str, _as_list(claim.get("evidence_locators"))))),
            _e(", ".join(map(str, _as_list(claim.get("citation_keys"))))),
            _e(str(claim.get("requires_softening", ""))),
        ]
        for claim in context.manuscripts["claim_uses"]
    ]
    return "\n".join(
        [
            "<h2>Sections</h2>",
            _filter_box(),
            _table(
                ["Manuscript", "Section", "Type", "Title", "Status", "Claims", "Papers", "Results", "Artifacts", "Warnings"],
                section_rows,
            ),
            "<h2>Claim Uses</h2>",
            _table(
                ["Manuscript", "Section", "Claim", "Use", "Support", "Text", "Evidence", "Citations", "Softening"],
                claim_rows,
            ),
        ]
    )


def _render_manuscript_bibliography(context: _DashboardContext) -> str:
    entry_rows = []
    known_keys: set[str] = set()
    for record in context.manuscripts["bibliographies"]:
        manuscript_id = str(record.get("manuscript_id", ""))
        for entry in _as_list(record.get("entries")):
            if not isinstance(entry, dict):
                continue
            key = str(entry.get("citation_key", ""))
            known_keys.add(key)
            entry_rows.append(
                [
                    _code(manuscript_id),
                    _code(key),
                    _code(str(entry.get("paper_id", ""))),
                    _e(str(entry.get("title", ""))),
                    _e("; ".join(map(str, _as_list(entry.get("authors"))))),
                    _e(str(entry.get("year", ""))),
                    _e(str(entry.get("venue", ""))),
                    _e(str(entry.get("doi", "") or entry.get("arxiv_id", "") or entry.get("url", ""))),
                ]
            )
    unresolved_rows = []
    for claim in context.manuscripts["claim_uses"]:
        for raw_key in _as_list(claim.get("citation_keys")):
            citation_key = str(raw_key)
            if citation_key in known_keys:
                continue
            unresolved_rows.append(
                [
                    _code(str(claim.get("manuscript_id", ""))),
                    _code(str(claim.get("claim_id", ""))),
                    _e(citation_key),
                    _e("fake-looking unresolved citation" if suspicious_citation_string(citation_key) else "unresolved citation key"),
                ]
            )
    warning_rows = []
    for record in context.manuscripts["bibliographies"]:
        for paper_id, fields in _dict(record.get("missing_metadata")).items():
            warning_rows.append(
                [_code(str(record.get("manuscript_id", ""))), _code(str(paper_id)), _e(", ".join(map(str, _as_list(fields))))]
            )
        for duplicate, canonical in _dict(record.get("duplicate_entries")).items():
            warning_rows.append([_code(str(record.get("manuscript_id", ""))), _code(str(duplicate)), _e(f"duplicate of {canonical}")])
    return "\n".join(
        [
            "<h2>Known Bibliography Entries</h2>",
            _filter_box(),
            _table(["Manuscript", "Citation Key", "Paper", "Title", "Authors", "Year", "Venue", "Locator"], entry_rows),
            "<h2>Unresolved/Fake-Looking Citations</h2>",
            _table(["Manuscript", "Claim", "Citation", "Status"], unresolved_rows),
            "<h2>Metadata Warnings</h2>",
            _table(["Manuscript", "Paper/Entry", "Warning"], warning_rows),
        ]
    )


def _render_manuscript_traceability(context: _DashboardContext) -> str:
    summary_rows = [
        [
            _code(str(report.get("manuscript_id", ""))),
            _e(str(report.get("claim_count", ""))),
            _e(str(report.get("supported_claim_count", ""))),
            _e(str(report.get("unsupported_claim_count", ""))),
            _e(str(report.get("empirical_claim_count", ""))),
            _e(str(report.get("novelty_claim_count", ""))),
            _e(str(report.get("limitation_claim_count", ""))),
            _e("; ".join(map(str, _as_list(report.get("blocking_issues"))))),
        ]
        for report in context.manuscripts["traceability_reports"]
    ]
    unsupported_rows = [
        [_code(str(report.get("manuscript_id", ""))), _code(str(claim_id))]
        for report in context.manuscripts["traceability_reports"]
        for claim_id in _as_list(report.get("unsupported_claims"))
    ]
    warning_rows = [
        [
            _code(str(warning.get("manuscript_id", report.get("manuscript_id", "")))),
            _code(str(warning.get("section_id", ""))),
            _e(str(warning.get("warning_type", ""))),
            _e(str(warning.get("severity", ""))),
            _e(str(warning.get("text", ""))),
            _e(str(warning.get("suggested_fix", ""))),
        ]
        for report in context.manuscripts["traceability_reports"]
        for warning in _dict_items(report.get("overclaim_warnings"))
    ]
    return "\n".join(
        [
            "<h2>Traceability Summary</h2>",
            _filter_box(),
            _table(
                ["Manuscript", "Claims", "Supported", "Unsupported", "Empirical", "Novelty", "Limitations", "Blocking Issues"],
                summary_rows,
            ),
            "<h2>Unsupported Claims</h2>",
            _table(["Manuscript", "Claim"], unsupported_rows),
            "<h2>Overclaim Warnings</h2>",
            _table(["Manuscript", "Section", "Type", "Severity", "Text", "Suggested Fix"], warning_rows),
        ]
    )


def _render_manuscript_figures_tables(context: _DashboardContext) -> str:
    figure_rows = [
        [
            _code(str(figure.get("manuscript_id", ""))),
            _code(str(figure.get("id", ""))),
            _e(str(figure.get("figure_type", ""))),
            _e(str(figure.get("title", ""))),
            _e(str(figure.get("caption", ""))),
            _e(", ".join(map(str, _as_list(figure.get("source_artifact_ids"))))),
            _e(str(figure.get("status", ""))),
            _e(_safe_path_label(str(figure.get("path", "")))),
        ]
        for figure in context.manuscripts["figures"]
    ]
    table_rows = [
        [
            _code(str(table.get("manuscript_id", ""))),
            _code(str(table.get("id", ""))),
            _e(str(table.get("table_type", ""))),
            _e(str(table.get("title", ""))),
            _e(str(table.get("caption", ""))),
            _e(", ".join(map(str, _as_list(table.get("source_result_ids"))))),
            _e(", ".join(map(str, _as_list(table.get("source_artifact_ids"))))),
            _e(str(table.get("status", ""))),
            _e(_safe_path_label(str(table.get("path", "")))),
        ]
        for table in context.manuscripts["tables"]
    ]
    return "\n".join(
        [
            "<p>Figures and tables list source result/artifact identifiers; raw result files are not embedded here.</p>",
            "<h2>Figures</h2>",
            _filter_box(),
            _table(["Manuscript", "Figure", "Type", "Title", "Caption", "Artifacts", "Status", "Path"], figure_rows),
            "<h2>Tables</h2>",
            _table(["Manuscript", "Table", "Type", "Title", "Caption", "Results", "Artifacts", "Status", "Path"], table_rows),
        ]
    )


def _render_manuscript_submission_checklist(context: _DashboardContext) -> str:
    check_rows = []
    blocker_rows = []
    for checklist in context.manuscripts["submission_checklists"]:
        manuscript_id = str(checklist.get("manuscript_id", ""))
        for name, value in _dict(checklist.get("checks")).items():
            check_rows.append([_code(manuscript_id), _code(str(name)), _e(str(value))])
        for issue in _as_list(checklist.get("blocking_issues")):
            blocker_rows.append([_code(manuscript_id), _e(str(issue)), _e(str(checklist.get("status", "")))])
        for warning in _as_list(checklist.get("warnings")):
            blocker_rows.append([_code(manuscript_id), _e(str(warning)), _e("warning")])
    return "\n".join(
        [
            "<h2>Checks</h2>",
            _filter_box(),
            _table(["Manuscript", "Check", "Result"], check_rows),
            "<h2>Blockers And Warnings</h2>",
            _table(["Manuscript", "Issue", "Status"], blocker_rows),
        ]
    )


def _render_manuscript_artifact_evaluation(context: _DashboardContext) -> str:
    rows = [
        [
            _code(str(package.get("manuscript_id", ""))),
            _code(str(package.get("id", ""))),
            _code(str(package.get("workspace_id", ""))),
            _code(str(package.get("replication_package_id", ""))),
            _e(str(package.get("status", ""))),
            _e(", ".join(map(str, _as_list(package.get("expected_badges"))))),
            _e("; ".join(map(str, _as_list(package.get("expected_outputs"))))),
            str(len(_as_list(package.get("files")))),
        ]
        for package in context.manuscripts["artifact_packages"]
    ]
    return "\n".join(
        [
            "<p>Artifact packages are summarized from package manifests. Restricted data and logs are not embedded.</p>",
            _filter_box(),
            _table(["Manuscript", "Package", "Workspace", "Replication", "Status", "Expected Badges", "Expected Outputs", "Files"], rows),
        ]
    )


def _render_manuscript_reviewer_panel(context: _DashboardContext) -> str:
    panel_rows = [
        [
            _code(str(panel.get("manuscript_id", ""))),
            _e(str(panel.get("decision_risk", ""))),
            _e("; ".join(map(str, _as_list(panel.get("fatal_flaws"))))),
            _e("; ".join(map(str, _as_list(panel.get("required_fixes"))))),
            _e(str(panel.get("area_chair_summary", ""))),
        ]
        for panel in context.manuscripts["review_panels"]
    ]
    review_rows = []
    for panel in context.manuscripts["review_panels"]:
        manuscript_id = str(panel.get("manuscript_id", ""))
        for review in _dict_items(panel.get("reviewer_reports")):
            review_rows.append(
                [
                    _code(manuscript_id),
                    _code(str(review.get("reviewer_id", ""))),
                    _e(str(review.get("role", ""))),
                    _e(str(review.get("score", ""))),
                    _e("; ".join(map(str, _as_list(review.get("fatal_flaws"))))),
                    _e("; ".join(map(str, _as_list(review.get("required_fixes"))))),
                    _e(", ".join(map(str, _as_list(review.get("evidence_or_prior_work"))))),
                ]
            )
    return "\n".join(
        [
            "<h2>Panel Summary</h2>",
            _filter_box(),
            _table(["Manuscript", "Decision Risk", "Fatal Flaws", "Required Fixes", "Area Chair"], panel_rows),
            "<h2>Reviewer Reports</h2>",
            _table(["Manuscript", "Reviewer", "Role", "Score", "Fatal Flaws", "Required Fixes", "Evidence"], review_rows),
        ]
    )


def _render_manuscript_rebuttal(context: _DashboardContext) -> str:
    rebuttal_rows = [
        [
            _code(str(item.get("manuscript_id", ""))),
            _code(str(item.get("id", ""))),
            _code(str(item.get("reviewer_id", ""))),
            _e(str(item.get("status", ""))),
            _e(str(item.get("objection", ""))),
            _e(str(item.get("response_strategy", ""))),
            _e("; ".join(map(str, _as_list(item.get("evidence_needed"))))),
            _e("; ".join(map(str, _as_list(item.get("experiments_needed"))))),
            _e("; ".join(map(str, _as_list(item.get("citations_needed"))))),
            _e("; ".join(map(str, _as_list(item.get("claim_softening_needed"))))),
        ]
        for item in context.manuscripts["rebuttal_items"]
    ]
    revision_rows = [
        [
            _code(str(plan.get("manuscript_id", ""))),
            _code(str(plan.get("id", ""))),
            _e(str(plan.get("status", ""))),
            _e("; ".join(map(str, _as_list(plan.get("section_edits"))))),
            _e("; ".join(map(str, _as_list(plan.get("required_experiments"))))),
            _e("; ".join(map(str, _as_list(plan.get("required_searches"))))),
            _e("; ".join(map(str, _as_list(plan.get("required_citations"))))),
        ]
        for plan in context.manuscripts["revision_plans"]
    ]
    return "\n".join(
        [
            "<h2>Rebuttal Items</h2>",
            _filter_box(),
            _table(
                [
                    "Manuscript",
                    "Item",
                    "Reviewer",
                    "Status",
                    "Objection",
                    "Strategy",
                    "Evidence Needed",
                    "Experiments",
                    "Citations",
                    "Softening",
                ],
                rebuttal_rows,
            ),
            "<h2>Revision Plans</h2>",
            _table(["Manuscript", "Plan", "Status", "Section Edits", "Experiments", "Searches", "Citations"], revision_rows),
        ]
    )


def _render_manuscript_submission_packages(context: _DashboardContext) -> str:
    rows = [
        [
            _code(str(package.get("manuscript_id", ""))),
            _code(str(package.get("id", ""))),
            _e(str(package.get("package_type", ""))),
            _code(str(package.get("venue_template_id", ""))),
            _e(str(package.get("status", ""))),
            _code(str(package.get("checklist_id", ""))),
            _code(str(package.get("anonymization_report_id", ""))),
            _code(str(package.get("artifact_package_id", ""))),
            _e(", ".join(_safe_path_label(str(item)) for item in _as_list(package.get("files")))),
        ]
        for package in context.manuscripts["submission_packages"]
    ]
    return _filter_box() + _table(
        ["Manuscript", "Package", "Type", "Venue", "Status", "Checklist", "Anonymization", "Artifact Package", "Files"],
        rows,
    )


def _render_v8_release_gate(context: _DashboardContext) -> str:
    report = _dict(context.manuscripts.get("v8_release_gate"))
    if not report:
        return "<p>No v0.8 manuscript release-gate report is available for this dashboard context.</p>"
    requirement_rows = [[_code(str(name)), _e(str(passed))] for name, passed in _dict(report.get("requirements")).items()]
    manuscript_rows = [
        [
            _code(str(item.get("manuscript_id", ""))),
            _e(str(item.get("status", ""))),
            _e("; ".join(map(str, _as_list(item.get("blockers"))))),
            _e("; ".join(map(str, _as_list(item.get("warnings"))))),
        ]
        for item in _dict_items(report.get("manuscripts"))
    ]
    status = "PASSED" if report.get("passed") else "NOT PASSED"
    return "\n".join(
        [
            f'<div class="{"card" if report.get("passed") else "card warning"}">'
            f"<h2>v0.8 Manuscript Release Gate: {_e(status)}</h2>"
            f"<p>Status: {_e(str(report.get('status', '')))}</p></div>",
            "<h2>Requirements</h2>",
            _filter_box(),
            _table(["Requirement", "Passed"], requirement_rows),
            "<h2>Blockers</h2>",
            _list([str(item) for item in _as_list(report.get("blockers"))], css_class="warning"),
            "<h2>Warnings</h2>",
            _list([str(item) for item in _as_list(report.get("warnings"))], css_class="warning"),
            "<h2>Manuscripts</h2>",
            _table(["Manuscript", "Status", "Blockers", "Warnings"], manuscript_rows),
        ]
    )


def _run_artifact_links(state: ResearchRunState) -> list[tuple[str, str]]:
    names = [
        "run_report.md",
        "final_report.md",
        "source_coverage.md",
        "full_text_coverage.md",
        "field_map.md",
        "gaps.md",
        "novelty_dossiers.md",
        "gap_evidence_matrix.md",
        "reviewer_simulation.md",
        "human_reviews.md",
        "review_queue.md",
    ]
    base = Path(state.run_dir)
    return [(name, f"../{name}") for name in names if (base / name).exists()]


def _project_artifact_links(program: ResearchProgramState) -> list[tuple[str, str]]:
    names = [
        "project_report.md",
        "related_work_matrix.md",
        "experiment_protocols.md",
        "review_panel.md",
        "rebuttal_plan.md",
        "meta_review.md",
        "claim_graph.md",
        "review_queue.md",
    ]
    base = Path(program.project.root_dir)
    return [(name, f"../{name}") for name in names if (base / name).exists()]


def _workspace_artifact_links(workspace_dir: Path) -> list[tuple[str, str]]:
    names = [
        "workspace.json",
        "reports/result_summary.md",
        "reports/empirical_claim_ledger.md",
        "reports/reproducibility_check.md",
        "reports/empirical_review.md",
        "paper_package_v2/README.md",
    ]
    return [(name, f"../{name}") for name in names if (workspace_dir / name).exists()]


def _manuscript_artifact_links(manuscript_root: Path) -> list[tuple[str, str]]:
    names = [
        "submission/status.md",
        "submission/manuscript_report.md",
        "submission/traceability_report.md",
        "submission/submission_checklist.md",
        "reviews/manuscript_review_panel.md",
        "reviews/rebuttal_plan_actionable.md",
    ]
    return [(name, f"../{name}") for name in names if (manuscript_root / name).exists()]


def _find_experiment_workspace_dir(project_root: Path, workspace_id: str) -> Path:
    for path in project_root.glob(f"*/experiment_workspaces/{workspace_id}"):
        if (path / "workspace.json").exists():
            return path
    raise FileNotFoundError(f"No experiment workspace found for {workspace_id}")


def _find_manuscript_root(project_root: Path, manuscript_id: str) -> Path:
    for path in project_root.glob(f"*/manuscripts/{manuscript_id}"):
        if (path / "manuscript.json").exists():
            return path
    raise FileNotFoundError(f"No manuscript found for {manuscript_id}")


def _empty_experiment_context() -> dict[str, list[dict[str, Any]]]:
    return {
        "workspaces": [],
        "manifests": [],
        "executions": [],
        "artifacts": [],
        "datasets": [],
        "baselines": [],
        "metrics": [],
        "metric_results": [],
        "empirical_claims": [],
        "reproducibility": [],
        "empirical_reviews": [],
        "paper_packages": [],
        "benchmarks": [],
        "benchmark_cards": [],
        "benchmark_suites": [],
        "benchmark_canaries": [],
        "jobs": [],
        "job_results": [],
        "sweeps": [],
        "ablation_plans": [],
        "seed_plans": [],
        "result_tables": [],
        "aggregate_results": [],
        "error_analysis": [],
        "benchmark_comparisons": [],
        "leaderboards": [],
        "replication_packages": [],
        "replication_verifications": [],
        "reproductions": [],
        "reproducibility_matrices": [],
        "v7_release_gate": [],
    }


def _empty_manuscript_context() -> dict[str, Any]:
    return {
        "roots": [],
        "states": [],
        "sections": [],
        "claim_uses": [],
        "citation_uses": [],
        "bibliographies": [],
        "traceability_reports": [],
        "figures": [],
        "tables": [],
        "submission_checklists": [],
        "artifact_packages": [],
        "review_panels": [],
        "rebuttal_items": [],
        "revision_plans": [],
        "submission_packages": [],
        "v8_release_gate": {},
    }


def _load_project_manuscript_context(project_dir: Path, config: GapForgeConfig | None) -> dict[str, Any]:
    roots = [path for path in sorted((project_dir / "manuscripts").glob("*")) if (path / "manuscript.json").exists()]
    return _load_manuscript_context(roots, config) if config is not None else _empty_manuscript_context()


def _load_manuscript_context(roots: list[Path], config: GapForgeConfig) -> dict[str, Any]:
    context = _empty_manuscript_context()
    context["roots"] = [str(root) for root in roots]
    for root in roots:
        state = _read_json_if_exists(root / "manuscript.json")
        if not state:
            continue
        manuscript_id = _state_manuscript_id(state, root)
        context["states"].append(state)
        context["sections"].extend(_tag_manuscript_records(_as_list(state.get("sections")), manuscript_id))
        context["claim_uses"].extend(_tag_manuscript_records(_as_list(state.get("claim_uses")), manuscript_id))
        context["citation_uses"].extend(_tag_manuscript_records(_as_list(state.get("citation_uses")), manuscript_id))
        _append_if_present(context["bibliographies"], root / "bibliography" / "bibliography.json", manuscript_id)
        _append_if_present(context["traceability_reports"], root / "submission" / "traceability_report.json", manuscript_id)
        for path in sorted((root / "figures").glob("*.json")):
            _append_if_present(context["figures"], path, manuscript_id)
        for path in sorted((root / "tables").glob("*.json")):
            _append_if_present(context["tables"], path, manuscript_id)
        _append_if_present(context["submission_checklists"], root / "submission" / "submission_checklist.json", manuscript_id)
        for path in sorted((root / "artifact_evaluation").glob("*/artifact_evaluation_package.json")):
            _append_if_present(context["artifact_packages"], path, manuscript_id)
        _append_if_present(context["review_panels"], root / "reviews" / "manuscript_review_panel.json", manuscript_id)
        _append_list_if_present(context["rebuttal_items"], root / "reviews" / "rebuttal_items.json", manuscript_id)
        _append_if_present(context["revision_plans"], root / "reviews" / "revision_plan.json", manuscript_id)
        for path in sorted((root / "submission" / "packages").glob("*/submission_package.json")):
            _append_if_present(context["submission_packages"], path, manuscript_id)
    context["v8_release_gate"] = V08ReleaseGateEnforcer(config).evaluate().to_dict() if roots else {}
    return context


def _load_experiment_context(base_dir: Path) -> dict[str, list[dict[str, Any]]]:
    context = _empty_experiment_context()
    workspace_dirs = _experiment_workspace_dirs(base_dir)
    for workspace_dir in workspace_dirs:
        workspace = _read_json_if_exists(workspace_dir / "workspace.json")
        workspace_id = str(workspace.get("id") or workspace_dir.name)
        if workspace:
            context["workspaces"].append(workspace)
        context["manifests"].extend(_tagged_json_files(workspace_dir / "manifests", "*.json", workspace_id))
        context["executions"].extend(_tagged_json_files(workspace_dir / "runs", "*.json", workspace_id))
        context["artifacts"].extend(_tagged_json_files(workspace_dir / "results", "result-*.artifact.json", workspace_id))
        context["datasets"].extend(_tagged_json_files(workspace_dir / "data", "dataset-*.record.json", workspace_id))
        context["baselines"].extend(_tagged_json_files(workspace_dir / "baselines", "baseline-*.record.json", workspace_id))
        context["metrics"].extend(_tagged_json_files(workspace_dir / "metrics", "metric-*.record.json", workspace_id))
        context["reproducibility"].extend(_tagged_json_files(workspace_dir / "reports", "reproducibility_check*.json", workspace_id))
        context["empirical_reviews"].extend(_tagged_json_files(workspace_dir / "reports", "empirical_review*.json", workspace_id))
        context["benchmarks"].extend(_tagged_json_files(workspace_dir / "benchmarks", "benchmark-*.record.json", workspace_id))
        context["benchmark_cards"].extend(_tagged_json_files(workspace_dir / "benchmarks" / "cards", "*.card.json", workspace_id))
        context["benchmark_canaries"].extend(
            _tagged_json_files(workspace_dir / "benchmark_canaries", "benchmark-canary-*.json", workspace_id)
        )
        for queue in _tagged_json_files(workspace_dir / "jobs", "queue-*.json", workspace_id):
            for job in _as_list(queue.get("jobs")):
                if isinstance(job, dict):
                    context["jobs"].append({**job, "workspace_id": workspace_id, "queue_id": queue.get("id", "")})
        context["job_results"].extend(_tagged_json_files(workspace_dir / "jobs", "job-*.result.json", workspace_id))
        context["sweeps"].extend(_tagged_json_files(workspace_dir / "sweeps", "sweep-*.json", workspace_id))
        context["ablation_plans"].extend(_tagged_json_files(workspace_dir / "sweeps", "ablation-*.json", workspace_id))
        context["seed_plans"].extend(_tagged_json_files(workspace_dir / "sweeps", "seed-plan-*.json", workspace_id))
        context["result_tables"].extend(_tagged_json_files(workspace_dir / "reports", "result_table.json", workspace_id))
        context["aggregate_results"].extend(_tagged_json_payloads(workspace_dir / "reports", "aggregate_results.json", workspace_id))
        context["error_analysis"].extend(_tagged_json_files(workspace_dir / "reports", "error_analysis_*.json", workspace_id))
        context["benchmark_comparisons"].extend(_tagged_json_files(workspace_dir / "reports", "benchmark_comparison_*.json", workspace_id))
        context["leaderboards"].extend(_tagged_json_files(workspace_dir / "reports", "leaderboard_*.json", workspace_id))
        context["replication_packages"].extend(
            _tagged_json_files(workspace_dir / "replication_packages", "*/replication_package.json", workspace_id)
        )
        context["replication_verifications"].extend(
            _tagged_json_files(workspace_dir / "replication_packages", "*/verification/replication_verification.json", workspace_id)
        )
        context["reproductions"].extend(_tagged_json_files(workspace_dir / "replication_packages", "*/reproductions/*.json", workspace_id))
        context["reproducibility_matrices"].extend(
            _tagged_json_files(
                workspace_dir / "replication_packages",
                "*/reproducibility_matrix/reproducibility_matrix.json",
                workspace_id,
            )
        )
        package = _read_json_if_exists(workspace_dir / "paper_package_v2" / "paper_package.json")
        if package:
            package["workspace_id"] = workspace_id
            context["paper_packages"].append(package)
        for summary in _tagged_json_files(workspace_dir / "reports", "result_summary_*.json", workspace_id):
            metric_results = _as_list(summary.get("metric_results"))
            empirical_claims = _as_list(summary.get("empirical_claims"))
            for item in metric_results:
                if isinstance(item, dict):
                    item = {**item, "workspace_id": workspace_id}
                    context["metric_results"].append(item)
            for item in empirical_claims:
                if isinstance(item, dict):
                    item = {**item, "workspace_id": workspace_id}
                    context["empirical_claims"].append(item)
    for release_dir in _candidate_release_gate_dirs(base_dir):
        context["v7_release_gate"].extend(_tagged_json_files(release_dir, "v0.7_latest.json", ""))
    return context


def _experiment_workspace_dirs(base_dir: Path) -> list[Path]:
    if (base_dir / "workspace.json").exists():
        return [base_dir]
    root = base_dir / "experiment_workspaces"
    if not root.exists():
        return []
    return sorted(path for path in root.iterdir() if path.is_dir() and (path / "workspace.json").exists())


def _candidate_release_gate_dirs(base_dir: Path) -> list[Path]:
    candidates = [base_dir / "data" / "release_gate"]
    for parent in base_dir.parents:
        candidates.append(parent / "data" / "release_gate")
    return [path for path in _dedupe_paths(candidates) if path.exists()]


def _tagged_json_files(root: Path, pattern: str, workspace_id: str) -> list[dict[str, Any]]:
    if not root.exists():
        return []
    records: list[dict[str, Any]] = []
    seen: set[Path] = set()
    for path in sorted(root.glob(pattern)):
        if path in seen:
            continue
        seen.add(path)
        raw = _read_json_if_exists(path)
        if raw:
            raw["workspace_id"] = workspace_id
            records.append(raw)
    return records


def _tagged_json_payloads(root: Path, pattern: str, workspace_id: str) -> list[Any]:
    if not root.exists():
        return []
    records: list[Any] = []
    for path in sorted(root.glob(pattern)):
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(raw, dict):
            raw["workspace_id"] = workspace_id
            records.append(raw)
        elif isinstance(raw, list):
            tagged_items = []
            for item in raw:
                tagged_items.append({**item, "workspace_id": workspace_id} if isinstance(item, dict) else item)
            records.append(tagged_items)
    return records


def _paper_package_status(context: _DashboardContext, workspace_id: str) -> str:
    package = next((item for item in context.experiments["paper_packages"] if item.get("workspace_id") == workspace_id), None)
    if not package:
        return "not exported"
    return str(package.get("readiness", "exported"))


def _execution_failed(record: dict[str, Any]) -> bool:
    return str(record.get("status", "")) == "failed" or bool(str(record.get("failure_reason", "")).strip())


def _fake_result_warnings(context: _DashboardContext) -> list[str]:
    fake_workspace_ids = {
        str(record.get("workspace_id", ""))
        for record in context.experiments["datasets"]
        if str(record.get("dataset_type", "")) in {"fixture", "synthetic", "generated"}
    }
    warnings = [
        f"Workspace `{workspace_id}` uses fixture/synthetic/generated data; results are workflow evidence, not real empirical acceptance."
        for workspace_id in sorted(fake_workspace_ids)
    ]
    for package in context.experiments["paper_packages"]:
        if package.get("workspace_id") in fake_workspace_ids and package.get("readiness") == "paper_ready_empirical":
            warnings.append(f"Workspace `{package.get('workspace_id')}` appears to accept fake results as paper-ready empirical evidence.")
    return warnings


def _load_campaign_states(program: ResearchProgramState) -> list[CampaignState]:
    states: list[CampaignState] = []
    project_dir = Path(program.project.root_dir)
    for campaign in program.campaigns:
        campaign_dir = project_dir / "campaigns" / campaign.id
        campaign_path = campaign_dir / "campaign.json"
        if not campaign_path.exists():
            continue
        raw_campaign = json.loads(campaign_path.read_text(encoding="utf-8"))
        raw_budget = _read_json_if_exists(campaign_dir / "budget.json")
        raw_acceptance = _read_json_if_exists(campaign_dir / "campaign_acceptance_summary.json")
        states.append(
            CampaignState(
                campaign=from_dict(ResearchCampaign, raw_campaign),
                steps=[from_dict(CampaignStep, item) for item in _read_list(campaign_dir / "steps.json")],
                decisions=[from_dict(CampaignDecision, item) for item in _read_list(campaign_dir / "decisions.json")],
                milestones=[from_dict(CampaignMilestone, item) for item in _read_list(campaign_dir / "milestones.json")],
                imports=[from_dict(CampaignImportRecord, item) for item in _read_list(campaign_dir / "imports.json")],
                stop_conditions=[from_dict(CampaignStopCondition, item) for item in _read_list(campaign_dir / "stop_conditions.json")],
                agent_actual_run_attestations=[
                    from_dict(AgentActualRunAttestation, item) for item in _read_list(campaign_dir / "agent_actual_run_attestations.json")
                ],
                human_reviews=[from_dict(CampaignHumanReview, item) for item in _read_list(campaign_dir / "campaign_reviews.json")],
                acceptance_summary=from_dict(CampaignAcceptanceSummary, raw_acceptance) if raw_acceptance else None,
                budget=from_dict(CampaignBudget, raw_budget) if raw_budget else None,
            )
        )
    return states


def _load_campaign_canaries(data_dir: Path, project_id: str) -> list[CampaignCanaryRecord]:
    root = data_dir / "campaign_canaries"
    records: list[CampaignCanaryRecord] = []
    if not root.exists():
        return records
    for path in sorted(root.glob("*/record.json")):
        try:
            record = from_dict(CampaignCanaryRecord, json.loads(path.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            continue
        if not record.project_id or record.project_id == project_id:
            records.append(record)
    return records


def _read_json_if_exists(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    raw = json.loads(path.read_text(encoding="utf-8"))
    return raw if isinstance(raw, dict) else {}


def _read_json_value_if_exists(path: Path) -> Any:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _read_list(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    raw = json.loads(path.read_text(encoding="utf-8"))
    return raw if isinstance(raw, list) else []


def _append_if_present(records: list[dict[str, Any]], path: Path, manuscript_id: str) -> None:
    raw = _read_json_value_if_exists(path)
    if isinstance(raw, dict):
        records.append(_tag_manuscript_record(raw, manuscript_id))


def _append_list_if_present(records: list[dict[str, Any]], path: Path, manuscript_id: str) -> None:
    raw = _read_json_value_if_exists(path)
    if isinstance(raw, dict):
        records.append(_tag_manuscript_record(raw, manuscript_id))
    elif isinstance(raw, list):
        records.extend(_tag_manuscript_records(raw, manuscript_id))


def _tag_manuscript_records(items: list[object], manuscript_id: str) -> list[dict[str, Any]]:
    return [_tag_manuscript_record(item, manuscript_id) for item in items if isinstance(item, dict)]


def _tag_manuscript_record(item: object, manuscript_id: str) -> dict[str, Any]:
    record = dict(item) if isinstance(item, dict) else {}
    record.setdefault("manuscript_id", manuscript_id)
    return record


def _state_manuscript_id(state: dict[str, Any], root: Path) -> str:
    manuscript = state.get("manuscript")
    if isinstance(manuscript, dict):
        return str(manuscript.get("id") or root.name)
    return root.name


def _manuscript_blockers(context: _DashboardContext, manuscript_id: str) -> list[str]:
    blockers: list[str] = []
    for report in context.manuscripts["traceability_reports"]:
        if str(report.get("manuscript_id", "")) != manuscript_id:
            continue
        blockers.extend(f"Unsupported claim: {item}" for item in _as_list(report.get("unsupported_claims")))
        blockers.extend(str(item) for item in _as_list(report.get("blocking_issues")))
    for checklist in context.manuscripts["submission_checklists"]:
        if str(checklist.get("manuscript_id", "")) == manuscript_id:
            blockers.extend(str(item) for item in _as_list(checklist.get("blocking_issues")))
    for panel in context.manuscripts["review_panels"]:
        if str(panel.get("manuscript_id", "")) == manuscript_id:
            blockers.extend(str(item) for item in _as_list(panel.get("fatal_flaws")))
    for item in context.manuscripts["rebuttal_items"]:
        if str(item.get("manuscript_id", "")) == manuscript_id and str(item.get("status", "")) in {"open", "deferred"}:
            blockers.append(f"Open rebuttal item: {item.get('id', '')}")
    for assessment in _dict_items(_dict(context.manuscripts.get("v8_release_gate")).get("manuscripts")):
        if str(assessment.get("manuscript_id", "")) == manuscript_id:
            blockers.extend(str(item) for item in _as_list(assessment.get("blockers")))
    return _dedupe(blockers)


def _campaign_dir_for(context: _DashboardContext, state: CampaignState) -> Path:
    return context.base_dir / "campaigns" / state.campaign.id


def _campaign_json(context: _DashboardContext, state: CampaignState, filename: str) -> dict[str, Any]:
    path = _campaign_dir_for(context, state) / filename
    if not path.exists():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return raw if isinstance(raw, dict) else {}


def _campaign_json_list(context: _DashboardContext, state: CampaignState, filename: str) -> list[dict[str, Any]]:
    path = _campaign_dir_for(context, state) / filename
    if not path.exists():
        return []
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    return raw if isinstance(raw, list) else [raw] if isinstance(raw, dict) else []


def _campaign_live_source_diagnostic(context: _DashboardContext, state: CampaignState) -> dict[str, Any]:
    diagnostic = _campaign_json(context, state, "live_source_diagnostic.json")
    if diagnostic:
        return diagnostic
    health = _campaign_json_list(context, state, "source_health.json")
    return {"source_health_checks": health}


def _as_list(value: object) -> list[object]:
    return value if isinstance(value, list) else []


def _dict(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _dict_items(value: object) -> list[dict[str, Any]]:
    return [item for item in _as_list(value) if isinstance(item, dict)]


def _safe_path_label(value: str) -> str:
    if not value:
        return ""
    path = Path(value)
    return path.name if path.is_absolute() else value


def _search_round_row(scope: str, round_item: SearchRound) -> list[str]:
    return [
        _code(scope),
        _code(round_item.id),
        _e(round_item.round_type),
        _e(round_item.status),
        _e(", ".join(round_item.sources)),
        str(len(round_item.result_paper_ids)),
        _e("; ".join(round_item.failures)),
    ]


def _state_refusal(state: CampaignState) -> bool:
    text = " ".join(condition.reason for condition in state.stop_conditions).lower()
    return any(term in text for term in ("refusal", "poor coverage", "not_ready", "not ready", "novelty unknown", "refused"))


def _coverage_warnings(reports: list[SourceCoverageReport]) -> list[str]:
    warnings = []
    for report in reports:
        warnings.extend(report.coverage_warnings)
        warnings.extend(report.missing_source_types)
        warnings.extend(f"Failed source: {source}" for source in report.failed_sources)
    return warnings


def _campaign_requires_actual_run(campaign: ResearchCampaign) -> bool:
    return campaign.mode in {"codex_task_pack", "codex_direct", "manual_handoff"}


def _record_has_actual_attestation(record: CampaignImportRecord) -> bool:
    return any(item.get("type") == "agent_actual_run_attestation" and item.get("accepted") is True for item in record.accepted_objects)


def _real_import_records(imports: list[CampaignImportRecord]) -> list[CampaignImportRecord]:
    return [record for record in imports if record.status in {"applied", "partial", "valid"} and _record_has_actual_attestation(record)]


def _attested_output_count(imports: list[CampaignImportRecord]) -> int:
    return sum(
        1
        for record in imports
        for item in record.accepted_objects
        if item.get("type") == "agent_actual_run_attestation" and item.get("accepted") is True
    )


def _default_actual_run_blocker(state: CampaignState) -> str:
    if state.campaign.mode == "fake_agent":
        return "Fake-agent campaign never counts as actual-run acceptance."
    if not _campaign_requires_actual_run(state.campaign):
        return "Deterministic campaign does not require actual-run acceptance."
    if not _real_import_records(state.imports):
        return "No attested validated Codex/GPT-5.4 import is present."
    if not state.human_reviews:
        return "No campaign human review is recorded."
    return "No campaign acceptance summary is recorded."


def _release_gate_blockers(context: _DashboardContext) -> list[str]:
    blockers: list[str] = []
    if not context.campaign_states:
        blockers.append("No campaigns are recorded for this project.")
    if not any(state.acceptance_summary and state.acceptance_summary.release_gate_eligible for state in context.campaign_states):
        blockers.append("No campaign is release-gate eligible with attested real Codex/GPT-5.4 output and human acceptance.")
    for state in context.campaign_states:
        if state.campaign.mode == "fake_agent" and not any(
            candidate.acceptance_summary and candidate.acceptance_summary.release_gate_eligible for candidate in context.campaign_states
        ):
            blockers.append(f"`{state.campaign.id}` is fake-agent only and cannot count as actual-run acceptance.")
        elif _campaign_requires_actual_run(state.campaign):
            if not _real_import_records(state.imports):
                blockers.append(f"`{state.campaign.id}` lacks an attested validated Codex/GPT-5.4 import.")
            if not state.human_reviews:
                blockers.append(f"`{state.campaign.id}` lacks campaign human review.")
        if state.acceptance_summary:
            blockers.extend(f"`{state.campaign.id}`: {item}" for item in state.acceptance_summary.blocking_failures)
    return _dedupe(blockers)


def _release_gate_next_commands(context: _DashboardContext, blockers: list[str]) -> list[str]:
    commands: list[str] = []
    if not context.campaign_states or not any(
        state.acceptance_summary and state.acceptance_summary.release_gate_eligible for state in context.campaign_states
    ):
        commands.append("gapforge campaign-canary-run --profile single_task_codex_handoff --real")
    text = " ".join(blockers).lower()
    if "attestation" in text:
        commands.append(
            'gapforge attest-agent-run --task-id <task-id> --agent codex --model gpt-5.4 --method task_pack --attester "<name>"'
        )
    if "human review" in text:
        commands.append('gapforge campaign-review --campaign-id <campaign-id> --accept --reviewer "<name>"')
    if "validated codex" in text or "import" in text:
        commands.append("gapforge validate-import-all --campaign-id <campaign-id>")
    commands.extend(
        [
            "gapforge campaign-canary-run --profile agentic_low_fpr_collusion --real",
            "gapforge campaign-canary-run --profile agentic_undercovered_refusal --real",
            "gapforge campaign-canary-run --profile manual_pdf_codex_reading_handoff --real",
        ]
    )
    return _dedupe(commands)


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if item and item not in seen:
            result.append(item)
            seen.add(item)
    return result


def _dedupe_paths(items: list[Path]) -> list[Path]:
    seen: set[Path] = set()
    result: list[Path] = []
    for item in items:
        resolved = item.resolve()
        if resolved in seen:
            continue
        result.append(item)
        seen.add(resolved)
    return result


def _metric(label: str, value: object) -> str:
    return f'<div class="card"><div class="muted">{_e(label)}</div><strong>{_e(str(value))}</strong></div>'


def _direction_cards(directions: list[dict[str, Any]]) -> str:
    if not directions:
        return "<p>No project directions available.</p>"
    cards = []
    for direction in directions:
        cards.append(
            '<div class="card">'
            f"<strong>{_e(str(direction['title']))}</strong><br>"
            f'<span class="muted">{_e(str(direction["id"]))} · {_e(str(direction["maturity"]))} · '
            f"{float(direction['readiness_score']):.2f}</span><br>"
            f"{_e('; '.join(direction['blocking_issues']) or 'No blocking issues recorded.')}"
            "</div>"
        )
    return '<div class="grid">' + "".join(cards) + "</div>"


def _rejected_ideas(ideas: list[RejectedIdea]) -> str:
    if not ideas:
        return "<p>No rejected ideas recorded.</p>"
    return _table(
        ["ID", "Idea", "Reason"],
        [[_code(idea.id), _e(idea.idea), _e(idea.reason)] for idea in ideas],
    )


def _artifact_links(links: list[tuple[str, str]]) -> str:
    if not links:
        return "<p>No markdown artifacts found next to this dashboard.</p>"
    return "<ul>" + "".join(f'<li><a href="{_e(href)}">{_e(label)}</a></li>' for label, href in links) + "</ul>"


def _open_queue_items(queue: ReviewQueue | None) -> list[Any]:
    return [item for item in (queue.items if queue else []) if item.status == "open"]


def _review_queue_table(queue: ReviewQueue | None) -> str:
    if queue is None:
        return "<p>No review queue has been generated yet.</p>"
    rows = [
        [
            _code(item.id),
            _e(item.status),
            _e(item.priority),
            _e(f"{item.object_type}:{item.object_id}"),
            _code(item.run_id) if item.run_id else "",
            _e(item.requested_by_skill),
            _e(item.assigned_to or "unassigned"),
            _e(item.reason),
        ]
        for item in queue.items
    ]
    return _filter_box() + _table(["ID", "Status", "Priority", "Object", "Run", "Requested By", "Assigned", "Reason"], rows)


def _filter_box() -> str:
    return '<input class="search" type="search" placeholder="Filter rows..." oninput="filterRows(this.value)">'


def _table(headers: list[str], rows: list[list[str]]) -> str:
    if not rows:
        return "<p>No records available.</p>"
    header_html = "".join(f"<th>{_e(header)}</th>" for header in headers)
    row_html = []
    for row in rows:
        filter_text = html.unescape(" ".join(row))
        row_html.append(f'<tr data-filter="{_e(filter_text)}">' + "".join(f"<td>{cell}</td>" for cell in row) + "</tr>")
    return f"<table><thead><tr>{header_html}</tr></thead><tbody>{''.join(row_html)}</tbody></table>"


def _list(items: list[str], *, css_class: str = "") -> str:
    if not items:
        return "<p>None recorded.</p>"
    class_attr = f' class="{_e(css_class)}"' if css_class else ""
    return f"<ul{class_attr}>" + "".join(f"<li>{_e(item)}</li>" for item in items) + "</ul>"


def _link(url: str, label: str) -> str:
    safe_url = _e(url)
    return f'<a href="{safe_url}">{_e(label)}</a>'


def _code(value: str) -> str:
    return f"<code>{_e(value)}</code>"


def _e(value: object) -> str:
    return html.escape(str(value), quote=True)


def dashboard_manifest(result: DashboardResult) -> str:
    return json.dumps(
        {
            "root": str(result.root),
            "index_path": str(result.index_path),
            "pages": [str(path) for path in result.pages],
        },
        indent=2,
    )
