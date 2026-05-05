"""Research run state persistence and validation."""

from __future__ import annotations

import json
import re
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from gapforge.config import GapForgeConfig
from gapforge.models import (
    Claim,
    EvidenceSpan,
    ExperimentPlan,
    Gap,
    Paper,
    PaperNote,
    PaperRankingResult,
    PaperTriageResult,
    ResearchRunState,
    ResearchTopic,
    ReviewerObjection,
    ReviewerSimulationSummary,
    ValidationIssue,
    ValidationResult,
    to_plain,
)
from gapforge.redaction import redact_text

RUN_ARTIFACTS = [
    "topic.md",
    "config.json",
    "state.json",
    "papers.json",
    "paper_artifacts.json",
    "paper_sections.json",
    "evidence_spans.json",
    "evidence_spans.md",
    "search_queries.json",
    "source_coverage.json",
    "source_coverage.md",
    "coverage_stopping_assessment.json",
    "coverage_stopping_assessment.md",
    "full_text_coverage.md",
    "citation_graph.json",
    "citation_graph.md",
    "references.json",
    "references.md",
    "tables.json",
    "tables.md",
    "equations.json",
    "equations.md",
    "captions.json",
    "captions.md",
    "ocr_attempts.json",
    "ocr_status.md",
    "related_work_expansion.md",
    "paper_notes.json",
    "paper_notes.md",
    "paper_ranking.json",
    "paper_ranking.md",
    "paper_triage.json",
    "paper_triage.md",
    "field_map.json",
    "field_map.md",
    "claims.json",
    "gaps.json",
    "gaps.md",
    "gap_evidence_matrix.json",
    "gap_evidence_matrix.md",
    "hypotheses.json",
    "cross_domain_analogies.json",
    "cross_domain_analogies.md",
    "cross_domain_transfers.json",
    "cross_domain_transfers.md",
    "novelty_gate.json",
    "novelty_gate.md",
    "novelty_dossiers.json",
    "novelty_dossiers.md",
    "related_work_matrix.json",
    "related_work_matrix.md",
    "experiments.json",
    "experiments.md",
    "experiment_protocols.json",
    "experiment_protocols.md",
    "baseline_candidates.json",
    "baseline_candidates.md",
    "implementation_tasks.md",
    "reviewer_objections.json",
    "reviewer_summaries.json",
    "reviewer_simulation.md",
    "revised_experiment_recommendations.md",
    "human_reviews.json",
    "human_reviews.md",
    "review_queue.json",
    "review_queue.md",
    "agent_tasks.json",
    "agent_task_specs.json",
    "agent_run_records.json",
    "agent_validations.json",
    "agent_validation_results.json",
    "agent_tasks.md",
    "orchestrator_plan.json",
    "orchestrator_result.json",
    "active_loop.json",
    "active_decisions.md",
    "run_log.json",
    "rejected_ideas.json",
    "provenance.json",
    "run_report.md",
]


def utc_now_compact() -> str:
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")


def utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


def slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug or "topic"


