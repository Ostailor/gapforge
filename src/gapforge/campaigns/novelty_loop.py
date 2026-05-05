"""Iterative novelty re-search loop for v0.4 campaigns."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from gapforge.campaigns import CampaignManager, CampaignState
from gapforge.campaigns.budgets import campaign_budget_status
from gapforge.campaigns.search_agent import CampaignSearchAgent, validate_search_request
from gapforge.config import GapForgeConfig
from gapforge.directions.maturation import DirectionMaturationManager
from gapforge.models import (
    AgentSearchRequest,
    Gap,
    NoveltyDossier,
    Provenance,
    RelatedWorkMatrix,
    ResearchDirection,
    ResearchProgramState,
    ResearchRunState,
    to_plain,
)
from gapforge.project_memory import ProjectMemoryManager
from gapforge.retrieval import build_project_index, build_run_index
from gapforge.skill_registry import default_sources
from gapforge.skills.novelty_gate import NoveltyGate
from gapforge.sources.base import ResearchSource
from gapforge.sources.policies import get_source_policy_profile
from gapforge.sources.stopping import refresh_stopping_assessment
from gapforge.state import ResearchStateManager, utc_now_compact, utc_now_iso

LOOP_BLOCKING_NOVELTY = {"unknown", "weak"}


class CampaignNoveltyLoop:
    """Drive prior-work re-search until novelty is rejected, plausible, or blocked."""

    def __init__(self, config: GapForgeConfig, sources: list[ResearchSource] | None = None) -> None:
        self.config = config
        self.sources = sources if sources is not None else default_sources(config)
        self.campaigns = CampaignManager(config)
        self.projects = ProjectMemoryManager(config)
        self.states = ResearchStateManager(config)
        self.search_agent = CampaignSearchAgent(config, sources=self.sources)

    def run(self, campaign_id: str, *, gap_id: str = "") -> dict[str, Any]:
        campaign_state = self.campaigns.load_campaign_state(campaign_id)
        program = self.projects.load_project(campaign_state.campaign.project_id)
        runs = _load_runs(self.states, campaign_state, program)
        budget = campaign_budget_status(campaign_state, papers_seen=sum(len(run.papers) for run in runs))
        if budget.exhausted:
            payload = self._payload(
                campaign_state,
                program,
                runs,
                gap_id=gap_id,
                stop_reason="budget_exhausted",
                blocking_issues=budget.reasons,
            )
            return self._write_status(payload)

        targets = _targets(program, runs, gap_id=gap_id)
        if not targets:
            payload = self._payload(
                campaign_state,
                program,
                runs,
                gap_id=gap_id,
                stop_reason="human_review_required" if _open_review_required(program) else "not_ready_novelty_unknown",
                blocking_issues=["No promising gap or direction target found for novelty loop."],
            )
            return self._write_status(payload)

        created_requests = self._create_research_requests(campaign_state, program, runs, targets)
        if created_requests:
            campaign_state = self.campaigns.load_campaign_state(campaign_id)
            executed_batch = self.search_agent.execute_searches(campaign_id)
        else:
            executed_batch = None

        refreshed_runs = self._refresh_novelty(campaign_id, target_gap_ids=[target["gap"].id for target in targets])
        refreshed_program = self.projects.sync_project_memory(campaign_state.campaign.project_id)
        self._refresh_indexes(refreshed_program, refreshed_runs)
        matured_directions = self._mature_directions(refreshed_program, targets)
        payload = self._payload(
            self.campaigns.load_campaign_state(campaign_id),
            self.projects.load_project(campaign_state.campaign.project_id),
            refreshed_runs,
            gap_id=gap_id,
            created_requests=created_requests,
            executed_batch=executed_batch,
            matured_directions=matured_directions,
        )
        return self._write_status(payload)

    def status(self, campaign_id: str) -> dict[str, Any]:
        campaign_state = self.campaigns.load_campaign_state(campaign_id)
        program = self.projects.load_project(campaign_state.campaign.project_id)
        runs = _load_runs(self.states, campaign_state, program)
        path = _campaign_dir(self.config, campaign_state) / "novelty_loop_status.json"
        if path.exists():
            raw = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                return raw
        return self._payload(campaign_state, program, runs)

    def _create_research_requests(
        self,
        campaign_state: CampaignState,
        program: ResearchProgramState,
        runs: list[ResearchRunState],
        targets: list[dict[str, Any]],
    ) -> list[AgentSearchRequest]:
        profile = get_source_policy_profile(campaign_state.campaign.source_profile or "generic")
        available_sources = [source.name for source in self.sources]
        existing_queries = {request.query.lower() for request in campaign_state.search_requests}
        requests: list[AgentSearchRequest] = []
        for target in targets:
            gap = target["gap"]
            dossier = target.get("dossier")
            matrix = target.get("related_work_matrix")
            for index, query in enumerate(_novelty_queries(campaign_state, gap, dossier, matrix, runs), start=1):
                if query.lower() in existing_queries:
                    continue
                request = AgentSearchRequest(
                    id=f"novelty-search-{utc_now_compact()}-{len(requests) + 1}",
                    campaign_id=campaign_state.campaign.id,
                    task_id="novelty-loop",
                    query=query,
                    purpose=_query_purpose(query),
                    source_profile=profile.id,
                    target_sources=_target_sources(profile, available_sources),
                    reason=f"Novelty loop re-search for {gap.id}: {_target_reason(dossier)}",
                    priority=min(5, index),
                    status="proposed",
                    provenance=_provenance(
                        [campaign_state.campaign.id, gap.id],
                        "Generated novelty re-search request from weak, unknown, contested, or missing prior-work evidence.",
                    ),
                )
                issues = validate_search_request(request, campaign_state, available_sources=available_sources)
                if issues:
                    request.status = "rejected"
                    request.reason += " Validation failed: " + "; ".join(issues)
                requests.append(request)
                existing_queries.add(query.lower())
        campaign_state.search_requests.extend(requests)
        self.campaigns.save_campaign_state(campaign_state)
        return requests

    def _refresh_novelty(self, campaign_id: str, *, target_gap_ids: list[str]) -> list[ResearchRunState]:
        campaign_state = self.campaigns.load_campaign_state(campaign_id)
        program = self.projects.load_project(campaign_state.campaign.project_id)
        runs = _load_runs(self.states, campaign_state, program)
        gate = NoveltyGate(self.sources, search_sources=False)
        refreshed: list[ResearchRunState] = []
        for run in runs:
            target_ids = [gap_id for gap_id in target_gap_ids if any(gap.id == gap_id for gap in run.gaps)]
            if not target_ids:
                refreshed.append(run)
                continue
            for target_id in target_ids:
                gate.assess(run, gap_id=target_id, deep=False)
            profile_id = campaign_state.campaign.source_profile or str(run.config.get("source_policy_profile", "generic"))
            refresh_stopping_assessment(run, profile=profile_id)
            self._block_strong_novelty_when_policy_missing(run)
            build_run_index(run)
            self.states.save_run(run)
            refreshed.append(run)
        return refreshed

    def _block_strong_novelty_when_policy_missing(self, run: ResearchRunState) -> None:
        assessment = run.coverage_stopping_assessment
        if assessment is None or assessment.enough_for_novelty:
            return
        missing = "Source policy novelty requirements remain incomplete: " + "; ".join(assessment.missing_requirements[:6])
        for dossier in run.novelty_dossiers:
            if dossier.novelty_strength == "strong":
                dossier.novelty_strength = "unknown"
                dossier.verdict = "unknown"
                dossier.confidence = "low"
                if missing not in dossier.missing_searches:
                    dossier.missing_searches.append(missing)
        for novelty in run.novelty_assessments:
            if novelty.novelty_strength == "strong":
                novelty.novelty_strength = "unknown"
                novelty.verdict = "unknown"
                novelty.confidence = "low"
                if missing not in novelty.missing_searches:
                    novelty.missing_searches.append(missing)

    def _refresh_indexes(self, program: ResearchProgramState, runs: list[ResearchRunState]) -> None:
        for run in runs:
            build_run_index(run)
            self.states.save_run(run)
        build_project_index(program)

    def _mature_directions(self, program: ResearchProgramState, targets: list[dict[str, Any]]) -> list[ResearchDirection]:
        direction_ids = _unique(
            [
                target["direction"].id
                for target in targets
                if target.get("direction") is not None and isinstance(target["direction"], ResearchDirection)
            ]
        )
        manager = DirectionMaturationManager(self.config)
        matured = []
        for direction_id in direction_ids:
            try:
                matured.append(manager.mature_direction(program.project.id, direction_id))
            except KeyError:
                continue
        return matured

    def _payload(
        self,
        campaign_state: CampaignState,
        program: ResearchProgramState,
        runs: list[ResearchRunState],
        *,
        gap_id: str = "",
        created_requests: list[AgentSearchRequest] | None = None,
        executed_batch: Any = None,
        matured_directions: list[ResearchDirection] | None = None,
        stop_reason: str = "",
        blocking_issues: list[str] | None = None,
    ) -> dict[str, Any]:
        targets = _targets(program, runs, gap_id=gap_id)
        pending_requests = [request for request in campaign_state.search_requests if request.status in {"proposed", "validated"}]
        stop = stop_reason or _stop_reason(targets, runs, pending_requests, matured_directions or [], program)
        return {
            "campaign_id": campaign_state.campaign.id,
            "project_id": campaign_state.campaign.project_id,
            "gap_id": gap_id,
            "stop_reason": stop,
            "target_count": len(targets),
            "created_search_request_count": len(created_requests or []),
            "pending_search_request_count": len(pending_requests),
            "executed_batch": to_plain(executed_batch) if executed_batch is not None else None,
            "matured_directions": [to_plain(direction) for direction in matured_directions or []],
            "blocking_issues": blocking_issues or _blocking_issues(targets, runs, pending_requests, stop),
            "targets": [_target_payload(target) for target in targets],
            "search_requests": [to_plain(request) for request in campaign_state.search_requests],
            "coverage_stopping_assessments": [
                to_plain(run.coverage_stopping_assessment) for run in runs if run.coverage_stopping_assessment is not None
            ],
            "generated_at": utc_now_iso(),
        }

    def _write_status(self, payload: dict[str, Any]) -> dict[str, Any]:
        campaign_state = self.campaigns.load_campaign_state(payload["campaign_id"])
        campaign_dir = _campaign_dir(self.config, campaign_state)
        json_path = campaign_dir / "novelty_loop_status.json"
        md_path = campaign_dir / "novelty_loop_status.md"
        json_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        md_path.write_text(render_novelty_loop_status(payload), encoding="utf-8")
        return payload


def render_novelty_loop_status(payload: dict[str, Any]) -> str:
    lines = [
        f"# Novelty Loop Status: {payload['campaign_id']}",
        "",
        f"- Stop reason: {payload['stop_reason']}",
        f"- Targets: {payload['target_count']}",
        f"- Created search requests: {payload['created_search_request_count']}",
        f"- Pending search requests: {payload['pending_search_request_count']}",
        "",
        "## Blocking Issues",
        "",
    ]
    lines.extend([f"- {issue}" for issue in payload.get("blocking_issues", [])] or ["- none"])
    lines.extend(["", "## Targets", ""])
    for target in payload.get("targets", []):
        lines.append(f"- `{target['gap_id']}` verdict={target.get('verdict', 'none')} strength={target.get('novelty_strength', 'none')}")
        if target.get("missing_searches"):
            lines.append(f"  - Missing searches: {'; '.join(target['missing_searches'][:4])}")
    lines.extend(["", "## Search Requests", ""])
    for request in payload.get("search_requests", []):
        lines.append(f"- `{request['id']}` {request['status']} {request['purpose']}: {request['query']}")
    if not payload.get("search_requests"):
        lines.append("- none")
    return "\n".join(lines).rstrip() + "\n"


def _targets(
    program: ResearchProgramState,
    runs: list[ResearchRunState],
    *,
    gap_id: str = "",
) -> list[dict[str, Any]]:
    matrices_by_direction = {matrix.direction_id: matrix for matrix in program.related_work_matrices}
    directions_by_gap: dict[str, ResearchDirection] = {}
    for program_direction in program.research_directions:
        if program_direction.maturity == "rejected":
            continue
        for linked_gap_id in program_direction.linked_gap_ids:
            directions_by_gap.setdefault(linked_gap_id, program_direction)
    targets: list[dict[str, Any]] = []
    for run in runs:
        dossiers = {dossier.target_id: dossier for dossier in run.novelty_dossiers}
        related_by_gap = {matrix.direction_id: matrix for matrix in run.related_work_matrices}
        for gap in run.gaps:
            if gap_id and gap.id != gap_id:
                continue
            dossier = dossiers.get(gap.id)
            direction: ResearchDirection | None = directions_by_gap.get(gap.id)
            matrix = (matrices_by_direction.get(direction.id) if direction else None) or related_by_gap.get(gap.id)
            if _needs_novelty_loop(gap, dossier, matrix, direction):
                targets.append(
                    {"run_id": run.run_id, "gap": gap, "dossier": dossier, "direction": direction, "related_work_matrix": matrix}
                )
    return targets


def _needs_novelty_loop(
    gap: Gap,
    dossier: NoveltyDossier | None,
    matrix: RelatedWorkMatrix | None,
    direction: ResearchDirection | None,
) -> bool:
    if gap.novelty_status in {"unchecked", "weak", "likely_not_new"}:
        return True
    if dossier is None:
        return True
    if dossier.verdict in {"unknown", "revise"}:
        return True
    if dossier.novelty_strength in LOOP_BLOCKING_NOVELTY:
        return True
    if dossier.missing_searches:
        return True
    if matrix is not None and any(entry.relationship in {"directly_solves", "partially_solves"} for entry in matrix.entries):
        return True
    return direction is not None and direction.maturity in {"seed", "candidate", "validated_gap"}


def _novelty_queries(
    campaign_state: CampaignState,
    gap: Gap,
    dossier: NoveltyDossier | None,
    matrix: RelatedWorkMatrix | None,
    runs: list[ResearchRunState],
) -> list[str]:
    base = " ".join([gap.title, gap.description, gap.minimum_experiment_needed]).strip() or campaign_state.campaign.topic
    queries = [
        f'"{gap.title or gap.description[:80]}" closest prior work',
        f"{base} benchmark dataset evaluation",
        f"{base} method metric",
        f"{campaign_state.campaign.topic} survey systematic review",
    ]
    if dossier is not None:
        queries.extend(dossier.missing_searches)
        queries.extend(f"{item.split(':', 1)[-1].strip()} benchmark" for item in dossier.top_prior_work[:3])
        queries.extend(f"{campaign_state.campaign.topic} {item}" for item in dossier.query_plan[:3])
    if matrix is not None:
        queries.extend(
            f"{entry.paper_id} related work"
            for entry in matrix.entries[:3]
            if entry.relationship in {"partially_solves", "directly_solves"}
        )
        queries.extend(f"{campaign_state.campaign.topic} {category}" for category in matrix.missing_categories[:4])
    for run in runs:
        paper_by_id = {paper.id: paper for paper in run.papers}
        prior_ids = _prior_ids(dossier)
        for paper_id in prior_ids[:3]:
            paper = paper_by_id.get(paper_id)
            if paper is None:
                continue
            queries.append(f'"{paper.title}"')
            if paper.authors:
                queries.append(f"{paper.authors[0]} {gap.title or campaign_state.campaign.topic}")
        if run.citation_graph is not None:
            for edge in run.citation_graph.edges[:5]:
                if edge.source_paper_id in prior_ids or edge.target_paper_id in prior_ids:
                    queries.append(f"{campaign_state.campaign.topic} citation neighborhood {edge.source_paper_id} {edge.target_paper_id}")
        for transfer in run.cross_domain_transfers:
            if transfer.target_gap_id == gap.id and transfer.status in {"query_only", "evidence_found", "promoted"}:
                queries.append(f"{transfer.source_field} {transfer.source_concept} {campaign_state.campaign.topic}")
    return _clean_queries(queries)


def _prior_ids(dossier: NoveltyDossier | None) -> list[str]:
    if dossier is None:
        return []
    ids = []
    ids.extend(dossier.candidates_considered)
    ids.extend(_paper_id_from_prior_label(item) for item in dossier.top_prior_work)
    ids.extend(str(row.get("paper_id", "")) for row in dossier.comparison_table)
    return _unique(ids)


def _paper_id_from_prior_label(value: str) -> str:
    return value.split(":", 1)[0].strip()


def _clean_queries(queries: list[str]) -> list[str]:
    cleaned = []
    for query in queries:
        text = " ".join(query.replace("source connector search:", "").split()).strip()
        if len(text) < 8 or text in cleaned:
            continue
        cleaned.append(text)
    return cleaned[:12]


def _query_purpose(query: str) -> str:
    text = query.lower()
    if "survey" in text or "systematic review" in text or "related work" in text:
        return "related_work"
    if "citation" in text or "neighborhood" in text:
        return "citation_expansion"
    if any(term in text for term in ["medicine", "economics", "cybersecurity", "control theory", "screening"]):
        return "analogy"
    return "novelty"


def _target_sources(profile: Any, available_sources: list[str]) -> list[str]:
    available = {_normalize(source): source for source in available_sources}
    selected = []
    for source in profile.required_sources + profile.recommended_sources:
        if _normalize(source) in available:
            selected.append(available[_normalize(source)])
    return _unique(selected or available_sources)


def _target_reason(dossier: NoveltyDossier | None) -> str:
    if dossier is None:
        return "no novelty dossier exists yet"
    if dossier.missing_searches:
        return "dossier lists missing searches"
    return f"current verdict={dossier.verdict}, novelty_strength={dossier.novelty_strength}"


def _refresh_program(config: GapForgeConfig, campaign_state: CampaignState) -> ResearchProgramState:
    return ProjectMemoryManager(config).sync_project_memory(campaign_state.campaign.project_id)


def _stop_reason(
    targets: list[dict[str, Any]],
    runs: list[ResearchRunState],
    pending_requests: list[AgentSearchRequest],
    matured_directions: list[ResearchDirection],
    program: ResearchProgramState,
) -> str:
    if pending_requests:
        return "human_review_required" if _open_review_required(program) else "coverage_still_insufficient"
    if any(direction.maturity == "rejected" for direction in matured_directions):
        return "closest_prior_work_rejects_idea"
    if any(_target_rejected(target) for target in targets):
        return "closest_prior_work_rejects_idea"
    if any(_target_plausible(target) for target in targets) and all(_enough_for_novelty(run) for run in runs if run.gaps):
        return "prior_work_searched_direction_plausible"
    if any(not _enough_for_novelty(run) for run in runs):
        return "coverage_still_insufficient"
    return "not_ready_novelty_unknown"


def _blocking_issues(
    targets: list[dict[str, Any]],
    runs: list[ResearchRunState],
    pending_requests: list[AgentSearchRequest],
    stop_reason: str,
) -> list[str]:
    issues = []
    if pending_requests:
        issues.append(f"{len(pending_requests)} novelty search request(s) remain unexecuted.")
    for target in targets:
        dossier = target.get("dossier")
        if dossier is None:
            issues.append(f"Gap {target['gap'].id} has no novelty dossier.")
        elif dossier.missing_searches:
            issues.append(f"Gap {target['gap'].id} has missing searches: {'; '.join(dossier.missing_searches[:3])}")
    for run in runs:
        if run.coverage_stopping_assessment is not None and not run.coverage_stopping_assessment.enough_for_novelty:
            issues.append(f"Run {run.run_id} is not source-policy sufficient for novelty.")
    if stop_reason == "closest_prior_work_rejects_idea":
        issues.append("Closest prior work appears to cover the idea; reject or substantially reframe.")
    return _unique(issues)


def _target_payload(target: dict[str, Any]) -> dict[str, Any]:
    gap = target["gap"]
    dossier = target.get("dossier")
    direction = target.get("direction")
    return {
        "run_id": target["run_id"],
        "gap_id": gap.id,
        "gap_title": gap.title,
        "direction_id": direction.id if direction is not None else "",
        "direction_maturity": direction.maturity if direction is not None else "",
        "verdict": dossier.verdict if dossier is not None else "",
        "novelty_strength": dossier.novelty_strength if dossier is not None else "",
        "confidence": dossier.confidence if dossier is not None else "",
        "top_prior_work": dossier.top_prior_work if dossier is not None else [],
        "missing_searches": dossier.missing_searches if dossier is not None else ["No novelty dossier exists."],
    }


def _target_rejected(target: dict[str, Any]) -> bool:
    gap = target["gap"]
    dossier = target.get("dossier")
    matrix = target.get("related_work_matrix")
    if gap.novelty_status == "likely_not_new":
        return True
    if dossier is not None and dossier.verdict == "reject":
        return True
    return matrix is not None and any(entry.relationship == "directly_solves" for entry in matrix.entries)


def _target_plausible(target: dict[str, Any]) -> bool:
    dossier = target.get("dossier")
    return dossier is not None and dossier.verdict in {"pursue", "revise"} and not dossier.missing_searches


def _enough_for_novelty(run: ResearchRunState) -> bool:
    return run.coverage_stopping_assessment is not None and run.coverage_stopping_assessment.enough_for_novelty


def _load_runs(
    state_manager: ResearchStateManager,
    campaign_state: CampaignState,
    program: ResearchProgramState,
) -> list[ResearchRunState]:
    runs = []
    for run_id in campaign_state.campaign.run_ids or program.run_ids:
        try:
            runs.append(state_manager.load_run(run_id))
        except FileNotFoundError:
            continue
    return runs


def _open_review_required(program: ResearchProgramState) -> bool:
    return program.review_queue is not None and any(item.status == "open" for item in program.review_queue.items)


def _campaign_dir(config: GapForgeConfig, campaign_state: CampaignState) -> Path:
    return config.project_root / campaign_state.campaign.project_id / "campaigns" / campaign_state.campaign.id


def _normalize(value: str) -> str:
    return value.strip().lower().replace(" ", "-").replace("_", "-")


def _unique(values: list[str]) -> list[str]:
    seen = set()
    result = []
    for value in values:
        if value and value not in seen:
            result.append(value)
            seen.add(value)
    return result


def _provenance(source_ids: list[str], summary: str) -> Provenance:
    return Provenance(
        created_by_skill="campaign-novelty-loop",
        source_ids=[source_id for source_id in source_ids if source_id],
        timestamp=utc_now_iso(),
        reasoning_summary=summary,
    )
