"""Build structured related-work matrices for gaps and research directions."""

from __future__ import annotations

import hashlib

from gapforge.config import GapForgeConfig
from gapforge.models import (
    EvidenceSpan,
    Gap,
    NoveltyDossier,
    Paper,
    Provenance,
    RelatedWorkEntry,
    RelatedWorkMatrix,
    ResearchDirection,
    ResearchRunState,
)
from gapforge.project_memory import ProjectMemoryManager
from gapforge.related_work.taxonomy import REQUIRED_CATEGORIES
from gapforge.retrieval.hybrid import retrieval_candidates_for_state
from gapforge.sources.ranking_v2 import infer_paper_role
from gapforge.state import ResearchStateManager, utc_now_iso


class RelatedWorkMatrixBuilder:
    """Classify prior work around a gap or project research direction."""

    def __init__(self, config: GapForgeConfig) -> None:
        self.config = config
        self.state_manager = ResearchStateManager(config)
        self.project_manager = ProjectMemoryManager(config)

    def build_for_run(self, run_id: str, gap_id: str) -> RelatedWorkMatrix:
        state = self.state_manager.load_run(run_id)
        gap = _require_gap(state, gap_id)
        matrix = self._build_matrix(state, direction_id=gap.id, gap=gap)
        state.related_work_matrices = _replace_matrix(state.related_work_matrices, matrix)
        _apply_baselines_to_experiments(state, matrix)
        self.state_manager.save_run(state)
        return matrix

    def build_for_project(self, project_id: str, direction_id: str) -> RelatedWorkMatrix:
        program = self.project_manager.load_project(project_id)
        direction = _require_direction(program.research_directions, direction_id)
        loaded_runs = [self.state_manager.load_run(run_id) for run_id in program.run_ids]
        if not loaded_runs:
            raise ValueError(f"Project {project_id} has no attached runs.")
        matrices = [self._build_matrix(state, direction_id=direction.id, gap=gap) for state, gap in _direction_gaps(loaded_runs, direction)]
        if not matrices:
            raise KeyError(f"Direction {direction_id} has no linked gap in attached runs.")
        matrix = _merge_matrices(direction.id, matrices)
        program.related_work_matrices = _replace_matrix(program.related_work_matrices, matrix)
        _apply_matrix_to_direction(direction, matrix)
        for state in loaded_runs:
            if any(gap.id in direction.linked_gap_ids for gap in state.gaps):
                state.related_work_matrices = _replace_matrix(state.related_work_matrices, matrix)
                _apply_baselines_to_experiments(state, matrix)
                self.state_manager.save_run(state)
        self.project_manager.save_project(program)
        return matrix

    def must_read_for_project(self, project_id: str, direction_id: str) -> list[str]:
        program = self.project_manager.load_project(project_id)
        matrix = next((item for item in program.related_work_matrices if item.direction_id == direction_id), None)
        if matrix is None:
            matrix = self.build_for_project(project_id, direction_id)
        return matrix.must_read_paper_ids

    def _build_matrix(self, state: ResearchRunState, *, direction_id: str, gap: Gap) -> RelatedWorkMatrix:
        query = " ".join([state.topic.text, gap.title, gap.description, gap.minimum_experiment_needed]).strip()
        retrieval_results, retrieval_paper_ids = retrieval_candidates_for_state(state, query, top_k=25, persist=False)
        scores = {result.paper_id: max(result.score, 0.0) for result in retrieval_results if result.paper_id}
        candidates = _candidate_paper_ids(state, gap, retrieval_paper_ids)
        entries = [
            _entry_for_paper(state, gap, paper, direction_id=direction_id, retrieval_score=scores.get(paper.id, 0.0))
            for paper in _papers_by_ids(state.papers, candidates)
        ]
        entries = sorted(_dedupe_entries(entries), key=lambda item: (-item.relevance_score, item.paper_id))
        categories = {entry.relationship for entry in entries}
        missing_categories = sorted(category for category in REQUIRED_CATEGORIES if category not in categories)
        must_read = _dedupe([entry.paper_id for entry in entries if entry.must_cite or entry.reviewer_risk_if_omitted])
        baselines = _dedupe([entry.paper_id for entry in entries if entry.baseline_candidate])
        summary = _coverage_summary(entries, missing_categories)
        return RelatedWorkMatrix(
            direction_id=direction_id,
            entries=entries,
            coverage_summary=summary,
            missing_categories=missing_categories,
            must_read_paper_ids=must_read,
            baseline_paper_ids=baselines,
            provenance=Provenance(
                created_by_skill="related-work-matrix",
                source_ids=[state.run_id, gap.id, *[entry.paper_id for entry in entries]],
                timestamp=utc_now_iso(),
                reasoning_summary=(
                    "Classified prior work using retrieval results, novelty dossiers, citation metadata, paper roles, "
                    "and evidence spans. Relationships are deterministic and conservative."
                ),
            ),
        )


