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
    ExperimentPlan,
    Gap,
    Paper,
    PaperNote,
    PaperTriageResult,
    ResearchRunState,
    ResearchTopic,
    ReviewerObjection,
    ReviewerSimulationSummary,
    ValidationIssue,
    ValidationResult,
    to_plain,
)

RUN_ARTIFACTS = [
    "topic.md",
    "config.json",
    "state.json",
    "papers.json",
    "paper_notes.json",
    "paper_notes.md",
    "paper_triage.json",
    "paper_triage.md",
    "field_map.json",
    "field_map.md",
    "claims.json",
    "gaps.json",
    "gaps.md",
    "hypotheses.json",
    "cross_domain_analogies.json",
    "cross_domain_analogies.md",
    "novelty_gate.json",
    "novelty_gate.md",
    "experiments.json",
    "experiments.md",
    "implementation_tasks.md",
    "reviewer_objections.json",
    "reviewer_summaries.json",
    "reviewer_simulation.md",
    "revised_experiment_recommendations.md",
    "orchestrator_plan.json",
    "orchestrator_result.json",
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
                "schema_version": 1,
                "source_mode": "deterministic-fake",
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
        self._write_json(run_dir / "paper_notes.json", state.paper_notes)
        self._write_json(run_dir / "paper_triage.json", state.paper_triage)
        self._write_json(run_dir / "field_map.json", state.field_map)
        self._write_json(run_dir / "claims.json", state.claims)
        self._write_json(run_dir / "gaps.json", state.gaps)
        self._write_json(run_dir / "hypotheses.json", state.hypotheses)
        self._write_json(run_dir / "cross_domain_analogies.json", state.cross_domain_analogies)
        self._write_json(run_dir / "novelty_gate.json", state.novelty_assessments)
        self._write_json(run_dir / "experiments.json", state.experiments)
        self._write_json(run_dir / "reviewer_objections.json", state.reviewer_objections)
        self._write_json(run_dir / "reviewer_summaries.json", state.reviewer_summaries)
        self._write_json(run_dir / "orchestrator_plan.json", state.orchestrator_plan)
        self._write_json(run_dir / "orchestrator_result.json", state.orchestrator_result)
        self._write_json(run_dir / "run_log.json", state.run_log)
        self._write_json(run_dir / "rejected_ideas.json", state.rejected_ideas)
        self._write_json(run_dir / "provenance.json", self._provenance_records(state))
        self._write_paper_notes_markdown(state)
        self._write_paper_triage_markdown(state)
        self._write_field_map_markdown(state)
        self._write_gaps_markdown(state)
        self._write_cross_domain_analogies_markdown(state)
        self._write_novelty_gate_markdown(state)
        self._write_experiments_markdown(state)
        self._write_implementation_tasks_markdown(state)
        self._write_reviewer_simulation_markdown(state)
        self._write_revised_experiment_recommendations_markdown(state)
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
        hypothesis_ids = {hypothesis.id for hypothesis in state.hypotheses}
        novelty_targets = {assessment.target_gap_or_hypothesis_id for assessment in state.novelty_assessments}

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
        report_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")

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
                    f"- Recommended reading depth: {decision.recommended_reading_depth}",
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
            lines.extend([f"- `{snippet.source_id}`: {snippet.quote}" for snippet in snippets] or ["- none"])
            lines.append("")
        path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")

    def _write_gaps_markdown(self, state: ResearchRunState) -> None:
        path = Path(state.run_dir, "gaps.md")
        if not state.gaps:
            path.write_text("# Research Gaps\n\nNo gaps mined yet.\n", encoding="utf-8")
            return
        lines = ["# Research Gaps", ""]
        for gap in state.gaps:
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
        path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")

    def _write_cross_domain_analogies_markdown(self, state: ResearchRunState) -> None:
        path = Path(state.run_dir, "cross_domain_analogies.md")
        if not state.cross_domain_analogies:
            path.write_text("# Cross-Domain Analogies\n\nNo cross-domain analogies generated yet.\n", encoding="utf-8")
            return
        lines = ["# Cross-Domain Analogies", ""]
        for analogy in state.cross_domain_analogies:
            lines.extend(
                [
                    f"## {analogy.source_field}: {analogy.source_concept}",
                    "",
                    f"- Target gap: `{analogy.target_gap_id}`",
                    f"- Confidence: {analogy.confidence}",
                    "",
                    "### Why It Maps",
                    "",
                    analogy.why_it_maps,
                    "",
                    "### What Breaks In The Mapping",
                    "",
                    analogy.what_breaks_in_the_mapping,
                    "",
                    "### Technical Transfer Candidate",
                    "",
                    analogy.technical_transfer_candidate,
                    "",
                    "### Papers Or Sources To Search",
                    "",
                ]
            )
            lines.extend([f"- {query}" for query in analogy.papers_or_sources_to_search] or ["- none"])
            lines.extend(
                [
                    "",
                    "### Possible Experiment",
                    "",
                    analogy.possible_experiment,
                    "",
                    "### Risk Of Fake Analogy",
                    "",
                    analogy.risk_of_fake_analogy,
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

    def _provenance_records(self, state: ResearchRunState) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        for collection_name in [
            "paper_notes",
            "paper_triage",
            "field_map",
            "claims",
            "gaps",
            "hypotheses",
            "cross_domain_analogies",
            "novelty_assessments",
            "experiments",
            "reviewer_objections",
            "reviewer_summaries",
            "rejected_ideas",
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


# Backward-compatible name for the initial scaffold.
StateStore = ResearchStateManager
