"""Executable related-work search campaigns for the selected benchmark."""

from __future__ import annotations

import json
import os
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path

from gapforge.config import GapForgeConfig
from gapforge.models import Paper, Provenance, from_dict, to_plain
from gapforge.project_memory import ProjectMemoryManager
from gapforge.selected_benchmark.related_work import REQUIRED_RELATED_WORK_CATEGORIES
from gapforge.selected_benchmark.related_work_completion import _category_score, _is_fallback_paper, _is_real_paper
from gapforge.selected_benchmark.spec import SelectedBenchmarkManager
from gapforge.sources.base import ResearchSource
from gapforge.sources.health import source_display_name, source_map, source_name_key
from gapforge.sources.live_diagnostics import run_live_source_diagnostic
from gapforge.sources.policies import get_source_policy_profile
from gapforge.state import ResearchStateManager, slugify, utc_now_iso


@dataclass(slots=True)
class RequiredRelatedWorkCategorySearch:
    id: str
    campaign_id: str
    category: str
    queries: list[str] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)
    result_paper_ids: list[str] = field(default_factory=list)
    accepted_paper_ids: list[str] = field(default_factory=list)
    rejected_paper_ids: list[str] = field(default_factory=list)
    fallback_paper_ids: list[str] = field(default_factory=list)
    status: str = "missing"
    failure_reason: str = ""
    provenance: Provenance = field(default_factory=lambda: Provenance(created_by_skill="selected-related-work-search"))


@dataclass(slots=True)
class RequiredRelatedWorkSearchCampaign:
    id: str
    benchmark_id: str
    required_categories: list[str] = field(default_factory=list)
    search_round_ids: list[str] = field(default_factory=list)
    status: str = "planned"
    created_at: str = ""
    provenance: Provenance = field(default_factory=lambda: Provenance(created_by_skill="selected-related-work-search"))
    category_searches: dict[str, RequiredRelatedWorkCategorySearch] = field(default_factory=dict)
    next_commands: list[str] = field(default_factory=list)