def _entry_for_paper(
    state: ResearchRunState,
    gap: Gap,
    paper: Paper,
    *,
    direction_id: str,
    retrieval_score: float,
) -> RelatedWorkEntry:
    dossier = next((item for item in state.novelty_dossiers if item.target_id == gap.id), None)
    relationship, reasons = _relationship_for_paper(state, gap, paper, dossier)
    evidence_span_ids = [span.id for span in _evidence_for_paper(state, paper.id)]
    relevance_score = _relevance_score(state, gap, paper, relationship, retrieval_score, dossier)
    must_cite = (
        relationship in {"directly_solves", "partially_solves", "survey_background", "theoretical_foundation"} or relevance_score >= 0.7
    )
    baseline_candidate = relationship in {"baseline_to_include", "benchmark_dataset_provider", "directly_solves", "partially_solves"}
    risk = _reviewer_risk(relationship, paper, relevance_score)
    return RelatedWorkEntry(
        direction_id=direction_id,
        paper_id=paper.id,
        relationship=relationship,
        relevance_score=round(relevance_score, 3),
        evidence_span_ids=evidence_span_ids,
        what_it_contributes="; ".join(reasons) or _paper_summary(paper),
        what_it_does_not_solve=_does_not_solve(gap, paper, relationship, dossier),
        must_cite=must_cite,
        baseline_candidate=baseline_candidate,
        reviewer_risk_if_omitted=risk,
        provenance=Provenance(
            created_by_skill="related-work-matrix",
            source_ids=[gap.id, paper.id, *evidence_span_ids],
            timestamp=utc_now_iso(),
            reasoning_summary="Classified one prior-work paper against the target research direction.",
        ),
    )


def _relationship_for_paper(
    state: ResearchRunState,
    gap: Gap,
    paper: Paper,
    dossier: NoveltyDossier | None,
) -> tuple[str, list[str]]:
    reasons: list[str] = []
    role, role_reasons = infer_paper_role(state.topic.text, paper, state=state)
    if _is_direct_prior(paper.id, dossier):
        reasons.append("closest prior work appears to cover the proposed problem, method, or evaluation")
        return "directly_solves", reasons
    if _is_partial_prior(paper.id, dossier):
        reasons.append("closest-prior-work dossier shows partial overlap")
        return "partially_solves", reasons
    if role == "survey":
        return "survey_background", role_reasons
    if role in {"benchmark", "dataset"}:
        return "benchmark_dataset_provider", role_reasons
    if role == "theory":
        return "theoretical_foundation", role_reasons
    if role == "negative_result":
        return "negative_result", role_reasons
    if role == "adjacent_field" or _is_cross_domain_source(state, paper.id, gap.id):
        return "cross_domain_analogy", role_reasons or ["linked to cross-domain transfer or adjacent-field search"]
    if _is_baseline_candidate(paper, gap, dossier):
        return "baseline_to_include", ["paper is a method or closest-prior-work candidate suitable as a baseline"]
    return "adjacent_method", role_reasons or ["retrieval or citation context suggests related method"]


