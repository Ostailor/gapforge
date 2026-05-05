"""Agent-proposed, GapForge-executed literature expansion for campaigns."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from gapforge.campaigns import CampaignManager, CampaignState
from gapforge.config import GapForgeConfig
from gapforge.models import AgentSearchBatch, AgentSearchRequest, Paper, Provenance, ResearchRunState, from_dict, to_plain
from gapforge.project_memory import ProjectMemoryManager
from gapforge.retrieval import build_project_index, build_run_index
from gapforge.skill_registry import SkillRegistry, default_sources
from gapforge.sources.base import ResearchSource
from gapforge.sources.coverage import add_search_query_record, refresh_source_coverage, render_source_coverage_markdown
from gapforge.sources.policies import get_source_policy_profile
from gapforge.sources.ranking import deduplicate_papers
from gapforge.sources.ranking_v2 import rank_papers_v2
from gapforge.sources.stopping import assess_literature_coverage, refresh_stopping_assessment, render_stopping_assessment_markdown
from gapforge.state import ResearchStateManager, utc_now_compact, utc_now_iso

VALID_SEARCH_PURPOSES = {
    "initial_topic",
    "analogy",
    "novelty",
    "citation_expansion",
    "related_work",
    "manual",
    "coverage",
    "gap",
}


class CampaignSearchAgent:
    """Validate agent search requests, execute source connectors, and update coverage."""

    def __init__(self, config: GapForgeConfig, sources: list[ResearchSource] | None = None) -> None:
        self.config = config
        self.campaigns = CampaignManager(config)
        self.projects = ProjectMemoryManager(config)
        self.states = ResearchStateManager(config)
        self.sources = sources if sources is not None else default_sources(config)

    def propose_searches(self, campaign_id: str, *, task_id: str = "", limit: int = 8) -> AgentSearchBatch:
        campaign_state = self.campaigns.load_campaign_state(campaign_id)
        run_state = self._ensure_campaign_run(campaign_state)
        profile = get_source_policy_profile(
            campaign_state.campaign.source_profile or str(run_state.config.get("source_policy_profile", "generic"))
        )
        assessment = assess_literature_coverage(run_state, profile=profile)
        existing_queries = {request.query.lower() for request in campaign_state.search_requests if request.status != "rejected"}
        requests: list[AgentSearchRequest] = []
        for index, query in enumerate(assessment.recommended_queries[:limit], start=1):
            if query.lower() in existing_queries:
                continue
            request = AgentSearchRequest(
                id=f"agent-search-{utc_now_compact()}-{index}",
                campaign_id=campaign_id,
                task_id=task_id,
                query=query,
                purpose=_purpose_for_query(query, assessment.missing_requirements),
                source_profile=profile.id,
                target_sources=_target_sources_for_profile(profile, self.sources),
                reason=_reason_for_query(query, assessment.missing_requirements),
                priority=min(5, index),
                status="proposed",
                provenance=_provenance([campaign_id, run_state.run_id], "Structured search request proposed from source policy gaps."),
            )
            validation_issues = validate_search_request(request, campaign_state, available_sources=_source_names(self.sources))
            if validation_issues:
                request.status = "rejected"
                request.reason = request.reason + " Validation failed: " + "; ".join(validation_issues)
            requests.append(request)
        if not requests and not assessment.recommended_queries:
            requests.append(
                AgentSearchRequest(
                    id=f"agent-search-{utc_now_compact()}-coverage",
                    campaign_id=campaign_id,
                    task_id=task_id,
                    query=f"{campaign_state.campaign.topic} survey benchmark",
                    purpose="coverage",
                    source_profile=profile.id,
                    target_sources=_target_sources_for_profile(profile, self.sources),
                    reason="Default coverage search because the policy assessment did not produce a query.",
                    priority=3,
                    provenance=_provenance([campaign_id, run_state.run_id], "Fallback structured search request for campaign coverage."),
                )
            )
        batch = AgentSearchBatch(
            id=f"agent-search-batch-{utc_now_compact()}",
            campaign_id=campaign_id,
            requests=requests,
            validation_status=_batch_validation_status(requests),
            provenance=_provenance([campaign_id, run_state.run_id], "Created auditable agentic literature search batch."),
        )
        campaign_state.search_requests.extend(requests)
        campaign_state.search_batches.append(batch)
        self._downgrade_novelty_for_pending_searches(run_state, campaign_state.search_requests)
        self.states.save_run(run_state)
        self.campaigns.save_campaign_state(campaign_state)
        return batch

    def execute_searches(self, campaign_id: str, *, max_results_per_query: int = 12) -> AgentSearchBatch:
        campaign_state = self.campaigns.load_campaign_state(campaign_id)
        run_state = self._ensure_campaign_run(campaign_state)
        available = _source_names(self.sources)
        pending = [request for request in campaign_state.search_requests if request.status in {"proposed", "validated"}]
        if not pending:
            pending = self.propose_searches(campaign_id).requests
            campaign_state = self.campaigns.load_campaign_state(campaign_id)
            pending = [request for request in campaign_state.search_requests if request.status in {"proposed", "validated"}]
        result_ids: list[str] = []
        failures: list[str] = []
        executed_requests: list[AgentSearchRequest] = []
        for request in pending:
            validation_issues = validate_search_request(request, campaign_state, available_sources=available)
            if validation_issues:
                request.status = "rejected"
                failures.extend(f"{request.id}: {issue}" for issue in validation_issues)
                continue
            request.status = "validated"
            selected_sources = _select_sources(self.sources, request.target_sources)
            papers, request_failures = _execute_request(request, selected_sources, max_results=max_results_per_query)
            run_state.papers = _merge_papers(run_state.papers, papers)
            result_paper_ids = [paper.id for paper in papers]
            add_search_query_record(
                run_state,
                query=request.query,
                source_names=[source.name for source in selected_sources],
                purpose=request.purpose,
                max_results=max_results_per_query,
                date_from=None,
                date_to=None,
                result_paper_ids=result_paper_ids,
                failure_messages=request_failures,
            )
            result_ids.extend(result_paper_ids)
            failures.extend(request_failures)
            request.status = "failed" if request_failures and not result_paper_ids else "executed"
            executed_requests.append(request)
        self._refresh_run_after_search(run_state, campaign_state)
        batch = AgentSearchBatch(
            id=f"agent-search-batch-{utc_now_compact()}-executed",
            campaign_id=campaign_id,
            requests=[_copy_request(request) for request in executed_requests],
            validation_status="executed" if executed_requests and not failures else ("partial" if executed_requests else "rejected"),
            executed_at=utc_now_iso(),
            result_paper_ids=_unique(result_ids),
            failures=_unique(failures),
            provenance=_provenance(
                [campaign_id, run_state.run_id], "Executed validated agent search requests through GapForge source connectors."
            ),
        )
        campaign_state.search_batches.append(batch)
        self.campaigns.save_campaign_state(campaign_state)
        return batch

    def status(self, campaign_id: str) -> dict[str, Any]:
        campaign_state = self.campaigns.load_campaign_state(campaign_id)
        runs = []
        for run_id in campaign_state.campaign.run_ids:
            try:
                runs.append(self.states.load_run(run_id))
            except FileNotFoundError:
                continue
        pending = [request for request in campaign_state.search_requests if request.status in {"proposed", "validated"}]
        executed = [request for request in campaign_state.search_requests if request.status == "executed"]
        rejected = [request for request in campaign_state.search_requests if request.status == "rejected"]
        return {
            "campaign_id": campaign_id,
            "request_count": len(campaign_state.search_requests),
            "pending_count": len(pending),
            "executed_count": len(executed),
            "rejected_count": len(rejected),
            "batch_count": len(campaign_state.search_batches),
            "novelty_blocked_by_pending_searches": bool(pending),
            "requests": [to_plain(request) for request in campaign_state.search_requests],
            "batches": [to_plain(batch) for batch in campaign_state.search_batches],
            "coverage": [to_plain(run.source_coverage) for run in runs if run.source_coverage is not None],
            "stopping_assessments": [
                to_plain(run.coverage_stopping_assessment) for run in runs if run.coverage_stopping_assessment is not None
            ],
        }

    def _ensure_campaign_run(self, campaign_state: CampaignState) -> ResearchRunState:
        for run_id in campaign_state.campaign.run_ids:
            try:
                return self.states.load_run(run_id)
            except FileNotFoundError:
                continue
        state = self.states.create_run(campaign_state.campaign.topic)
        state.config["project_id"] = campaign_state.campaign.project_id
        state.config["source_policy_profile"] = campaign_state.campaign.source_profile or "generic"
        self.states.save_run(state)
        self.projects.attach_run(campaign_state.campaign.project_id, state.run_id)
        updated = self.campaigns.attach_run(campaign_state.campaign.id, state.run_id)
        campaign_state.campaign.run_ids = updated.campaign.run_ids
        campaign_state.steps = updated.steps
        campaign_state.decisions = updated.decisions
        campaign_state.milestones = updated.milestones
        campaign_state.stop_conditions = updated.stop_conditions
        campaign_state.imports = updated.imports
        campaign_state.human_reviews = updated.human_reviews
        campaign_state.acceptance_summary = updated.acceptance_summary
        return state

    def _refresh_run_after_search(self, run_state: ResearchRunState, campaign_state: CampaignState) -> None:
        run_state.paper_ranking = rank_papers_v2(
            run_state.topic.text,
            run_state.papers,
            state=run_state,
            query_purpose="coverage",
            source_diversity_target=2,
            role_diversity_target=2,
        )
        try:
            SkillRegistry(self.config).get("paper-triage").run(run_state)
        except Exception:
            pass
        report = refresh_source_coverage(run_state)
        profile_id = campaign_state.campaign.source_profile or str(run_state.config.get("source_policy_profile", "generic"))
        assessment = refresh_stopping_assessment(run_state, profile=profile_id)
        self._downgrade_novelty_for_pending_searches(run_state, campaign_state.search_requests)
        build_run_index(run_state)
        self.states.save_run(run_state)
        self.projects.sync_project_memory(campaign_state.campaign.project_id)
        program = self.projects.load_project(campaign_state.campaign.project_id)
        build_project_index(program)
        run_dir = Path(run_state.run_dir)
        (run_dir / "source_coverage.md").write_text(render_source_coverage_markdown(report), encoding="utf-8")
        (run_dir / "coverage_stopping_assessment.md").write_text(render_stopping_assessment_markdown(assessment), encoding="utf-8")

    def _downgrade_novelty_for_pending_searches(
        self,
        run_state: ResearchRunState,
        requests: list[AgentSearchRequest],
    ) -> None:
        pending = [request for request in requests if request.status in {"proposed", "validated"}]
        if not pending:
            return
        pending_queries = [request.query for request in pending]
        note = "Required campaign search requests remain unexecuted: " + "; ".join(pending_queries[:5])
        for dossier in run_state.novelty_dossiers:
            if dossier.novelty_strength == "strong" or dossier.verdict == "pursue":
                dossier.verdict = "unknown"
                dossier.novelty_strength = "unknown"
                dossier.confidence = "low"
                if note not in dossier.missing_searches:
                    dossier.missing_searches.append(note)
        for assessment in run_state.novelty_assessments:
            if assessment.novelty_strength == "strong" or assessment.verdict == "pursue":
                assessment.verdict = "unknown"
                assessment.novelty_strength = "unknown"
                assessment.confidence = "low"
                if note not in assessment.missing_searches:
                    assessment.missing_searches.append(note)


def validate_search_request(
    request: AgentSearchRequest,
    campaign_state: CampaignState,
    *,
    available_sources: list[str],
) -> list[str]:
    issues: list[str] = []
    query = " ".join(request.query.split())
    if len(query) < 8:
        issues.append("query is too short")
    if not any(char.isalpha() for char in query):
        issues.append("query must contain alphabetic search terms")
    tokens = _tokens(query)
    if len(tokens) < 2:
        issues.append("query must contain at least two meaningful terms")
    nonsense = {"asdf", "qwerty", "lorem", "ipsum", "foo", "bar", "test"}
    if tokens and len(tokens & nonsense) / max(1, len(tokens)) > 0.4:
        issues.append("query looks like nonsense or a placeholder")
    if request.purpose not in VALID_SEARCH_PURPOSES:
        issues.append(f"unsupported search purpose: {request.purpose}")
    if not request.reason.strip():
        issues.append("request must explain the coverage, gap, or novelty reason")
    profile_id = request.source_profile or campaign_state.campaign.source_profile or "generic"
    try:
        profile = get_source_policy_profile(profile_id)
    except KeyError:
        issues.append(f"unknown source profile: {profile_id}")
        profile = get_source_policy_profile("generic")
    allowed_sources = {_normalize(source) for source in profile.required_sources + profile.recommended_sources + available_sources}
    for source in request.target_sources:
        if _normalize(source) not in allowed_sources:
            issues.append(f"target source is not allowed by profile or connector set: {source}")
    profile_terms = _tokens(
        " ".join(profile.must_include_query_patterns + profile.novelty_search_requirements + profile.adjacent_field_requirements)
    )
    topic_terms = _tokens(campaign_state.campaign.topic)
    reason_terms = _tokens(request.reason)
    if not (tokens & topic_terms or tokens & profile_terms or tokens & reason_terms):
        issues.append("query is not tied to campaign topic, source policy requirements, or stated reason")
    return issues


def render_campaign_search_status(payload: dict[str, Any]) -> str:
    lines = [
        f"# Campaign Search Status: {payload['campaign_id']}",
        "",
        f"- Requests: {payload['request_count']}",
        f"- Pending: {payload['pending_count']}",
        f"- Executed: {payload['executed_count']}",
        f"- Rejected: {payload['rejected_count']}",
        f"- Novelty blocked by pending searches: {str(payload['novelty_blocked_by_pending_searches']).lower()}",
        "",
        "## Requests",
        "",
    ]
    for request in payload["requests"]:
        lines.append(f"- `{request['id']}` {request['status']} {request['purpose']}: {request['query']}")
        lines.append(f"  - Sources: {', '.join(request.get('target_sources', [])) or 'none'}")
        lines.append(f"  - Reason: {request.get('reason', '')}")
    if not payload["requests"]:
        lines.append("- none")
    return "\n".join(lines).rstrip() + "\n"


def write_campaign_search_status(config: GapForgeConfig, campaign_id: str, payload: dict[str, Any]) -> Path:
    state = CampaignManager(config).load_campaign_state(campaign_id)
    campaign_dir = config.project_root / state.campaign.project_id / "campaigns" / campaign_id
    path = campaign_dir / "campaign_search_status.md"
    path.write_text(render_campaign_search_status(payload), encoding="utf-8")
    (campaign_dir / "campaign_search_status.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path


def _execute_request(request: AgentSearchRequest, sources: list[ResearchSource], *, max_results: int) -> tuple[list[Paper], list[str]]:
    papers: list[Paper] = []
    failures: list[str] = []
    per_source = max(1, max_results // max(1, len(sources)))
    if not sources:
        return [], [f"No configured sources matched request {request.id}."]
    for source in sources:
        try:
            papers.extend(source.search(request.query, max_results=per_source, sort="newest"))
        except Exception as exc:
            failures.append(f"{source.name} search failed for {request.query!r}: {exc}")
    return papers, failures


def _select_sources(sources: list[ResearchSource], target_sources: list[str]) -> list[ResearchSource]:
    if not target_sources:
        return sources
    targets = {_normalize(source) for source in target_sources}
    return [source for source in sources if _normalize(source.name) in targets]


def _source_names(sources: list[ResearchSource]) -> list[str]:
    return [source.name for source in sources]


def _target_sources_for_profile(profile: Any, sources: list[ResearchSource]) -> list[str]:
    available = {_normalize(source.name): source.name for source in sources}
    selected: list[str] = []
    for source in profile.required_sources + profile.recommended_sources:
        normalized = _normalize(source)
        if normalized in available and available[normalized] not in selected:
            selected.append(available[normalized])
    return selected or list(available.values())


def _purpose_for_query(query: str, missing_requirements: list[str]) -> str:
    text = f"{query} {' '.join(missing_requirements)}".lower()
    if "novelty" in text or "closest prior" in text:
        return "novelty"
    if "citation" in text or "related work" in text or "cited by" in text:
        return "citation_expansion"
    if "analogy" in text or "adjacent" in text:
        return "analogy"
    if "gap" in text or "metric" in text or "dataset" in text:
        return "gap"
    return "coverage"


def _reason_for_query(query: str, missing_requirements: list[str]) -> str:
    query_terms = _tokens(query)
    matches = [item for item in missing_requirements if query_terms & _tokens(item)]
    if matches:
        return "Addresses source policy requirement: " + matches[0]
    return "Addresses missing source coverage from the campaign source policy."


def _merge_papers(existing: list[Paper], new: list[Paper]) -> list[Paper]:
    return deduplicate_papers(existing + new)


def _copy_request(request: AgentSearchRequest) -> AgentSearchRequest:
    return from_dict(AgentSearchRequest, to_plain(request))


def _batch_validation_status(requests: list[AgentSearchRequest]) -> str:
    if not requests:
        return "empty"
    if all(request.status == "rejected" for request in requests):
        return "rejected"
    if any(request.status == "rejected" for request in requests):
        return "partial"
    return "valid"


def _tokens(text: str) -> set[str]:
    return {token for token in "".join(char.lower() if char.isalnum() else " " for char in text).split() if len(token) > 2}


def _normalize(source: str) -> str:
    return source.strip().lower().replace(" ", "-").replace("_", "-")


def _unique(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value and value not in seen:
            result.append(value)
            seen.add(value)
    return result


def _provenance(source_ids: list[str], summary: str) -> Provenance:
    return Provenance(
        created_by_skill="campaign-search-agent",
        source_ids=[source_id for source_id in source_ids if source_id],
        timestamp=utc_now_iso(),
        reasoning_summary=summary,
    )
