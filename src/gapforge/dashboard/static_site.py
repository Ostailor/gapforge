"""Dependency-free static HTML dashboards for runs and projects."""

from __future__ import annotations

import html
import json
import webbrowser
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from gapforge.config import GapForgeConfig
from gapforge.models import (
    EvidenceSpan,
    Gap,
    HumanReviewRecord,
    NoveltyDossier,
    Paper,
    RejectedIdea,
    ResearchProgramState,
    ResearchRunState,
    ReviewPanel,
    ReviewQueue,
    SourceCoverageReport,
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
        )

    @classmethod
    def from_project(cls, program: ResearchProgramState, states: list[ResearchRunState]) -> _DashboardContext:
        coverage_reports = [state.source_coverage for state in states if state.source_coverage is not None]
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


def _coverage_warnings(reports: list[SourceCoverageReport]) -> list[str]:
    warnings = []
    for report in reports:
        warnings.extend(report.coverage_warnings)
        warnings.extend(report.missing_source_types)
        warnings.extend(f"Failed source: {source}" for source in report.failed_sources)
    return warnings


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