def _relevance_score(
    state: ResearchRunState,
    gap: Gap,
    paper: Paper,
    relationship: str,
    retrieval_score: float,
    dossier: NoveltyDossier | None,
) -> float:
    text_overlap = _token_overlap(" ".join([gap.title, gap.description]), " ".join([paper.title, paper.abstract]))
    role_bonus = {
        "directly_solves": 0.45,
        "partially_solves": 0.35,
        "baseline_to_include": 0.25,
        "benchmark_dataset_provider": 0.22,
        "survey_background": 0.2,
        "theoretical_foundation": 0.16,
        "negative_result": 0.14,
        "cross_domain_analogy": 0.12,
        "adjacent_method": 0.08,
    }.get(relationship, 0.0)
    dossier_score = _dossier_score(paper.id, dossier)
    citation = min(max(paper.citation_count, 0) / 500.0, 0.15)
    evidence = 0.08 if any(span.paper_id == paper.id for span in state.evidence_spans) else 0.0
    return min(1.0, max(retrieval_score, text_overlap) * 0.45 + role_bonus + dossier_score + citation + evidence)


def _candidate_paper_ids(state: ResearchRunState, gap: Gap, retrieval_paper_ids: list[str]) -> list[str]:
    paper_ids = [*gap.supporting_paper_ids, *gap.linked_paper_ids, *retrieval_paper_ids]
    for assessment in state.novelty_assessments:
        if assessment.target_gap_or_hypothesis_id == gap.id:
            paper_ids.extend(_prior_ids_from_strings(assessment.closest_prior_work))
    for dossier in state.novelty_dossiers:
        if dossier.target_id == gap.id:
            paper_ids.extend(dossier.candidates_considered)
            paper_ids.extend(dossier.top_prior_work)
            paper_ids.extend(str(row.get("paper_id", "")) for row in dossier.comparison_table)
    for paper in state.papers:
        role, _ = infer_paper_role(state.topic.text, paper, state=state)
        if role in {"survey", "benchmark", "dataset", "theory", "negative_result"}:
            paper_ids.append(paper.id)
    if state.citation_graph is not None:
        important = set(gap.supporting_paper_ids + gap.linked_paper_ids)
        for edge in state.citation_graph.edges:
            if edge.source_paper_id in important:
                paper_ids.append(edge.target_paper_id)
            if edge.target_paper_id in important:
                paper_ids.append(edge.source_paper_id)
    for transfer in state.cross_domain_transfers:
        if transfer.target_gap_id == gap.id:
            paper_ids.extend(transfer.source_paper_ids)
    return _dedupe(paper_ids)


def _is_direct_prior(paper_id: str, dossier: NoveltyDossier | None) -> bool:
    if dossier is None:
        return False
    if dossier.verdict == "reject" and paper_id in set(dossier.top_prior_work + dossier.candidates_considered):
        return True
    for row in dossier.comparison_table:
        if str(row.get("paper_id", "")) != paper_id:
            continue
        overall = float(row.get("overall_similarity") or row.get("score") or 0.0)
        problem = float(row.get("problem_overlap") or 0.0)
        method = float(row.get("method_overlap") or 0.0)
        evaluation = float(row.get("evaluation_overlap") or 0.0)
        if overall >= 0.82 or (problem >= 0.7 and method >= 0.65 and evaluation >= 0.55):
            return True
    return False


def _is_partial_prior(paper_id: str, dossier: NoveltyDossier | None) -> bool:
    if dossier is None:
        return False
    if paper_id in set(dossier.top_prior_work + dossier.candidates_considered):
        return True
    for row in dossier.comparison_table:
        if str(row.get("paper_id", "")) == paper_id:
            overall = float(row.get("overall_similarity") or row.get("score") or 0.0)
            return overall >= 0.45
    return False


def _is_baseline_candidate(paper: Paper, gap: Gap, dossier: NoveltyDossier | None) -> bool:
    text = " ".join([paper.title, paper.abstract, " ".join(paper.roles)]).lower()
    if any(term in text for term in ["baseline", "method", "algorithm", "detector", "model", "benchmark"]):
        return True
    return dossier is not None and paper.id in set(dossier.top_prior_work + dossier.candidates_considered)


def _is_cross_domain_source(state: ResearchRunState, paper_id: str, gap_id: str) -> bool:
    return any(transfer.target_gap_id == gap_id and paper_id in transfer.source_paper_ids for transfer in state.cross_domain_transfers)