class RequiredRelatedWorkSearchManager:
    """Plan and execute category-specific related-work searches."""

    def __init__(self, config: GapForgeConfig, sources: Iterable[ResearchSource] | None = None) -> None:
        self.config = config
        self.config.ensure_dirs()
        self.sources = list(sources) if sources is not None else None
        self.project_manager = ProjectMemoryManager(config)
        self.state_manager = ResearchStateManager(config)
        self.benchmark_manager = SelectedBenchmarkManager(config)

    def plan(self, benchmark_id: str) -> RequiredRelatedWorkSearchCampaign:
        spec = self.benchmark_manager.load_spec(benchmark_id)
        campaign_id = f"required-related-work-search-{slugify(benchmark_id)}"
        category_searches = {
            category: RequiredRelatedWorkCategorySearch(
                id=_round_id(campaign_id, category),
                campaign_id=campaign_id,
                category=category,
                queries=_queries_for_category(category),
                sources=_source_names_for_category(category),
                status="missing",
                provenance=Provenance(
                    created_by_skill="selected-related-work-search",
                    source_ids=[benchmark_id, spec.project_id],
                    timestamp=utc_now_iso(),
                    reasoning_summary=f"Planned category-specific related-work searches for `{category}`.",
                ),
            )
            for category in REQUIRED_RELATED_WORK_CATEGORIES
        }
        campaign = RequiredRelatedWorkSearchCampaign(
            id=campaign_id,
            benchmark_id=benchmark_id,
            required_categories=list(REQUIRED_RELATED_WORK_CATEGORIES),
            search_round_ids=[search.id for search in category_searches.values()],
            status="planned",
            created_at=utc_now_iso(),
            provenance=Provenance(
                created_by_skill="selected-related-work-search",
                source_ids=[benchmark_id, spec.project_id],
                timestamp=utc_now_iso(),
                reasoning_summary="Created executable category-specific related-work search plan for the selected benchmark.",
            ),
            category_searches=category_searches,
            next_commands=[_next_command(benchmark_id, category) for category in REQUIRED_RELATED_WORK_CATEGORIES],
        )
        self._write_campaign(campaign)
        return campaign

    def run(self, benchmark_id: str, *, max_results_per_query: int = 5) -> RequiredRelatedWorkSearchCampaign:
        campaign = self.load_or_plan(benchmark_id)
        campaign.status = "running"
        searches: dict[str, RequiredRelatedWorkCategorySearch] = {}
        found_papers: dict[str, Paper] = {}
        for category in campaign.required_categories:
            search = campaign.category_searches.get(category) or self.plan(benchmark_id).category_searches[category]
            executed = self._run_category_search(
                benchmark_id,
                campaign.id,
                search,
                max_results_per_query=max_results_per_query,
            )
            searches[category] = executed
            for paper in executed_papers(executed):
                found_papers[paper.id] = paper
        campaign.category_searches = searches
        campaign.search_round_ids = [search.id for search in searches.values()]
        campaign.next_commands = [
            _next_command(benchmark_id, category) for category, search in searches.items() if search.status != "complete"
        ]
        campaign.status = _campaign_status(campaign)
        campaign.provenance = Provenance(
            created_by_skill="selected-related-work-search",
            source_ids=[benchmark_id, *campaign.search_round_ids],
            timestamp=utc_now_iso(),
            reasoning_summary="Executed selected benchmark related-work search campaign and classified category coverage.",
        )
        self._persist_results_run(benchmark_id, [paper for paper in found_papers.values()])
        self._write_campaign(campaign)
        return campaign

    def load_or_plan(self, benchmark_id: str) -> RequiredRelatedWorkSearchCampaign:
        path = self.campaign_path(benchmark_id)
        if not path.exists():
            return self.plan(benchmark_id)
        return from_dict(RequiredRelatedWorkSearchCampaign, json.loads(path.read_text(encoding="utf-8")))

    def status_report(self, benchmark_id: str) -> str:
        campaign = self.load_or_plan(benchmark_id)
        rendered = render_required_related_work_search_report(campaign)
        self.campaign_path(benchmark_id).with_suffix(".md").write_text(rendered, encoding="utf-8")
        return rendered

    def campaign_path(self, benchmark_id: str) -> Path:
        spec = self.benchmark_manager.load_spec(benchmark_id)
        return self._search_dir(spec.project_id) / "required_related_work_search_campaign.json"

    def _run_category_search(
        self,
        benchmark_id: str,
        campaign_id: str,
        search: RequiredRelatedWorkCategorySearch,
        *,
        max_results_per_query: int,
    ) -> RequiredRelatedWorkCategorySearch:
        if os.environ.get("GAPFORGE_DISABLE_NETWORK") == "1":
            return _blocked_search(
                benchmark_id,
                campaign_id,
                search,
                "Network disabled by GAPFORGE_DISABLE_NETWORK=1; live related-work search was not executed.",
            )
        profile_id = _source_profile_for_category(search.category)
        diagnostic = run_live_source_diagnostic(
            self.config,
            topic=search.queries[0],
            source_profile=profile_id,
            sources=self.sources,
            max_results=1,
        )
        diagnostic_blockers = _diagnostic_blockers(diagnostic.blocking_issues, injected_sources=self.sources is not None)
        available_sources = _available_sources(self.config, search.sources, sources=self.sources)
        if not available_sources:
            failure = "; ".join(diagnostic_blockers) or "No configured source is available for this category."
            return _blocked_search(benchmark_id, campaign_id, search, failure)

        papers_by_id: dict[str, Paper] = {}
        errors: list[str] = list(diagnostic_blockers)
        for query in search.queries:
            for source in available_sources:
                try:
                    papers = source.search(query, max_results=max_results_per_query, sort="relevance", date_from=None, date_to=None)
                except Exception as exc:
                    errors.append(f"{source.name}: {exc}")
                    continue
                for paper in papers:
                    papers_by_id.setdefault(paper.id, paper)

        result_ids = sorted(papers_by_id)
        accepted = sorted(
            paper.id for paper in papers_by_id.values() if _is_real_paper(paper) and _category_score(search.category, paper) > 0
        )
        fallback = sorted(
            paper.id for paper in papers_by_id.values() if _is_fallback_paper(paper) and _category_score(search.category, paper) > 0
        )
        rejected = sorted(set(result_ids) - set(accepted) - set(fallback))
        if accepted and not errors:
            status = "complete"
            failure_reason = ""
        elif accepted:
            status = "partial"
            failure_reason = "Source blocker recorded: " + "; ".join(errors)
        elif fallback:
            status = "partial"
            failure_reason = "Only fallback-only records were found; real paper records are still required."
        else:
            status = "missing"
            failure_reason = "; ".join(errors) or "No category-matching real paper records were found."
        executed = RequiredRelatedWorkCategorySearch(
            id=search.id,
            campaign_id=campaign_id,
            category=search.category,
            queries=list(search.queries),
            sources=[source.name for source in available_sources],
            result_paper_ids=result_ids,
            accepted_paper_ids=accepted,
            rejected_paper_ids=rejected,
            fallback_paper_ids=fallback,
            status=status,
            failure_reason=failure_reason,
            provenance=Provenance(
                created_by_skill="selected-related-work-search",
                source_ids=[benchmark_id, diagnostic.id, *result_ids],
                timestamp=utc_now_iso(),
                reasoning_summary=f"Executed related-work search round for `{search.category}`.",
            ),
        )
        _SEARCH_PAPER_CACHE[executed.id] = papers_by_id
        self._write_category_search(benchmark_id, executed)
        return executed

    def _persist_results_run(self, benchmark_id: str, papers: list[Paper]) -> None:
        if not papers:
            return
        spec = self.benchmark_manager.load_spec(benchmark_id)
        run = self.state_manager.create_run(f"selected benchmark related-work search {benchmark_id}")
        run.papers = sorted(papers, key=lambda paper: paper.id)
        self.state_manager.save_run(run)
        self.project_manager.attach_run(spec.project_id, run.run_id)

    def _write_campaign(self, campaign: RequiredRelatedWorkSearchCampaign) -> None:
        path = self.campaign_path(campaign.benchmark_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(to_plain(campaign), indent=2) + "\n", encoding="utf-8")
        path.with_suffix(".md").write_text(render_required_related_work_search_report(campaign), encoding="utf-8")
        for search in campaign.category_searches.values():
            self._write_category_search(campaign.benchmark_id, search)

    def _write_category_search(self, benchmark_id: str, search: RequiredRelatedWorkCategorySearch) -> None:
        spec = self.benchmark_manager.load_spec(benchmark_id)
        path = self._search_dir(spec.project_id) / "rounds" / f"{slugify(search.category)}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(to_plain(search), indent=2) + "\n", encoding="utf-8")
        path.with_suffix(".md").write_text(render_required_related_work_category_search(search), encoding="utf-8")

    def _search_dir(self, project_id: str) -> Path:
        program = self.project_manager.load_project(project_id)
        path = Path(program.project.root_dir) / "selected_benchmark" / "related_work_search"
        path.mkdir(parents=True, exist_ok=True)
        return path


