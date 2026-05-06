"""Retrieval-selected compact context for campaign-level Codex tasks."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from gapforge.campaigns import CampaignManager, CampaignState
from gapforge.campaigns.import_workflow import find_campaign_task
from gapforge.config import GapForgeConfig
from gapforge.models import (
    ClaimGraph,
    EvidenceSpan,
    NoveltyDossier,
    Paper,
    PaperSection,
    ResearchProgramState,
    ResearchRunState,
    RetrievalResult,
    to_plain,
)
from gapforge.project_memory import ProjectMemoryManager
from gapforge.retrieval.hybrid import retrieval_candidates_for_state
from gapforge.state import ResearchStateManager, utc_now_iso


@dataclass(frozen=True, slots=True)
class TaskContextBudget:
    name: str
    max_papers: int
    max_sections: int
    max_evidence_spans: int
    max_claim_nodes: int
    max_novelty_snippets: int
    max_related_work_snippets: int
    max_chars: int
    max_text_chars: int


TASK_CONTEXT_BUDGETS: dict[str, TaskContextBudget] = {
    "small": TaskContextBudget(
        name="small",
        max_papers=3,
        max_sections=4,
        max_evidence_spans=6,
        max_claim_nodes=6,
        max_novelty_snippets=3,
        max_related_work_snippets=3,
        max_chars=9_000,
        max_text_chars=500,
    ),
    "medium": TaskContextBudget(
        name="medium",
        max_papers=6,
        max_sections=10,
        max_evidence_spans=15,
        max_claim_nodes=10,
        max_novelty_snippets=6,
        max_related_work_snippets=6,
        max_chars=18_000,
        max_text_chars=900,
    ),
    "large": TaskContextBudget(
        name="large",
        max_papers=12,
        max_sections=20,
        max_evidence_spans=30,
        max_claim_nodes=16,
        max_novelty_snippets=10,
        max_related_work_snippets=10,
        max_chars=36_000,
        max_text_chars=1_500,
    ),
}


def build_task_context(
    config: GapForgeConfig,
    campaign_id: str,
    task_type: str,
    *,
    budget: str = "medium",
    task_id: str = "",
) -> dict[str, Any]:
    """Build a compact, retrieval-selected context payload for a campaign task."""

    campaign_state = CampaignManager(config).load_campaign_state(campaign_id)
    program = ProjectMemoryManager(config).load_project(campaign_state.campaign.project_id)
    run_states = _load_campaign_runs(config, campaign_state, program)
    context_budget = TASK_CONTEXT_BUDGETS.get(budget, TASK_CONTEXT_BUDGETS["medium"])
    normalized_task_type = task_type.strip().lower().replace("-", "_")
    query = _query_for_task(normalized_task_type, campaign_state, program, run_states)
    retrieval_results = _search_runs(run_states, query, context_budget)
    retrieval_results = sorted(retrieval_results, key=lambda result: result.score, reverse=True)
    result_limited = len(retrieval_results) > _retrieval_top_k(context_budget)
    retrieval_results = retrieval_results[: _retrieval_top_k(context_budget)]

    closest_prior_ids = _closest_prior_work_ids(run_states, program, normalized_task_type)
    selected_paper_ids = _selected_paper_ids(retrieval_results, closest_prior_ids, context_budget)
    papers = _select_papers(run_states, selected_paper_ids, context_budget, query, closest_prior_ids)
    selected_paper_ids = [paper.id for paper in papers]
    evidence_spans, omitted_evidence = _select_evidence_spans(run_states, retrieval_results, selected_paper_ids, context_budget)
    sections, omitted_sections = _select_sections(run_states, retrieval_results, selected_paper_ids, context_budget)
    novelty_snippets, omitted_novelty = _select_novelty_snippets(run_states, program, selected_paper_ids, context_budget)
    related_work_snippets, omitted_related = _select_related_work_snippets(run_states, program, selected_paper_ids, context_budget)
    claim_nodes, omitted_claims = _select_claim_nodes(program.claim_graph, selected_paper_ids, query, context_budget)

    context_limited = any([result_limited, omitted_evidence, omitted_sections, omitted_novelty, omitted_related, omitted_claims])
    payload: dict[str, Any] = {
        "generated_at": utc_now_iso(),
        "task_id": task_id,
        "task_type": normalized_task_type,
        "campaign_summary": _campaign_summary(campaign_state),
        "source_coverage": _source_coverage_summary(run_states),
        "retrieval": {
            "query": query,
            "result_count": len(retrieval_results),
            "used_hybrid_retrieval": bool(retrieval_results),
            "top_results": [_retrieval_result_payload(result) for result in retrieval_results[:12]],
        },
        "top_relevant_papers": [_paper_payload(paper) for paper in papers],
        "relevant_sections": [_section_payload(section, context_budget) for section in sections],
        "relevant_evidence_spans": [_span_payload(span, context_budget) for span in evidence_spans],
        "related_claim_graph_nodes": claim_nodes,
        "novelty_dossier_snippets": novelty_snippets,
        "related_work_matrix_snippets": related_work_snippets,
        "human_review_constraints": _human_review_constraints(program, run_states),
        "allowed_object_ids": _allowed_object_ids(campaign_state, program, run_states),
        "uncertainty_and_missing_coverage": _uncertainty_and_missing_coverage(run_states, bool(retrieval_results)),
        "closest_prior_candidates": _closest_prior_candidates(run_states, program, closest_prior_ids, retrieval_results),
        "context_budget": {
            "name": context_budget.name,
            "max_papers": context_budget.max_papers,
            "max_sections": context_budget.max_sections,
            "max_evidence_spans": context_budget.max_evidence_spans,
            "max_chars": context_budget.max_chars,
        },
        "context_limited": context_limited,
        "compression_summaries": [],
    }
    payload = _enforce_char_budget(payload, context_budget)
    return payload


def write_task_context(
    config: GapForgeConfig,
    campaign_id: str,
    task_type: str,
    *,
    budget: str = "medium",
    task_id: str = "",
) -> Path:
    campaign_state = CampaignManager(config).load_campaign_state(campaign_id)
    resolved_task_id = task_id or f"context-preview-{task_type.strip().lower().replace('-', '_')}"
    pack_dir = (
        config.project_root
        / campaign_state.campaign.project_id
        / "campaigns"
        / campaign_state.campaign.id
        / "agent_tasks"
        / resolved_task_id
    )
    pack_dir.mkdir(parents=True, exist_ok=True)
    payload = build_task_context(config, campaign_id, task_type, budget=budget, task_id=resolved_task_id)
    path = pack_dir / "task_context.json"
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path


def inspect_task_context(config: GapForgeConfig, task_id: str) -> dict[str, Any]:
    _campaign_state, pack_dir = find_campaign_task(config, task_id)
    path = pack_dir / "task_context.json"
    if not path.exists():
        raise FileNotFoundError(f"No task_context.json found for task {task_id}")
    raw = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(raw, dict):
        return raw
    raise ValueError(f"Invalid task_context.json for task {task_id}")


def _load_campaign_runs(
    config: GapForgeConfig,
    campaign_state: CampaignState,
    program: ResearchProgramState,
) -> list[ResearchRunState]:
    state_manager = ResearchStateManager(config)
    run_ids = campaign_state.campaign.run_ids or program.run_ids
    runs: list[ResearchRunState] = []
    for run_id in run_ids:
        try:
            runs.append(state_manager.load_run(run_id))
        except FileNotFoundError:
            continue
    return runs


def _query_for_task(
    task_type: str,
    campaign_state: CampaignState,
    program: ResearchProgramState,
    runs: list[ResearchRunState],
) -> str:
    pieces = [campaign_state.campaign.topic, campaign_state.campaign.title]
    if task_type == "novelty_reviewer":
        pieces.extend(["closest prior work", "novelty", "benchmark", "evaluation"])
        for run in runs:
            pieces.extend(gap.title or gap.description for gap in run.gaps[:6])
            pieces.extend(dossier.idea_summary for dossier in run.novelty_dossiers[:6])
    elif task_type == "gap_synthesis":
        pieces.extend(["repeated limitations", "missing metrics", "datasets", "assumptions", "counterevidence"])
        for run in runs:
            pieces.extend(claim.text for claim in run.claims[:8])
    elif task_type == "deep_reader_batch":
        pieces.extend(["method", "results", "limitations", "datasets", "metrics"])
    elif task_type == "experiment_architect":
        pieces.extend(["experiment protocol", "baseline", "metric", "falsification", "benchmark"])
        pieces.extend(direction.summary or direction.title for direction in program.research_directions[:6])
    elif task_type == "reviewer_panel":
        pieces.extend(["novelty", "baselines", "metrics", "dataset", "reviewer objection"])
    elif task_type == "literature_scout":
        pieces.extend(["survey", "systematic review", "benchmark", "related work"])
    elif task_type == "campaign_stop_decision":
        pieces.extend(["source coverage", "novelty unknown", "uncertainty", "stop reason"])
    elif task_type == "research_synthesis":
        pieces.extend(
            [
                "research direction",
                "evidence-backed gap",
                "closest prior work",
                "counterevidence",
                "source policy",
                "missing searches",
            ]
        )
        for run in runs:
            pieces.extend(gap.title or gap.description for gap in run.gaps[:6])
            pieces.extend(dossier.idea_summary for dossier in run.novelty_dossiers[:6])
    return " ".join(piece for piece in pieces if piece).strip()


def _search_runs(runs: list[ResearchRunState], query: str, budget: TaskContextBudget) -> list[RetrievalResult]:
    top_k = _retrieval_top_k(budget)
    results: list[RetrievalResult] = []
    for run in runs:
        run_results, _paper_ids = retrieval_candidates_for_state(run, query, top_k=top_k, persist=False)
        results.extend(result for result in run_results if _result_has_task_overlap(result))
    return _dedupe_results(results)


def _retrieval_top_k(budget: TaskContextBudget) -> int:
    return max(12, budget.max_papers * 3 + budget.max_sections + budget.max_evidence_spans)


def _dedupe_results(results: list[RetrievalResult]) -> list[RetrievalResult]:
    deduped: dict[tuple[str, str, str], RetrievalResult] = {}
    for result in results:
        key = (result.object_type, result.object_id, result.paper_id)
        existing = deduped.get(key)
        if existing is None or result.score > existing.score:
            deduped[key] = result
    return list(deduped.values())


def _result_has_task_overlap(result: RetrievalResult) -> bool:
    return result.lexical_score > 0 or result.rerank_score > 0


def _closest_prior_work_ids(runs: list[ResearchRunState], program: ResearchProgramState, task_type: str) -> list[str]:
    if task_type not in {"novelty_reviewer", "research_synthesis"}:
        return []
    paper_ids: list[str] = []
    for run in runs:
        for assessment in run.novelty_assessments:
            paper_ids.extend(assessment.closest_prior_work)
        for dossier in run.novelty_dossiers:
            paper_ids.extend(dossier.top_prior_work)
            paper_ids.extend(_paper_ids_from_comparison_table(dossier.comparison_table))
    for direction in program.research_directions:
        paper_ids.extend(direction.counterevidence_paper_ids)
    return _unique_ids(_normalize_prior_work_id(paper_id) for paper_id in paper_ids)


def _selected_paper_ids(
    retrieval_results: list[RetrievalResult],
    closest_prior_ids: list[str],
    budget: TaskContextBudget,
) -> list[str]:
    selected: list[str] = []
    for paper_id in closest_prior_ids:
        if paper_id:
            selected.append(paper_id)
    for result in retrieval_results:
        if result.paper_id:
            selected.append(result.paper_id)
        linked = result.metadata.get("linked_paper_ids")
        if isinstance(linked, list):
            selected.extend(str(item) for item in linked if item)
    return _unique_ids(selected)[: budget.max_papers]


def _select_papers(
    runs: list[ResearchRunState],
    selected_paper_ids: list[str],
    budget: TaskContextBudget,
    query: str,
    closest_prior_ids: list[str],
) -> list[Paper]:
    paper_by_id = _papers_by_id(runs)
    closest_set = set(closest_prior_ids)
    query_terms = _focus_tokens(query)
    papers = [
        paper_by_id[paper_id]
        for paper_id in selected_paper_ids
        if paper_id in paper_by_id and (paper_id in closest_set or _paper_matches_query(paper_by_id[paper_id], query_terms))
    ]
    if papers:
        return papers[: budget.max_papers]
    # If retrieval finds nothing, include a small corpus preview but mark limitations elsewhere.
    return list(paper_by_id.values())[: budget.max_papers]


def _select_evidence_spans(
    runs: list[ResearchRunState],
    retrieval_results: list[RetrievalResult],
    selected_paper_ids: list[str],
    budget: TaskContextBudget,
) -> tuple[list[EvidenceSpan], bool]:
    spans_by_id = {span.id: span for run in runs for span in run.evidence_spans}
    span_ids = [
        result.object_id for result in retrieval_results if result.object_type == "evidence_span" and result.object_id in spans_by_id
    ]
    selected_set = set(selected_paper_ids)
    span_ids.extend(span.id for span in spans_by_id.values() if span.paper_id in selected_set)
    unique_ids = _unique_ids(span_ids)
    selected = [spans_by_id[span_id] for span_id in unique_ids[: budget.max_evidence_spans]]
    return selected, len(unique_ids) > len(selected)


def _select_sections(
    runs: list[ResearchRunState],
    retrieval_results: list[RetrievalResult],
    selected_paper_ids: list[str],
    budget: TaskContextBudget,
) -> tuple[list[PaperSection], bool]:
    sections_by_id = {section.id: section for run in runs for section in run.paper_sections}
    section_ids = [
        result.object_id for result in retrieval_results if result.object_type == "paper_section" and result.object_id in sections_by_id
    ]
    selected_set = set(selected_paper_ids)
    section_ids.extend(section.id for section in sections_by_id.values() if section.paper_id in selected_set)
    unique_ids = _unique_ids(section_ids)
    selected = [sections_by_id[section_id] for section_id in unique_ids[: budget.max_sections]]
    return selected, len(unique_ids) > len(selected)


def _select_novelty_snippets(
    runs: list[ResearchRunState],
    program: ResearchProgramState,
    selected_paper_ids: list[str],
    budget: TaskContextBudget,
) -> tuple[list[dict[str, Any]], bool]:
    selected_set = set(selected_paper_ids)
    snippets: list[dict[str, Any]] = []
    for run in runs:
        for dossier in run.novelty_dossiers:
            if _dossier_mentions_papers(dossier, selected_set) or not selected_set:
                snippets.append(_dossier_payload(dossier))
    for record in program.memory_records:
        if record.record_type == "prior_work" and (set(record.linked_paper_ids) & selected_set):
            snippets.append(
                {
                    "record_id": record.id,
                    "text": _limit_text(record.text, budget.max_text_chars),
                    "linked_paper_ids": record.linked_paper_ids,
                    "confidence": record.confidence,
                }
            )
    selected = snippets[: budget.max_novelty_snippets]
    return selected, len(snippets) > len(selected)


def _select_related_work_snippets(
    runs: list[ResearchRunState],
    program: ResearchProgramState,
    selected_paper_ids: list[str],
    budget: TaskContextBudget,
) -> tuple[list[dict[str, Any]], bool]:
    matrices = [*program.related_work_matrices]
    for run in runs:
        matrices.extend(run.related_work_matrices)
    snippets: list[dict[str, Any]] = []
    selected_set = set(selected_paper_ids)
    for matrix in matrices:
        entries = [
            {
                "paper_id": entry.paper_id,
                "relationship": entry.relationship,
                "relevance_score": entry.relevance_score,
                "evidence_span_ids": entry.evidence_span_ids,
                "what_it_contributes": _limit_text(entry.what_it_contributes, budget.max_text_chars // 2),
                "what_it_does_not_solve": _limit_text(entry.what_it_does_not_solve, budget.max_text_chars // 2),
                "must_cite": entry.must_cite,
                "baseline_candidate": entry.baseline_candidate,
            }
            for entry in matrix.entries
            if not selected_set or entry.paper_id in selected_set
        ]
        if entries or matrix.coverage_summary:
            snippets.append(
                {
                    "direction_id": matrix.direction_id,
                    "coverage_summary": _limit_text(matrix.coverage_summary, budget.max_text_chars),
                    "missing_categories": matrix.missing_categories,
                    "must_read_paper_ids": matrix.must_read_paper_ids,
                    "baseline_paper_ids": matrix.baseline_paper_ids,
                    "entries": entries[:5],
                }
            )
    selected = snippets[: budget.max_related_work_snippets]
    return selected, len(snippets) > len(selected)


def _select_claim_nodes(
    claim_graph: ClaimGraph | None,
    selected_paper_ids: list[str],
    query: str,
    budget: TaskContextBudget,
) -> tuple[list[dict[str, Any]], bool]:
    if claim_graph is None:
        return [], False
    selected_set = set(selected_paper_ids)
    query_terms = _tokens(query)
    nodes = []
    for node in claim_graph.nodes:
        node_terms = _tokens(node.text)
        if selected_set & set(node.source_paper_ids) or query_terms & node_terms:
            nodes.append(
                {
                    "id": node.id,
                    "text": _limit_text(node.text, budget.max_text_chars),
                    "claim_type": node.claim_type,
                    "status": node.status,
                    "confidence": node.confidence,
                    "supporting_evidence_span_ids": node.supporting_evidence_span_ids,
                    "counterevidence_span_ids": node.counterevidence_span_ids,
                    "source_paper_ids": node.source_paper_ids,
                    "run_ids": node.run_ids,
                }
            )
    selected = nodes[: budget.max_claim_nodes]
    return selected, len(nodes) > len(selected)


def _campaign_summary(campaign_state: CampaignState) -> dict[str, Any]:
    campaign = campaign_state.campaign
    return {
        "id": campaign.id,
        "project_id": campaign.project_id,
        "topic": campaign.topic,
        "title": campaign.title,
        "status": campaign.status,
        "mode": campaign.mode,
        "agent_name": campaign.agent_name,
        "model": campaign.model,
        "source_profile": campaign.source_profile,
        "run_ids": campaign.run_ids,
        "task_ids": campaign.task_ids,
        "decision_count": len(campaign_state.decisions),
        "milestone_count": len(campaign_state.milestones),
        "stop_conditions": to_plain(campaign_state.stop_conditions),
    }


def _source_coverage_summary(runs: list[ResearchRunState]) -> dict[str, Any]:
    reports = [run.source_coverage for run in runs if run.source_coverage is not None]
    searched_sources = sorted({source for report in reports for source in report.searched_sources})
    failed_sources = sorted({source for report in reports for source in report.failed_sources})
    papers_with_full_text = sorted({paper_id for report in reports for paper_id in report.papers_with_full_text})
    papers_abstract_only = sorted({paper_id for report in reports for paper_id in report.papers_abstract_only})
    warnings = [warning for report in reports for warning in report.coverage_warnings]
    if not reports:
        warnings.append("No SourceCoverageReport is available for attached runs.")
    if not papers_with_full_text:
        warnings.append("No parsed full text is recorded for attached runs.")
    return {
        "run_count": len(runs),
        "searched_sources": searched_sources,
        "failed_sources": failed_sources,
        "papers_by_source": _merged_papers_by_source(reports),
        "papers_with_full_text": papers_with_full_text,
        "papers_abstract_only": papers_abstract_only,
        "coverage_warnings": warnings,
        "confidence": _lowest_confidence([report.confidence for report in reports]),
    }


def _human_review_constraints(program: ResearchProgramState, runs: list[ResearchRunState]) -> dict[str, Any]:
    open_queue = []
    if program.review_queue is not None:
        open_queue = [to_plain(item) for item in program.review_queue.items if item.status == "open"]
    run_reviews = [to_plain(review) for run in runs for review in run.human_reviews]
    return {
        "open_review_queue_items": open_queue,
        "run_human_reviews": run_reviews,
        "locked_objects": [review for review in run_reviews if review.get("action") == "lock"],
        "rejected_objects": [review for review in run_reviews if review.get("action") == "reject"],
    }


def _allowed_object_ids(
    campaign_state: CampaignState,
    program: ResearchProgramState,
    runs: list[ResearchRunState],
) -> dict[str, list[str]]:
    return {
        "run_ids": [run.run_id for run in runs],
        "campaign_task_ids": list(campaign_state.campaign.task_ids),
        "paper_ids": _unique_ids(paper.id for run in runs for paper in run.papers),
        "paper_section_ids": _unique_ids(section.id for run in runs for section in run.paper_sections),
        "evidence_span_ids": _unique_ids(span.id for run in runs for span in run.evidence_spans),
        "claim_ids": _unique_ids(claim.id for run in runs for claim in run.claims),
        "gap_ids": _unique_ids(gap.id for run in runs for gap in run.gaps),
        "novelty_target_ids": _unique_ids(dossier.target_id for run in runs for dossier in run.novelty_dossiers),
        "research_direction_ids": _unique_ids(direction.id for direction in program.research_directions),
        "related_work_direction_ids": _unique_ids(matrix.direction_id for matrix in [*program.related_work_matrices]),
        "claim_graph_node_ids": _unique_ids(node.id for node in program.claim_graph.nodes) if program.claim_graph else [],
        "project_memory_record_ids": _unique_ids(record.id for record in program.memory_records),
    }


def _uncertainty_and_missing_coverage(runs: list[ResearchRunState], has_retrieval_results: bool) -> list[str]:
    warnings: list[str] = []
    if not runs:
        warnings.append("No attached run state is available; context is limited to project metadata.")
    if not has_retrieval_results:
        warnings.append("Hybrid retrieval returned no matching documents; inspect allowed IDs before making claims.")
    if not any(run.evidence_spans for run in runs):
        warnings.append("No EvidenceSpan locators are available; high-confidence claims should be avoided.")
    if not any(run.paper_sections for run in runs):
        warnings.append("No PaperSection full-text context is available; abstract-only uncertainty applies.")
    for run in runs:
        if run.source_coverage is None:
            warnings.append(f"Run {run.run_id} has no source coverage report.")
        elif run.source_coverage.confidence == "low":
            warnings.append(f"Run {run.run_id} has low source coverage confidence.")
        if run.coverage_stopping_assessment is not None and not run.coverage_stopping_assessment.enough_for_novelty:
            warnings.append(f"Run {run.run_id} is not coverage-sufficient for novelty checking.")
    return _unique_ids(warnings)


def _closest_prior_candidates(
    runs: list[ResearchRunState],
    program: ResearchProgramState,
    closest_prior_ids: list[str],
    retrieval_results: list[RetrievalResult],
) -> list[dict[str, Any]]:
    paper_ids = list(closest_prior_ids)
    if not paper_ids:
        paper_ids.extend(
            result.paper_id
            for result in retrieval_results
            if result.paper_id and result.object_type in {"paper", "paper_section", "evidence_span"}
        )
    paper_by_id = _papers_by_id(runs)
    candidates: list[dict[str, Any]] = []
    for paper_id in _unique_ids(paper_ids):
        paper = paper_by_id.get(paper_id)
        if paper:
            candidates.append(_paper_payload(paper))
        elif any(record.paper_id == paper_id or paper_id in record.source_paper_ids for record in program.corpus_papers):
            candidates.append({"paper_id": paper_id, "title": "", "source": "project-corpus", "known_in_corpus": True})
    return candidates[:8]


def _paper_payload(paper: Paper) -> dict[str, Any]:
    return {
        "id": paper.id,
        "title": paper.title,
        "authors": paper.authors,
        "year": paper.year,
        "venue": paper.venue,
        "source": paper.source,
        "doi": paper.doi,
        "arxiv_id": paper.arxiv_id,
        "roles": paper.roles,
        "citation_count": paper.citation_count,
        "abstract": _limit_text(paper.abstract, 700),
    }


def _section_payload(section: PaperSection, budget: TaskContextBudget) -> dict[str, Any]:
    return {
        "id": section.id,
        "paper_id": section.paper_id,
        "title": section.title,
        "section_type": section.section_type,
        "page_start": section.page_start,
        "page_end": section.page_end,
        "locator": f"{section.paper_id}:{section.title or section.section_type}:p{section.page_start or '?'}",
        "confidence": section.confidence,
        "text": _limit_text(section.text, budget.max_text_chars),
    }


def _span_payload(span: EvidenceSpan, budget: TaskContextBudget) -> dict[str, Any]:
    return {
        "id": span.id,
        "paper_id": span.paper_id,
        "section_id": span.section_id,
        "locator": span.locator,
        "evidence_type": span.evidence_type,
        "confidence": span.confidence,
        "quote": _limit_text(span.quote, min(500, budget.max_text_chars)),
    }


def _retrieval_result_payload(result: RetrievalResult) -> dict[str, Any]:
    return {
        "document_id": result.document_id,
        "object_type": result.object_type,
        "object_id": result.object_id,
        "paper_id": result.paper_id,
        "score": result.score,
        "locator": result.locator,
        "snippet": result.text_snippet,
    }


def _dossier_payload(dossier: NoveltyDossier) -> dict[str, Any]:
    return {
        "target_id": dossier.target_id,
        "idea_summary": dossier.idea_summary,
        "top_prior_work": dossier.top_prior_work,
        "candidates_considered": dossier.candidates_considered,
        "decisive_difference_needed": dossier.decisive_difference_needed,
        "missing_searches": dossier.missing_searches,
        "verdict": dossier.verdict,
        "novelty_strength": dossier.novelty_strength,
        "confidence": dossier.confidence,
        "reviewer_objection": dossier.reviewer_objection,
        "recommended_action": dossier.recommended_action,
    }


def _enforce_char_budget(payload: dict[str, Any], budget: TaskContextBudget) -> dict[str, Any]:
    actual = _json_chars(payload)
    payload["context_budget"]["actual_chars"] = actual
    if actual <= budget.max_chars:
        return payload
    payload["context_limited"] = True
    payload["compression_summaries"].append(
        f"Initial context was {actual} chars, above {budget.max_chars}; section and evidence text was further compressed."
    )
    for section in payload["relevant_sections"]:
        section["text"] = _limit_text(str(section.get("text", "")), max(180, budget.max_text_chars // 3))
    for span in payload["relevant_evidence_spans"]:
        span["quote"] = _limit_text(str(span.get("quote", "")), max(160, budget.max_text_chars // 3))
    for paper in payload["top_relevant_papers"]:
        paper["abstract"] = _limit_text(str(paper.get("abstract", "")), 220)
    actual = _json_chars(payload)
    payload["context_budget"]["actual_chars"] = actual
    if actual > budget.max_chars:
        payload["compression_summaries"].append(f"Compressed context is still {actual} chars; use artifact links for additional details.")
        payload["retrieval"]["top_results"] = payload["retrieval"]["top_results"][:5]
        payload["novelty_dossier_snippets"] = payload["novelty_dossier_snippets"][:2]
        payload["related_work_matrix_snippets"] = payload["related_work_matrix_snippets"][:2]
        while actual > budget.max_chars and payload["relevant_sections"]:
            removed = payload["relevant_sections"].pop()
            payload["compression_summaries"].append(f"Omitted section {removed.get('id')} to fit the context budget.")
            actual = _json_chars(payload)
        while actual > budget.max_chars and payload["relevant_evidence_spans"]:
            removed = payload["relevant_evidence_spans"].pop()
            payload["compression_summaries"].append(f"Omitted evidence span {removed.get('id')} to fit the context budget.")
            actual = _json_chars(payload)
        payload["context_budget"]["actual_chars"] = actual
    return payload


def _json_chars(payload: dict[str, Any]) -> int:
    return len(json.dumps(payload, sort_keys=True))


def _papers_by_id(runs: list[ResearchRunState]) -> dict[str, Paper]:
    return {paper.id: paper for run in runs for paper in run.papers}


def _paper_ids_from_comparison_table(rows: list[dict[str, Any]]) -> list[str]:
    paper_ids: list[str] = []
    for row in rows:
        for key in ("paper_id", "prior_work_id", "id"):
            value = row.get(key)
            if isinstance(value, str):
                paper_ids.append(value)
        value = row.get("top_prior_work")
        if isinstance(value, list):
            paper_ids.extend(str(item) for item in value if item)
    return paper_ids


def _normalize_prior_work_id(value: str) -> str:
    text = str(value).strip()
    if text.startswith("paper:"):
        return text.removeprefix("paper:")
    return text


def _dossier_mentions_papers(dossier: NoveltyDossier, paper_ids: set[str]) -> bool:
    mentioned = (
        set(dossier.top_prior_work) | set(dossier.candidates_considered) | set(_paper_ids_from_comparison_table(dossier.comparison_table))
    )
    return bool(mentioned & paper_ids)


def _merged_papers_by_source(reports: list[Any]) -> dict[str, int]:
    merged: dict[str, int] = {}
    for report in reports:
        for source, count in report.papers_by_source.items():
            merged[source] = merged.get(source, 0) + int(count)
    return merged


def _lowest_confidence(values: list[str]) -> str:
    order = {"low": 0, "medium": 1, "high": 2}
    if not values:
        return "low"
    return min(values, key=lambda item: order.get(item, 0))


def _tokens(text: str) -> set[str]:
    return {token for token in "".join(char.lower() if char.isalnum() else " " for char in text).split() if len(token) > 2}


def _focus_tokens(text: str) -> set[str]:
    generic = {
        "closest",
        "prior",
        "work",
        "novelty",
        "benchmark",
        "evaluation",
        "results",
        "result",
        "method",
        "methods",
        "dataset",
        "datasets",
        "metric",
        "metrics",
        "evidence",
        "paper",
        "papers",
    }
    return _tokens(text) - generic


def _paper_matches_query(paper: Paper, query_terms: set[str]) -> bool:
    if not query_terms:
        return True
    paper_terms = _tokens(" ".join([paper.title, paper.abstract, paper.venue, " ".join(paper.keywords), " ".join(paper.roles)]))
    return len(query_terms & paper_terms) >= min(2, len(query_terms))


def _limit_text(text: str, max_chars: int) -> str:
    normalized = " ".join(text.split())
    if len(normalized) <= max_chars:
        return normalized
    return normalized[: max(0, max_chars - 18)].rstrip() + " ... [truncated]"


def _unique_ids(values: Any) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        text = str(value).strip()
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result
