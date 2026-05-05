"""Final researcher-facing report generation for GapForge runs."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from gapforge.models import (
    Claim,
    ExperimentPlan,
    Gap,
    NoveltyAssessment,
    Paper,
    PaperNote,
    ResearchRunState,
    ReviewerObjection,
    ReviewerSimulationSummary,
    to_plain,
)

CONFIDENCE_RANK = {"high": 3, "medium": 2, "low": 1}
NOVELTY_RANK = {"strong": 4, "medium": 3, "weak": 2, "unchecked": 1, "likely_not_new": 0}
VERDICT_RANK = {"pursue": 3, "revise": 2, "unknown": 1, "reject": 0}


def write_final_report(state: ResearchRunState, *, output_format: str = "markdown") -> Path:
    """Write the final report artifact into a run directory."""

    report = build_final_report(state)
    run_dir = Path(state.run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)
    if output_format == "markdown":
        path = run_dir / "final_report.md"
        path.write_text(render_markdown_report(report), encoding="utf-8")
        return path
    if output_format == "json":
        path = run_dir / "final_report.json"
        path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        return path
    raise ValueError(f"Unsupported report format: {output_format}")


def build_final_report(state: ResearchRunState) -> dict[str, Any]:
    """Build a structured report dictionary before rendering."""

    paper_by_id = {paper.id: paper for paper in state.papers}
    notes_by_paper = {note.paper_id: note for note in state.paper_notes}
    novelty_by_target = {item.target_gap_or_hypothesis_id: item for item in state.novelty_assessments}
    objections_by_experiment = _group_objections(state.reviewer_objections)
    top_gap = _top_gap(state.gaps, novelty_by_target)
    top_experiment = _top_experiment(state.experiments, top_gap, novelty_by_target, objections_by_experiment)
    top_direction = _top_direction(top_gap, top_experiment, novelty_by_target, objections_by_experiment)
    supported_claims = [claim for claim in state.claims if claim.status == "supported" and claim.supporting_evidence]
    uncertain_claims = [
        claim for claim in state.claims if claim.status in {"unsupported", "uncertain", "contested"} or claim.needs_verification
    ]

    return {
        "run_id": state.run_id,
        "topic": state.topic.text,
        "generated_from": {
            "papers": len(state.papers),
            "paper_notes": len(state.paper_notes),
            "claims": len(state.claims),
            "gaps": len(state.gaps),
            "novelty_assessments": len(state.novelty_assessments),
            "experiments": len(state.experiments),
            "reviewer_objections": len(state.reviewer_objections),
        },
        "executive_summary": {
            "recommended_direction": top_direction,
            "evidence_backed_claim_count": len(supported_claims),
            "uncertain_or_unsupported_claim_count": len(uncertain_claims),
            "novelty_warning": _novelty_warning(state.novelty_assessments),
        },
        "broad_topic_interpretation": _topic_interpretation(state),
        "literature_map": _literature_map(state, paper_by_id),
        "search_coverage": _search_coverage(state),
        "top_paper_clusters": _top_paper_clusters(state, paper_by_id),
        "key_papers_read_deeply": _key_papers_read_deeply(state, paper_by_id, notes_by_paper),
        "strongest_research_gaps": [_gap_record(gap, novelty_by_target) for gap in _ranked_gaps(state.gaps, novelty_by_target)[:8]],
        "cross_domain_connections": [
            {
                "source_field": item.source_field,
                "source_concept": item.source_concept,
                "target_gap_id": item.target_gap_id,
                "why_it_maps": item.why_it_maps,
                "what_breaks": item.what_breaks_in_the_mapping,
                "candidate_transfer": item.technical_transfer_candidate,
                "search_queries": item.papers_or_sources_to_search,
                "confidence": item.confidence,
            }
            for item in state.cross_domain_analogies
        ],
        "novelty_gate_results": [_novelty_record(item) for item in state.novelty_assessments],
        "recommended_experiment_plans": [
            _experiment_record(experiment, novelty_by_target, objections_by_experiment)
            for experiment in _ranked_experiments(state.experiments, novelty_by_target, objections_by_experiment)
        ],
        "reviewer_simulation": _reviewer_simulation(state),
        "claim_ledger_summary": _claim_ledger_summary(state),
        "unsupported_or_uncertain_claims": [_claim_record(claim) for claim in uncertain_claims[:20]],
        "rejected_ideas": _rejected_ideas(state),
        "next_actions": _next_actions(state, top_gap, top_experiment),
    }


def render_markdown_report(report: dict[str, Any]) -> str:
    """Render a structured report dictionary as Markdown."""

    lines = [
        f"# GapForge Final Research Report: {report['topic']}",
        "",
        f"Run ID: `{report['run_id']}`",
        "",
    ]
    _section(lines, "1. Executive Summary")
    summary = report["executive_summary"]
    direction = summary["recommended_direction"]
    lines.extend(
        [
            f"Recommended strongest direction: **{direction['title']}**",
            "",
            direction["justification"],
            "",
            f"- Linked gap: `{direction.get('gap_id') or 'none'}`",
            f"- Linked experiment: `{direction.get('experiment_id') or 'none'}`",
            f"- Novelty verdict: {direction.get('novelty_verdict', 'unknown')}",
            f"- Novelty strength: {direction.get('novelty_strength', 'unknown')}",
            f"- Confidence: {direction.get('confidence', 'low')}",
            f"- Evidence-backed ledger claims: {summary['evidence_backed_claim_count']}",
            f"- Unsupported or uncertain ledger claims: {summary['uncertain_or_unsupported_claim_count']}",
            "",
            f"Novelty caution: {summary['novelty_warning']}",
            "",
        ]
    )

    _section(lines, "2. Broad Topic Interpretation")
    interpretation = report["broad_topic_interpretation"]
    lines.extend(
        [
            interpretation["interpretation"],
            "",
            f"- Run maturity: {interpretation['run_maturity']}",
            f"- Evidence posture: {interpretation['evidence_posture']}",
            f"- Hypotheses recorded: {interpretation['hypothesis_count']}",
            "",
        ]
    )

    _section(lines, "3. Literature Map")
    literature_map = report["literature_map"]
    lines.append(f"Field-map confidence: **{literature_map['confidence']}**")
    lines.append("")
    _bullet_lines(lines, "Major questions", literature_map["major_questions"])
    _bullet_lines(lines, "Dominant methods", literature_map["dominant_methods"])
    _bullet_lines(lines, "Common datasets", literature_map["common_datasets"])
    _bullet_lines(lines, "Common metrics", literature_map["common_metrics"])
    _bullet_lines(lines, "Saturated areas", literature_map["saturated_areas"])
    _bullet_lines(lines, "Underexplored areas", literature_map["underexplored_areas"])
    _bullet_lines(lines, "Limitations", literature_map["limitations"])

    _section(lines, "4. Search Coverage")
    coverage = report["search_coverage"]
    lines.extend(
        [
            f"- Papers collected: {coverage['paper_count']}",
            f"- Source counts: {_format_counts(coverage['source_counts'])}",
            f"- Year range: {coverage['year_range']}",
            f"- Papers with DOI: {coverage['papers_with_doi']}",
            f"- Papers with PDF URL: {coverage['papers_with_pdf']}",
            f"- Abstract-only notes: {coverage['abstract_only_notes']}",
            f"- Search limitations: {coverage['limitations']}",
            "",
        ]
    )

    _section(lines, "5. Top Paper Clusters")
    for cluster in report["top_paper_clusters"]:
        lines.extend(
            [
                f"### {cluster['name']}",
                "",
                cluster["description"],
                "",
                f"- Papers: {_format_ids(cluster['paper_ids'])}",
                f"- Representative papers: {_format_ids(cluster['representative_papers'])}",
                f"- Newest papers: {_format_ids(cluster['newest_papers'])}",
                f"- Dominant methods: {', '.join(cluster['dominant_methods']) or 'unknown'}",
                "",
            ]
        )
    if not report["top_paper_clusters"]:
        lines.extend(["No clusters were generated.", ""])

    _section(lines, "6. Key Papers Read Deeply")
    for paper in report["key_papers_read_deeply"]:
        lines.extend(
            [
                f"- `{paper['paper_id']}` {paper['citation']}",
                f"  - Source basis: {paper['source_basis']}; confidence: {paper['confidence']}",
                f"  - Summary: {paper['summary']}",
                f"  - Evidence snippets: {paper['evidence_snippet_count']}",
            ]
        )
    if not report["key_papers_read_deeply"]:
        lines.append("- No paper notes are available.")
    lines.append("")

    _section(lines, "7. Strongest Research Gaps")
    for gap in report["strongest_research_gaps"]:
        lines.extend(
            [
                f"### {gap['title']}",
                "",
                f"- Gap ID: `{gap['id']}`",
                f"- Type: {gap['type']}",
                f"- Confidence: {gap['confidence']}",
                f"- Novelty status: {gap['novelty_status']}",
                f"- Supporting papers: {_format_ids(gap['supporting_paper_ids'])}",
                f"- Supporting claims: {_format_ids(gap['supporting_claim_ids'])}",
                f"- Risk that gap is fake: {gap['risk_that_gap_is_fake']}",
                "",
                gap["description"],
                "",
            ]
        )
    if not report["strongest_research_gaps"]:
        lines.extend(["No gap candidates are available.", ""])

    _section(lines, "8. Cross-Domain Connections")
    for item in report["cross_domain_connections"]:
        lines.extend(
            [
                f"- {item['source_field']} / {item['source_concept']} -> `{item['target_gap_id']}`",
                f"  - Why it may map: {item['why_it_maps']}",
                f"  - What breaks: {item['what_breaks']}",
                f"  - Search next: {', '.join(item['search_queries'][:3]) or 'none'}",
                f"  - Confidence: {item['confidence']}",
            ]
        )
    if not report["cross_domain_connections"]:
        lines.append("- No cross-domain analogies were generated.")
    lines.append("")

    _section(lines, "9. Novelty Gate Results")
    for item in report["novelty_gate_results"]:
        lines.extend(
            [
                f"- `{item['target_id']}` verdict={item['verdict']}, strength={item['novelty_strength']}, confidence={item['confidence']}",
                f"  - Closest prior work: {_format_ids(item['closest_prior_work'])}",
                f"  - What is new: {'; '.join(item['what_is_new']) or 'not established'}",
                f"  - What is not new: {'; '.join(item['what_is_not_new']) or 'unknown'}",
                f"  - Missing searches: {len(item['missing_searches'])}",
            ]
        )
    if not report["novelty_gate_results"]:
        lines.append("- No novelty assessments are available. Treat novelty as unchecked.")
    lines.append("")

    _section(lines, "10. Recommended Experiment Plans")
    for experiment in report["recommended_experiment_plans"][:8]:
        lines.extend(
            [
                f"### {experiment['title']}",
                "",
                f"- Experiment ID: `{experiment['id']}`",
                f"- Linked gaps: {_format_ids(experiment['linked_gap_ids'])}",
                f"- Novelty assessment: `{experiment['novelty_assessment_id'] or 'none'}`",
                f"- Confidence: {experiment['confidence']}",
                f"- Baselines: {', '.join(experiment['baselines']) or 'missing'}",
                f"- Metrics: {', '.join(experiment['metrics']) or 'missing'}",
                f"- Falsification condition: {experiment['falsification_condition']}",
                f"- Publishable result pattern: {experiment['reviewer_killer_result']}",
                f"- Blocking reviewer objections: {experiment['blocking_objection_count']}",
                "",
            ]
        )
    if not report["recommended_experiment_plans"]:
        lines.extend(["No experiment plans are available.", ""])

    _section(lines, "11. Reviewer Simulation")
    review = report["reviewer_simulation"]
    for summary in review["summaries"]:
        readiness = (
            f"- `{summary['experiment_id']}` readiness={summary['submission_readiness_score']}/100, "
            f"recommendation={summary['final_recommendation']}"
        )
        lines.extend(
            [
                readiness,
                f"  - Blocking issues: {'; '.join(summary['blocking_issues']) or 'none'}",
                f"  - Required fixes: {'; '.join(summary['required_fixes']) or 'none'}",
            ]
        )
    if not review["summaries"]:
        lines.append("- No reviewer summaries are available.")
    lines.extend(["", "Most serious objections:", ""])
    for objection in review["serious_objections"]:
        lines.extend(
            [
                f"- `{objection['experiment_id']}` {objection['severity']}/{objection['category']}: {objection['objection']}",
                f"  - Fix: {objection['suggested_fix']}",
            ]
        )
    if not review["serious_objections"]:
        lines.append("- No major or fatal objections recorded.")
    lines.append("")

    _section(lines, "12. Claim Ledger Summary")
    claim_summary = report["claim_ledger_summary"]
    lines.extend(
        [
            f"- Status counts: {_format_counts(claim_summary['status_counts'])}",
            f"- Type counts: {_format_counts(claim_summary['type_counts'])}",
            f"- Claims needing verification: {claim_summary['claims_needing_verification']}",
            f"- Claims without sources: {claim_summary['claims_without_sources']}",
            "",
            "Evidence-backed claims:",
            "",
        ]
    )
    for claim in claim_summary["evidence_backed_claims"]:
        lines.append(f"- `{claim['id']}` ({claim['type']}, {claim['confidence']}): {claim['text']}")
    if not claim_summary["evidence_backed_claims"]:
        lines.append("- none")
    lines.append("")
    _bullet_lines(lines, "Hypotheses", claim_summary["hypotheses"])

    _section(lines, "13. Unsupported or Uncertain Claims")
    for claim in report["unsupported_or_uncertain_claims"]:
        lines.extend(
            [
                f"- `{claim['id']}` ({claim['type']}; status={claim['status']}; confidence={claim['confidence']})",
                f"  - {claim['text']}",
                f"  - Source papers: {_format_ids(claim['source_paper_ids'])}",
            ]
        )
    if not report["unsupported_or_uncertain_claims"]:
        lines.append("- No unsupported, contested, or uncertain claims are recorded.")
    lines.append("")

    _section(lines, "14. Rejected Ideas")
    for idea in report["rejected_ideas"]:
        lines.extend([f"- `{idea['id']}` {idea['idea']}", f"  - Reason: {idea['reason']}"])
    if not report["rejected_ideas"]:
        lines.append("- No rejected ideas are recorded.")
    lines.append("")

    _section(lines, "15. Next Actions")
    lines.extend([f"- {item}" for item in report["next_actions"]] or ["- No next actions generated."])
    lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _section(lines: list[str], title: str) -> None:
    lines.extend([f"## {title}", ""])


def _bullet_lines(lines: list[str], title: str, values: list[str]) -> None:
    lines.extend([f"### {title}", ""])
    lines.extend([f"- {value}" for value in values] or ["- none"])
    lines.append("")


def _group_objections(objections: list[ReviewerObjection]) -> dict[str, list[ReviewerObjection]]:
    grouped: dict[str, list[ReviewerObjection]] = {}
    for objection in objections:
        key = objection.experiment_id or objection.target_id
        grouped.setdefault(key, []).append(objection)
    return grouped


def _top_gap(gaps: list[Gap], novelty_by_target: dict[str, NoveltyAssessment]) -> Gap | None:
    ranked = _ranked_gaps(gaps, novelty_by_target)
    return ranked[0] if ranked else None


def _ranked_gaps(gaps: list[Gap], novelty_by_target: dict[str, NoveltyAssessment]) -> list[Gap]:
    def score(gap: Gap) -> tuple[int, int, int, int, int, str]:
        novelty = novelty_by_target.get(gap.id)
        verdict_score = VERDICT_RANK.get(novelty.verdict, 1) if novelty is not None else 1
        novelty_score = NOVELTY_RANK.get(gap.novelty_status, 1)
        confidence_score = CONFIDENCE_RANK.get(gap.confidence, 1)
        evidence_score = len(gap.supporting_paper_ids or gap.linked_paper_ids) + len(gap.supporting_claim_ids)
        non_meta_score = 0 if _is_meta_gap(gap) else 1
        return (verdict_score, non_meta_score, novelty_score, confidence_score, evidence_score, gap.id)

    return sorted(gaps, key=score, reverse=True)


def _top_experiment(
    experiments: list[ExperimentPlan],
    top_gap: Gap | None,
    novelty_by_target: dict[str, NoveltyAssessment],
    objections_by_experiment: dict[str, list[ReviewerObjection]],
) -> ExperimentPlan | None:
    ranked = _ranked_experiments(experiments, novelty_by_target, objections_by_experiment)
    if top_gap is not None:
        for experiment in ranked:
            if top_gap.id in experiment.linked_gap_ids:
                return experiment
    return ranked[0] if ranked else None


def _is_meta_gap(gap: Gap) -> bool:
    text = " ".join([gap.title, gap.description, gap.why_existing_work_does_not_solve_it]).lower()
    return "metadata/abstract" in text or "abstract text" in text or "abstract-only" in text


def _ranked_experiments(
    experiments: list[ExperimentPlan],
    novelty_by_target: dict[str, NoveltyAssessment],
    objections_by_experiment: dict[str, list[ReviewerObjection]],
) -> list[ExperimentPlan]:
    def score(experiment: ExperimentPlan) -> tuple[int, int, int, int, int, str]:
        novelty = _novelty_for_experiment(experiment, novelty_by_target)
        blocking = sum(1 for item in objections_by_experiment.get(experiment.id, []) if item.blocks_submission)
        completeness = sum(
            1
            for value in [
                experiment.baselines,
                experiment.metrics,
                experiment.what_result_would_falsify_the_idea,
                experiment.reviewer_killer_result,
            ]
            if value
        )
        return (
            VERDICT_RANK.get(novelty.verdict, 1) if novelty is not None else 1,
            CONFIDENCE_RANK.get(experiment.confidence, 1),
            completeness,
            -blocking,
            len(experiment.linked_gap_ids),
            experiment.id,
        )

    return sorted(experiments, key=score, reverse=True)


def _top_direction(
    top_gap: Gap | None,
    top_experiment: ExperimentPlan | None,
    novelty_by_target: dict[str, NoveltyAssessment],
    objections_by_experiment: dict[str, list[ReviewerObjection]],
) -> dict[str, Any]:
    if top_gap is None and top_experiment is None:
        return {
            "title": "No recommendation yet",
            "justification": "The run has not produced enough gaps or experiments to recommend a research direction.",
            "confidence": "low",
            "novelty_verdict": "unknown",
            "novelty_strength": "unknown",
        }
    novelty = None
    if top_gap is not None:
        novelty = novelty_by_target.get(top_gap.id)
    if novelty is None and top_experiment is not None:
        novelty = _novelty_for_experiment(top_experiment, novelty_by_target)
    objections = objections_by_experiment.get(top_experiment.id, []) if top_experiment is not None else []
    blocking = sum(1 for item in objections if item.blocks_submission)
    if top_experiment is not None:
        title = top_experiment.title
    elif top_gap is not None:
        title = top_gap.title or top_gap.description or top_gap.id
    else:
        title = "No recommendation yet"
    if top_gap is not None:
        gap_id = top_gap.id
    elif top_experiment is not None and top_experiment.linked_gap_ids:
        gap_id = top_experiment.linked_gap_ids[0]
    else:
        gap_id = ""
    confidence = top_experiment.confidence if top_experiment is not None else (top_gap.confidence if top_gap is not None else "low")
    justification = (
        "This direction is the best current candidate because it links a ranked gap to a concrete experiment, "
        "names baselines and falsification criteria, and has the strongest available novelty-gate posture. "
        "Treat it as provisional until missing searches, abstract-only notes, and reviewer blocking issues are resolved."
    )
    if top_experiment is None:
        justification = "This direction is the best current gap, but it still needs an experiment plan before it can guide work."
    if novelty is not None and novelty.verdict in {"reject", "unknown"}:
        justification += " The novelty gate does not yet support a strong novelty claim."
    if blocking:
        justification += f" Reviewer simulation currently lists {blocking} blocking issue(s)."
    return {
        "title": title,
        "gap_id": gap_id,
        "experiment_id": top_experiment.id if top_experiment is not None else "",
        "justification": justification,
        "confidence": confidence,
        "novelty_verdict": novelty.verdict if novelty is not None else "unknown",
        "novelty_strength": novelty.novelty_strength if novelty is not None else "unknown",
        "blocking_reviewer_issues": blocking,
    }


def _novelty_for_experiment(experiment: ExperimentPlan, novelty_by_target: dict[str, NoveltyAssessment]) -> NoveltyAssessment | None:
    if experiment.novelty_assessment_id in novelty_by_target:
        return novelty_by_target[experiment.novelty_assessment_id]
    for gap_id in experiment.linked_gap_ids:
        if gap_id in novelty_by_target:
            return novelty_by_target[gap_id]
    return None


def _novelty_warning(assessments: list[NoveltyAssessment]) -> str:
    if not assessments:
        return "No novelty gate has been run; all novelty statements should be treated as unchecked."
    missing = sum(1 for item in assessments if item.missing_searches)
    strong_without_prior = [
        item.target_gap_or_hypothesis_id for item in assessments if item.novelty_strength == "strong" and not item.closest_prior_work
    ]
    if strong_without_prior:
        return "At least one strong novelty label lacks closest prior work and should not be trusted."
    if missing:
        return f"{missing} novelty assessment(s) still list missing searches; novelty remains provisional."
    return "Closest prior work is recorded for the available novelty assessments, but novelty is still not a proof of publishability."


def _topic_interpretation(state: ResearchRunState) -> dict[str, Any]:
    if state.field_map is None:
        interpretation = (
            f"The broad topic is interpreted as a research search space around `{state.topic.text}`, but no field map is available yet."
        )
    else:
        clusters = ", ".join(cluster.name for cluster in state.field_map.clusters[:4]) or "no clusters"
        interpretation = (
            f"The topic is interpreted through {len(state.field_map.clusters)} literature cluster(s): {clusters}. "
            "The report separates claims grounded in the ledger from candidate hypotheses and experiment ideas."
        )
    maturity = "complete loop" if state.experiments and state.reviewer_objections else "partial run"
    evidence = "ledger-backed" if any(claim.supporting_evidence for claim in state.claims) else "mostly heuristic"
    return {
        "interpretation": interpretation,
        "run_maturity": maturity,
        "evidence_posture": evidence,
        "hypothesis_count": len(state.hypotheses),
    }


def _literature_map(state: ResearchRunState, paper_by_id: dict[str, Paper]) -> dict[str, Any]:
    if state.field_map is None:
        return {
            "confidence": "low",
            "major_questions": [],
            "dominant_methods": [],
            "common_datasets": [],
            "common_metrics": [],
            "saturated_areas": [],
            "underexplored_areas": [],
            "limitations": ["No field map artifact was available."],
            "cluster_count": 0,
            "mapped_paper_count": len(paper_by_id),
        }
    field_map = state.field_map
    return {
        "confidence": field_map.confidence,
        "major_questions": field_map.major_questions,
        "dominant_methods": field_map.dominant_methods,
        "common_datasets": field_map.common_datasets,
        "common_metrics": field_map.common_metrics,
        "saturated_areas": field_map.saturated_areas,
        "underexplored_areas": field_map.underexplored_areas,
        "limitations": field_map.limitations,
        "cluster_count": len(field_map.clusters),
        "mapped_paper_count": len({paper_id for cluster in field_map.clusters for paper_id in cluster.paper_ids}),
    }


def _search_coverage(state: ResearchRunState) -> dict[str, Any]:
    years = [paper.year for paper in state.papers if paper.year]
    source_counts = Counter(paper.source or "unknown" for paper in state.papers)
    abstract_only = sum(1 for note in state.paper_notes if note.source_basis == "metadata/abstract only")
    limitations = []
    if not state.papers:
        limitations.append("No papers were collected.")
    if abstract_only:
        limitations.append(f"{abstract_only} note(s) are based on metadata/abstract only.")
    if any(item.missing_searches for item in state.novelty_assessments):
        limitations.append("Some novelty-gate searches remain missing.")
    if not limitations:
        limitations.append("No explicit search limitation was recorded.")
    return {
        "paper_count": len(state.papers),
        "source_counts": dict(sorted(source_counts.items())),
        "year_range": f"{min(years)}-{max(years)}" if years else "unknown",
        "papers_with_doi": sum(1 for paper in state.papers if paper.doi),
        "papers_with_pdf": sum(1 for paper in state.papers if paper.pdf_url),
        "abstract_only_notes": abstract_only,
        "limitations": " ".join(limitations),
    }


def _top_paper_clusters(state: ResearchRunState, paper_by_id: dict[str, Paper]) -> list[dict[str, Any]]:
    if state.field_map is None:
        return []
    records = []
    for cluster in state.field_map.clusters:
        newest = sorted(
            [paper_by_id[paper_id] for paper_id in cluster.paper_ids if paper_id in paper_by_id],
            key=lambda paper: paper.year,
            reverse=True,
        )
        records.append(
            {
                "name": cluster.name,
                "description": cluster.description,
                "paper_ids": cluster.paper_ids,
                "representative_papers": cluster.representative_papers,
                "newest_papers": [paper.id for paper in newest[:3]],
                "dominant_methods": cluster.dominant_methods,
                "open_questions": cluster.open_questions,
                "why_it_matters": cluster.why_it_matters,
            }
        )
    return sorted(records, key=lambda record: len(record["paper_ids"]), reverse=True)


def _key_papers_read_deeply(
    state: ResearchRunState, paper_by_id: dict[str, Paper], notes_by_paper: dict[str, PaperNote]
) -> list[dict[str, Any]]:
    candidate_ids: list[str] = []
    if state.paper_triage is not None:
        candidate_ids.extend(decision.paper_id for decision in state.paper_triage.decisions if decision.tier in {"Tier 1", "Tier 2"})
    candidate_ids.extend(note.paper_id for note in state.paper_notes)
    records: list[dict[str, Any]] = []
    for paper_id in _dedupe(candidate_ids):
        note = notes_by_paper.get(paper_id)
        paper = paper_by_id.get(paper_id)
        if note is None:
            continue
        records.append(
            {
                "paper_id": paper_id,
                "citation": _citation(paper) if paper is not None else paper_id,
                "summary": note.one_sentence_summary or note.summary or "No summary recorded.",
                "source_basis": note.source_basis,
                "confidence": note.confidence,
                "core_claims": note.core_claims,
                "main_results": note.main_results,
                "evidence_snippet_count": len(note.quotes_or_evidence_snippets or note.evidence),
            }
        )
    return records[:12]


def _gap_record(gap: Gap, novelty_by_target: dict[str, NoveltyAssessment]) -> dict[str, Any]:
    novelty = novelty_by_target.get(gap.id)
    return {
        "id": gap.id,
        "title": gap.title or gap.id,
        "type": gap.type,
        "description": gap.description or gap.explicit_reason or "No description recorded.",
        "supporting_paper_ids": gap.supporting_paper_ids or gap.linked_paper_ids,
        "supporting_claim_ids": gap.supporting_claim_ids,
        "counterevidence_claim_ids": gap.counterevidence_claim_ids,
        "why_existing_work_does_not_solve_it": gap.why_existing_work_does_not_solve_it,
        "why_it_matters": gap.why_it_matters,
        "minimum_experiment_needed": gap.minimum_experiment_needed,
        "risk_that_gap_is_fake": gap.risk_that_gap_is_fake or "No risk recorded; treat confidence as low.",
        "confidence": gap.confidence,
        "novelty_status": gap.novelty_status,
        "novelty_verdict": novelty.verdict if novelty is not None else "unknown",
    }


def _novelty_record(assessment: NoveltyAssessment) -> dict[str, Any]:
    return {
        "target_id": assessment.target_gap_or_hypothesis_id,
        "idea_summary": assessment.idea_summary,
        "closest_prior_work": assessment.closest_prior_work,
        "similarity_to_prior_work": assessment.similarity_to_prior_work,
        "what_is_new": assessment.what_is_new,
        "what_is_not_new": assessment.what_is_not_new,
        "possible_reviewer_objection": assessment.possible_reviewer_objection,
        "decisive_difference_needed": assessment.decisive_difference_needed,
        "search_queries_used": assessment.search_queries_used,
        "missing_searches": assessment.missing_searches,
        "verdict": assessment.verdict,
        "novelty_strength": assessment.novelty_strength,
        "confidence": assessment.confidence,
    }


def _experiment_record(
    experiment: ExperimentPlan,
    novelty_by_target: dict[str, NoveltyAssessment],
    objections_by_experiment: dict[str, list[ReviewerObjection]],
) -> dict[str, Any]:
    novelty = _novelty_for_experiment(experiment, novelty_by_target)
    objections = objections_by_experiment.get(experiment.id, [])
    return {
        "id": experiment.id,
        "title": experiment.title,
        "linked_gap_ids": experiment.linked_gap_ids,
        "hypothesis": experiment.hypothesis,
        "core_claim_being_tested": experiment.core_claim_being_tested,
        "minimum_viable_experiment": experiment.minimum_viable_experiment or experiment.design,
        "datasets_needed": experiment.datasets_needed or experiment.datasets,
        "baselines": experiment.baselines,
        "metrics": experiment.metrics,
        "statistical_tests": experiment.statistical_tests,
        "ablations": experiment.ablations,
        "falsification_condition": experiment.what_result_would_falsify_the_idea,
        "reviewer_killer_result": experiment.reviewer_killer_result,
        "risks": experiment.risks,
        "novelty_assessment_id": experiment.novelty_assessment_id,
        "novelty_verdict": novelty.verdict if novelty is not None else "unknown",
        "confidence": experiment.confidence,
        "blocking_objection_count": sum(1 for item in objections if item.blocks_submission),
    }


def _reviewer_simulation(state: ResearchRunState) -> dict[str, Any]:
    serious = [
        _objection_record(item)
        for item in sorted(
            state.reviewer_objections,
            key=lambda objection: (_severity_rank(objection.severity), objection.blocks_submission),
            reverse=True,
        )
        if item.severity in {"fatal", "major"} or item.blocks_submission
    ]
    return {
        "summaries": [_summary_record(item) for item in state.reviewer_summaries],
        "serious_objections": serious[:12],
    }


def _summary_record(summary: ReviewerSimulationSummary) -> dict[str, Any]:
    return {
        "experiment_id": summary.experiment_id,
        "submission_readiness_score": summary.submission_readiness_score,
        "blocking_issues": summary.blocking_issues,
        "required_fixes": summary.required_fixes,
        "optional_fixes": summary.optional_fixes,
        "final_recommendation": summary.final_recommendation,
    }


def _objection_record(objection: ReviewerObjection) -> dict[str, Any]:
    return {
        "id": objection.id,
        "experiment_id": objection.experiment_id or objection.target_id,
        "severity": objection.severity,
        "category": objection.category,
        "objection": objection.objection,
        "why_reviewer_would_care": objection.why_reviewer_would_care,
        "evidence_or_prior_work": objection.evidence_or_prior_work,
        "suggested_fix": objection.suggested_fix,
        "blocks_submission": objection.blocks_submission,
        "confidence": objection.confidence,
    }


def _claim_ledger_summary(state: ResearchRunState) -> dict[str, Any]:
    claims = state.claims
    status_counts = Counter(claim.status for claim in claims)
    type_counts = Counter(claim.type for claim in claims)
    evidence_backed = [_claim_record(claim) for claim in claims if claim.status == "supported" and claim.supporting_evidence][:10]
    hypotheses = [f"`{hypothesis.id}` {hypothesis.text}" for hypothesis in state.hypotheses]
    hypotheses.extend(f"`{experiment.id}` {experiment.hypothesis}" for experiment in state.experiments if experiment.hypothesis)
    hypotheses.extend(
        f"`{claim.id}` {claim.text}"
        for claim in claims
        if claim.type in {"gap", "analogy"} and claim.status in {"unsupported", "uncertain"}
    )
    return {
        "status_counts": dict(sorted(status_counts.items())),
        "type_counts": dict(sorted(type_counts.items())),
        "claims_needing_verification": sum(1 for claim in claims if claim.needs_verification),
        "claims_without_sources": sum(1 for claim in claims if not claim.source_paper_ids),
        "evidence_backed_claims": evidence_backed,
        "hypotheses": _dedupe(hypotheses)[:8],
    }


def _claim_record(claim: Claim) -> dict[str, Any]:
    return {
        "id": claim.id,
        "text": claim.text,
        "type": claim.type,
        "status": claim.status,
        "confidence": claim.confidence,
        "source_paper_ids": claim.source_paper_ids,
        "supporting_evidence_count": len(claim.supporting_evidence),
        "counter_evidence_count": len(claim.counter_evidence),
        "needs_verification": claim.needs_verification,
        "closest_prior_work": claim.closest_prior_work,
    }


def _rejected_ideas(state: ResearchRunState) -> list[dict[str, Any]]:
    records = [{"id": item.id, "idea": item.idea, "reason": item.reason} for item in state.rejected_ideas]
    existing = {item["id"] for item in records}
    for assessment in state.novelty_assessments:
        if assessment.verdict != "reject":
            continue
        rejected_id = f"rejected-{assessment.target_gap_or_hypothesis_id}"
        if rejected_id in existing:
            continue
        records.append(
            {
                "id": rejected_id,
                "idea": assessment.idea_summary,
                "reason": (
                    f"Novelty gate verdict was reject; closest prior work: {'; '.join(assessment.closest_prior_work) or 'not recorded'}."
                ),
            }
        )
    return records


def _next_actions(state: ResearchRunState, top_gap: Gap | None, top_experiment: ExperimentPlan | None) -> list[str]:
    actions = []
    if top_gap is not None:
        actions.append(f"Read full text for every paper supporting `{top_gap.id}` and update paper notes with evidence snippets.")
    if top_experiment is not None:
        actions.append(f"Implement the minimum viable experiment `{top_experiment.id}` with the named baselines first.")
        actions.append("Define the primary metric, acceptable false-positive or error budget, and falsification threshold before running.")
    missing_searches = sum(len(item.missing_searches) for item in state.novelty_assessments)
    if missing_searches:
        actions.append(f"Resolve {missing_searches} novelty-gate missing search query item(s) before claiming novelty.")
    blockers = [item for item in state.reviewer_objections if item.blocks_submission]
    if blockers:
        actions.append(f"Address {len(blockers)} reviewer blocking issue(s), starting with novelty and baseline objections.")
    abstract_only = [note.paper_id for note in state.paper_notes if note.source_basis == "metadata/abstract only"]
    if abstract_only:
        actions.append(f"Replace abstract-only notes with full-text notes for: {', '.join(abstract_only[:5])}.")
    unsupported = [claim.id for claim in state.claims if claim.status == "unsupported" or claim.needs_verification]
    if unsupported:
        actions.append(f"Verify or downgrade uncertain ledger claims: {', '.join(unsupported[:6])}.")
    return actions[:8]


def _citation(paper: Paper | None) -> str:
    if paper is None:
        return "unknown paper"
    venue = paper.venue or paper.source or "unknown venue"
    authors = ", ".join(paper.authors[:2])
    if len(paper.authors) > 2:
        authors += " et al."
    author_part = f"{authors}. " if authors else ""
    return f"{author_part}{paper.title} ({paper.year or 'n.d.'}, {venue})"


def _format_counts(counts: dict[str, int]) -> str:
    return ", ".join(f"{key}: {value}" for key, value in counts.items()) or "none"


def _format_ids(values: list[str]) -> str:
    return ", ".join(f"`{value}`" for value in values) if values else "none"


def _severity_rank(severity: str) -> int:
    return {"fatal": 3, "major": 2, "minor": 1}.get(severity, 0)


def _dedupe(values: list[str]) -> list[str]:
    output: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value and value not in seen:
            output.append(value)
            seen.add(value)
    return output


def report_to_plain(report: dict[str, Any]) -> dict[str, Any]:
    """Expose report serialization for callers that need plain JSON-compatible data."""

    return to_plain(report)
