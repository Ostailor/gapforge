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
from gapforge.models import (
    CampaignAcceptanceSummary,
    CampaignBudget,
    CampaignCanaryRecord,
    CampaignDecision,
    CampaignHumanReview,
    CampaignImportRecord,
    CampaignMilestone,
    CampaignStep,
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
    SourceCoverageReport,
    from_dict,
)
from gapforge.project_memory import ProjectMemoryManager
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

    def build_project(self, project_id: str) -> DashboardResult:
        program = self.project_manager.load_project(project_id)
        states = [self.state_manager.load_run(run_id) for run_id in program.run_ids]
        context = _DashboardContext.from_project(program, states)
        return _write_dashboard(Path(program.project.root_dir) / "dashboard", context)

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
        )

    @classmethod
    def from_project(cls, program: ResearchProgramState, states: list[ResearchRunState]) -> _DashboardContext:
        coverage_reports = [state.source_coverage for state in states if state.source_coverage is not None]
        campaign_states = _load_campaign_states(program)
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
            "<h2>Fake Run Warnings</h2>",
            _list(fake_warnings, css_class="warning"),
            "<h2>Acceptance Blockers</h2>",
            _list(blockers, css_class="warning"),
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


def _read_list(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    raw = json.loads(path.read_text(encoding="utf-8"))
    return raw if isinstance(raw, list) else []


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


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if item and item not in seen:
            result.append(item)
            seen.add(item)
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