_SEARCH_PAPER_CACHE: dict[str, dict[str, Paper]] = {}


def executed_papers(search: RequiredRelatedWorkCategorySearch) -> list[Paper]:
    return list(_SEARCH_PAPER_CACHE.get(search.id, {}).values())


def render_required_related_work_search_report(campaign: RequiredRelatedWorkSearchCampaign) -> str:
    lines = [
        "# Required Related-Work Search Campaign",
        "",
        f"- Benchmark ID: `{campaign.benchmark_id}`",
        f"- Campaign ID: `{campaign.id}`",
        f"- Status: `{campaign.status}`",
        f"- Search rounds: {len(campaign.search_round_ids)}",
        "",
        "## Categories",
        "",
    ]
    for category in campaign.required_categories:
        search = campaign.category_searches.get(category)
        if search is None:
            lines.extend([f"### {category}", "- Status: `missing`", ""])
            continue
        lines.extend(
            [
                f"### {category}",
                f"- Round ID: `{search.id}`",
                f"- Status: `{search.status}`",
                f"- Sources: {', '.join(search.sources) or 'none'}",
                f"- Queries: {'; '.join(search.queries) or 'none'}",
                f"- Result paper IDs: {', '.join(search.result_paper_ids) or 'none'}",
                f"- Accepted paper IDs: {', '.join(search.accepted_paper_ids) or 'none'}",
                f"- Rejected paper IDs: {', '.join(search.rejected_paper_ids) or 'none'}",
                f"- Fallback paper IDs: {', '.join(search.fallback_paper_ids) or 'none'}",
                f"- Failure reason: {search.failure_reason or 'none'}",
                "",
            ]
        )
    lines.extend(["## Next Commands", ""])
    lines.extend([f"- `{command}`" for command in campaign.next_commands] or ["- none"])
    lines.extend(["", "## Claim Boundary", ""])
    lines.extend(
        [
            "- Fallback-only categories do not count as complete.",
            "- Missing or unavailable sources remain blockers until rerun or explicitly accepted as no-go evidence.",
            "- Search evidence supports related-work completion only after real records are reviewed.",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def render_required_related_work_category_search(search: RequiredRelatedWorkCategorySearch) -> str:
    return (
        "\n".join(
            [
                f"# Related-Work Search Round: {search.category}",
                "",
                f"- Round ID: `{search.id}`",
                f"- Status: `{search.status}`",
                f"- Sources: {', '.join(search.sources) or 'none'}",
                f"- Queries: {'; '.join(search.queries) or 'none'}",
                f"- Accepted paper IDs: {', '.join(search.accepted_paper_ids) or 'none'}",
                f"- Fallback paper IDs: {', '.join(search.fallback_paper_ids) or 'none'}",
                f"- Failure reason: {search.failure_reason or 'none'}",
            ]
        ).rstrip()
        + "\n"
    )


def _blocked_search(
    benchmark_id: str,
    campaign_id: str,
    search: RequiredRelatedWorkCategorySearch,
    failure_reason: str,
) -> RequiredRelatedWorkCategorySearch:
    blocked = RequiredRelatedWorkCategorySearch(
        id=search.id,
        campaign_id=campaign_id,
        category=search.category,
        queries=list(search.queries),
        sources=list(search.sources),
        status="missing",
        failure_reason=failure_reason,
        provenance=Provenance(
            created_by_skill="selected-related-work-search",
            source_ids=[benchmark_id],
            timestamp=utc_now_iso(),
            reasoning_summary=f"Blocked related-work search round for `{search.category}`.",
        ),
    )
    _SEARCH_PAPER_CACHE[blocked.id] = {}
    return blocked


def _campaign_status(campaign: RequiredRelatedWorkSearchCampaign) -> str:
    statuses = [search.status for search in campaign.category_searches.values()]
    if statuses and all(status == "complete" for status in statuses):
        return "complete"
    if any(status in {"complete", "partial"} for status in statuses):
        return "incomplete"
    return "incomplete"


def _available_sources(
    config: GapForgeConfig,
    planned_sources: list[str],
    *,
    sources: list[ResearchSource] | None,
) -> list[ResearchSource]:
    by_name = source_map(config, sources)
    planned_keys = [source_name_key(source) for source in planned_sources]
    if sources is not None:
        return [source for key, source in by_name.items() if key in planned_keys or not planned_keys]
    return [by_name[key] for key in planned_keys if key in by_name]


def _diagnostic_blockers(blocking_issues: list[str], *, injected_sources: bool) -> list[str]:
    if not injected_sources:
        return blocking_issues
    return [
        issue
        for issue in blocking_issues
        if "No GapForge connector is configured for this source" not in issue and "was not checked" not in issue
    ]


def _round_id(campaign_id: str, category: str) -> str:
    return f"{campaign_id}-{slugify(category)}"


def _next_command(benchmark_id: str, category: str) -> str:
    return f"gapforge selected-related-work-search-run --benchmark-id {benchmark_id} # retry {category}"


def _source_profile_for_category(category: str) -> str:
    return {
        "low-FPR detection/evaluation": "ai_safety",
        "multi-agent collusion/covert coordination": "multi_agent_systems",
        "monitor evasion": "ai_safety",
        "sequential testing/change-point detection": "machine_learning",
        "benchmark/evaluation protocol papers": "machine_learning",
        "anomaly detection specificity": "machine_learning",
        "medical screening specificity analogies if used": "medicine",
        "cartel/covert-channel analogies if used": "economics",
    }[category]


def _source_names_for_category(category: str) -> list[str]:
    profile = get_source_policy_profile(_source_profile_for_category(category))
    return [source_display_name(source) for source in [*profile.required_sources, *profile.recommended_sources]]


def _queries_for_category(category: str) -> list[str]:
    return {
        "low-FPR detection/evaluation": [
            "low false-positive detector evaluation specificity benchmark",
            "low false positive rate evaluation false alarm detector",
            "specificity calibration low false alarm machine learning detector",
        ],
        "multi-agent collusion/covert coordination": [
            "multi-agent collusion covert coordination detection",
            "cooperative agent collusion monitoring benchmark",
            "multi-agent systems covert coordination safety evaluation",
        ],
        "monitor evasion": [
            "monitor evasion adversarial auditing detector evasion",
            "evasion of safety monitors classifiers audit systems",
            "adversarial examples monitor evasion language model safety",
        ],
        "sequential testing/change-point detection": [
            "sequential testing repeated looks alpha spending change-point detection",
            "online change-point detection false alarm control",
            "sequential probability ratio test false positive control",
        ],
        "benchmark/evaluation protocol papers": [
            "benchmark evaluation protocol validity contamination baselines",
            "machine learning benchmark design evaluation methodology",
            "dataset benchmark protocol artifact evaluation reproducibility",
        ],
        "anomaly detection specificity": [
            "anomaly detection specificity false alarm evaluation",
            "rare event anomaly detector false positive calibration",
            "outlier detection specificity benchmark evaluation",
        ],
        "medical screening specificity analogies if used": [
            "medical screening specificity sensitivity false positive diagnostic test",
            "diagnostic test specificity screening evaluation false positives",
            "clinical screening specificity sensitivity systematic review",
        ],
        "cartel/covert-channel analogies if used": [
            "cartel detection covert coordination empirical evaluation",
            "covert channel detection false positive evaluation",
            "price fixing cartel screening detection specificity",
        ],
    }[category]