class ResearchStateManager:
    """Durable state manager for GapForge research runs."""

    def __init__(self, config: GapForgeConfig) -> None:
        self.config = config
        self.config.ensure_dirs()

    def create_run(self, topic: str) -> ResearchRunState:
        slug = slugify(topic)
        base_run_id = f"{utc_now_compact()}-{slug}"
        run_id = base_run_id
        run_dir = self.config.runs_dir / run_id
        suffix = 2
        while run_dir.exists():
            run_id = f"{base_run_id}-{suffix}"
            run_dir = self.config.runs_dir / run_id
            suffix += 1
        run_dir.mkdir(parents=True, exist_ok=False)

        topic_model = ResearchTopic(text=topic, slug=slug, created_at=utc_now_iso())
        state = ResearchRunState(
            run_id=run_id,
            topic=topic_model,
            run_dir=str(run_dir),
            config={
                "schema_version": 2,
                "source_mode": "deterministic-fake",
                "llm_mode": self.config.llm_mode,
                "created_at": topic_model.created_at,
            },
        )
        self.save_run(state)
        return state

    def load_run(self, run_id: str) -> ResearchRunState:
        run_dir = self.config.runs_dir / run_id
        state_path = run_dir / "state.json"
        if not state_path.exists():
            raise FileNotFoundError(f"No run state found for {run_id}")
        raw = json.loads(state_path.read_text(encoding="utf-8"))
        return ResearchRunState.from_dict(raw)

    def save_run(self, state: ResearchRunState) -> None:
        run_dir = Path(state.run_dir)
        run_dir.mkdir(parents=True, exist_ok=True)
        self._write_topic(state)
        self._write_json(run_dir / "config.json", state.config)
        self._write_json(run_dir / "state.json", state.to_dict())
        self._write_json(run_dir / "papers.json", state.papers)
        self._write_json(run_dir / "paper_artifacts.json", state.paper_artifacts)
        self._write_json(run_dir / "paper_sections.json", state.paper_sections)
        self._write_json(run_dir / "evidence_spans.json", state.evidence_spans)
        self._write_json(run_dir / "search_queries.json", state.search_queries)
        self._write_json(run_dir / "source_coverage.json", state.source_coverage)
        self._write_json(run_dir / "coverage_stopping_assessment.json", state.coverage_stopping_assessment)
        self._write_json(run_dir / "citation_graph.json", state.citation_graph)
        self._write_json(run_dir / "references.json", state.references)
        self._write_json(run_dir / "tables.json", state.tables)
        self._write_json(run_dir / "equations.json", state.equations)
        self._write_json(run_dir / "captions.json", state.captions)
        self._write_json(run_dir / "ocr_attempts.json", state.ocr_attempts)
        self._write_json(run_dir / "paper_notes.json", state.paper_notes)
        self._write_json(run_dir / "paper_ranking.json", state.paper_ranking)
        self._write_json(run_dir / "paper_triage.json", state.paper_triage)
        self._write_json(run_dir / "field_map.json", state.field_map)
        self._write_json(run_dir / "claims.json", state.claims)
        self._write_json(run_dir / "gaps.json", state.gaps)
        self._write_json(run_dir / "gap_evidence_matrix.json", state.gap_evidence_matrices)
        self._write_json(run_dir / "hypotheses.json", state.hypotheses)
        self._write_json(run_dir / "cross_domain_analogies.json", state.cross_domain_analogies)
        self._write_json(run_dir / "cross_domain_transfers.json", state.cross_domain_transfers)
        self._write_json(run_dir / "novelty_gate.json", state.novelty_assessments)
        self._write_json(run_dir / "novelty_dossiers.json", state.novelty_dossiers)
        self._write_json(run_dir / "related_work_matrix.json", state.related_work_matrices)
        self._write_json(run_dir / "experiments.json", state.experiments)
        self._write_json(run_dir / "experiment_protocols.json", state.experiment_protocols)
        self._write_json(run_dir / "baseline_candidates.json", state.baseline_candidates)
        self._write_json(run_dir / "reviewer_objections.json", state.reviewer_objections)
        self._write_json(run_dir / "reviewer_summaries.json", state.reviewer_summaries)
        self._write_json(run_dir / "human_reviews.json", state.human_reviews)
        self._write_json(run_dir / "review_queue.json", state.review_queue)
        self._write_json(run_dir / "agent_tasks.json", state.agent_task_specs)
        self._write_json(run_dir / "agent_task_specs.json", state.agent_task_specs)
        self._write_json(run_dir / "agent_run_records.json", state.agent_run_records)
        self._write_json(run_dir / "agent_validations.json", state.agent_validation_results)
        self._write_json(run_dir / "agent_validation_results.json", state.agent_validation_results)
        self._write_json(run_dir / "orchestrator_plan.json", state.orchestrator_plan)
        self._write_json(run_dir / "orchestrator_result.json", state.orchestrator_result)
        self._write_json(run_dir / "active_loop.json", state.active_loop)
        self._write_json(run_dir / "run_log.json", state.run_log)
        self._write_json(run_dir / "rejected_ideas.json", state.rejected_ideas)
        self._write_json(run_dir / "provenance.json", self._provenance_records(state))
        self._write_paper_notes_markdown(state)
        self._write_source_coverage_markdown(state)
        self._write_coverage_stopping_markdown(state)
        self._write_full_text_coverage_markdown(state)
        self._write_evidence_spans_markdown(state)
        self._write_citation_graph_markdown(state)
        self._write_structure_markdown(state)
        self._write_ocr_status_markdown(state)
        self._write_related_work_expansion_markdown(state)
        self._write_paper_ranking_markdown(state)
        self._write_paper_triage_markdown(state)
        self._write_field_map_markdown(state)
        self._write_gaps_markdown(state)
        self._write_gap_evidence_matrix_markdown(state)
        self._write_cross_domain_analogies_markdown(state)
        self._write_cross_domain_transfers_markdown(state)
        self._write_novelty_gate_markdown(state)
        self._write_novelty_dossiers_markdown(state)
        self._write_related_work_matrix_markdown(state)
        self._write_experiments_markdown(state)
        self._write_experiment_protocols_markdown(state)
        self._write_baseline_candidates_markdown(state)
        self._write_implementation_tasks_markdown(state)
        self._write_reviewer_simulation_markdown(state)
        self._write_revised_experiment_recommendations_markdown(state)
        self._write_human_reviews_markdown(state)
        self._write_review_queue_markdown(state)
        self._write_agent_tasks_markdown(state)
        self._write_active_loop_markdown(state)
        self._write_report(state)

    def append_papers(self, state: ResearchRunState, papers: Iterable[Paper]) -> ResearchRunState:
        state.papers = _append_unique(state.papers, papers)
        self.save_run(state)
        return state

    def append_notes(self, state: ResearchRunState, notes: Iterable[PaperNote]) -> ResearchRunState:
        state.paper_notes = _append_unique(state.paper_notes, notes, key="paper_id")
        self.save_run(state)
        return state

    def save_paper_triage(self, state: ResearchRunState, triage: PaperTriageResult) -> ResearchRunState:
        state.paper_triage = triage
        self.save_run(state)
        return state

    def save_paper_ranking(self, state: ResearchRunState, ranking: PaperRankingResult) -> ResearchRunState:
        state.paper_ranking = ranking
        self.save_run(state)
        return state

    def append_claims(self, state: ResearchRunState, claims: Iterable[Claim]) -> ResearchRunState:
        state.claims = _append_unique(state.claims, claims)
        self.save_run(state)
        return state

    def append_gaps(self, state: ResearchRunState, gaps: Iterable[Gap]) -> ResearchRunState:
        state.gaps = _append_unique(state.gaps, gaps)
        self.save_run(state)
        return state

    def append_experiments(self, state: ResearchRunState, experiments: Iterable[ExperimentPlan]) -> ResearchRunState:
        state.experiments = _append_unique(state.experiments, experiments)
        self.save_run(state)
        return state

    def append_reviewer_objections(self, state: ResearchRunState, objections: Iterable[ReviewerObjection]) -> ResearchRunState:
        state.reviewer_objections = _append_unique(state.reviewer_objections, objections)
        self.save_run(state)
        return state

    def save_reviewer_summaries(self, state: ResearchRunState, summaries: Iterable[ReviewerSimulationSummary]) -> ResearchRunState:
        state.reviewer_summaries = _append_unique(state.reviewer_summaries, summaries, key="experiment_id")
        self.save_run(state)
        return state

    def validate_state(self, state: ResearchRunState) -> ValidationResult:
        issues: list[ValidationIssue] = []
        paper_ids = {paper.id for paper in state.papers}
        section_ids = {section.id for section in state.paper_sections}
        span_paper_ids = {span.paper_id for span in state.evidence_spans}
        full_text_paper_ids = {section.paper_id for section in state.paper_sections if section.text.strip()} | {
            artifact.paper_id
            for artifact in state.paper_artifacts
            if artifact.status == "available" and artifact.artifact_type in {"pdf", "html", "text"}
        }
        hypothesis_ids = {hypothesis.id for hypothesis in state.hypotheses}
        novelty_targets = {assessment.target_gap_or_hypothesis_id for assessment in state.novelty_assessments}
        matrix_by_gap = {matrix.gap_id: matrix for matrix in state.gap_evidence_matrices}
        review_object_ids = {
            "paper": paper_ids,
            "claim": {claim.id for claim in state.claims},
            "gap": {gap.id for gap in state.gaps},
            "novelty_assessment": {assessment.target_gap_or_hypothesis_id for assessment in state.novelty_assessments},
            "novelty_dossier": {dossier.target_id for dossier in state.novelty_dossiers},
            "experiment": {experiment.id for experiment in state.experiments},
            "reviewer_objection": {objection.id for objection in state.reviewer_objections},
            "source_policy": {state.coverage_stopping_assessment.profile_id if state.coverage_stopping_assessment else ""},
            "run": {state.run_id},
        }

        for claim in state.claims:
            if claim.status == "supported" and not claim.supporting_evidence:
                issues.append(
                    ValidationIssue(
                        code="supported-claim-without-evidence",
                        object_id=claim.id,
                        message=f"Claim {claim.id} is supported but has no supporting evidence.",
                    )
                )
            if claim.status == "supported" and not claim.source_paper_ids:
                issues.append(
                    ValidationIssue(
                        code="supported-claim-without-source",
                        object_id=claim.id,
                        message=f"Claim {claim.id} is supported but has no source paper IDs.",
                    )
                )
            if claim.type == "novelty" and not claim.closest_prior_work:
                issues.append(
                    ValidationIssue(
                        code="novelty-claim-without-prior-work",
                        object_id=claim.id,
                        message=f"Novelty claim {claim.id} has no closest prior work.",
                    )
                )
            claim_source_ids = set(claim.source_paper_ids)
            if (
                claim.status == "supported"
                and state.evidence_spans
                and claim_source_ids & span_paper_ids
                and not _claim_has_evidence_span(claim, state.evidence_spans)
            ):
                issues.append(
                    ValidationIssue(
                        code="supported-claim-without-evidence-span",
                        object_id=claim.id,
                        severity="warning",
                        message=(
                            f"Claim {claim.id} is supported and evidence spans are available for its source papers, "
                            "but no EvidenceSpan links to the claim's source papers."
                        ),
                    )
                )
            if (
                claim.status == "supported"
                and claim.confidence == "high"
                and claim_source_ids & full_text_paper_ids
                and not _claim_has_evidence_span(claim, state.evidence_spans)
            ):
                issues.append(
                    ValidationIssue(
                        code="high-confidence-full-text-claim-without-evidence-span",
                        object_id=claim.id,
                        message=(
                            f"Claim {claim.id} is high-confidence and source papers have full-text artifacts, "
                            "but no EvidenceSpan supports it."
                        ),
                    )
                )

        for artifact in state.paper_artifacts:
            if artifact.paper_id not in paper_ids:
                issues.append(
                    ValidationIssue(
                        code="paper-artifact-unknown-paper",
                        object_id=artifact.id,
                        message=f"Paper artifact {artifact.id} references unknown paper {artifact.paper_id}.",
                    )
                )

        for section in state.paper_sections:
            if section.paper_id not in paper_ids:
                issues.append(
                    ValidationIssue(
                        code="paper-section-unknown-paper",
                        object_id=section.id,
                        message=f"Paper section {section.id} references unknown paper {section.paper_id}.",
                    )
                )

        for span in state.evidence_spans:
            if span.paper_id not in paper_ids:
                issues.append(
                    ValidationIssue(
                        code="evidence-span-unknown-paper",
                        object_id=span.id,
                        message=f"Evidence span {span.id} references unknown paper {span.paper_id}.",
                    )
                )
            if span.section_id and span.section_id not in section_ids:
                issues.append(
                    ValidationIssue(
                        code="evidence-span-unknown-section",
                        object_id=span.id,
                        message=f"Evidence span {span.id} references unknown section {span.section_id}.",
                    )
                )

        if state.citation_graph is not None:
            unknown_graph_papers = sorted(set(state.citation_graph.paper_ids) - paper_ids)
            if unknown_graph_papers:
                issues.append(
                    ValidationIssue(
                        code="citation-graph-unknown-paper",
                        message=f"Citation graph references unknown papers: {', '.join(unknown_graph_papers)}.",
                    )
                )
            for edge in state.citation_graph.edges:
                if edge.edge_type in {"same_doi", "same_arxiv", "manual"}:
                    continue
                unknown_edge_ids = sorted({edge.source_paper_id, edge.target_paper_id} - paper_ids)
                if unknown_edge_ids:
                    issues.append(
                        ValidationIssue(
                            code="citation-edge-unknown-paper",
                            object_id=f"{edge.source_paper_id}->{edge.target_paper_id}",
                            message=f"Citation edge references unknown papers: {', '.join(unknown_edge_ids)}.",
                        )
                    )

        for transfer in state.cross_domain_transfers:
            if transfer.target_gap_id and transfer.target_gap_id not in {gap.id for gap in state.gaps}:
                issues.append(
                    ValidationIssue(
                        code="cross-domain-transfer-unknown-gap",
                        object_id=transfer.id,
                        message=f"Cross-domain transfer {transfer.id} references unknown gap {transfer.target_gap_id}.",
                    )
                )
            unknown_transfer_papers = sorted(set(transfer.source_paper_ids) - paper_ids)
            if unknown_transfer_papers:
                issues.append(
                    ValidationIssue(
                        code="cross-domain-transfer-unknown-paper",
                        object_id=transfer.id,
                        message=f"Cross-domain transfer {transfer.id} references unknown papers: {', '.join(unknown_transfer_papers)}.",
                    )
                )
            if transfer.status == "promoted" and not transfer.source_paper_ids:
                issues.append(
                    ValidationIssue(
                        code="promoted-transfer-without-source-paper",
                        object_id=transfer.id,
                        message=f"Promoted transfer {transfer.id} has no source paper evidence.",
                    )
                )

        for gap in state.gaps:
            linked_ids = set(gap.supporting_paper_ids or gap.linked_paper_ids)
            if not linked_ids and not gap.explicit_reason:
                issues.append(
                    ValidationIssue(
                        code="gap-without-linked-papers-or-reason",
                        object_id=gap.id,
                        message=f"Gap {gap.id} has no linked papers and no explicit reason.",
                    )
                )
            if not gap.risk_that_gap_is_fake:
                issues.append(
                    ValidationIssue(
                        code="gap-without-fake-risk",
                        object_id=gap.id,
                        message=f"Gap {gap.id} does not explain the risk that the gap is fake.",
                    )
                )
            if gap.id not in matrix_by_gap and not gap.explicit_reason:
                issues.append(
                    ValidationIssue(
                        code="gap-without-evidence-matrix",
                        object_id=gap.id,
                        severity="warning",
                        message=f"Gap {gap.id} has no evidence matrix and no explicit reason for evidence absence.",
                    )
                )
            if gap.confidence == "high" and not linked_ids and not gap.supporting_claim_ids:
                issues.append(
                    ValidationIssue(
                        code="high-confidence-gap-without-support",
                        object_id=gap.id,
                        message=f"Gap {gap.id} is high confidence without supporting papers or claims.",
                    )
                )
            unknown_links = sorted(linked_ids - paper_ids)
            if unknown_links:
                issues.append(
                    ValidationIssue(
                        code="gap-links-unknown-paper",
                        object_id=gap.id,
                        message=f"Gap {gap.id} links unknown papers: {', '.join(unknown_links)}.",
                    )
                )

        gap_ids = {gap.id for gap in state.gaps}
        for matrix in state.gap_evidence_matrices:
            if matrix.gap_id not in gap_ids:
                issues.append(
                    ValidationIssue(
                        code="gap-evidence-matrix-unknown-gap",
                        object_id=matrix.gap_id,
                        message=f"Gap evidence matrix references unknown gap {matrix.gap_id}.",
                    )
                )
            for row in matrix.evidence_rows:
                if row.paper_id and row.paper_id not in paper_ids:
                    issues.append(
                        ValidationIssue(
                            code="gap-evidence-row-unknown-paper",
                            object_id=matrix.gap_id,
                            message=f"Gap evidence row for {matrix.gap_id} references unknown paper {row.paper_id}.",
                        )
                    )
                if row.evidence_span_id and row.evidence_span_id not in {span.id for span in state.evidence_spans}:
                    issues.append(
                        ValidationIssue(
                            code="gap-evidence-row-unknown-span",
                            object_id=matrix.gap_id,
                            message=f"Gap evidence row for {matrix.gap_id} references unknown span {row.evidence_span_id}.",
                        )
                    )

        for experiment in state.experiments:
            has_known_hypothesis = bool(experiment.hypothesis_id and experiment.hypothesis_id in hypothesis_ids)
            has_inline_hypothesis = bool(experiment.hypothesis)
            if not has_known_hypothesis and not has_inline_hypothesis:
                issues.append(
                    ValidationIssue(
                        code="experiment-without-hypothesis",
                        object_id=experiment.id,
                        message=f"Experiment {experiment.id} does not reference a known hypothesis or include one inline.",
                    )
                )
            experiment_novelty_targets = set(experiment.linked_gap_ids)
            if experiment.hypothesis_id:
                experiment_novelty_targets.add(experiment.hypothesis_id)
            if experiment.novelty_assessment_id:
                experiment_novelty_targets.add(experiment.novelty_assessment_id)
            if experiment.paper_ready and not (experiment_novelty_targets & novelty_targets):
                issues.append(
                    ValidationIssue(
                        code="paper-ready-experiment-without-novelty-assessment",
                        object_id=experiment.id,
                        message=f"Experiment {experiment.id} is paper-ready without a novelty assessment.",
                    )
                )
            if experiment.paper_ready and not any(
                protocol.linked_experiment_plan_id == experiment.id for protocol in state.experiment_protocols
            ):
                issues.append(
                    ValidationIssue(
                        code="paper-ready-experiment-without-protocol",
                        object_id=experiment.id,
                        message=f"Experiment {experiment.id} is paper-ready without an experiment protocol.",
                    )
                )
            if not experiment.baselines:
                issues.append(
                    ValidationIssue(
                        code="experiment-without-baselines",
                        object_id=experiment.id,
                        message=f"Experiment {experiment.id} does not specify baselines.",
                    )
                )
            if not experiment.metrics:
                issues.append(
                    ValidationIssue(
                        code="experiment-without-metrics",
                        object_id=experiment.id,
                        message=f"Experiment {experiment.id} does not specify metrics.",
                    )
                )
            if not experiment.what_result_would_falsify_the_idea:
                issues.append(
                    ValidationIssue(
                        code="experiment-without-falsification-condition",
                        object_id=experiment.id,
                        message=f"Experiment {experiment.id} does not specify a falsification condition.",
                    )
                )

        for assessment in state.novelty_assessments:
            if assessment.novelty_strength == "strong" and not assessment.closest_prior_work:
                issues.append(
                    ValidationIssue(
                        code="strong-novelty-without-prior-work",
                        object_id=assessment.target_gap_or_hypothesis_id,
                        message=(f"Novelty assessment {assessment.target_gap_or_hypothesis_id} is strong without closest prior work."),
                    )
                )
            if (
                assessment.novelty_strength == "strong"
                and state.coverage_stopping_assessment is not None
                and not state.coverage_stopping_assessment.enough_for_novelty
            ):
                issues.append(
                    ValidationIssue(
                        code="strong-novelty-without-policy-coverage",
                        object_id=assessment.target_gap_or_hypothesis_id,
                        message=(
                            f"Novelty assessment {assessment.target_gap_or_hypothesis_id} is strong, but "
                            f"{state.coverage_stopping_assessment.profile_id} source policy novelty coverage has not passed."
                        ),
                    )
                )

        for review in state.human_reviews:
            known_ids = review_object_ids.get(review.object_type)
            if known_ids is None:
                issues.append(
                    ValidationIssue(
                        code="human-review-unknown-object-type",
                        object_id=review.id,
                        message=f"Human review {review.id} uses unknown object type {review.object_type}.",
                    )
                )
            elif review.object_id not in known_ids:
                issues.append(
                    ValidationIssue(
                        code="human-review-unknown-object",
                        object_id=review.id,
                        message=f"Human review {review.id} references unknown {review.object_type} {review.object_id}.",
                    )
                )

        if state.review_queue is not None:
            for item in state.review_queue.items:
                if item.status not in {"open", "completed", "dismissed"}:
                    issues.append(
                        ValidationIssue(
                            code="review-queue-invalid-status",
                            object_id=item.id,
                            message=f"Review queue item {item.id} has unsupported status {item.status}.",
                        )
                    )
                known_ids = review_object_ids.get(item.object_type)
                if known_ids is not None and item.object_id not in known_ids:
                    issues.append(
                        ValidationIssue(
                            code="review-queue-unknown-object",
                            object_id=item.id,
                            severity="warning",
                            message=f"Review queue item {item.id} references unknown {item.object_type} {item.object_id}.",
                        )
                    )

        for note in state.paper_notes:
            if not note.paper_id:
                issues.append(
                    ValidationIssue(
                        code="paper-note-without-paper-id",
                        message="A paper note is missing paper_id.",
                    )
                )
            elif note.paper_id not in paper_ids:
                issues.append(
                    ValidationIssue(
                        code="paper-note-unknown-paper",
                        object_id=note.paper_id,
                        message=f"Paper note references unknown paper {note.paper_id}.",
                    )
                )
            if note.main_results and not note.quotes_or_evidence_snippets and not note.evidence:
                issues.append(
                    ValidationIssue(
                        code="paper-note-results-without-evidence",
                        object_id=note.paper_id,
                        message=f"Paper note {note.paper_id} has main results without evidence snippets.",
                    )
                )
            if note.source_basis == "metadata/abstract only" and note.confidence == "high":
                issues.append(
                    ValidationIssue(
                        code="abstract-only-note-high-confidence",
                        object_id=note.paper_id,
                        message=f"Paper note {note.paper_id} is abstract-only but marked high confidence.",
                    )
                )

        return ValidationResult(ok=not issues, issues=issues)

    def latest_run_dir(self) -> Path | None:
        if not self.config.runs_dir.exists():
            return None
        candidates = [path for path in self.config.runs_dir.iterdir() if path.is_dir()]
        return sorted(candidates)[-1] if candidates else None

    def load_latest_raw(self) -> dict[str, Any] | None:
        run_dir = self.latest_run_dir()
        if run_dir is None:
            return None
        state_path = run_dir / "state.json"
        if not state_path.exists():
            return None
        return json.loads(state_path.read_text(encoding="utf-8"))

    def load_latest(self) -> ResearchRunState | None:
        run_dir = self.latest_run_dir()
        if run_dir is None:
            return None
        return self.load_run(run_dir.name)

    def validate_latest(self) -> ValidationResult:
        state = self.load_latest()
        if state is None:
            return ValidationResult(
                ok=False,
                issues=[ValidationIssue(code="missing-run", message="No run state found.")],
            )
        return self.validate_state(state)

    def _write_json(self, path: Path, value: object) -> None:
        path.write_text(json.dumps(to_plain(value), indent=2) + "\n", encoding="utf-8")

    def _write_topic(self, state: ResearchRunState) -> None:
        Path(state.run_dir, "topic.md").write_text(f"# {state.topic.text}\n\nRun: `{state.run_id}`\n", encoding="utf-8")

    def _write_report(self, state: ResearchRunState) -> None:
        report_path = Path(state.run_dir, "run_report.md")
        lines = [
            f"# GapForge Run Report: {state.topic.text}",
            "",
            f"Run ID: `{state.run_id}`",
            "",
            "## Orchestrator Status",
            "",
        ]
        if state.orchestrator_result is not None:
            lines.extend(
                [
                    f"- Status: {state.orchestrator_result.status}",
                    f"- Completed steps: {len(state.orchestrator_result.completed_steps)}",
                    f"- Failed steps: {len(state.orchestrator_result.failed_steps)}",
                    f"- Skipped steps: {len(state.orchestrator_result.skipped_steps)}",
                ]
            )
        else:
            lines.append("- Status: not orchestrated")
        lines.extend(
            [
                "",
                "## State",
                "",
                f"- Papers: {len(state.papers)}",
                f"- Paper notes: {len(state.paper_notes)}",
                f"- Claims: {len(state.claims)}",
                f"- Gaps: {len(state.gaps)}",
                f"- Hypotheses: {len(state.hypotheses)}",
                f"- Novelty assessments: {len(state.novelty_assessments)}",
                f"- Experiments: {len(state.experiments)}",
                f"- Reviewer objections: {len(state.reviewer_objections)}",
                f"- Human review records: {len(state.human_reviews)}",
                "",
                "## Field Map",
                "",
            ]
        )
        if state.field_map is None:
            lines.append("No field map generated.")
        else:
            lines.append(f"Confidence: **{state.field_map.confidence}**")
            lines.append("")
            lines.extend([f"- {cluster.name}: {cluster.description}" for cluster in state.field_map.clusters[:5]] or ["- none"])
        lines.extend(["", "## Top Papers", ""])
        top_papers = sorted(state.papers, key=lambda paper: (paper.citation_count, paper.year), reverse=True)[:10]
        lines.extend(
            [f"- `{paper.id}` {paper.title} ({paper.year or 'n.d.'}, {paper.source or 'unknown source'})" for paper in top_papers]
            or ["- none"]
        )
        lines.extend(["", "## Strongest Gaps", ""])
        gap_rank = {"high": 0, "medium": 1, "low": 2}
        for gap in sorted(state.gaps, key=lambda item: (gap_rank.get(item.confidence, 3), item.novelty_status))[:8]:
            lines.append(
                f"- `{gap.id}` {gap.title or gap.description} [{gap.type}; confidence={gap.confidence}; novelty={gap.novelty_status}]"
            )
        if not state.gaps:
            lines.append("- none")
        lines.extend(["", "## Novelty Assessments", ""])
        lines.extend(
            [
                f"- `{item.target_gap_or_hypothesis_id}` verdict={item.verdict}, strength={item.novelty_strength}, "
                f"closest prior={item.closest_prior_work[0] if item.closest_prior_work else 'missing'}"
                for item in state.novelty_assessments[:8]
            ]
            or ["- none"]
        )
        lines.extend(["", "## Experiment Plans", ""])
        for experiment in state.experiments[:8]:
            lines.append(
                f"- `{experiment.id}` {experiment.title}: metrics={', '.join(experiment.metrics[:3]) or 'none'}, "
                f"baselines={', '.join(experiment.baselines[:2]) or 'none'}"
            )
        if not state.experiments:
            lines.append("- none")
        lines.extend(["", "## Reviewer Objections", ""])
        lines.extend(
            [
                f"- `{item.experiment_id or item.target_id}` {item.severity}/{item.category}: {item.objection}"
                for item in state.reviewer_objections[:10]
            ]
            or ["- none"]
        )
        supported = sum(1 for claim in state.claims if claim.status == "supported")
        contested = sum(1 for claim in state.claims if claim.status == "contested")
        uncertain = sum(1 for claim in state.claims if claim.status == "uncertain")
        unsupported = sum(1 for claim in state.claims if claim.status == "unsupported")
        lines.extend(
            [
                "",
                "## Claim Ledger Summary",
                "",
                f"- Supported: {supported}",
                f"- Contested: {contested}",
                f"- Uncertain: {uncertain}",
                f"- Unsupported: {unsupported}",
                "",
                "## Uncertainty",
                "",
            ]
        )
        uncertainty: list[str] = []
        uncertainty.extend(item for item in (state.field_map.limitations if state.field_map else [])[:5])
        uncertainty.extend(
            f"Novelty searches missing for {item.target_gap_or_hypothesis_id}: {len(item.missing_searches)}"
            for item in state.novelty_assessments
            if item.missing_searches
        )
        uncertainty.extend(gap.risk_that_gap_is_fake for gap in state.gaps[:5] if gap.risk_that_gap_is_fake)
        lines.extend([f"- {item}" for item in uncertainty[:12]] or ["- No explicit uncertainty recorded."])
        lines.extend(["", "## Human Review", ""])
        if state.human_reviews:
            lines.extend(
                [
                    f"- `{record.id}` {record.action} `{record.object_type}:{record.object_id}`"
                    + (f": {record.note}" if record.note else "")
                    for record in state.human_reviews[-8:]
                ]
            )
        else:
            lines.append("- none")
        lines.extend(["", "## Review Queue", ""])
        open_items = [item for item in (state.review_queue.items if state.review_queue else []) if item.status == "open"]
        if open_items:
            lines.extend(
                [f"- `{item.id}` {item.priority} `{item.object_type}:{item.object_id}`: {item.reason}" for item in open_items[:10]]
            )
        else:
            lines.append("- none")
        report_path.write_text(redact_text("\n".join(lines).rstrip() + "\n"), encoding="utf-8")

    def _write_field_map_markdown(self, state: ResearchRunState) -> None:
        path = Path(state.run_dir, "field_map.md")
        if state.field_map is None:
            path.write_text("# Field Map\n\nNo field map generated yet.\n", encoding="utf-8")
            return
        field_map = state.field_map
        lines = [
            f"# Field Map: {field_map.topic}",
            "",
            f"Confidence: **{field_map.confidence}**",
            "",
            "## Clusters",
            "",
        ]
        for cluster in field_map.clusters:
            lines.extend(
                [
                    f"### {cluster.name}",
                    "",
                    cluster.description,
                    "",
                    f"- Papers: {', '.join(cluster.paper_ids) if cluster.paper_ids else 'none'}",
                    f"- Representative papers: {', '.join(cluster.representative_papers) if cluster.representative_papers else 'none'}",
                    f"- Dominant methods: {', '.join(cluster.dominant_methods) if cluster.dominant_methods else 'unknown'}",
                    f"- Why it matters: {cluster.why_it_matters}",
                    "",
                    "Open questions:",
                    "",
                ]
            )
            lines.extend([f"- {question}" for question in cluster.open_questions] or ["- none identified"])
            lines.append("")
        sections = [
            ("Major Questions", field_map.major_questions),
            ("Dominant Methods", field_map.dominant_methods),
            ("Common Datasets", field_map.common_datasets),
            ("Common Metrics", field_map.common_metrics),
            ("Saturated Areas", field_map.saturated_areas),
            ("Underexplored Areas", field_map.underexplored_areas),
            ("Contradictions", field_map.contradictions),
            ("Adjacent Fields", field_map.adjacent_fields),
            ("Initial Gap Candidates", field_map.initial_gap_candidates),
            ("Limitations", field_map.limitations),
        ]
        for title, values in sections:
            lines.extend([f"## {title}", ""])
            lines.extend([f"- {value}" for value in values] or ["- none identified"])
            lines.append("")
        path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")

    def _write_paper_triage_markdown(self, state: ResearchRunState) -> None:
        path = Path(state.run_dir, "paper_triage.md")
        if state.paper_triage is None:
            path.write_text("# Paper Triage\n\nNo paper triage generated yet.\n", encoding="utf-8")
            return
        triage = state.paper_triage
        lines = [
            f"# Paper Triage: {triage.topic}",
            "",
            triage.scoring_summary,
            "",
            "## Tier Counts",
            "",
        ]
        for tier in ["Tier 1", "Tier 2", "Tier 3", "Tier 4"]:
            lines.append(f"- {tier}: {triage.tier_counts.get(tier, 0)}")
        lines.extend(["", "## Decisions", ""])
        for decision in triage.decisions:
            lines.extend(
                [
                    f"### {decision.tier}: {decision.title}",
                    "",
                    f"- Paper ID: `{decision.paper_id}`",
                    f"- Score: {decision.score:.2f}",
                    f"- Role: {decision.paper_role}",
                    f"- Why this role: {decision.why_this_role or 'unclear'}",
                    f"- Recommended reading depth: {decision.recommended_reading_depth}",
                    f"- Source coverage: {decision.source_coverage_reason or 'unknown'}",
                    f"- Download full text: {str(decision.should_download_full_text).lower()}",
                    f"- Important for novelty checking: {str(decision.important_for_novelty_checking).lower()}",
                    f"- Important for cross-domain transfer: {str(decision.important_for_cross_domain_transfer).lower()}",
                    "",
                    "Reasons:",
                    "",
                ]
            )
            lines.extend([f"- {reason}" for reason in decision.reasons] or ["- none"])
            lines.extend(["", "Concerns:", ""])
            lines.extend([f"- {concern}" for concern in decision.concerns] or ["- none"])
            lines.append("")
        lines.extend(["## Limitations", ""])
        lines.extend([f"- {limitation}" for limitation in triage.limitations] or ["- none"])
        path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")

    def _write_paper_ranking_markdown(self, state: ResearchRunState) -> None:
        path = Path(state.run_dir, "paper_ranking.md")
        if state.paper_ranking is None:
            path.write_text("# Paper Ranking\n\nNo paper ranking generated yet.\n", encoding="utf-8")
            return
        ranking = state.paper_ranking
        lines = [
            f"# Paper Ranking: {ranking.topic}",
            "",
            ranking.scoring_summary,
            "",
            f"- Query purpose: {ranking.query_purpose}",
            f"- Recency preference: {ranking.recency_preference}",
            f"- Source diversity target: {ranking.source_diversity_target}",
            f"- Role diversity target: {ranking.role_diversity_target}",
            "",
            "## Ranked Papers",
            "",
        ]
        for decision in ranking.decisions:
            lines.extend(
                [
                    f"### {decision.rank}. {decision.title}",
                    "",
                    f"- Paper ID: `{decision.paper_id}`",
                    f"- Score: {decision.score:.2f}",
                    f"- Role: {decision.paper_role}",
                    f"- Source: {decision.source or 'unknown'}",
                    f"- Source diversity: {decision.source_diversity_reason}",
                    f"- Role diversity: {decision.role_diversity_reason}",
                    f"- Relevance: {decision.relevance_score:.3f}",
                    f"- Recency: {decision.recency_score:.3f}",
                    f"- Citation: {decision.citation_score:.3f}",
                    f"- Full text: {decision.full_text_score:.1f}",
                    f"- Novelty importance: {decision.novelty_score:.1f}",
                    f"- Adjacent transfer importance: {decision.adjacent_transfer_score:.1f}",
                    "",
                    "Role reasons:",
                    "",
                ]
            )
            lines.extend([f"- {reason}" for reason in decision.role_reasons] or ["- none"])
            lines.append("")
        path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")

    def _write_paper_notes_markdown(self, state: ResearchRunState) -> None:
        path = Path(state.run_dir, "paper_notes.md")
        if not state.paper_notes:
            path.write_text("# Paper Notes\n\nNo paper notes generated yet.\n", encoding="utf-8")
            return
        lines = ["# Paper Notes", ""]
        for note in state.paper_notes:
            lines.extend(
                [
                    f"## {note.citation_key or note.paper_id}",
                    "",
                    f"- Paper ID: `{note.paper_id}`",
                    f"- Source basis: {note.source_basis}",
                    f"- Confidence: {note.confidence}",
                    f"- Relevance to topic: {note.relevance_to_topic or 'unknown'}",
                    f"- Sections used: {', '.join(note.sections_used) if note.sections_used else 'none'}",
                    f"- Missing sections: {', '.join(note.missing_sections) if note.missing_sections else 'none recorded'}",
                    "",
                    note.one_sentence_summary or note.summary,
                    "",
                ]
            )
            sections = [
                ("Core Claims", note.core_claims),
                ("What It Demonstrates", note.main_results),
                ("Method", note.method or note.methods),
                ("Datasets", note.datasets),
                ("Metrics", note.metrics),
                ("Assumptions", note.assumptions),
                ("Stated Limitations", note.stated_limitations),
                ("Unstated Limitations", note.unstated_limitations or note.limitations),
                ("What It Cannot Answer", note.what_it_cannot_answer),
                ("Useful Technical Tools", note.useful_technical_tools),
                ("Possible Connections", note.possible_connections),
            ]
            for title, values in sections:
                lines.extend([f"### {title}", ""])
                lines.extend([f"- {value}" for value in values] or ["- none identified"])
                lines.append("")
            lines.extend(["### Evidence Snippets", ""])
            snippets = note.quotes_or_evidence_snippets or note.evidence
            lines.extend([f"- `{snippet.locator}` (`{snippet.source_id}`): {snippet.quote}" for snippet in snippets] or ["- none"])
            lines.append("")
        path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")

    def _write_full_text_coverage_markdown(self, state: ResearchRunState) -> None:
        path = Path(state.run_dir, "full_text_coverage.md")
        coverage = state.source_coverage
        if coverage is None:
            papers_with_pdf = sorted(
                {paper.id for paper in state.papers if paper.pdf_url}
                | {
                    artifact.paper_id
                    for artifact in state.paper_artifacts
                    if artifact.artifact_type == "pdf" and artifact.status == "available"
                }
            )
            papers_with_full_text = sorted({section.paper_id for section in state.paper_sections if section.text.strip()})
            abstract_only = sorted({note.paper_id for note in state.paper_notes if note.source_basis == "metadata/abstract only"})
            lines = [
                "# Full Text Coverage",
                "",
                "No source coverage report generated yet. Counts below are inferred from current state artifacts.",
                "",
                f"- Papers: {len(state.papers)}",
                f"- Papers with PDF: {len(papers_with_pdf)}",
                f"- Papers with full text sections: {len(papers_with_full_text)}",
                f"- Abstract-only notes: {len(abstract_only)}",
                f"- Failed downloads: {sum(1 for artifact in state.paper_artifacts if artifact.status == 'failed')}",
                "",
            ]
            path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
            return

        lines = [
            f"# Full Text Coverage: {coverage.topic}",
            "",
            f"- Run ID: `{coverage.run_id}`",
            f"- Confidence: {coverage.confidence}",
            f"- Searched sources: {', '.join(coverage.searched_sources) if coverage.searched_sources else 'none'}",
            f"- Papers with PDF: {len(coverage.papers_with_pdf)}",
            f"- Papers with full text: {len(coverage.papers_with_full_text)}",
            f"- Abstract-only papers: {len(coverage.papers_abstract_only)}",
            f"- Failed downloads: {len(coverage.failed_downloads)}",
            "",
            "## Papers By Source",
            "",
        ]
        lines.extend([f"- {source}: {count}" for source, count in sorted(coverage.papers_by_source.items())] or ["- none"])
        lines.extend(["", "## Query Records", ""])
        for record in coverage.query_records or state.search_queries:
            lines.extend(
                [
                    f"- `{record.id}` {record.purpose}: {record.query}",
                    f"  - Sources: {', '.join(record.source_names) if record.source_names else 'none'}",
                    f"  - Results: {len(record.result_paper_ids)}",
                    f"  - Failures: {len(record.failure_messages)}",
                ]
            )
        if not coverage.query_records and not state.search_queries:
            lines.append("- none")
        lines.extend(["", "## Warnings", ""])
        lines.extend([f"- {warning}" for warning in coverage.coverage_warnings] or ["- none"])
        path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")

    def _write_source_coverage_markdown(self, state: ResearchRunState) -> None:
        from gapforge.sources.coverage import render_source_coverage_markdown

        path = Path(state.run_dir, "source_coverage.md")
        if state.source_coverage is None:
            path.write_text("# Source Coverage\n\nNo source coverage report generated yet.\n", encoding="utf-8")
            return
        path.write_text(render_source_coverage_markdown(state.source_coverage), encoding="utf-8")

    def _write_coverage_stopping_markdown(self, state: ResearchRunState) -> None:
        from gapforge.sources.stopping import render_stopping_assessment_markdown

        path = Path(state.run_dir, "coverage_stopping_assessment.md")
        if state.coverage_stopping_assessment is None:
            path.write_text("# Coverage Stopping Assessment\n\nNo policy-aware assessment generated yet.\n", encoding="utf-8")
            return
        path.write_text(render_stopping_assessment_markdown(state.coverage_stopping_assessment), encoding="utf-8")

    def _write_evidence_spans_markdown(self, state: ResearchRunState) -> None:
        path = Path(state.run_dir, "evidence_spans.md")
        if not state.evidence_spans:
            path.write_text("# Evidence Spans\n\nNo evidence spans recorded yet.\n", encoding="utf-8")
            return
        lines = ["# Evidence Spans", ""]
        for span in state.evidence_spans:
            lines.extend(
                [
                    f"## {span.id}",
                    "",
                    f"- Paper ID: `{span.paper_id}`",
                    f"- Section ID: `{span.section_id or 'metadata-only'}`",
                    f"- Evidence type: {span.evidence_type}",
                    f"- Locator: {span.locator or _span_locator(span)}",
                    f"- Confidence: {span.confidence}",
                    "",
                    span.quote or "No quote recorded.",
                    "",
                ]
            )
        path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")

    def _write_citation_graph_markdown(self, state: ResearchRunState) -> None:
        path = Path(state.run_dir, "citation_graph.md")
        graph = state.citation_graph
        if graph is None:
            path.write_text("# Citation Graph\n\nNo citation graph generated yet.\n", encoding="utf-8")
            return
        lines = [
            "# Citation Graph",
            "",
            f"- Papers: {len(graph.paper_ids)}",
            f"- Edges: {len(graph.edges)}",
            f"- Unresolved references: {len(graph.unresolved_references)}",
            "",
            "## Edges",
            "",
        ]
        lines.extend(
            [
                (
                    f"- `{edge.source_paper_id}` --{edge.edge_type}/{edge.confidence}--> "
                    f"`{edge.target_paper_id}` ({edge.source or 'unknown source'})"
                )
                for edge in graph.edges
            ]
            or ["- none"]
        )
        lines.extend(["", "## Unresolved References", ""])
        lines.extend([f"- {reference}" for reference in graph.unresolved_references] or ["- none"])
        path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")

    def _write_structure_markdown(self, state: ResearchRunState) -> None:
        _write_records_markdown(
            Path(state.run_dir, "references.md"),
            "References",
            [
                f"- `{record.id}` paper=`{record.paper_id}` year={record.parsed_year or 'unknown'} "
                f"doi={record.doi or 'none'} arxiv={record.arxiv_id or 'none'} resolved={record.resolved_paper_id or 'none'}: "
                f"{record.parsed_title or record.raw_reference[:220]}"
                for record in state.references
            ],
        )
        _write_records_markdown(
            Path(state.run_dir, "tables.md"),
            "Tables",
            [
                f"- `{record.id}` paper=`{record.paper_id}` section=`{record.section_id or 'unknown'}` "
                f"locator={record.locator or 'none'} caption={record.caption or 'none'}"
                for record in state.tables
            ],
        )
        _write_records_markdown(
            Path(state.run_dir, "equations.md"),
            "Equations",
            [
                f"- `{record.id}` paper=`{record.paper_id}` section=`{record.section_id or 'unknown'}` "
                f"locator={record.locator or 'none'}: {record.text[:220]}"
                for record in state.equations
            ],
        )
        _write_records_markdown(
            Path(state.run_dir, "captions.md"),
            "Captions",
            [
                f"- `{record.id}` {record.caption_type} paper=`{record.paper_id}` section=`{record.section_id or 'unknown'}` "
                f"locator={record.locator or 'none'}: {record.caption}"
                for record in state.captions
            ],
        )

    def _write_ocr_status_markdown(self, state: ResearchRunState) -> None:
        path = Path(state.run_dir, "ocr_status.md")
        if not state.ocr_attempts:
            path.write_text("# OCR Status\n\nNo OCR attempts or recommendations recorded yet.\n", encoding="utf-8")
            return
        lines = ["# OCR Status", ""]
        for record in state.ocr_attempts:
            lines.extend(
                [
                    f"## {record.id}",
                    "",
                    f"- Paper ID: `{record.paper_id}`",
                    f"- Artifact ID: `{record.artifact_id or 'unknown'}`",
                    f"- Status: {record.status}",
                    f"- Pages attempted: {', '.join(str(page) for page in record.pages_attempted) or 'none'}",
                    "",
                    "### Warnings",
                    "",
                ]
            )
            lines.extend([f"- {warning}" for warning in record.warnings] or ["- none"])
            lines.append("")
        path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")

    def _write_related_work_expansion_markdown(self, state: ResearchRunState) -> None:
        path = Path(state.run_dir, "related_work_expansion.md")
        records = [record for record in state.search_queries if record.purpose == "citation_expansion"]
        if not records:
            path.write_text("# Related Work Expansion\n\nNo citation-expansion searches have been run yet.\n", encoding="utf-8")
            return
        result_ids = sorted({paper_id for record in records for paper_id in record.result_paper_ids})
        failures = [failure for record in records for failure in record.failure_messages]
        lines = [
            f"# Related Work Expansion: {state.topic.text}",
            "",
            f"- Queries run: {len(records)}",
            f"- Result paper IDs: {len(result_ids)}",
            f"- Source failures: {len(failures)}",
            "",
            "## Queries",
            "",
        ]
        lines.extend([f"- `{record.id}` {record.query} ({len(record.result_paper_ids)} results)" for record in records])
        lines.extend(["", "## Result Paper IDs", ""])
        lines.extend([f"- `{paper_id}`" for paper_id in result_ids] or ["- none"])
        lines.extend(["", "## Failures", ""])
        lines.extend([f"- {failure}" for failure in failures] or ["- none"])
        path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")

    def _write_gaps_markdown(self, state: ResearchRunState) -> None:
        path = Path(state.run_dir, "gaps.md")
        if not state.gaps:
            path.write_text("# Research Gaps\n\nNo gaps mined yet.\n", encoding="utf-8")
            return
        lines = ["# Research Gaps", ""]
        matrix_by_gap = {matrix.gap_id: matrix for matrix in state.gap_evidence_matrices}
        for gap in state.gaps:
            matrix = matrix_by_gap.get(gap.id)
            lines.extend(
                [
                    f"## {gap.title or gap.id}",
                    "",
                    f"- ID: `{gap.id}`",
                    f"- Type: {gap.type}",
                    f"- Confidence: {gap.confidence}",
                    f"- Novelty status: {gap.novelty_status}",
                    f"- Supporting papers: {_linked_gap_papers(gap)}",
                    f"- Supporting claims: {', '.join(gap.supporting_claim_ids) if gap.supporting_claim_ids else 'none'}",
                    f"- Counterevidence papers: {', '.join(matrix.papers_countering) if matrix and matrix.papers_countering else 'none'}",
                    "",
                    gap.description,
                    "",
                    "### Why Existing Work Does Not Solve It",
                    "",
                    gap.why_existing_work_does_not_solve_it or gap.explicit_reason or "Not specified.",
                    "",
                    "### Why It Matters",
                    "",
                    gap.why_it_matters or "Not specified.",
                    "",
                    "### Research Questions",
                    "",
                ]
            )
            lines.extend([f"- {question}" for question in gap.possible_research_questions] or ["- none"])
            lines.extend(
                [
                    "",
                    "### Minimum Experiment Needed",
                    "",
                    gap.minimum_experiment_needed or "Not specified.",
                    "",
                    "### Risk That Gap Is Fake",
                    "",
                    gap.risk_that_gap_is_fake or "Not specified.",
                    "",
                ]
            )
            if matrix is not None:
                lines.extend(
                    [
                        "### Evidence Matrix",
                        "",
                        f"- Supporting papers in matrix: {', '.join(matrix.papers_supporting) if matrix.papers_supporting else 'none'}",
                        f"- Countering papers in matrix: {', '.join(matrix.papers_countering) if matrix.papers_countering else 'none'}",
                        f"- Repeated limitations: {matrix.repeated_limitation_count}",
                        f"- Missing metrics: {matrix.missing_metric_count}",
                        f"- Missing datasets: {matrix.missing_dataset_count}",
                        f"- Assumption patterns: {matrix.assumption_pattern_count}",
                        "",
                    ]
                )
                for row in matrix.evidence_rows[:8]:
                    lines.append(
                        f"- `{row.paper_id}` {row.supports_or_counters}/{row.evidence_type} "
                        f"({row.section_type or 'unknown'}; {row.locator or row.evidence_span_id or 'no locator'}): {row.text[:220]}"
                    )
                if len(matrix.evidence_rows) > 8:
                    lines.append(f"- ... {len(matrix.evidence_rows) - 8} more evidence rows")
                lines.append("")
        path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")

    def _write_gap_evidence_matrix_markdown(self, state: ResearchRunState) -> None:
        path = Path(state.run_dir, "gap_evidence_matrix.md")
        if not state.gap_evidence_matrices:
            path.write_text("# Gap Evidence Matrix\n\nNo gap evidence matrices generated yet.\n", encoding="utf-8")
            return
        lines = ["# Gap Evidence Matrix", ""]
        for matrix in state.gap_evidence_matrices:
            lines.extend(
                [
                    f"## {matrix.gap_id}",
                    "",
                    f"- Confidence: {matrix.confidence}",
                    f"- Papers supporting: {', '.join(matrix.papers_supporting) if matrix.papers_supporting else 'none'}",
                    f"- Papers countering: {', '.join(matrix.papers_countering) if matrix.papers_countering else 'none'}",
                    f"- Repeated limitation count: {matrix.repeated_limitation_count}",
                    f"- Missing metric count: {matrix.missing_metric_count}",
                    f"- Missing dataset count: {matrix.missing_dataset_count}",
                    f"- Assumption pattern count: {matrix.assumption_pattern_count}",
                    "",
                ]
            )
            for row in matrix.evidence_rows:
                lines.append(
                    f"- `{row.paper_id}` {row.supports_or_counters}/{row.evidence_type} "
                    f"span=`{row.evidence_span_id or 'none'}` locator={row.locator or 'none'}: {row.text[:260]}"
                )
            lines.append("")
        path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")

    def _write_cross_domain_analogies_markdown(self, state: ResearchRunState) -> None:
        path = Path(state.run_dir, "cross_domain_analogies.md")
        if not state.cross_domain_analogies:
            path.write_text("# Cross-Domain Analogies\n\nNo cross-domain analogies generated yet.\n", encoding="utf-8")
            return
        lines = ["# Cross-Domain Analogies", ""]
        transfer_by_id = {transfer.id: transfer for transfer in state.cross_domain_transfers}
        for title, status in [
            ("Query-Only Analogies", "query_only"),
            ("Evidence-Backed Transfer Candidates", "promoted"),
            ("Rejected Analogies", "rejected"),
        ]:
            matching = [analogy for analogy in state.cross_domain_analogies if analogy.status == status]
            if not matching:
                continue
            lines.extend([f"## {title}", ""])
            for analogy in matching:
                transfer = transfer_by_id.get(analogy.transfer_candidate_id)
                lines.extend(
                    [
                        f"### {analogy.source_field}: {analogy.source_concept}",
                        "",
                        f"- Target gap: `{analogy.target_gap_id}`",
                        f"- Status: {analogy.status}",
                        f"- Confidence: {analogy.confidence}",
                        f"- Source papers: {', '.join(analogy.source_paper_ids) if analogy.source_paper_ids else 'none'}",
                        "",
                        "#### Why It Maps",
                        "",
                        analogy.why_it_maps,
                        "",
                        "#### What Breaks In The Mapping",
                        "",
                        analogy.what_breaks_in_the_mapping,
                        "",
                        "#### Technical Transfer Candidate",
                        "",
                        analogy.technical_transfer_candidate,
                        "",
                    ]
                )
                if transfer is not None:
                    lines.extend(
                        [
                            "#### Required Adaptation",
                            "",
                            transfer.required_adaptation or "Not specified.",
                            "",
                            "#### Evidence Span IDs",
                            "",
                        ]
                    )
                    lines.extend([f"- `{span_id}`" for span_id in transfer.evidence_span_ids] or ["- none"])
                    lines.append("")
                lines.extend(["#### Papers Or Sources To Search", ""])
                lines.extend([f"- {query}" for query in analogy.papers_or_sources_to_search] or ["- none"])
                lines.extend(
                    [
                        "",
                        "#### Possible Experiment",
                        "",
                        analogy.possible_experiment,
                        "",
                        "#### Risk Of Fake Analogy",
                        "",
                        analogy.risk_of_fake_analogy,
                        "",
                    ]
                )
        path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")

    def _write_cross_domain_transfers_markdown(self, state: ResearchRunState) -> None:
        path = Path(state.run_dir, "cross_domain_transfers.md")
        if not state.cross_domain_transfers:
            path.write_text("# Cross-Domain Transfer Candidates\n\nNo transfer candidates generated yet.\n", encoding="utf-8")
            return
        lines = ["# Cross-Domain Transfer Candidates", ""]
        for transfer in state.cross_domain_transfers:
            lines.extend(
                [
                    f"## {transfer.source_field}: {transfer.source_concept}",
                    "",
                    f"- ID: `{transfer.id}`",
                    f"- Target gap: `{transfer.target_gap_id}`",
                    f"- Status: {transfer.status}",
                    f"- Confidence: {transfer.confidence}",
                    f"- Source papers: {', '.join(transfer.source_paper_ids) if transfer.source_paper_ids else 'none'}",
                    f"- Evidence spans: {', '.join(transfer.evidence_span_ids) if transfer.evidence_span_ids else 'none'}",
                    "",
                    "### Technical Mechanism",
                    "",
                    transfer.technical_mechanism or "No transferable mechanism found.",
                    "",
                    "### Why It Maps",
                    "",
                    transfer.why_it_maps,
                    "",
                    "### What Breaks",
                    "",
                    transfer.what_breaks,
                    "",
                    "### Required Adaptation",
                    "",
                    transfer.required_adaptation or "Not specified.",
                    "",
                    "### Proposed Experiment",
                    "",
                    transfer.proposed_experiment or "Not specified.",
                    "",
                    "### Risk Of Fake Analogy",
                    "",
                    transfer.risk_of_fake_analogy,
                    "",
                ]
            )
        path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")

    def _write_experiments_markdown(self, state: ResearchRunState) -> None:
        path = Path(state.run_dir, "experiments.md")
        if not state.experiments:
            path.write_text("# Experiments\n\nNo experiments designed yet.\n", encoding="utf-8")
            return
        lines = ["# Experiments", ""]
        for experiment in state.experiments:
            lines.extend(
                [
                    f"## {experiment.title}",
                    "",
                    f"- ID: `{experiment.id}`",
                    f"- Linked gaps: {', '.join(experiment.linked_gap_ids) if experiment.linked_gap_ids else 'none'}",
                    f"- Novelty assessment: `{experiment.novelty_assessment_id or 'none'}`",
                    f"- Confidence: {experiment.confidence}",
                    f"- Paper ready: {str(experiment.paper_ready).lower()}",
                    "",
                    "### Hypothesis",
                    "",
                    experiment.hypothesis or experiment.hypothesis_id or "Not specified.",
                    "",
                    "### Core Claim Being Tested",
                    "",
                    experiment.core_claim_being_tested or "Not specified.",
                    "",
                    "### Minimum Viable Experiment",
                    "",
                    experiment.minimum_viable_experiment or experiment.design or "Not specified.",
                    "",
                ]
            )
            sections = [
                ("Datasets Needed", experiment.datasets_needed or experiment.datasets),
                ("Baselines", experiment.baselines),
                ("Metrics", experiment.metrics),
                ("Statistical Tests", experiment.statistical_tests),
                ("Ablations", experiment.ablations),
                ("Failure Modes", experiment.failure_modes or experiment.expected_failure_modes),
                ("Implementation Steps", experiment.implementation_steps),
                ("Expected Result Patterns", experiment.expected_result_patterns),
                ("Risks", experiment.risks),
                ("Ethical Or Safety Considerations", experiment.ethical_or_safety_considerations),
            ]
            for title, values in sections:
                lines.extend([f"### {title}", ""])
                lines.extend([f"- {value}" for value in values] or ["- none specified"])
                lines.append("")
            lines.extend(
                [
                    "### Compute Requirements",
                    "",
                    experiment.compute_requirements or "Not specified.",
                    "",
                    "### What Result Would Falsify The Idea",
                    "",
                    experiment.what_result_would_falsify_the_idea or "Not specified.",
                    "",
                    "### Reviewer Killer Result",
                    "",
                    experiment.reviewer_killer_result or "Not specified.",
                    "",
                ]
            )
        path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")

    def _write_experiment_protocols_markdown(self, state: ResearchRunState) -> None:
        path = Path(state.run_dir, "experiment_protocols.md")
        if not state.experiment_protocols:
            path.write_text("# Experiment Protocols\n\nNo experiment protocols generated yet.\n", encoding="utf-8")
            return
        from gapforge.experiments.protocol import render_protocols_markdown

        path.write_text(render_protocols_markdown(state.experiment_protocols), encoding="utf-8")

    def _write_baseline_candidates_markdown(self, state: ResearchRunState) -> None:
        path = Path(state.run_dir, "baseline_candidates.md")
        if not state.baseline_candidates:
            path.write_text("# Baseline Candidates\n\nNo baseline candidates generated yet.\n", encoding="utf-8")
            return
        from gapforge.experiments.baselines import render_baseline_candidates_markdown

        path.write_text(render_baseline_candidates_markdown(state.baseline_candidates), encoding="utf-8")

    def _write_implementation_tasks_markdown(self, state: ResearchRunState) -> None:
        path = Path(state.run_dir, "implementation_tasks.md")
        if not state.experiments:
            path.write_text("# Implementation Tasks\n\nNo experiment implementation tasks generated yet.\n", encoding="utf-8")
            return
        lines = ["# Implementation Tasks", ""]
        for experiment in state.experiments:
            lines.extend([f"## {experiment.title}", ""])
            steps = experiment.implementation_steps or ["Define dataset adapter", "Run baseline", "Compute metrics"]
            for index, step in enumerate(steps, start=1):
                lines.append(f"{index}. {step}")
            lines.append("")
        path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")

    def _write_reviewer_simulation_markdown(self, state: ResearchRunState) -> None:
        path = Path(state.run_dir, "reviewer_simulation.md")
        if not state.reviewer_objections and not state.reviewer_summaries:
            path.write_text("# Reviewer Simulation\n\nNo reviewer simulation generated yet.\n", encoding="utf-8")
            return
        lines = ["# Reviewer Simulation", ""]
        summary_by_experiment = {summary.experiment_id: summary for summary in state.reviewer_summaries}
        objections_by_experiment: dict[str, list[ReviewerObjection]] = {}
        for objection in state.reviewer_objections:
            objections_by_experiment.setdefault(objection.experiment_id or objection.target_id, []).append(objection)
        for experiment_id in sorted(set(summary_by_experiment) | set(objections_by_experiment)):
            summary = summary_by_experiment.get(experiment_id)
            lines.extend([f"## {experiment_id}", ""])
            if summary is not None:
                lines.extend(
                    [
                        f"- Submission readiness score: {summary.submission_readiness_score}",
                        f"- Final recommendation: {summary.final_recommendation}",
                        f"- Blocking issues: {len(summary.blocking_issues)}",
                        "",
                    ]
                )
            for objection in objections_by_experiment.get(experiment_id, []):
                lines.extend(
                    [
                        f"### {objection.reviewer_role or 'Reviewer'}: {objection.category}",
                        "",
                        f"- Severity: {objection.severity}",
                        f"- Blocks submission: {str(objection.blocks_submission).lower()}",
                        f"- Confidence: {objection.confidence}",
                        "",
                        objection.objection,
                        "",
                        "Why reviewer would care:",
                        "",
                        objection.why_reviewer_would_care or "Not specified.",
                        "",
                        "Evidence or prior work:",
                        "",
                    ]
                )
                lines.extend([f"- {item}" for item in objection.evidence_or_prior_work] or ["- none"])
                lines.extend(["", "Suggested fix:", "", objection.suggested_fix or objection.mitigation or "Not specified.", ""])
        path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")

    def _write_revised_experiment_recommendations_markdown(self, state: ResearchRunState) -> None:
        path = Path(state.run_dir, "revised_experiment_recommendations.md")
        if not state.reviewer_summaries:
            path.write_text(
                "# Revised Experiment Recommendations\n\nNo reviewer recommendations generated yet.\n",
                encoding="utf-8",
            )
            return
        lines = ["# Revised Experiment Recommendations", ""]
        for summary in state.reviewer_summaries:
            lines.extend(
                [
                    f"## {summary.experiment_id}",
                    "",
                    f"- Submission readiness score: {summary.submission_readiness_score}",
                    f"- Final recommendation: {summary.final_recommendation}",
                    "",
                    "### Required Fixes",
                    "",
                ]
            )
            lines.extend([f"- {fix}" for fix in summary.required_fixes] or ["- none"])
            lines.extend(["", "### Optional Fixes", ""])
            lines.extend([f"- {fix}" for fix in summary.optional_fixes] or ["- none"])
            lines.extend(["", "### Blocking Issues", ""])
            lines.extend([f"- {issue}" for issue in summary.blocking_issues] or ["- none"])
            lines.append("")
        path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")

    def _write_novelty_gate_markdown(self, state: ResearchRunState) -> None:
        path = Path(state.run_dir, "novelty_gate.md")
        if not state.novelty_assessments:
            path.write_text("# Novelty Gate\n\nNo novelty assessments generated yet.\n", encoding="utf-8")
            return
        lines = ["# Novelty Gate", ""]
        for assessment in state.novelty_assessments:
            lines.extend(
                [
                    f"## {assessment.target_gap_or_hypothesis_id}",
                    "",
                    f"- Verdict: {assessment.verdict}",
                    f"- Novelty strength: {assessment.novelty_strength}",
                    f"- Confidence: {assessment.confidence}",
                    f"- Similarity to prior work: {assessment.similarity_to_prior_work:.2f}",
                    "",
                    "### Idea Summary",
                    "",
                    assessment.idea_summary,
                    "",
                    "### Closest Prior Work",
                    "",
                ]
            )
            lines.extend([f"- {item}" for item in assessment.closest_prior_work] or ["- none found in current run"])
            lines.extend(["", "### What Is New", ""])
            lines.extend([f"- {item}" for item in assessment.what_is_new] or ["- not established"])
            lines.extend(["", "### What Is Not New", ""])
            lines.extend([f"- {item}" for item in assessment.what_is_not_new] or ["- not established"])
            lines.extend(
                [
                    "",
                    "### Possible Reviewer Objection",
                    "",
                    assessment.possible_reviewer_objection or "No objection generated.",
                    "",
                    "### Decisive Difference Needed",
                    "",
                    assessment.decisive_difference_needed or "Not specified.",
                    "",
                    "### Search Queries Used",
                    "",
                ]
            )
            lines.extend([f"- {query}" for query in assessment.search_queries_used] or ["- none"])
            lines.extend(["", "### Missing Searches", ""])
            lines.extend([f"- {query}" for query in assessment.missing_searches] or ["- none"])
            lines.append("")
        path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")

    def _write_novelty_dossiers_markdown(self, state: ResearchRunState) -> None:
        path = Path(state.run_dir, "novelty_dossiers.md")
        if not state.novelty_dossiers:
            path.write_text("# Novelty Dossiers\n\nNo novelty dossiers generated yet.\n", encoding="utf-8")
            return
        lines = ["# Novelty Dossiers", ""]
        for dossier in state.novelty_dossiers:
            lines.extend(
                [
                    f"## {dossier.target_id}",
                    "",
                    f"- Verdict: {dossier.verdict}",
                    f"- Novelty strength: {dossier.novelty_strength}",
                    f"- Confidence: {dossier.confidence}",
                    f"- Candidates considered: {len(dossier.candidates_considered)}",
                    "",
                    "### Idea Summary",
                    "",
                    dossier.idea_summary,
                    "",
                    "### Top Prior Work",
                    "",
                ]
            )
            lines.extend([f"- {item}" for item in dossier.top_prior_work] or ["- none"])
            lines.extend(["", "### Comparison Table", ""])
            for row in dossier.comparison_table[:10]:
                overall = float(row.get("overall_similarity") or 0.0)
                problem = float(row.get("problem_overlap") or 0.0)
                method = float(row.get("method_overlap") or 0.0)
                evaluation = float(row.get("evaluation_overlap") or 0.0)
                lines.append(
                    f"- `{row.get('paper_id', 'unknown')}` score={overall:.2f}; "
                    f"problem={problem:.2f}; method={method:.2f}; "
                    f"evaluation={evaluation:.2f}: {row.get('title', '')}"
                )
            if not dossier.comparison_table:
                lines.append("- none")
            lines.extend(
                [
                    "",
                    "### Decisive Difference Needed",
                    "",
                    dossier.decisive_difference_needed or "Not specified.",
                    "",
                    "### Reviewer Objection",
                    "",
                    dossier.reviewer_objection or "No objection generated.",
                    "",
                    "### Recommended Action",
                    "",
                    dossier.recommended_action or "Not specified.",
                    "",
                    "### Query Plan",
                    "",
                ]
            )
            lines.extend([f"- {query}" for query in dossier.query_plan] or ["- none"])
            lines.extend(["", "### Missing Searches", ""])
            lines.extend([f"- {query}" for query in dossier.missing_searches] or ["- none"])
            lines.append("")
        path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")

    def _write_related_work_matrix_markdown(self, state: ResearchRunState) -> None:
        path = Path(state.run_dir, "related_work_matrix.md")
        if not state.related_work_matrices:
            path.write_text("# Related Work Matrix\n\nNo related-work matrices generated yet.\n", encoding="utf-8")
            return
        from gapforge.related_work.renderer import render_related_work_matrices_markdown

        path.write_text(render_related_work_matrices_markdown(state.related_work_matrices), encoding="utf-8")

    def _write_human_reviews_markdown(self, state: ResearchRunState) -> None:
        from gapforge.review.audit import render_human_reviews_markdown

        Path(state.run_dir, "human_reviews.md").write_text(render_human_reviews_markdown(state), encoding="utf-8")

    def _write_review_queue_markdown(self, state: ResearchRunState) -> None:
        from gapforge.review.queue import render_review_queue_markdown

        Path(state.run_dir, "review_queue.md").write_text(render_review_queue_markdown(state.review_queue), encoding="utf-8")

    def _write_agent_tasks_markdown(self, state: ResearchRunState) -> None:
        path = Path(state.run_dir, "agent_tasks.md")
        lines = [
            "# Agent Tasks",
            "",
            "Agent task packs are validation-gated handoffs for optional Codex/GPT-5.4 actual runs.",
            "Imported agent outputs do not update research objects unless validation passes.",
            "",
        ]
        if not state.agent_task_specs:
            path.write_text("\n".join(lines + ["No agent tasks have been created yet.", ""]), encoding="utf-8")
            return
        validation_by_task = {result.task_spec_id: result for result in state.agent_validation_results}
        runs_by_task: dict[str, list[Any]] = {}
        for record in state.agent_run_records:
            runs_by_task.setdefault(record.task_spec_id, []).append(record)
        for task in state.agent_task_specs:
            result = validation_by_task.get(task.id)
            lines.extend(
                [
                    f"## {task.id}",
                    "",
                    f"- Skill: {task.skill_name}",
                    f"- Task type: {task.task_type}",
                    f"- Output schema: {task.output_schema_name or 'unspecified'}",
                    f"- Required output files: {', '.join(task.required_output_files) if task.required_output_files else 'none'}",
                    f"- Validation: {result.status if result else 'not validated'}",
                    "",
                ]
            )
            if result and result.issues:
                lines.append("Validation issues:")
                lines.extend(f"- {issue}" for issue in result.issues)
                lines.append("")
            for record in runs_by_task.get(task.id, []):
                lines.extend(
                    [
                        f"- Run record {record.id}: {record.status} ({record.agent_name}/{record.model})",
                        f"  outputs: {', '.join(record.output_paths) if record.output_paths else 'none'}",
                    ]
                )
            if runs_by_task.get(task.id):
                lines.append("")
        path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")

    def _write_active_loop_markdown(self, state: ResearchRunState) -> None:
        path = Path(state.run_dir, "active_decisions.md")
        if state.active_loop is None:
            path.write_text("# Active Loop Decisions\n\nNo active research loop has run yet.\n", encoding="utf-8")
            return
        loop = state.active_loop
        lines = [
            "# Active Loop Decisions",
            "",
            f"- Status: {loop.status}",
            f"- Current iteration: {loop.current_iteration}",
            f"- Max iterations: {loop.budget.max_iterations}",
            f"- Max papers: {loop.budget.max_papers}",
            f"- Max full-text papers: {loop.budget.max_full_text_papers}",
            f"- Max queries: {loop.budget.max_queries}",
            "",
            "## Decisions",
            "",
        ]
        for decision in loop.decisions:
            lines.extend(
                [
                    f"### {decision.id}: {decision.decision_type}",
                    "",
                    f"- Iteration: {decision.iteration}",
                    f"- Status: {decision.status}",
                    f"- Expected value: {decision.expected_value:.2f}",
                    f"- Cost estimate: {decision.cost_estimate:.2f}",
                    f"- Reason: {decision.reason or 'none'}",
                    "",
                    "Evidence:",
                    "",
                ]
            )
            lines.extend([f"- {item}" for item in decision.evidence] or ["- none"])
            lines.append("")
        path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")

    def _provenance_records(self, state: ResearchRunState) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        for collection_name in [
            "paper_notes",
            "paper_artifacts",
            "paper_sections",
            "evidence_spans",
            "search_queries",
            "source_coverage",
            "coverage_stopping_assessment",
            "citation_graph",
            "references",
            "tables",
            "equations",
            "captions",
            "ocr_attempts",
            "paper_ranking",
            "paper_triage",
            "field_map",
            "claims",
            "gaps",
            "gap_evidence_matrices",
            "hypotheses",
            "cross_domain_analogies",
            "cross_domain_transfers",
            "novelty_assessments",
            "novelty_dossiers",
            "experiments",
            "reviewer_objections",
            "reviewer_summaries",
            "rejected_ideas",
            "human_reviews",
            "review_queue",
            "agent_task_specs",
            "agent_run_records",
            "agent_validation_results",
            "active_loop",
        ]:
            value = getattr(state, collection_name)
            items = value if isinstance(value, list) else ([value] if value is not None else [])
            for item in items:
                provenance = getattr(item, "provenance", None)
                if provenance is None:
                    continue
                records.append({"collection": collection_name, "object_id": getattr(item, "id", ""), **to_plain(provenance)})
        records.extend(to_plain(state.provenance))
        return records