def _dossier_score(paper_id: str, dossier: NoveltyDossier | None) -> float:
    if dossier is None:
        return 0.0
    if paper_id in dossier.top_prior_work:
        return 0.28
    if paper_id in dossier.candidates_considered:
        return 0.18
    for row in dossier.comparison_table:
        if str(row.get("paper_id", "")) == paper_id:
            return min(0.28, float(row.get("overall_similarity") or row.get("score") or 0.0) * 0.25)
    return 0.0


def _does_not_solve(gap: Gap, paper: Paper, relationship: str, dossier: NoveltyDossier | None) -> str:
    if relationship == "directly_solves":
        return "This paper may already solve the direction; the direction should be blocked or reframed."
    if dossier is not None and dossier.decisive_difference_needed:
        return dossier.decisive_difference_needed
    if gap.why_existing_work_does_not_solve_it:
        return gap.why_existing_work_does_not_solve_it
    return f"No evidence yet that `{paper.id}` fully resolves {gap.title or gap.id}."


def _reviewer_risk(relationship: str, paper: Paper, relevance_score: float) -> str:
    if relationship == "directly_solves":
        return "fatal novelty risk if omitted or mischaracterized"
    if relationship == "partially_solves":
        return "major positioning risk; reviewer may view the idea as incremental"
    if relationship == "survey_background":
        return "background coverage risk; reviewer may question literature awareness"
    if relationship == "benchmark_dataset_provider":
        return "empirical rigor risk; dataset or benchmark may be expected"
    if relationship == "baseline_to_include":
        return "baseline omission risk; experiment may be considered underpowered"
    if relevance_score >= 0.7:
        return "highly relevant work should be cited or justified"
    return ""


def _evidence_for_paper(state: ResearchRunState, paper_id: str) -> list[EvidenceSpan]:
    spans = [span for span in state.evidence_spans if span.paper_id == paper_id]
    for dossier in state.novelty_dossiers:
        spans.extend(span for span in dossier.evidence_spans if span.paper_id == paper_id)
    seen: set[str] = set()
    result = []
    for span in spans:
        if span.id not in seen:
            result.append(span)
            seen.add(span.id)
    return result


def _merge_matrices(direction_id: str, matrices: list[RelatedWorkMatrix]) -> RelatedWorkMatrix:
    entries = _dedupe_entries([entry for matrix in matrices for entry in matrix.entries], direction_id=direction_id)
    categories = {entry.relationship for entry in entries}
    missing = sorted(category for category in REQUIRED_CATEGORIES if category not in categories)
    return RelatedWorkMatrix(
        direction_id=direction_id,
        entries=entries,
        coverage_summary=_coverage_summary(entries, missing),
        missing_categories=missing,
        must_read_paper_ids=_dedupe([entry.paper_id for entry in entries if entry.must_cite or entry.reviewer_risk_if_omitted]),
        baseline_paper_ids=_dedupe([entry.paper_id for entry in entries if entry.baseline_candidate]),
        provenance=Provenance(
            created_by_skill="related-work-matrix",
            source_ids=[direction_id],
            timestamp=utc_now_iso(),
            reasoning_summary="Merged related-work matrices from attached project runs for one research direction.",
        ),
    )


def _apply_matrix_to_direction(direction: ResearchDirection, matrix: RelatedWorkMatrix) -> None:
    if any(entry.relationship == "directly_solves" for entry in matrix.entries):
        issue = "Related-work matrix contains directly solving prior work."
        if issue not in direction.blocking_issues:
            direction.blocking_issues.append(issue)
        if direction.maturity not in {"seed", "candidate", "rejected"}:
            direction.maturity = "candidate"
            direction.readiness_score = min(direction.readiness_score, 0.35)
    direction.supporting_paper_ids = _dedupe([*direction.supporting_paper_ids, *matrix.must_read_paper_ids])
    direction.counterevidence_paper_ids = _dedupe(
        [*direction.counterevidence_paper_ids, *[entry.paper_id for entry in matrix.entries if entry.relationship == "directly_solves"]]
    )


