"""Related-work completion campaign for the selected benchmark."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from gapforge.config import GapForgeConfig
from gapforge.models import Paper, Provenance, from_dict, to_plain
from gapforge.project_memory import ProjectMemoryManager
from gapforge.selected_benchmark.related_work import REQUIRED_RELATED_WORK_CATEGORIES
from gapforge.selected_benchmark.spec import SelectedBenchmarkManager
from gapforge.state import ResearchStateManager, slugify, utc_now_iso


@dataclass(slots=True)
class CategoryStatus:
    category: str
    real_paper_ids: list[str] = field(default_factory=list)
    fallback_paper_ids: list[str] = field(default_factory=list)
    closest_prior_work_ids: list[str] = field(default_factory=list)
    status: str = "missing"
    notes: list[str] = field(default_factory=list)
    provenance: Provenance = field(default_factory=lambda: Provenance(created_by_skill="selected-related-work-completion"))


@dataclass(slots=True)
class RelatedWorkCompletionStatus:
    id: str
    benchmark_id: str
    required_categories: list[str] = field(default_factory=list)
    category_statuses: dict[str, CategoryStatus] = field(default_factory=dict)
    missing_categories: list[str] = field(default_factory=list)
    attached_paper_ids: list[str] = field(default_factory=list)
    real_paper_count: int = 0
    fallback_paper_count: int = 0
    novelty_status: str = "unknown"
    blockers: list[str] = field(default_factory=list)
    provenance: Provenance = field(default_factory=lambda: Provenance(created_by_skill="selected-related-work-completion"))


class RelatedWorkCompletionManager:
    """Classify attached related-work records and produce category-specific search work."""

    def __init__(self, config: GapForgeConfig) -> None:
        self.config = config
        self.config.ensure_dirs()
        self.project_manager = ProjectMemoryManager(config)
        self.state_manager = ResearchStateManager(config)
        self.benchmark_manager = SelectedBenchmarkManager(config)

    def complete(self, benchmark_id: str) -> RelatedWorkCompletionStatus:
        spec = self.benchmark_manager.load_spec(benchmark_id)
        papers = self._papers_for_benchmark(benchmark_id)
        category_statuses = {
            category: self._category_status(benchmark_id, category, papers) for category in REQUIRED_RELATED_WORK_CATEGORIES
        }
        missing_categories = [category for category, status in category_statuses.items() if status.status in {"missing", "partial"}]
        real_paper_ids = sorted({paper.id for paper in papers if _is_real_paper(paper)})
        fallback_paper_ids = sorted({paper.id for paper in papers if _is_fallback_paper(paper)})
        blockers = []
        if missing_categories:
            blockers.append(f"Missing real paper records for required categories: {', '.join(missing_categories)}.")
        if any(status.fallback_paper_ids and not status.real_paper_ids for status in category_statuses.values()):
            blockers.append("Fallback-only records do not complete required related-work categories.")
        novelty_status = "coverage_complete_review_required" if not missing_categories else "unknown"
        status = RelatedWorkCompletionStatus(
            id=f"related-work-completion-{slugify(benchmark_id)}",
            benchmark_id=benchmark_id,
            required_categories=list(REQUIRED_RELATED_WORK_CATEGORIES),
            category_statuses=category_statuses,
            missing_categories=missing_categories,
            attached_paper_ids=sorted({paper.id for paper in papers}),
            real_paper_count=len(real_paper_ids),
            fallback_paper_count=len(fallback_paper_ids),
            novelty_status=novelty_status,
            blockers=blockers,
            provenance=Provenance(
                created_by_skill="selected-related-work-completion",
                source_ids=[benchmark_id, spec.project_id, *[paper.id for paper in papers]],
                timestamp=utc_now_iso(),
                reasoning_summary="Classified attached selected-benchmark papers into real and fallback related-work coverage.",
            ),
        )
        self._write_json(self.status_path(benchmark_id), status)
        searches = self.next_searches_for_status(status)
        self.status_path(benchmark_id).with_suffix(".md").write_text(
            render_related_work_completion_status(status, searches),
            encoding="utf-8",
        )
        self._write_json(self.next_searches_path(benchmark_id).with_suffix(".json"), {"commands": searches})
        self.next_searches_path(benchmark_id).write_text("\n".join(searches) + ("\n" if searches else ""), encoding="utf-8")
        return status

    def load_status(self, benchmark_id: str) -> RelatedWorkCompletionStatus:
        path = self.status_path(benchmark_id)
        if not path.exists():
            return self.complete(benchmark_id)
        return from_dict(RelatedWorkCompletionStatus, json.loads(path.read_text(encoding="utf-8")))

    def status_report(self, benchmark_id: str) -> str:
        status = self.load_status(benchmark_id)
        searches = self.next_searches_for_status(status)
        rendered = render_related_work_completion_status(status, searches)
        self.status_path(benchmark_id).with_suffix(".md").write_text(rendered, encoding="utf-8")
        return rendered

    def next_searches(self, benchmark_id: str) -> list[str]:
        status = self.load_status(benchmark_id)
        searches = self.next_searches_for_status(status)
        self._write_json(self.next_searches_path(benchmark_id).with_suffix(".json"), {"commands": searches})
        self.next_searches_path(benchmark_id).write_text("\n".join(searches) + ("\n" if searches else ""), encoding="utf-8")
        return searches

    def next_searches_for_status(self, status: RelatedWorkCompletionStatus) -> list[str]:
        return [_search_command(category) for category in status.missing_categories]

    def status_path(self, benchmark_id: str) -> Path:
        spec = self.benchmark_manager.load_spec(benchmark_id)
        return self._completion_dir(spec.project_id) / "related_work_completion_status.json"

    def next_searches_path(self, benchmark_id: str) -> Path:
        spec = self.benchmark_manager.load_spec(benchmark_id)
        return self._completion_dir(spec.project_id) / "related_work_next_searches.md"

    def _category_status(self, benchmark_id: str, category: str, papers: list[Paper]) -> CategoryStatus:
        matched = [(paper, _category_score(category, paper)) for paper in papers]
        real_ids = [paper.id for paper, score in matched if score > 0 and _is_real_paper(paper)]
        fallback_ids = [paper.id for paper, score in matched if score > 0 and _is_fallback_paper(paper)]
        closest = real_ids[:3]
        if real_ids:
            status = "complete"
            notes = ["At least one attached real paper record covers this required category."]
        elif fallback_ids:
            status = "partial"
            notes = ["Only fallback or fixture records cover this category; real paper records are still required."]
        else:
            status = "missing"
            notes = ["No attached paper record covers this category; run the next search command."]
        return CategoryStatus(
            category=category,
            real_paper_ids=real_ids,
            fallback_paper_ids=fallback_ids,
            closest_prior_work_ids=closest,
            status=status,
            notes=notes,
            provenance=Provenance(
                created_by_skill="selected-related-work-completion",
                source_ids=[benchmark_id, *real_ids, *fallback_ids],
                timestamp=utc_now_iso(),
                reasoning_summary=f"Classified related-work coverage for `{category}`.",
            ),
        )

    def _papers_for_benchmark(self, benchmark_id: str) -> list[Paper]:
        spec = self.benchmark_manager.load_spec(benchmark_id)
        program = self.project_manager.load_project(spec.project_id)
        papers: list[Paper] = []
        seen: set[str] = set()
        for run_id in program.run_ids:
            state = self.state_manager.load_run(run_id)
            for paper in state.papers:
                if paper.id not in seen:
                    papers.append(paper)
                    seen.add(paper.id)
        return papers

    def _completion_dir(self, project_id: str) -> Path:
        path = self._benchmark_dir(project_id) / "related_work_completion"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _benchmark_dir(self, project_id: str) -> Path:
        program = self.project_manager.load_project(project_id)
        path = Path(program.project.root_dir) / "selected_benchmark"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _write_json(self, path: Path, value: object) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(to_plain(value), indent=2) + "\n", encoding="utf-8")


def render_related_work_completion_status(status: RelatedWorkCompletionStatus, next_searches: list[str]) -> str:
    lines = [
        "# Related-Work Completion Status",
        "",
        f"- Benchmark ID: `{status.benchmark_id}`",
        f"- Real attached papers: {status.real_paper_count}",
        f"- Fallback attached papers: {status.fallback_paper_count}",
        f"- Novelty status: `{status.novelty_status}`",
        f"- Missing categories: {', '.join(status.missing_categories) or 'none'}",
        "",
        "## Categories",
        "",
    ]
    for category in status.required_categories:
        category_status = status.category_statuses[category]
        lines.extend(
            [
                f"### {category}",
                f"- Status: `{category_status.status}`",
                f"- Real paper IDs: {', '.join(category_status.real_paper_ids) or 'none'}",
                f"- Fallback paper IDs: {', '.join(category_status.fallback_paper_ids) or 'none'}",
                f"- Closest prior-work IDs: {', '.join(category_status.closest_prior_work_ids) or 'none'}",
            ]
        )
        lines.extend(f"- Note: {note}" for note in category_status.notes)
        lines.append("")
    lines.extend(["## Blockers", ""])
    lines.extend([f"- {blocker}" for blocker in status.blockers] or ["- none"])
    lines.extend(["", "## Next Search Commands", ""])
    lines.extend([f"- `{command}`" for command in next_searches] or ["- none"])
    lines.extend(["", "## Claim Boundary", ""])
    lines.extend(
        [
            "- Fallback-only records do not complete categories.",
            "- Novelty remains unknown until all required categories have real attached paper records.",
            "- Completed related-work coverage permits review; it does not prove strong novelty by itself.",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def _category_score(category: str, paper: Paper) -> int:
    text = " ".join([paper.title, paper.abstract, paper.venue, paper.source, " ".join(paper.roles)]).lower()
    return sum(1 for keyword in _category_keywords(category) if keyword in text)


def _category_keywords(category: str) -> list[str]:
    return {
        "low-FPR detection/evaluation": ["low false positive", "false-positive", "false positive", "false alarm", "specificity", "low-fpr"],
        "multi-agent collusion/covert coordination": ["multi-agent", "collusion", "covert coordination", "coordination"],
        "monitor evasion": ["monitor evasion", "evasion", "adversarial", "evade", "audit detector"],
        "sequential testing/change-point detection": ["sequential", "change-point", "changepoint", "change point", "repeated alarm"],
        "benchmark/evaluation protocol papers": ["benchmark", "evaluation protocol", "protocol", "dataset", "baselines"],
        "anomaly detection specificity": ["anomaly", "specificity", "rare event", "outlier", "false-positive"],
        "medical screening specificity analogies if used": ["medical", "screening", "diagnostic", "sensitivity", "specificity"],
        "cartel/covert-channel analogies if used": ["cartel", "covert-channel", "covert channel", "price-fixing", "price fixing"],
    }[category]


def _is_real_paper(paper: Paper) -> bool:
    if _is_fallback_paper(paper):
        return False
    if paper.source.lower() == "fixture":
        return False
    trusted_sources = {"arxiv", "semantic-scholar", "crossref", "openreview", "pubmed", "zotero"}
    has_external_identity = any([paper.url, paper.pdf_url, paper.doi, paper.arxiv_id, paper.openreview_id, paper.semantic_scholar_id])
    return bool(paper.id and paper.title and (paper.source.lower() in trusted_sources or has_external_identity))


def _is_fallback_paper(paper: Paper) -> bool:
    text = " ".join([paper.source, paper.provenance.created_by_skill, paper.provenance.reasoning_summary]).lower()
    return (
        bool(paper.raw_metadata.get("fallback"))
        or bool(paper.raw_metadata.get("fixture_notice"))
        or "fallback" in text
        or "fixture" in text
    )


def _search_command(category: str) -> str:
    query = _search_query(category)
    return f'gapforge search "{query}" --sources arxiv,semantic-scholar,crossref --max-results 20'


def _search_query(category: str) -> str:
    return {
        "low-FPR detection/evaluation": "low false-positive detector evaluation specificity false alarm",
        "multi-agent collusion/covert coordination": "multi-agent collusion covert coordination detection",
        "monitor evasion": "monitor evasion adversarial auditing detector evasion",
        "sequential testing/change-point detection": "sequential testing change-point detection false alarm",
        "benchmark/evaluation protocol papers": "benchmark evaluation protocol design dataset baselines",
        "anomaly detection specificity": "anomaly detection specificity false positive evaluation",
        "medical screening specificity analogies if used": "medical screening specificity sensitivity diagnostic test evaluation",
        "cartel/covert-channel analogies if used": "cartel covert channel coordination detection analogy",
    }[category]