def _append_unique(existing: list[Any], new_items: Iterable[Any], key: str = "id") -> list[Any]:
    items = list(existing)
    seen = {getattr(item, key) for item in items}
    for item in new_items:
        item_key = getattr(item, key)
        if item_key not in seen:
            items.append(item)
            seen.add(item_key)
    return items


def _linked_gap_papers(gap: Gap) -> str:
    linked_ids = gap.supporting_paper_ids or gap.linked_paper_ids
    return ", ".join(linked_ids) if linked_ids else "indirect evidence only"


def _claim_has_evidence_span(claim: Claim, spans: list[EvidenceSpan]) -> bool:
    claim_source_ids = set(claim.source_paper_ids)
    if not claim_source_ids:
        return False
    return any(span.paper_id in claim_source_ids for span in spans)


def _span_locator(span: EvidenceSpan) -> str:
    parts = []
    if span.page_start:
        page = (
            f"page {span.page_start}"
            if span.page_start == span.page_end or not span.page_end
            else f"pages {span.page_start}-{span.page_end}"
        )
        parts.append(page)
    if span.char_start or span.char_end:
        parts.append(f"chars {span.char_start}-{span.char_end}")
    return ", ".join(parts) or "unlocated"


def _write_records_markdown(path: Path, title: str, lines: list[str]) -> None:
    if not lines:
        path.write_text(f"# {title}\n\nNo {title.lower()} recorded yet.\n", encoding="utf-8")
        return
    path.write_text(f"# {title}\n\n" + "\n".join(lines).rstrip() + "\n", encoding="utf-8")


# Backward-compatible name for the initial scaffold.
StateStore = ResearchStateManager
