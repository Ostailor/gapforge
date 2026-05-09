"""Related-work grounding for the selected benchmark."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from gapforge.config import GapForgeConfig
from gapforge.models import Paper, Provenance, from_dict, to_plain
from gapforge.project_memory import ProjectMemoryManager
from gapforge.selected_benchmark.spec import SelectedBenchmarkManager
from gapforge.state import ResearchStateManager, slugify, utc_now_iso

REQUIRED_RELATED_WORK_CATEGORIES = [
    "low-FPR detection/evaluation",
    "multi-agent collusion/covert coordination",
    "monitor evasion",
    "sequential testing/change-point detection",
    "benchmark/evaluation protocol papers",
    "anomaly detection specificity",
    "medical screening specificity analogies if used",
    "cartel/covert-channel analogies if used",
]


@dataclass(slots=True)
class SelectedPriorWorkRecall:
    id: str
    benchmark_id: str
    required_categories: list[str] = field(default_factory=list)
    category_paper_ids: dict[str, list[str]] = field(default_factory=dict)
    missing_categories: list[str] = field(default_factory=list)
    closest_prior_work_ids: list[str] = field(default_factory=list)
    blocking_issues: list[str] = field(default_factory=list)
    provenance: Provenance = field(default_factory=lambda: Provenance(created_by_skill="selected-benchmark-related-work"))


@dataclass(slots=True)
class SelectedRelatedWorkEntry:
    category: str
    paper_id: str
    title: str
    relationship: str
    relevance_score: float
    closest_prior_work: bool = False
    reviewer_risk_if_omitted: str = ""
    positioning_note: str = ""
    provenance: Provenance = field(default_factory=lambda: Provenance(created_by_skill="selected-benchmark-related-work"))


@dataclass(slots=True)
class SelectedRelatedWorkMatrix:
    id: str
    benchmark_id: str
    entries: list[SelectedRelatedWorkEntry] = field(default_factory=list)
    required_categories: list[str] = field(default_factory=list)
    missing_categories: list[str] = field(default_factory=list)
    closest_prior_work_ids: list[str] = field(default_factory=list)
    contribution_positioning: str = "benchmark/evaluation protocol"
    blocking_issues: list[str] = field(default_factory=list)
    provenance: Provenance = field(default_factory=lambda: Provenance(created_by_skill="selected-benchmark-related-work"))


@dataclass(slots=True)
class SelectedNoveltyPositioning:
    id: str
    benchmark_id: str
    novelty_strength: str
    contribution_positioning: str
    strong_novelty_allowed: bool
    closest_prior_work_ids: list[str] = field(default_factory=list)
    missing_categories: list[str] = field(default_factory=list)
    blocking_issues: list[str] = field(default_factory=list)
    summary: str = ""
    provenance: Provenance = field(default_factory=lambda: Provenance(created_by_skill="selected-benchmark-related-work"))


class SelectedBenchmarkRelatedWorkManager:
    """Attach prior-work recall and a related-work matrix to the selected benchmark."""

    def __init__(self, config: GapForgeConfig) -> None:
        self.config = config
        self.config.ensure_dirs()
        self.project_manager = ProjectMemoryManager(config)
        self.state_manager = ResearchStateManager(config)
        self.benchmark_manager = SelectedBenchmarkManager(config)

    def build_prior_work_recall(self, benchmark_id: str) -> SelectedPriorWorkRecall:
        spec = self.benchmark_manager.load_spec(benchmark_id)
        papers = self._papers_for_benchmark(benchmark_id)
        category_paper_ids = {
            category: [paper.id for paper in _rank_category_matches(category, papers)] for category in REQUIRED_RELATED_WORK_CATEGORIES
        }
        missing = [category for category, paper_ids in category_paper_ids.items() if not paper_ids]
        closest = _closest_prior_work(papers, category_paper_ids)
        blockers = []
        if missing:
            blockers.append(f"Missing prior-work categories: {', '.join(missing)}.")
        if not closest:
            blockers.append("Closest prior work is not explicit; novelty remains unknown.")
        recall = SelectedPriorWorkRecall(
            id=f"selected-prior-work-recall-{slugify(benchmark_id)}",
            benchmark_id=benchmark_id,
            required_categories=list(REQUIRED_RELATED_WORK_CATEGORIES),
            category_paper_ids=category_paper_ids,
            missing_categories=missing,
            closest_prior_work_ids=closest,
            blocking_issues=blockers,
            provenance=Provenance(
                created_by_skill="selected-benchmark-related-work",
                source_ids=[benchmark_id, spec.project_id, *[paper.id for paper in papers]],
                timestamp=utc_now_iso(),
                reasoning_summary="Classified attached real paper records against selected benchmark prior-work recall categories.",
            ),
        )
        self._write_json(self.prior_work_recall_path(benchmark_id), recall)
        self.prior_work_recall_path(benchmark_id).with_suffix(".md").write_text(render_prior_work_recall(recall, papers), encoding="utf-8")
        return recall

    def load_prior_work_recall(self, benchmark_id: str) -> SelectedPriorWorkRecall:
        path = self.prior_work_recall_path(benchmark_id)
        if not path.exists():
            return self.build_prior_work_recall(benchmark_id)
        return from_dict(SelectedPriorWorkRecall, json.loads(path.read_text(encoding="utf-8")))

    def build_related_work_matrix(self, benchmark_id: str) -> SelectedRelatedWorkMatrix:
        spec = self.benchmark_manager.load_spec(benchmark_id)
        papers = self._papers_for_benchmark(benchmark_id)
        paper_by_id = {paper.id: paper for paper in papers}
        recall = self.load_prior_work_recall(benchmark_id)
        self._reject_fake_citations(recall, paper_by_id)
        entries: list[SelectedRelatedWorkEntry] = []
        for category, paper_ids in recall.category_paper_ids.items():
            for index, paper_id in enumerate(paper_ids):
                paper = paper_by_id[paper_id]
                entries.append(
                    SelectedRelatedWorkEntry(
                        category=category,
                        paper_id=paper.id,
                        title=paper.title,
                        relationship=_relationship(category, closest=paper.id in recall.closest_prior_work_ids),
                        relevance_score=max(0.35, 0.9 - index * 0.08),
                        closest_prior_work=paper.id in recall.closest_prior_work_ids,
                        reviewer_risk_if_omitted=_reviewer_risk(category, closest=paper.id in recall.closest_prior_work_ids),
                        positioning_note=(
                            "Positions the selected contribution as a benchmark/evaluation protocol, not a deployment-valid monitor."
                        ),
                        provenance=Provenance(
                            created_by_skill="selected-benchmark-related-work",
                            source_ids=[benchmark_id, paper.id],
                            timestamp=utc_now_iso(),
                            reasoning_summary="Added an attached paper to the selected benchmark related-work matrix.",
                        ),
                    )
                )
        blockers = list(recall.blocking_issues)
        if recall.missing_categories:
            blockers.append("Strong novelty is blocked until all required related-work categories are attached.")
        matrix = SelectedRelatedWorkMatrix(
            id=f"selected-related-work-matrix-{slugify(benchmark_id)}",
            benchmark_id=benchmark_id,
            entries=entries,
            required_categories=list(REQUIRED_RELATED_WORK_CATEGORIES),
            missing_categories=list(recall.missing_categories),
            closest_prior_work_ids=list(recall.closest_prior_work_ids),
            contribution_positioning="benchmark/evaluation protocol",
            blocking_issues=_dedupe(blockers),
            provenance=Provenance(
                created_by_skill="selected-benchmark-related-work",
                source_ids=[benchmark_id, spec.project_id, *[entry.paper_id for entry in entries]],
                timestamp=utc_now_iso(),
                reasoning_summary="Built a conservative selected benchmark related-work matrix from validated attached papers.",
            ),
        )
        self._write_json(self.related_work_matrix_path(benchmark_id), matrix)
        self.related_work_matrix_path(benchmark_id).with_suffix(".md").write_text(render_related_work_matrix(matrix), encoding="utf-8")
        return matrix

    def render_related_work_matrix(self, benchmark_id: str) -> str:
        matrix = self.load_related_work_matrix(benchmark_id)
        rendered = render_related_work_matrix(matrix)
        self.related_work_matrix_path(benchmark_id).with_suffix(".md").write_text(rendered, encoding="utf-8")
        return rendered

    def load_related_work_matrix(self, benchmark_id: str) -> SelectedRelatedWorkMatrix:
        path = self.related_work_matrix_path(benchmark_id)
        if not path.exists():
            return self.build_related_work_matrix(benchmark_id)
        return from_dict(SelectedRelatedWorkMatrix, json.loads(path.read_text(encoding="utf-8")))

    def novelty_report(self, benchmark_id: str) -> SelectedNoveltyPositioning:
        spec = self.benchmark_manager.load_spec(benchmark_id)
        recall = self.load_prior_work_recall(benchmark_id)
        if self.related_work_matrix_path(benchmark_id).exists():
            matrix = self.load_related_work_matrix(benchmark_id)
        else:
            matrix = self.build_related_work_matrix(benchmark_id)
        missing = _dedupe([*recall.missing_categories, *matrix.missing_categories])
        blockers = _dedupe([*recall.blocking_issues, *matrix.blocking_issues])
        novelty_strength = "weak" if recall.closest_prior_work_ids else "unknown"
        if missing:
            novelty_strength = "weak" if recall.closest_prior_work_ids else "unknown"
        strong_allowed = False
        positioning = SelectedNoveltyPositioning(
            id=f"selected-novelty-positioning-{slugify(benchmark_id)}",
            benchmark_id=benchmark_id,
            novelty_strength=novelty_strength,
            contribution_positioning="benchmark/evaluation protocol",
            strong_novelty_allowed=strong_allowed,
            closest_prior_work_ids=list(recall.closest_prior_work_ids),
            missing_categories=missing,
            blocking_issues=blockers,
            summary=(
                "The selected benchmark can be discussed as a pilot-maturity benchmark/evaluation protocol. "
                "Novelty should remain conservative unless external evidence supports stronger positioning."
            ),
            provenance=Provenance(
                created_by_skill="selected-benchmark-related-work",
                source_ids=[benchmark_id, spec.project_id, *recall.closest_prior_work_ids],
                timestamp=utc_now_iso(),
                reasoning_summary="Rendered conservative novelty positioning from selected benchmark prior-work artifacts.",
            ),
        )
        self._write_json(self.novelty_positioning_path(benchmark_id).with_suffix(".json"), positioning)
        self.novelty_positioning_path(benchmark_id).write_text(render_novelty_positioning(positioning), encoding="utf-8")
        return positioning

    def prior_work_recall_path(self, benchmark_id: str) -> Path:
        spec = self.benchmark_manager.load_spec(benchmark_id)
        return self._related_work_dir(spec.project_id) / "selected_prior_work_recall.json"

    def related_work_matrix_path(self, benchmark_id: str) -> Path:
        spec = self.benchmark_manager.load_spec(benchmark_id)
        return self._related_work_dir(spec.project_id) / "selected_related_work_matrix.json"

    def novelty_positioning_path(self, benchmark_id: str) -> Path:
        spec = self.benchmark_manager.load_spec(benchmark_id)
        return self._related_work_dir(spec.project_id) / "novelty_positioning.md"

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

    def _reject_fake_citations(self, recall: SelectedPriorWorkRecall, paper_by_id: dict[str, Paper]) -> None:
        referenced = set(recall.closest_prior_work_ids)
        for paper_ids in recall.category_paper_ids.values():
            referenced.update(paper_ids)
        unknown = sorted(paper_id for paper_id in referenced if paper_id not in paper_by_id)
        if unknown:
            raise ValueError(f"Selected benchmark related work contains fake or unknown paper IDs: {', '.join(unknown)}.")

    def _related_work_dir(self, project_id: str) -> Path:
        path = self._benchmark_dir(project_id) / "related_work"
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


def render_prior_work_recall(recall: SelectedPriorWorkRecall, papers: list[Paper]) -> str:
    paper_by_id = {paper.id: paper for paper in papers}
    lines = [
        f"# Selected Benchmark Prior-Work Recall `{recall.benchmark_id}`",
        "",
        f"- Closest prior work: {', '.join(recall.closest_prior_work_ids) or 'none'}",
        f"- Missing categories: {', '.join(recall.missing_categories) or 'none'}",
        "",
        "## Required Categories",
        "",
    ]
    for category in recall.required_categories:
        lines.append(f"### {category}")
        paper_ids = recall.category_paper_ids.get(category, [])
        if not paper_ids:
            lines.append("- missing")
        for paper_id in paper_ids:
            paper = paper_by_id.get(paper_id)
            title = paper.title if paper else "UNKNOWN PAPER"
            lines.append(f"- `{paper_id}` {title}")
        lines.append("")
    lines.extend(["## Blocking Issues", ""])
    lines.extend([f"- {item}" for item in recall.blocking_issues] or ["- none"])
    return "\n".join(lines).rstrip() + "\n"


def render_related_work_matrix(matrix: SelectedRelatedWorkMatrix) -> str:
    lines = [
        f"# Selected Benchmark Related-Work Matrix `{matrix.benchmark_id}`",
        "",
        f"- Contribution positioning: `{matrix.contribution_positioning}`",
        f"- Closest prior work: {', '.join(matrix.closest_prior_work_ids) or 'none'}",
        f"- Missing categories: {', '.join(matrix.missing_categories) or 'none'}",
        "",
        "## Matrix",
        "",
    ]
    for entry in matrix.entries:
        marker = "closest prior work" if entry.closest_prior_work else entry.relationship
        lines.extend(
            [
                f"- `{entry.paper_id}` {entry.title}",
                f"  - Category: {entry.category}",
                f"  - Relationship: {marker}",
                f"  - Positioning note: {entry.positioning_note}",
            ]
        )
    lines.extend(["", "## Blocking Issues", ""])
    lines.extend([f"- {item}" for item in matrix.blocking_issues] or ["- none"])
    return "\n".join(lines).rstrip() + "\n"


def render_novelty_positioning(positioning: SelectedNoveltyPositioning) -> str:
    lines = [
        f"# Novelty Positioning `{positioning.benchmark_id}`",
        "",
        f"- Novelty strength: `{positioning.novelty_strength}`",
        f"- Contribution positioning: `{positioning.contribution_positioning}`",
        f"- Elevated novelty allowed: {str(positioning.strong_novelty_allowed).lower()}",
        f"- Closest prior work: {', '.join(positioning.closest_prior_work_ids) or 'none'}",
        "",
        positioning.summary,
        "",
        "## Missing Categories",
        "",
    ]
    lines.extend([f"- {item}" for item in positioning.missing_categories] or ["- none"])
    lines.extend(["", "## Blocking Issues", ""])
    lines.extend([f"- {item}" for item in positioning.blocking_issues] or ["- none"])
    lines.extend(["", "## Non-Claims", ""])
    lines.extend(
        [
            "- This report does not claim deployment validity.",
            "- This report does not claim publication readiness from related-work attachment alone.",
            "- The selected benchmark contribution is positioned as a benchmark/evaluation protocol "
            "unless stronger evidence is later attached.",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def _rank_category_matches(category: str, papers: list[Paper]) -> list[Paper]:
    scored = [(paper, _category_score(category, paper)) for paper in papers]
    return [paper for paper, score in sorted(scored, key=lambda item: (-item[1], item[0].id)) if score > 0]


def _category_score(category: str, paper: Paper) -> int:
    text = " ".join([paper.title, paper.abstract, " ".join(paper.roles)]).lower()
    keywords = _category_keywords(category)
    return sum(1 for keyword in keywords if keyword in text)


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


def _closest_prior_work(papers: list[Paper], category_paper_ids: dict[str, list[str]]) -> list[str]:
    counts: dict[str, int] = {}
    for paper_ids in category_paper_ids.values():
        for paper_id in paper_ids:
            counts[paper_id] = counts.get(paper_id, 0) + 1
    if not counts:
        return []
    ranked = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    return [paper_id for paper_id, _ in ranked[:5] if any(paper.id == paper_id for paper in papers)]


def _relationship(category: str, *, closest: bool) -> str:
    if closest:
        return "closest_prior_work"
    if "benchmark" in category:
        return "benchmark_protocol_background"
    if "analogies" in category:
        return "cross_domain_analogy"
    return "required_background"


def _reviewer_risk(category: str, *, closest: bool) -> str:
    if closest:
        return "major novelty-positioning risk if omitted"
    if "benchmark" in category:
        return "reviewer may question evaluation-protocol grounding"
    return "coverage risk if omitted"


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            result.append(value)
    return result
