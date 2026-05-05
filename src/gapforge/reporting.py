"""Final researcher-facing report generation for GapForge runs."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from gapforge.models import (
    Claim,
    CrossDomainTransferCandidate,
    ExperimentPlan,
    Gap,
    GapEvidenceMatrix,
    NoveltyAssessment,
    NoveltyDossier,
    Paper,
    PaperNote,
    ResearchRunState,
    ReviewerObjection,
    ReviewerSimulationSummary,
    to_plain,
)
from gapforge.redaction import redact_text
from gapforge.retrieval.index_store import RetrievalIndexStore
from gapforge.review.audit import is_rejected, review_summary
from gapforge.sources.coverage import generate_source_coverage
from gapforge.sources.stopping import assess_literature_coverage

CONFIDENCE_RANK = {"high": 3, "medium": 2, "low": 1}
NOVELTY_RANK = {"strong": 4, "medium": 3, "weak": 2, "unchecked": 1, "likely_not_new": 0}
VERDICT_RANK = {"pursue": 3, "revise": 2, "unknown": 1, "reject": 0}


def write_final_report(state: ResearchRunState, *, output_format: str = "markdown", strict: bool = False) -> Path:
    """Write the final report artifact into a run directory."""

    report = build_final_report(state, strict=strict)
    run_dir = Path(state.run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)
    if output_format == "markdown":
        path = run_dir / "final_report.md"
        path.write_text(redact_text(render_markdown_report(report)), encoding="utf-8")
        return path
    if output_format == "json":
        path = run_dir / "final_report.json"
        path.write_text(redact_text(json.dumps(report, indent=2)) + "\n", encoding="utf-8")
        return path
    raise ValueError(f"Unsupported report format: {output_format}")


def build_final_report(state: ResearchRunState, *, strict: bool = False) -> dict[str, Any]:
    """Build a structured report dictionary before rendering."""

    paper_by_id = {paper.id: paper for paper in state.papers}
    notes_by_paper = {note.paper_id: note for note in state.paper_notes}
    novelty_by_target = {item.target_gap_or_hypothesis_id: item for item in state.novelty_assessments}
    dossier_by_target = {item.target_id: item for item in state.novelty_dossiers}
    matrix_by_gap = {item.gap_id: item for item in state.gap_evidence_matrices}
    transfer_by_id = {item.id: item for item in state.cross_domain_transfers}
    objections_by_experiment = _group_objections(state.reviewer_objections)
    active_gaps = [gap for gap in state.gaps if not is_rejected(state, "gap", gap.id)]
    top_gap = _top_gap(active_gaps, novelty_by_target, matrix_by_gap)
    top_experiment = _top_experiment(state.experiments, top_gap, novelty_by_target, objections_by_experiment)
    coverage = _search_coverage(state)
    retrieval_coverage = _retrieval_coverage(state)
    evidence_index = _evidence_locator_index(state)
    top_direction = _top_direction_v2(
        top_gap,
        top_experiment,
        novelty_by_target,
        objections_by_experiment,
        dossier_by_target,
        matrix_by_gap,
        coverage,
        evidence_index,
        strict=strict,
    )
    supported_claims = [claim for claim in state.claims if claim.status == "supported" and claim.supporting_evidence]
    uncertain_claims = [
        claim for claim in state.claims if claim.status in {"unsupported", "uncertain", "contested"} or claim.needs_verification
    ]
    strongest_gaps = [
        _gap_record(gap, novelty_by_target, matrix_by_gap.get(gap.id), evidence_index)
        for gap in _ranked_gaps(active_gaps, novelty_by_target, matrix_by_gap)[:8]
    ]
    deeply_read = _key_papers_read_deeply(state, paper_by_id, notes_by_paper, evidence_index)
    novelty_records = [_novelty_record(item, dossier_by_target.get(item.target_gap_or_hypothesis_id)) for item in state.novelty_assessments]
    experiment_records = [
        _experiment_record(experiment, novelty_by_target, objections_by_experiment)
        for experiment in _ranked_experiments(state.experiments, novelty_by_target, objections_by_experiment)
    ]
    claim_summary = _claim_ledger_summary(state)
    rejected = _rejected_ideas(state)
    human_summary = review_summary(state)
    review_queue_summary = _review_queue_summary(state)
    agent_summary = _agent_execution_summary(state)
    if strict and agent_summary["imported_without_validation"]:
        top_direction.setdefault("blocking_reasons", []).append("Agent-backed outputs were imported without validation.")
        top_direction["readiness"] = "not_ready"
        top_direction["title"] = "No direction ready"
    uncertainty = _uncertainty_section(state, coverage, uncertain_claims, novelty_records)
    next_actions = _next_actions_v2(state, top_gap, top_experiment, coverage, top_direction, uncertainty)
    sections = {
        "executive_summary": {
            "recommended_direction": top_direction,
            "evidence_backed_claim_count": len(supported_claims),
            "uncertain_or_unsupported_claim_count": len(uncertain_claims),
            "novelty_warning": _novelty_warning(state.novelty_assessments),
            "strict_mode": strict,
        },
        "what_was_searched": _what_was_searched(coverage),
        "source_and_full_text_coverage": coverage,
        "retrieval_coverage": retrieval_coverage,
        "field_map": _literature_map(state, paper_by_id),
        "important_paper_clusters": _top_paper_clusters(state, paper_by_id),
        "papers_read_deeply": deeply_read,
        "evidence_backed_research_gaps": strongest_gaps,
        "gap_evidence_matrix_summary": _gap_matrix_summary(state, evidence_index),
        "cross_domain_transfer_candidates": _cross_domain_transfer_candidates(state, transfer_by_id),
        "closest_prior_work_dossiers": novelty_records,
        "recommended_top_research_direction": top_direction,
        "experiment_plan_for_top_direction": _experiment_for_top_direction(top_experiment, experiment_records),
        "reviewer_simulation_and_blocking_issues": _reviewer_simulation(state),
        "claim_ledger_summary": claim_summary,
        "human_review_summary": human_summary,
        "review_queue": review_queue_summary,
        "agent_execution_provenance": agent_summary,
        "rejected_ideas": rejected,
        "what_remains_uncertain": uncertainty,
        "next_actions": next_actions,
    }

    report_version = "v0.3" if state.config.get("v3") else "v0.2"

    return {
        "run_id": state.run_id,
        "topic": state.topic.text,
        "schema_version": state.config.get("schema_version", 1),
        "report_version": report_version,
        "strict": strict,
        "generated_from": {
            "papers": len(state.papers),
            "paper_notes": len(state.paper_notes),
            "claims": len(state.claims),
            "gaps": len(state.gaps),
            "novelty_assessments": len(state.novelty_assessments),
            "novelty_dossiers": len(state.novelty_dossiers),
            "evidence_spans": len(state.evidence_spans),
            "paper_sections": len(state.paper_sections),
            "experiments": len(state.experiments),
            "reviewer_objections": len(state.reviewer_objections),
            "retrieval_documents": retrieval_coverage.get("document_count", 0),
            "agent_tasks": len(state.agent_task_specs),
            "agent_imports": agent_summary["imported_count"],
        },
        "sections": sections,
        "evidence_locators": _all_evidence_locators(state),
        "source_coverage": coverage,
        "retrieval_coverage": retrieval_coverage,
        "executive_summary": sections["executive_summary"],
        "broad_topic_interpretation": _topic_interpretation(state),
        "literature_map": sections["field_map"],
        "search_coverage": coverage,
        "top_paper_clusters": sections["important_paper_clusters"],
        "key_papers_read_deeply": deeply_read,
        "strongest_research_gaps": strongest_gaps,
        "cross_domain_connections": sections["cross_domain_transfer_candidates"],
        "novelty_gate_results": novelty_records,
        "recommended_experiment_plans": experiment_records,
        "reviewer_simulation": sections["reviewer_simulation_and_blocking_issues"],
        "claim_ledger_summary": claim_summary,
        "unsupported_or_uncertain_claims": [_claim_record(claim) for claim in uncertain_claims[:20]],
        "rejected_ideas": rejected,
        "human_review_summary": human_summary,
        "review_queue": review_queue_summary,
        "agent_execution_provenance": agent_summary,
        "next_actions": next_actions,
    }


def render_markdown_report(report: dict[str, Any]) -> str:
    """Render an evidence-located research dossier as Markdown."""

    sections = report.get("sections", {})
    summary = sections.get("executive_summary", report.get("executive_summary", {}))
    direction = summary.get("recommended_direction", {})
    coverage = sections.get("source_and_full_text_coverage", report.get("search_coverage", {}))
    lines = [
        f"# GapForge Final Research Report: {report['topic']}",
        "",
        f"Run ID: `{report['run_id']}`",
        f"Report version: `{report.get('report_version', 'v0.2')}`",
        f"Strict mode: {str(report.get('strict', False)).lower()}",
        "",
    ]

    _section(lines, "1. Executive Summary")
    lines.extend(
        [
            f"Recommendation: **{direction.get('title', 'No direction ready')}**",
            "",
            direction.get("justification", "No recommendation was produced."),
            "",
            f"- Readiness: {direction.get('readiness', 'not_ready')}",
            f"- Linked gap: `{direction.get('gap_id') or 'none'}`",
            f"- Linked experiment: `{direction.get('experiment_id') or 'none'}`",
            f"- Novelty verdict: {direction.get('novelty_verdict', 'unknown')}",
            f"- Novelty strength: {direction.get('novelty_strength', 'unknown')}",
            f"- Closest-prior-work dossier: `{direction.get('dossier_id') or 'none'}`",
            f"- Evidence locators: {_format_ids(direction.get('evidence_locators', []))}",
            f"- Blocking reasons: {'; '.join(direction.get('blocking_reasons', [])) or 'none'}",
            f"- Evidence-backed ledger claims: {summary.get('evidence_backed_claim_count', 0)}",
            f"- Unsupported or uncertain ledger claims: {summary.get('uncertain_or_unsupported_claim_count', 0)}",
            "",
            f"Novelty caution: {summary.get('novelty_warning', 'Novelty has not been established.')}",
            "",
        ]
    )

    _section(lines, "2. What Was Searched")
    searched = sections.get("what_was_searched", {})
    lines.extend(
        [
            f"- Queries run: {searched.get('query_count', 0)}",
            f"- Purposes: {_format_counts(searched.get('purpose_counts', {}))}",
            f"- Sources searched: {', '.join(searched.get('searched_sources', [])) or 'none'}",
            "",
        ]
    )
    for query in searched.get("queries", [])[:16]:
        lines.append(
            f"- `{query['id']}` {query['purpose']}: {query['query']} "
            f"(sources={', '.join(query['source_names']) or 'none'}, results={len(query['result_paper_ids'])}, "
            f"failures={len(query['failure_messages'])})"
        )
    if not searched.get("queries"):
        lines.append("- No searches are recorded. Treat the report as an offline or manually assembled smoke artifact.")
    lines.append("")

    _section(lines, "3. Source and Full-Text Coverage")
    lines.extend(
        [
            "Compatibility label: Search and Source Coverage.",
            "",
            f"- Papers collected: {coverage.get('paper_count', 0)}",
            f"- Source counts: {_format_counts(coverage.get('source_counts', {}))}",
            f"- Failed sources: {', '.join(coverage.get('failed_sources', [])) or 'none'}",
            f"- Papers with parsed full text: {coverage.get('papers_with_full_text', 0)}",
            f"- Parsed references: {coverage.get('reference_count', 0)}",
            f"- Parsed tables: {coverage.get('table_count', 0)}",
            f"- Parsed equations: {coverage.get('equation_count', 0)}",
            f"- Parsed captions: {coverage.get('caption_count', 0)}",
            f"- OCR records: {coverage.get('ocr_attempt_count', 0)}",
            f"- Abstract-only notes: {coverage.get('abstract_only_notes', 0)}",
            f"- Fallback/offline papers: {coverage.get('fallback_paper_count', 0)}",
            f"- Fixture/fallback label: {coverage.get('fixture_or_fallback_label', 'not detected')}",
            f"- Coverage confidence: {coverage.get('confidence', 'low')}",
            f"- Coverage assessment: {coverage.get('coverage_assessment', 'unknown')}",
            f"- Source policy profile: {coverage.get('policy_profile_id', 'generic')}",
            f"- Policy enough for mapping: {str(coverage.get('policy_enough_for_mapping', False)).lower()}",
            f"- Policy enough for gap mining: {str(coverage.get('policy_enough_for_gap_mining', False)).lower()}",
            f"- Policy enough for novelty: {str(coverage.get('policy_enough_for_novelty', False)).lower()}",
            f"- Policy enough for experiment design: {str(coverage.get('policy_enough_for_experiment_design', False)).lower()}",
            f"- Limitations: {coverage.get('limitations', 'No limitations recorded.')}",
            "",
        ]
    )
    if coverage.get("policy_missing_requirements"):
        lines.extend(["Policy missing requirements:"])
        lines.extend([f"- {item}" for item in coverage.get("policy_missing_requirements", [])[:12]])
        lines.append("")
    if coverage.get("policy_recommended_queries"):
        lines.extend(["Policy recommended next searches:"])
        lines.extend([f"- {query}" for query in coverage.get("policy_recommended_queries", [])[:8]])
        lines.append("")

    _section(lines, "3a. Skill Execution Provenance")
    agent_summary = sections.get("agent_execution_provenance", report.get("agent_execution_provenance", {}))
    lines.extend(
        [
            f"- Deterministic completed skills: {', '.join(agent_summary.get('deterministic_skills', [])) or 'none recorded'}",
            f"- LLM-backed notes: {agent_summary.get('llm_backed_note_count', 0)}",
            f"- Codex agent task packs: {agent_summary.get('task_count', 0)}",
            f"- Codex agent imported outputs: {agent_summary.get('imported_count', 0)}",
            f"- Agent validation results: {agent_summary.get('validation_count', 0)}",
        ]
    )
    if agent_summary.get("imported_without_validation"):
        lines.append("- Warning: agent-backed outputs were imported without validation.")
    for record in agent_summary.get("agent_records", [])[:8]:
        lines.append(
            f"- `{record.get('task_spec_id', 'unknown')}`: {record.get('status', 'unknown')} "
            f"via {record.get('agent_name', 'agent')}/{record.get('model', 'model')} "
            f"(validation={record.get('validation_result_id') or 'none'})"
        )
    lines.append("")

    _section(lines, "3b. Retrieval Coverage")
    retrieval = sections.get("retrieval_coverage", report.get("retrieval_coverage", {}))
    lines.extend(
        [
            f"- Index available: {str(retrieval.get('available', False)).lower()}",
            f"- Documents indexed: {retrieval.get('document_count', 0)}",
            f"- Index type: {retrieval.get('index_type', 'none')}",
            f"- Embedding model: {retrieval.get('embedding_model', 'none')}",
            f"- Path: `{retrieval.get('path', 'none')}`",
            "",
        ]
    )
    for object_type, count in sorted(retrieval.get("document_type_counts", {}).items()):
        lines.append(f"- {object_type}: {count}")
    if not retrieval.get("available"):
        lines.append("- No retrieval index was available for this report.")
    lines.append("")

    _section(lines, "4. Field Map")
    literature_map = sections.get("field_map", {})
    lines.append(f"Field-map confidence: **{literature_map.get('confidence', 'low')}**")
    lines.append("")
    _bullet_lines(lines, "Major questions", literature_map.get("major_questions", []))
    _bullet_lines(lines, "Dominant methods", literature_map.get("dominant_methods", []))
    _bullet_lines(lines, "Common datasets", literature_map.get("common_datasets", []))
    _bullet_lines(lines, "Common metrics", literature_map.get("common_metrics", []))
    _bullet_lines(lines, "Underexplored areas", literature_map.get("underexplored_areas", []))
    _bullet_lines(lines, "Limitations", literature_map.get("limitations", []))

    _section(lines, "5. Important Paper Clusters")
    for cluster in sections.get("important_paper_clusters", []):
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
    if not sections.get("important_paper_clusters"):
        lines.extend(["No clusters were generated.", ""])

    _section(lines, "6. Papers Read Deeply")
    for paper in sections.get("papers_read_deeply", []):
        lines.extend(
            [
                f"- `{paper['paper_id']}` {paper['citation']}",
                f"  - Evidence basis: {paper['evidence_label']}; confidence: {paper['confidence']}",
                f"  - Sections used: {', '.join(paper.get('sections_used', [])) or 'none'}",
                f"  - Evidence locators: {_format_ids(paper.get('evidence_locators', []))}",
                f"  - Summary: {paper['summary']}",
            ]
        )
    if not sections.get("papers_read_deeply"):
        lines.append("- No paper notes are available.")
    lines.append("")

    _section(lines, "7. Evidence-Backed Research Gaps")
    for gap in sections.get("evidence_backed_research_gaps", []):
        lines.extend(
            [
                f"### {gap['title']}",
                "",
                f"- Gap ID: `{gap['id']}`",
                f"- Type: {gap['type']}",
                f"- Confidence: {gap['confidence']}",
                f"- Novelty status: {gap['novelty_status']}",
                f"- Evidence basis: {gap['evidence_basis']}",
                f"- Supporting papers: {_format_ids(gap['supporting_paper_ids'])}",
                f"- Evidence locators: {_format_ids(gap.get('evidence_locators', []))}",
                f"- Counterevidence papers: {_format_ids(gap['counterevidence_paper_ids'])}",
                f"- Risk that gap is fake: {gap['risk_that_gap_is_fake']}",
                "",
                gap["description"],
                "",
            ]
        )
    if not sections.get("evidence_backed_research_gaps"):
        lines.extend(["No evidence-backed gap candidates are available.", ""])

    _section(lines, "8. Gap Evidence Matrix Summary")
    for matrix in sections.get("gap_evidence_matrix_summary", []):
        lines.extend(
            [
                f"- `{matrix['gap_id']}` confidence={matrix['confidence']}; rows={matrix['evidence_row_count']}; "
                f"supporting={_format_ids(matrix['papers_supporting'])}; countering={_format_ids(matrix['papers_countering'])}",
                f"  - Locators: {_format_ids(matrix.get('evidence_locators', []))}",
            ]
        )
    if not sections.get("gap_evidence_matrix_summary"):
        lines.append("- No gap evidence matrices are available.")
    lines.append("")

    _section(lines, "9. Cross-Domain Transfer Candidates")
    for item in sections.get("cross_domain_transfer_candidates", []):
        lines.extend(
            [
                f"- {item['source_field']} / {item['source_concept']} -> `{item['target_gap_id']}`",
                f"  - Status: {item['status']}",
                f"  - Source papers: {_format_ids(item['source_paper_ids'])}",
                f"  - Evidence spans: {_format_ids(item.get('evidence_span_ids', []))}",
                f"  - Transfer mechanism: {item.get('technical_mechanism') or item.get('candidate_transfer') or 'not established'}",
                f"  - What breaks: {item.get('what_breaks') or 'not specified'}",
                f"  - Confidence: {item['confidence']}",
            ]
        )
        if item["status"] == "query_only":
            lines.append("  - Interpretation: query-only seed, not an evidence-backed conclusion.")
    if not sections.get("cross_domain_transfer_candidates"):
        lines.append("- No cross-domain transfer candidates are available.")
    lines.append("")

    _section(lines, "10. Closest-Prior-Work Dossiers")
    for item in sections.get("closest_prior_work_dossiers", []):
        lines.extend(
            [
                f"- `{item['target_id']}` verdict={item['verdict']}, strength={item['novelty_strength']}, confidence={item['confidence']}",
                f"  - Closest prior work: {_format_ids(item['closest_prior_work'] or item.get('dossier_top_prior_work', []))}",
                f"  - Candidates considered: {item.get('dossier_candidate_count', 0)}",
                f"  - Missing searches: {'; '.join(item['missing_searches']) or 'none'}",
                f"  - Decisive difference needed: {item['decisive_difference_needed'] or 'not specified'}",
                f"  - Dossier action: {item.get('dossier_recommended_action') or 'not available'}",
            ]
        )
    if not sections.get("closest_prior_work_dossiers"):
        lines.append("- No novelty dossiers are available. Treat novelty as unchecked.")
    lines.append("")

    _section(lines, "11. Recommended Top Research Direction")
    lines.extend(
        [
            f"Direction: **{direction.get('title', 'No direction ready')}**",
            f"Recommended strongest direction: {direction.get('title', 'No direction ready')}.",
            "",
            direction.get("justification", "No recommendation was produced."),
            "",
            f"- Readiness: {direction.get('readiness', 'not_ready')}",
            f"- This is a novelty claim: {str(direction.get('claims_novelty', False)).lower()}",
            f"- Blocking reasons: {'; '.join(direction.get('blocking_reasons', [])) or 'none'}",
            "",
        ]
    )

    _section(lines, "12. Experiment Plan for Top Direction")
    experiment = sections.get("experiment_plan_for_top_direction") or {}
    if experiment:
        lines.extend(
            [
                f"### {experiment['title']}",
                "",
                f"- Experiment ID: `{experiment['id']}`",
                f"- Linked gaps: {_format_ids(experiment['linked_gap_ids'])}",
                f"- Baselines: {', '.join(experiment['baselines']) or 'missing'}",
                f"- Metrics: {', '.join(experiment['metrics']) or 'missing'}",
                f"- Falsification condition: {experiment['falsification_condition']}",
                f"- Publishable result pattern: {experiment['reviewer_killer_result']}",
                f"- Blocking reviewer objections: {experiment['blocking_objection_count']}",
                "",
            ]
        )
    else:
        lines.extend(["No experiment is ready for the top direction.", ""])

    _section(lines, "13. Reviewer Simulation and Blocking Issues")
    review = sections.get("reviewer_simulation_and_blocking_issues", {})
    for summary_item in review.get("summaries", []):
        lines.extend(
            [
                f"- `{summary_item['experiment_id']}` readiness={summary_item['submission_readiness_score']}/100, "
                f"recommendation={summary_item['final_recommendation']}",
                f"  - Blocking issues: {'; '.join(summary_item['blocking_issues']) or 'none'}",
                f"  - Required fixes: {'; '.join(summary_item['required_fixes']) or 'none'}",
            ]
        )
    if not review.get("summaries"):
        lines.append("- No reviewer summaries are available.")
    lines.extend(["", "Most serious objections:", ""])
    for objection in review.get("serious_objections", []):
        lines.extend(
            [
                f"- `{objection['experiment_id']}` {objection['severity']}/{objection['category']}: {objection['objection']}",
                f"  - Evidence/prior work: {', '.join(objection['evidence_or_prior_work']) or 'none'}",
                f"  - Fix: {objection['suggested_fix']}",
            ]
        )
    if not review.get("serious_objections"):
        lines.append("- No major or fatal objections recorded.")
    lines.append("")

    _section(lines, "14. Claim Ledger Summary")
    claim_summary = sections.get("claim_ledger_summary", {})
    lines.extend(
        [
            f"- Status counts: {_format_counts(claim_summary.get('status_counts', {}))}",
            f"- Type counts: {_format_counts(claim_summary.get('type_counts', {}))}",
            f"- Claims needing verification: {claim_summary.get('claims_needing_verification', 0)}",
            f"- Claims without sources: {claim_summary.get('claims_without_sources', 0)}",
            "",
            "Evidence-backed claims:",
            "",
        ]
    )
    for claim in claim_summary.get("evidence_backed_claims", []):
        lines.append(
            f"- `{claim['id']}` ({claim['type']}, {claim['confidence']}): {claim['text']} "
            f"locators={_format_ids(claim.get('evidence_locators', []))}"
        )
    if not claim_summary.get("evidence_backed_claims"):
        lines.append("- none")
    lines.extend(["", "Unsupported or uncertain claims:", ""])
    for claim in report.get("unsupported_or_uncertain_claims", []):
        lines.append(f"- `{claim['id']}` ({claim['type']}; status={claim['status']}): {claim['text']}")
    if not report.get("unsupported_or_uncertain_claims"):
        lines.append("- none")
    lines.append("")

    _section(lines, "15. Human Review Summary")
    human_review = sections.get("human_review_summary", {})
    lines.extend(
        [
            f"- Review records: {human_review.get('review_count', 0)}",
            f"- Actions: {_format_counts(human_review.get('action_counts', {}))}",
            f"- Locked objects: {_format_ids(human_review.get('locked_objects', []))}",
            f"- Rejected objects: {_format_ids(human_review.get('rejected_objects', []))}",
            "",
        ]
    )
    for record in human_review.get("recent_reviews", []):
        lines.append(
            f"- `{record['id']}` {record['action']} `{record['object_type']}:{record['object_id']}`"
            + (f": {record['note']}" if record["note"] else "")
        )
    if not human_review.get("recent_reviews"):
        lines.append("- none")
    lines.extend(["", "Open review queue items:", ""])
    review_queue = sections.get("review_queue", report.get("review_queue", {}))
    for item in review_queue.get("open_items", []):
        lines.append(
            f"- `{item['id']}` {item['priority']} `{item['object_type']}:{item['object_id']}`"
            + (f" run=`{item['run_id']}`" if item.get("run_id") else "")
            + f": {item['reason']}"
        )
    if not review_queue.get("open_items"):
        lines.append("- none")
    lines.append("")

    _section(lines, "16. Rejected Ideas")
    for idea in sections.get("rejected_ideas", []):
        lines.extend([f"- `{idea['id']}` {idea['idea']}", f"  - Reason: {idea['reason']}"])
    if not sections.get("rejected_ideas"):
        lines.append("- No rejected ideas are recorded.")
    lines.append("")

    _section(lines, "17. What Remains Uncertain")
    uncertainty = sections.get("what_remains_uncertain", {})
    for title, values in [
        ("Missing searches", uncertainty.get("missing_searches", [])),
        ("Poor or fallback coverage", uncertainty.get("coverage_warnings", [])),
        ("Unsupported claims", uncertainty.get("unsupported_claims", [])),
        ("Abstract-only evidence", uncertainty.get("abstract_only_papers", [])),
        ("Fake-gap risks", uncertainty.get("gap_risks", [])),
    ]:
        _bullet_lines(lines, title, values)

    _section(lines, "18. Next Actions")
    lines.extend([f"- {item}" for item in sections.get("next_actions", [])] or ["- No next actions generated."])
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


def _top_gap(
    gaps: list[Gap],
    novelty_by_target: dict[str, NoveltyAssessment],
    matrix_by_gap: dict[str, GapEvidenceMatrix] | None = None,
) -> Gap | None:
    ranked = _ranked_gaps(gaps, novelty_by_target, matrix_by_gap)
    return ranked[0] if ranked else None


def _ranked_gaps(
    gaps: list[Gap],
    novelty_by_target: dict[str, NoveltyAssessment],
    matrix_by_gap: dict[str, GapEvidenceMatrix] | None = None,
) -> list[Gap]:
    matrices = matrix_by_gap or {}

    def score(gap: Gap) -> tuple[int, int, int, int, int, int, str]:
        novelty = novelty_by_target.get(gap.id)
        matrix = matrices.get(gap.id)
        verdict_score = VERDICT_RANK.get(novelty.verdict, 1) if novelty is not None else 1
        novelty_score = NOVELTY_RANK.get(gap.novelty_status, 1)
        confidence_score = CONFIDENCE_RANK.get(gap.confidence, 1)
        evidence_score = len(gap.supporting_paper_ids or gap.linked_paper_ids) + len(gap.supporting_claim_ids)
        matrix_score = len(matrix.evidence_rows) + len(matrix.papers_supporting) if matrix is not None else 0
        counter_penalty = -(len(matrix.papers_countering) if matrix is not None else 0)
        non_meta_score = 0 if _is_meta_gap(gap) else 1
        return (verdict_score, non_meta_score, novelty_score, confidence_score, matrix_score, evidence_score + counter_penalty, gap.id)

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


def _top_direction_v2(
    top_gap: Gap | None,
    top_experiment: ExperimentPlan | None,
    novelty_by_target: dict[str, NoveltyAssessment],
    objections_by_experiment: dict[str, list[ReviewerObjection]],
    dossier_by_target: dict[str, NoveltyDossier],
    matrix_by_gap: dict[str, GapEvidenceMatrix],
    coverage: dict[str, Any],
    evidence_index: dict[str, list[str]],
    *,
    strict: bool,
) -> dict[str, Any]:
    if top_gap is None:
        return _no_direction("No evidence-backed gap is available.", strict)

    novelty = novelty_by_target.get(top_gap.id)
    dossier = dossier_by_target.get(top_gap.id)
    evidence_locators = _gap_evidence_locators(top_gap, matrix_by_gap.get(top_gap.id), evidence_index)
    objections = objections_by_experiment.get(top_experiment.id, []) if top_experiment is not None else []
    blocking = [item for item in objections if item.blocks_submission]
    missing_searches = list(dossier.missing_searches if dossier is not None else (novelty.missing_searches if novelty is not None else []))
    blocking_reasons = []
    if coverage.get("coverage_assessment") == "poor":
        blocking_reasons.append("Source or full-text coverage is poor.")
    if coverage.get("policy_assessment_active") and not coverage.get("policy_enough_for_novelty", False):
        blocking_reasons.append("Field-specific source policy does not pass novelty coverage.")
    if strict and coverage.get("policy_assessment_active") and not coverage.get("policy_enough_for_experiment_design", False):
        blocking_reasons.append("Field-specific source policy does not pass experiment-design coverage.")
    if coverage.get("fallback_paper_count", 0):
        blocking_reasons.append("Some papers are fallback/offline artifacts.")
    if not evidence_locators:
        blocking_reasons.append("The top gap has no EvidenceSpan locator-backed evidence.")
    if dossier is None:
        blocking_reasons.append("No closest-prior-work dossier exists for the top gap.")
    elif dossier.verdict != "pursue":
        blocking_reasons.append(f"Closest-prior-work dossier verdict is {dossier.verdict}, not pursue.")
    if missing_searches:
        blocking_reasons.append(f"{len(missing_searches)} novelty search item(s) are still missing.")
    if top_experiment is None:
        blocking_reasons.append("No experiment plan exists for the top gap.")
    if blocking:
        blocking_reasons.append(f"{len(blocking)} reviewer blocking issue(s) remain.")

    ready = not blocking_reasons
    if strict and not ready:
        return _no_direction(
            "Strict mode refused to recommend a paper direction until coverage, evidence, and novelty gates pass.",
            strict,
            blocking_reasons,
        )
    if coverage.get("coverage_assessment") == "poor":
        return _no_direction(
            "Coverage is too weak to recommend a paper idea; run the next search and full-text steps first.",
            strict,
            blocking_reasons,
        )

    title = top_experiment.title if top_experiment is not None else (top_gap.title or top_gap.id)
    claims_novelty = bool(
        dossier and dossier.verdict == "pursue" and dossier.novelty_strength in {"medium", "strong"} and not missing_searches
    )
    novelty_phrase = (
        "The dossier supports a provisional novelty claim." if claims_novelty else "The report does not claim this direction is novel yet."
    )
    return {
        "title": title,
        "readiness": "ready" if ready else "provisional",
        "gap_id": top_gap.id,
        "experiment_id": top_experiment.id if top_experiment is not None else "",
        "dossier_id": dossier.target_id if dossier is not None else "",
        "justification": (
            f"This is the strongest current candidate because it has the best ranked evidence-backed gap posture and a concrete "
            f"experiment plan. {novelty_phrase} Treat it as provisional wherever blocking reasons remain."
        ),
        "confidence": top_experiment.confidence if top_experiment is not None else top_gap.confidence,
        "novelty_verdict": dossier.verdict if dossier is not None else (novelty.verdict if novelty is not None else "unknown"),
        "novelty_strength": (
            dossier.novelty_strength if dossier is not None else (novelty.novelty_strength if novelty is not None else "unknown")
        ),
        "dossier_recommended_action": dossier.recommended_action if dossier is not None else "not available",
        "dossier_decisive_difference_needed": dossier.decisive_difference_needed if dossier is not None else "",
        "blocking_reasons": blocking_reasons,
        "evidence_locators": evidence_locators,
        "missing_searches": missing_searches,
        "claims_novelty": claims_novelty,
    }


def _no_direction(message: str, strict: bool, blocking_reasons: list[str] | None = None) -> dict[str, Any]:
    return {
        "title": "No direction ready",
        "readiness": "not_ready",
        "gap_id": "",
        "experiment_id": "",
        "dossier_id": "",
        "justification": message,
        "confidence": "low",
        "novelty_verdict": "unknown",
        "novelty_strength": "unknown",
        "dossier_recommended_action": "run more search and full-text evidence collection",
        "dossier_decisive_difference_needed": "",
        "blocking_reasons": blocking_reasons or [],
        "evidence_locators": [],
        "missing_searches": [],
        "claims_novelty": False,
        "strict_mode": strict,
    }


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
    dossier_by_target: dict[str, Any],
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
    dossier = dossier_by_target.get(top_gap.id) if top_gap is not None else None
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
    if dossier is not None and dossier.decisive_difference_needed:
        justification += f" Dossier decisive difference: {dossier.decisive_difference_needed}"
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
        "dossier_recommended_action": dossier.recommended_action if dossier is not None else "not available",
        "dossier_decisive_difference_needed": dossier.decisive_difference_needed if dossier is not None else "",
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
    coverage = state.source_coverage or generate_source_coverage(state)
    abstract_only = len(coverage.papers_abstract_only)
    limitations = []
    limitations.extend(coverage.coverage_warnings)
    if any(item.missing_searches for item in state.novelty_assessments):
        limitations.append("Some novelty-gate searches remain missing.")
    if not limitations:
        limitations.append("No explicit search limitation was recorded.")
    fixture_or_fallback = _fixture_or_fallback_label(state, coverage.fallback_paper_count)
    coverage_assessment = _coverage_assessment(coverage.confidence, len(coverage.query_records), len(coverage.papers_with_full_text))
    policy_active = state.coverage_stopping_assessment is not None or bool(state.config.get("source_policy_profile"))
    stopping = state.coverage_stopping_assessment or assess_literature_coverage(state)
    return {
        "paper_count": len(state.papers),
        "source_counts": dict(sorted(source_counts.items())),
        "query_count": len(coverage.query_records),
        "queries": [
            {
                "id": record.id,
                "query": record.query,
                "purpose": record.purpose,
                "source_names": record.source_names,
                "result_paper_ids": record.result_paper_ids,
                "failure_messages": record.failure_messages,
            }
            for record in coverage.query_records
        ],
        "searched_sources": coverage.searched_sources,
        "failed_sources": coverage.failed_sources,
        "year_range": f"{min(years)}-{max(years)}" if years else "unknown",
        "papers_with_doi": sum(1 for paper in state.papers if paper.doi),
        "papers_with_pdf": len(coverage.papers_with_pdf),
        "papers_with_full_text": len(coverage.papers_with_full_text),
        "reference_count": len(state.references),
        "table_count": len(state.tables),
        "equation_count": len(state.equations),
        "caption_count": len(state.captions),
        "ocr_attempt_count": len(state.ocr_attempts),
        "abstract_only_notes": abstract_only,
        "fallback_paper_count": coverage.fallback_paper_count,
        "fixture_or_fallback_label": fixture_or_fallback,
        "confidence": coverage.confidence,
        "coverage_assessment": coverage_assessment,
        "policy_profile_id": stopping.profile_id,
        "policy_assessment_active": policy_active,
        "policy_enough_for_mapping": stopping.enough_for_mapping,
        "policy_enough_for_gap_mining": stopping.enough_for_gap_mining,
        "policy_enough_for_novelty": stopping.enough_for_novelty,
        "policy_enough_for_experiment_design": stopping.enough_for_experiment_design,
        "policy_missing_requirements": stopping.missing_requirements,
        "policy_recommended_queries": stopping.recommended_queries,
        "policy_confidence": stopping.confidence,
        "limitations": " ".join(limitations),
    }


def _retrieval_coverage(state: ResearchRunState) -> dict[str, Any]:
    store = RetrievalIndexStore.for_run(state.run_dir)
    if not store.exists():
        return {
            "available": False,
            "document_count": 0,
            "document_type_counts": {},
            "index_type": "none",
            "embedding_model": "none",
            "path": "",
        }
    try:
        manifest = store.load_manifest()
        documents = store.load_documents()
    except (FileNotFoundError, ValueError, OSError):
        return {
            "available": False,
            "document_count": 0,
            "document_type_counts": {},
            "index_type": "unreadable",
            "embedding_model": "unknown",
            "path": str(store.index_dir),
        }
    counts = Counter(document.object_type for document in documents)
    return {
        "available": True,
        "index_id": manifest.id,
        "document_count": manifest.document_count,
        "document_type_counts": dict(sorted(counts.items())),
        "index_type": manifest.index_type,
        "embedding_model": manifest.embedding_model,
        "path": manifest.path,
        "created_at": manifest.created_at,
    }


def _fixture_or_fallback_label(state: ResearchRunState, fallback_count: int) -> str:
    if fallback_count:
        return "fallback/offline papers present"
    if any(paper.source == "fixture" or paper.raw_metadata.get("fixture_notice") for paper in state.papers):
        return "synthetic fixture data"
    return "not detected"


def _coverage_assessment(confidence: str, query_count: int, full_text_count: int) -> str:
    if confidence == "low" or query_count == 0:
        return "poor"
    if full_text_count == 0:
        return "limited"
    return "adequate"


def _what_was_searched(coverage: dict[str, Any]) -> dict[str, Any]:
    purpose_counts = Counter(query["purpose"] for query in coverage.get("queries", []))
    return {
        "query_count": coverage.get("query_count", 0),
        "queries": coverage.get("queries", []),
        "purpose_counts": dict(sorted(purpose_counts.items())),
        "searched_sources": coverage.get("searched_sources", []),
        "failed_sources": coverage.get("failed_sources", []),
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
    state: ResearchRunState,
    paper_by_id: dict[str, Paper],
    notes_by_paper: dict[str, PaperNote],
    evidence_index: dict[str, list[str]],
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
                "evidence_label": _evidence_label(note.source_basis),
                "confidence": note.confidence,
                "core_claims": note.core_claims,
                "main_results": note.main_results,
                "evidence_snippet_count": len(note.quotes_or_evidence_snippets or note.evidence),
                "evidence_locators": _note_evidence_locators(note, evidence_index),
                "sections_used": note.sections_used,
                "missing_sections": note.missing_sections,
            }
        )
    return records[:12]


def _gap_record(
    gap: Gap,
    novelty_by_target: dict[str, NoveltyAssessment],
    matrix: GapEvidenceMatrix | None = None,
    evidence_index: dict[str, list[str]] | None = None,
) -> dict[str, Any]:
    novelty = novelty_by_target.get(gap.id)
    index = evidence_index or {}
    locators = _gap_evidence_locators(gap, matrix, index)
    full_text_locators = {locator for values in index.values() for locator in values}
    has_full_text_evidence = bool(set(locators) & full_text_locators) or bool(
        matrix is not None and any(row.evidence_span_id for row in matrix.evidence_rows)
    )
    return {
        "id": gap.id,
        "title": gap.title or gap.id,
        "type": gap.type,
        "description": gap.description or gap.explicit_reason or "No description recorded.",
        "supporting_paper_ids": gap.supporting_paper_ids or gap.linked_paper_ids,
        "supporting_claim_ids": gap.supporting_claim_ids,
        "counterevidence_claim_ids": gap.counterevidence_claim_ids,
        "counterevidence_paper_ids": matrix.papers_countering if matrix is not None else [],
        "evidence_row_count": len(matrix.evidence_rows) if matrix is not None else 0,
        "evidence_locators": locators,
        "evidence_basis": "full-text evidence" if has_full_text_evidence else "abstract-only or indirect evidence",
        "evidence_matrix_confidence": matrix.confidence if matrix is not None else "none",
        "why_existing_work_does_not_solve_it": gap.why_existing_work_does_not_solve_it,
        "why_it_matters": gap.why_it_matters,
        "minimum_experiment_needed": gap.minimum_experiment_needed,
        "risk_that_gap_is_fake": gap.risk_that_gap_is_fake or "No risk recorded; treat confidence as low.",
        "confidence": gap.confidence,
        "novelty_status": gap.novelty_status,
        "novelty_verdict": novelty.verdict if novelty is not None else "unknown",
    }


def _transfer_record(transfer: CrossDomainTransferCandidate | None) -> dict[str, Any]:
    if transfer is None:
        return {}
    return {
        "id": transfer.id,
        "status": transfer.status,
        "source_paper_ids": transfer.source_paper_ids,
        "technical_mechanism": transfer.technical_mechanism,
        "required_adaptation": transfer.required_adaptation,
        "evidence_span_ids": transfer.evidence_span_ids,
        "confidence": transfer.confidence,
    }


def _cross_domain_transfer_candidates(
    state: ResearchRunState,
    transfer_by_id: dict[str, CrossDomainTransferCandidate],
) -> list[dict[str, Any]]:
    records = []
    for item in state.cross_domain_analogies:
        transfer_record = _transfer_record(transfer_by_id.get(item.transfer_candidate_id))
        records.append(
            {
                "source_field": item.source_field,
                "source_concept": item.source_concept,
                "target_gap_id": item.target_gap_id,
                "why_it_maps": item.why_it_maps,
                "what_breaks": item.what_breaks_in_the_mapping,
                "candidate_transfer": item.technical_transfer_candidate,
                "search_queries": item.papers_or_sources_to_search,
                "confidence": item.confidence,
                "status": item.status,
                "source_paper_ids": item.source_paper_ids,
                "technical_mechanism": transfer_record.get("technical_mechanism", ""),
                "required_adaptation": transfer_record.get("required_adaptation", ""),
                "evidence_span_ids": transfer_record.get("evidence_span_ids", []),
                "transfer": transfer_record,
            }
        )
    for transfer in state.cross_domain_transfers:
        if any(record.get("transfer", {}).get("id") == transfer.id for record in records):
            continue
        records.append(
            {
                "source_field": transfer.source_field,
                "source_concept": transfer.source_concept,
                "target_gap_id": transfer.target_gap_id,
                "why_it_maps": transfer.why_it_maps,
                "what_breaks": transfer.what_breaks,
                "candidate_transfer": transfer.technical_mechanism,
                "search_queries": [],
                "confidence": transfer.confidence,
                "status": transfer.status,
                "source_paper_ids": transfer.source_paper_ids,
                "technical_mechanism": transfer.technical_mechanism,
                "required_adaptation": transfer.required_adaptation,
                "evidence_span_ids": transfer.evidence_span_ids,
                "transfer": _transfer_record(transfer),
            }
        )
    return records


def _novelty_record(assessment: NoveltyAssessment, dossier: NoveltyDossier | None = None) -> dict[str, Any]:
    return {
        "target_id": assessment.target_gap_or_hypothesis_id,
        "idea_summary": assessment.idea_summary,
        "closest_prior_work": assessment.closest_prior_work,
        "dossier_top_prior_work": dossier.top_prior_work if dossier is not None else [],
        "dossier_recommended_action": dossier.recommended_action if dossier is not None else "",
        "dossier_candidate_count": len(dossier.candidates_considered) if dossier is not None else 0,
        "dossier_comparison_table": dossier.comparison_table if dossier is not None else [],
        "evidence_locators": [span.locator for span in dossier.evidence_spans if span.locator] if dossier is not None else [],
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
        "evidence_locators": [item.locator for item in claim.supporting_evidence if item.locator],
        "needs_verification": claim.needs_verification,
        "closest_prior_work": claim.closest_prior_work,
    }


def _review_queue_summary(state: ResearchRunState) -> dict[str, Any]:
    queue = state.review_queue
    items = queue.items if queue is not None else []
    status_counts = Counter(item.status for item in items)
    open_items = [
        {
            "id": item.id,
            "project_id": item.project_id,
            "run_id": item.run_id,
            "object_type": item.object_type,
            "object_id": item.object_id,
            "priority": item.priority,
            "reason": item.reason,
            "requested_by_skill": item.requested_by_skill,
            "assigned_to": item.assigned_to,
            "created_at": item.created_at,
        }
        for item in items
        if item.status == "open"
    ]
    return {
        "summary": queue.summary if queue is not None else "No review queue has been generated.",
        "status_counts": dict(sorted(status_counts.items())),
        "open_count": len(open_items),
        "open_items": open_items[:20],
    }


def _agent_execution_summary(state: ResearchRunState) -> dict[str, Any]:
    validation_ids = {result.id for result in state.agent_validation_results}
    imported_records = [record for record in state.agent_run_records if record.status == "imported"]
    imported_without_validation = [
        record.id for record in imported_records if not record.validation_result_id or record.validation_result_id not in validation_ids
    ]
    llm_backed_notes = [
        note.paper_id
        for note in state.paper_notes
        if "llm" in note.created_by_skill.lower() or "llm" in note.source_basis.lower() or "llm" in note.provenance.created_by_skill.lower()
    ]
    return {
        "deterministic_skills": state.completed_skills,
        "llm_backed_note_count": len(llm_backed_notes),
        "llm_backed_note_paper_ids": llm_backed_notes[:20],
        "task_count": len(state.agent_task_specs),
        "run_record_count": len(state.agent_run_records),
        "imported_count": len(imported_records),
        "validation_count": len(state.agent_validation_results),
        "imported_without_validation": imported_without_validation,
        "agent_records": [
            {
                "id": record.id,
                "agent_name": record.agent_name,
                "model": record.model,
                "task_spec_id": record.task_spec_id,
                "status": record.status,
                "validation_result_id": record.validation_result_id,
                "output_paths": record.output_paths,
            }
            for record in state.agent_run_records
        ],
        "validation_records": [
            {
                "id": result.id,
                "task_spec_id": result.task_spec_id,
                "status": result.status,
                "unsupported_claim_count": result.unsupported_claim_count,
                "invalid_locator_count": result.invalid_locator_count,
                "invalid_prior_work_count": result.invalid_prior_work_count,
            }
            for result in state.agent_validation_results
        ],
    }


def _rejected_ideas(state: ResearchRunState) -> list[dict[str, Any]]:
    records = [{"id": item.id, "idea": item.idea, "reason": item.reason} for item in state.rejected_ideas]
    existing = {item["id"] for item in records}
    gap_by_id = {gap.id: gap for gap in state.gaps}
    for record in state.human_reviews:
        if record.object_type != "gap" or record.action != "reject":
            continue
        rejected_id = f"human-rejected-{record.object_id}"
        if rejected_id in existing:
            continue
        gap = gap_by_id.get(record.object_id)
        records.append(
            {
                "id": rejected_id,
                "idea": (gap.title or gap.description) if gap is not None else record.object_id,
                "reason": f"Human reviewer rejected this gap: {record.note or 'no reason recorded'}.",
            }
        )
        existing.add(rejected_id)
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


def _evidence_locator_index(state: ResearchRunState) -> dict[str, list[str]]:
    index: dict[str, list[str]] = {}
    for span in state.evidence_spans:
        if span.locator:
            index.setdefault(span.paper_id, []).append(span.locator)
            if span.section_id:
                index.setdefault(span.section_id, []).append(span.locator)
            index.setdefault(span.id, []).append(span.locator)
    return {key: _dedupe(values) for key, values in index.items()}


def _all_evidence_locators(state: ResearchRunState) -> list[dict[str, Any]]:
    return [
        {
            "id": span.id,
            "paper_id": span.paper_id,
            "section_id": span.section_id,
            "locator": span.locator,
            "evidence_type": span.evidence_type,
            "confidence": span.confidence,
        }
        for span in state.evidence_spans
        if span.locator
    ]


def _note_evidence_locators(note: PaperNote, evidence_index: dict[str, list[str]]) -> list[str]:
    locators = list(evidence_index.get(note.paper_id, []))
    locators.extend(item.locator for item in (note.quotes_or_evidence_snippets or note.evidence) if item.locator)
    for section_id in note.sections_used:
        locators.extend(evidence_index.get(section_id, []))
    return _dedupe(locators)


def _gap_evidence_locators(
    gap: Gap,
    matrix: GapEvidenceMatrix | None,
    evidence_index: dict[str, list[str]],
) -> list[str]:
    locators: list[str] = []
    if matrix is not None:
        locators.extend(row.locator for row in matrix.evidence_rows if row.locator)
        locators.extend(row.evidence_span_id for row in matrix.evidence_rows if row.evidence_span_id and not row.locator)
    for paper_id in gap.supporting_paper_ids or gap.linked_paper_ids:
        locators.extend(evidence_index.get(paper_id, []))
    return _dedupe(locators)


def _gap_matrix_summary(state: ResearchRunState, evidence_index: dict[str, list[str]]) -> list[dict[str, Any]]:
    gap_by_id = {gap.id: gap for gap in state.gaps}
    records = []
    for matrix in state.gap_evidence_matrices:
        gap = gap_by_id.get(matrix.gap_id)
        records.append(
            {
                "gap_id": matrix.gap_id,
                "confidence": matrix.confidence,
                "evidence_row_count": len(matrix.evidence_rows),
                "papers_supporting": matrix.papers_supporting,
                "papers_countering": matrix.papers_countering,
                "repeated_limitation_count": matrix.repeated_limitation_count,
                "missing_metric_count": matrix.missing_metric_count,
                "missing_dataset_count": matrix.missing_dataset_count,
                "assumption_pattern_count": matrix.assumption_pattern_count,
                "evidence_locators": _gap_evidence_locators(gap, matrix, evidence_index) if gap is not None else [],
            }
        )
    return records


def _experiment_for_top_direction(top_experiment: ExperimentPlan | None, experiment_records: list[dict[str, Any]]) -> dict[str, Any]:
    if top_experiment is None:
        return {}
    for record in experiment_records:
        if record["id"] == top_experiment.id:
            return record
    return {}


def _uncertainty_section(
    state: ResearchRunState,
    coverage: dict[str, Any],
    uncertain_claims: list[Claim],
    novelty_records: list[dict[str, Any]],
) -> dict[str, list[str]]:
    missing_searches = _dedupe(
        [search for item in novelty_records for search in item.get("missing_searches", [])]
        + [f"{query['id']}: {failure}" for query in coverage.get("queries", []) for failure in query.get("failure_messages", [])]
    )
    coverage_warnings = []
    if coverage.get("coverage_assessment") != "adequate":
        coverage_warnings.append(f"Coverage assessment is {coverage.get('coverage_assessment', 'unknown')}.")
    if coverage.get("fixture_or_fallback_label") != "not detected":
        coverage_warnings.append(f"Data label: {coverage.get('fixture_or_fallback_label')}.")
    if coverage.get("limitations"):
        coverage_warnings.append(coverage["limitations"])
    if coverage.get("policy_missing_requirements"):
        coverage_warnings.append("Field-specific source policy is missing: " + "; ".join(coverage["policy_missing_requirements"][:6]))
    return {
        "missing_searches": missing_searches,
        "coverage_warnings": _dedupe(coverage_warnings),
        "unsupported_claims": [f"{claim.id}: {claim.text}" for claim in uncertain_claims[:12]],
        "abstract_only_papers": [note.paper_id for note in state.paper_notes if note.source_basis != "full text"][:12],
        "gap_risks": _dedupe([f"{gap.id}: {gap.risk_that_gap_is_fake}" for gap in state.gaps if gap.risk_that_gap_is_fake])[:12],
    }


def _next_actions_v2(
    state: ResearchRunState,
    top_gap: Gap | None,
    top_experiment: ExperimentPlan | None,
    coverage: dict[str, Any],
    direction: dict[str, Any],
    uncertainty: dict[str, list[str]],
) -> list[str]:
    actions = []
    if direction.get("readiness") == "not_ready" or coverage.get("coverage_assessment") == "poor":
        actions.append("Run additional source searches and build a source coverage report before choosing a paper direction.")
    if coverage.get("papers_with_full_text", 0) == 0 and state.papers:
        actions.append("Download and parse full text for Tier 1 and Tier 2 papers.")
    if uncertainty.get("missing_searches"):
        actions.append(f"Resolve missing novelty/source searches, starting with: {uncertainty['missing_searches'][0]}.")
    if coverage.get("policy_recommended_queries"):
        actions.append(f"Run policy-recommended search: {coverage['policy_recommended_queries'][0]}.")
    if top_gap is not None and not direction.get("evidence_locators"):
        actions.append(f"Add EvidenceSpan locators for the evidence supporting `{top_gap.id}`.")
    if top_experiment is not None and direction.get("readiness") != "not_ready":
        actions.append(f"Implement `{top_experiment.id}` only after the listed dossier and reviewer blockers are resolved.")
    unsupported = [claim.id for claim in state.claims if claim.status == "unsupported" or claim.needs_verification]
    if unsupported:
        actions.append(f"Verify, contest, or downgrade uncertain ledger claims: {', '.join(unsupported[:6])}.")
    return _dedupe(actions)[:8]


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


def _evidence_label(source_basis: str) -> str:
    lower = source_basis.lower()
    if lower.startswith("llm") and "full text" in lower:
        return "LLM-backed full-text evidence"
    if lower.startswith("llm") and "abstract" in lower:
        return "LLM-backed abstract-only evidence"
    if source_basis == "full text":
        return "full-text evidence"
    if "abstract" in lower:
        return "abstract-only evidence"
    return source_basis or "unknown evidence basis"


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