def _apply_baselines_to_experiments(state: ResearchRunState, matrix: RelatedWorkMatrix) -> None:
    candidate_labels = [f"related-work baseline paper: {paper_id}" for paper_id in matrix.baseline_paper_ids]
    if not candidate_labels:
        return
    linked_gap_ids = {matrix.direction_id}
    for gap in state.gaps:
        if gap.id == matrix.direction_id:
            linked_gap_ids.add(gap.id)
    for experiment in state.experiments:
        if linked_gap_ids.intersection(experiment.linked_gap_ids):
            experiment.baselines = _dedupe([*experiment.baselines, *candidate_labels])


def _direction_gaps(loaded_runs: list[ResearchRunState], direction: ResearchDirection) -> list[tuple[ResearchRunState, Gap]]:
    pairs: list[tuple[ResearchRunState, Gap]] = []
    for state in loaded_runs:
        for gap in state.gaps:
            if gap.id in direction.linked_gap_ids:
                pairs.append((state, gap))
    return pairs


def _require_gap(state: ResearchRunState, gap_id: str) -> Gap:
    gap = next((item for item in state.gaps if item.id == gap_id), None)
    if gap is None:
        raise KeyError(f"Unknown gap: {gap_id}")
    return gap


def _require_direction(directions: list[ResearchDirection], direction_id: str) -> ResearchDirection:
    direction = next((item for item in directions if item.id == direction_id), None)
    if direction is None:
        raise KeyError(f"Unknown research direction: {direction_id}")
    return direction


def _papers_by_ids(papers: list[Paper], paper_ids: list[str]) -> list[Paper]:
    by_id = {paper.id: paper for paper in papers}
    return [by_id[paper_id] for paper_id in paper_ids if paper_id in by_id]


def _prior_ids_from_strings(values: list[str]) -> list[str]:
    return [value.split(":", 1)[0].strip() for value in values if value.split(":", 1)[0].strip()]


def _coverage_summary(entries: list[RelatedWorkEntry], missing: list[str]) -> str:
    direct = sum(1 for entry in entries if entry.relationship == "directly_solves")
    baselines = sum(1 for entry in entries if entry.baseline_candidate)
    must = sum(1 for entry in entries if entry.must_cite)
    return (
        f"Classified {len(entries)} paper(s): {direct} directly solving risk(s), "
        f"{baselines} baseline candidate(s), {must} must-cite/must-read paper(s). "
        f"Missing categories: {', '.join(missing) or 'none'}."
    )


def _paper_summary(paper: Paper) -> str:
    return paper.abstract[:240] if paper.abstract else paper.title


def _token_overlap(left: str, right: str) -> float:
    left_tokens = {token for token in _tokens(left) if len(token) > 3}
    right_tokens = {token for token in _tokens(right) if len(token) > 3}
    if not left_tokens or not right_tokens:
        return 0.0
    return len(left_tokens & right_tokens) / max(1, len(left_tokens | right_tokens))


def _tokens(text: str) -> list[str]:
    return [token.strip(".,;:()[]{}").lower() for token in text.split()]


def _replace_matrix(matrices: list[RelatedWorkMatrix], matrix: RelatedWorkMatrix) -> list[RelatedWorkMatrix]:
    return [item for item in matrices if item.direction_id != matrix.direction_id] + [matrix]


def _dedupe_entries(entries: list[RelatedWorkEntry], *, direction_id: str | None = None) -> list[RelatedWorkEntry]:
    by_paper: dict[str, RelatedWorkEntry] = {}
    for entry in entries:
        if direction_id is not None:
            entry.direction_id = direction_id
        existing = by_paper.get(entry.paper_id)
        if existing is None or entry.relevance_score > existing.relevance_score:
            by_paper[entry.paper_id] = entry
        elif existing is not None:
            existing.evidence_span_ids = _dedupe([*existing.evidence_span_ids, *entry.evidence_span_ids])
            existing.must_cite = existing.must_cite or entry.must_cite
            existing.baseline_candidate = existing.baseline_candidate or entry.baseline_candidate
            if entry.reviewer_risk_if_omitted and not existing.reviewer_risk_if_omitted:
                existing.reviewer_risk_if_omitted = entry.reviewer_risk_if_omitted
    return list(by_paper.values())


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if item and item not in seen:
            result.append(item)
            seen.add(item)
    return result


def _stable_id(*parts: str) -> str:
    return hashlib.sha1("::".join(parts).encode("utf-8")).hexdigest()[:12]
