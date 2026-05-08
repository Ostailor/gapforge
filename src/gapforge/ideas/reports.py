"""Markdown reports for v2 idea discovery state."""

from __future__ import annotations

from typing import Any

from gapforge.ideas.models import IdeaBank, IdeaCandidate, IdeaEvidenceLink, IdeaNoveltyAssessment, IdeaReviewRecord
from gapforge.ideas.state import IdeaDiscoveryState


def render_idea_discovery_report(
    state: IdeaDiscoveryState,
    *,
    portfolios: list[Any] | None = None,
    metrics: Any | None = None,
    release_gate: Any | None = None,
) -> str:
    bank = state.idea_bank
    selected_id = _selected_idea_id(state, metrics)
    selected = next((candidate for candidate in state.candidates if candidate.id == selected_id), None)
    rejected = [candidate for candidate in state.candidates if candidate.maturity == "rejected" or candidate.rejection_reason]
    latest_tournament = state.tournaments[-1] if state.tournaments else None
    lines = [
        "# Idea Discovery Report",
        "",
        f"- Project ID: `{bank.project_id if bank else getattr(metrics, 'project_id', 'unknown')}`",
        f"- Root topic: {bank.root_topic if bank else 'unknown'}",
        f"- Selected idea: `{selected_id or 'none'}`",
        f"- Agenda: `{_agenda_id(state, metrics) or 'none'}`",
        f"- Candidates: {len(state.candidates)}",
        f"- Rejected ideas retained: {len(rejected)}",
        f"- Human-accepted ideas: {getattr(metrics, 'human_accepted_idea_count', 'unknown') if metrics else 'unknown'}",
        "",
        "## Selected Idea",
        "",
    ]
    if selected is None:
        lines.append("No idea survived as the selected candidate.")
    else:
        lines.extend(
            [
                f"- `{selected.id}` {selected.title}",
                f"- Contribution type: `{selected.contribution_type}`",
                f"- Maturity: `{selected.maturity}`",
                f"- Novelty status: `{selected.novelty_status}`",
                f"- Core claim: {selected.core_claim or 'not recorded'}",
                f"- Proposed experiment: {selected.proposed_experiment or 'not recorded'}",
                f"- Closest prior work: {', '.join(selected.closest_prior_work_ids) or 'none'}",
                f"- Supporting papers: {', '.join(selected.supporting_paper_ids) or 'none'}",
                f"- Evidence spans: {', '.join(selected.evidence_span_ids) or 'none'}",
                f"- Counterevidence papers: {', '.join(selected.counterevidence_paper_ids) or 'none'}",
            ]
        )
    lines.extend(["", "## Rejected Ideas", ""])
    if rejected:
        for candidate in rejected:
            lines.extend(
                [
                    f"### `{candidate.id}` {candidate.title}",
                    "",
                    f"- Contribution type: `{candidate.contribution_type}`",
                    f"- Novelty status: `{candidate.novelty_status}`",
                    f"- Rejection reason: {candidate.rejection_reason or 'not recorded'}",
                    f"- Likely failure mode: {candidate.likely_failure_mode or 'not recorded'}",
                    "",
                ]
            )
    else:
        lines.append("- none")
    lines.extend(["", "## Novelty Blockers", ""])
    novelty_rows = []
    for assessment in state.novelty_assessments:
        if assessment.verdict in {"reject", "revise", "unknown"} or assessment.missing_searches or assessment.counterevidence:
            novelty_rows.append(
                f"- `{assessment.idea_id}` verdict=`{assessment.verdict}` strength=`{assessment.novelty_strength}`; "
                f"closest={', '.join(assessment.closest_prior_work_ids) or 'none'}; "
                f"missing={'; '.join(assessment.missing_searches) or 'none'}; "
                f"counterevidence={'; '.join(assessment.counterevidence) or 'none'}; "
                f"required mutation={assessment.required_mutation or 'none'}"
            )
    lines.extend(novelty_rows or ["- none"])
    lines.extend(["", "## Evidence Links", ""])
    if state.evidence_links:
        for link in state.evidence_links:
            target = link.paper_id or link.evidence_span_id or link.claim_id or "missing target"
            lines.append(f"- `{link.idea_id}` `{link.link_type}` {target} confidence={link.confidence}: {link.note or 'no note'}")
    else:
        lines.append("- none")
    lines.extend(["", "## Tournament Scores", ""])
    if latest_tournament is None:
        lines.append("- no tournament recorded")
    else:
        lines.extend(
            [
                f"- Tournament: `{latest_tournament.id}`",
                f"- Selected candidate: `{latest_tournament.selected_candidate_id or 'none'}`",
                f"- Agenda: `{latest_tournament.agenda_id or 'none'}`",
                f"- Selection reason: {latest_tournament.selection_reason or 'not recorded'}",
                "",
            ]
        )
        for record in sorted(latest_tournament.score_records, key=lambda item: item.total_score, reverse=True):
            lines.append(
                f"- `{record.idea_id}` total={record.total_score:.3f} evidence={record.evidence_score:.2f} "
                f"novelty={record.novelty_score:.2f} tractability={record.tractability_score:.2f} "
                f"impact={record.impact_score:.2f} reviewer_risk={record.reviewer_risk_score:.2f} "
                f"blockers={'; '.join(record.blockers) or 'none'}"
            )
    lines.extend(["", "## Human Feedback", ""])
    if state.feedback_records or state.reviews:
        for feedback in state.feedback_records:
            lines.append(
                f"- Feedback `{feedback.id}` idea=`{feedback.idea_id}` action=`{feedback.action}` reviewer={feedback.reviewer}: "
                f"{feedback.rationale or feedback.notes or 'no rationale'}"
            )
        for review in state.reviews:
            lines.append(
                f"- Review `{review.id}` idea=`{review.idea_id}` status=`{review.status}` reviewer={review.reviewer}: "
                f"{review.notes or 'no notes'}"
            )
    else:
        lines.append("- none")
    lines.extend(["", "## Research Agenda", ""])
    if state.agendas:
        for agenda in state.agendas:
            lines.extend(
                [
                    f"### `{agenda.id}`",
                    "",
                    f"- Blockers: {agenda.blocker_summary}",
                    f"- Expected artifacts: {', '.join(agenda.expected_artifacts) or 'none'}",
                    f"- Decision points: {'; '.join(agenda.decision_points) or 'none'}",
                    f"- Stop conditions: {'; '.join(agenda.stop_conditions) or 'none'}",
                    "",
                ]
            )
            for step in agenda.agenda_steps:
                lines.append(f"- Step `{step.id}` `{step.step_type}`: {step.description} artifact={step.required_artifact}")
    else:
        lines.append("- none")
    lines.extend(["", "## Topic Portfolio Coverage", ""])
    for portfolio in portfolios or []:
        lines.append(f"- `{portfolio.id}` variants={len(portfolio.topic_variants)} root={portfolio.root_topic}")
    if not portfolios:
        lines.append("- none")
    lines.extend(["", "## Idea Yield", ""])
    if metrics is None:
        lines.append("- metrics not generated")
    else:
        lines.extend(
            [
                f"- Topic variants: {metrics.topic_variant_count}",
                f"- Candidates: {metrics.candidate_count}",
                f"- Mutations: {metrics.mutation_count}",
                f"- Constructive gaps: {metrics.constructive_gap_count}",
                f"- Cross-domain transfers: {metrics.cross_domain_transfer_count}",
                f"- Tournament survivors: {metrics.tournament_survivor_count}",
                f"- Human-accepted ideas: {metrics.human_accepted_idea_count}",
                f"- Agenda generated: {str(metrics.agenda_generated).lower()}",
                f"- Idea yield rate: {metrics.idea_yield_rate:.4f}",
            ]
        )
    lines.extend(["", "## v2 Release Gate", ""])
    if release_gate is None:
        lines.append("- release gate not evaluated")
    else:
        lines.extend(
            [
                f"- Passed: {str(release_gate.passed).lower()}",
                f"- Status: `{release_gate.status}`",
                f"- Recommended next version: `{release_gate.recommended_next_version}`",
                f"- Blockers: {'; '.join(release_gate.blockers) or 'none'}",
                f"- Warnings: {'; '.join(release_gate.warnings) or 'none'}",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def render_idea_bank_markdown(state: IdeaDiscoveryState) -> str:
    bank = state.idea_bank
    if bank is None:
        return "# Idea Bank\n\nNo idea bank has been created yet.\n"
    active = [item for item in state.candidates if item.id in set(bank.candidate_ids) and item.maturity != "rejected"]
    rejected = [item for item in state.candidates if item.id in set(bank.rejected_candidate_ids) or item.maturity == "rejected"]
    lines = [
        f"# Idea Bank `{bank.id}`",
        "",
        f"- Project ID: `{bank.project_id}`",
        f"- Root topic: {bank.root_topic}",
        f"- Candidates: {len(state.candidates)}",
        f"- Active candidates: {len(active)}",
        f"- Rejected candidates retained: {len(rejected)}",
        f"- Selected candidate: `{bank.selected_candidate_id or 'none'}`",
        f"- Agenda ID: `{bank.agenda_id or 'none'}`",
        "",
        "Idea maturity is separate from paper readiness. A candidate can be useful search state without being manuscript-ready.",
        "",
        "## Active Candidates",
        "",
    ]
    lines.extend(_candidate_line(candidate) for candidate in active[:50])
    if not active:
        lines.append("- none")
    lines.extend(["", "## Rejected Candidates", ""])
    lines.extend(_candidate_line(candidate, include_reason=True) for candidate in rejected[:50])
    if not rejected:
        lines.append("- none")
    return "\n".join(lines).rstrip() + "\n"


def render_idea_report_markdown(
    candidate: IdeaCandidate,
    *,
    bank: IdeaBank | None = None,
    evidence_links: list[IdeaEvidenceLink] | None = None,
    novelty_assessments: list[IdeaNoveltyAssessment] | None = None,
    reviews: list[IdeaReviewRecord] | None = None,
) -> str:
    links = evidence_links or []
    assessments = novelty_assessments or []
    review_records = reviews or []
    lines = [
        f"# Idea Candidate `{candidate.id}`",
        "",
        f"- Title: {candidate.title}",
        f"- Project ID: `{candidate.project_id}`",
        f"- Source topic ID: `{candidate.source_topic_id or 'none'}`",
        f"- Bank ID: `{bank.id if bank else 'unknown'}`",
        f"- Contribution type: `{candidate.contribution_type}`",
        f"- Maturity: `{candidate.maturity}`",
        f"- Novelty status: `{candidate.novelty_status}`",
        f"- Tractability score: {candidate.tractability_score:.2f}",
        f"- Impact score: {candidate.impact_score:.2f}",
        f"- Evidence score: {candidate.evidence_score:.2f}",
        f"- Reviewer risk score: {candidate.reviewer_risk_score:.2f}",
        f"- Idea yield score: {candidate.idea_yield_score:.2f}",
        f"- Likely failure mode: {candidate.likely_failure_mode or 'not recorded'}",
        "",
        "Idea maturity is not paper readiness. `experiment_ready` and `manuscript_ready` still require the downstream evidence gates.",
        "",
        "## Summary",
        "",
        candidate.summary or "No summary recorded.",
        "",
        "## Core Claim",
        "",
        candidate.core_claim or "No core claim recorded.",
        "",
        "## Proposed Experiment",
        "",
        candidate.proposed_experiment or "No proposed experiment recorded.",
        "",
        "## Expected Baselines",
        "",
    ]
    lines.extend([f"- {item}" for item in candidate.expected_baselines] or ["- none"])
    lines.extend(["", "## Expected Metrics", ""])
    lines.extend([f"- {item}" for item in candidate.expected_metrics] or ["- none"])
    lines.extend(["", "## Prior Work and Evidence", ""])
    lines.extend(
        [
            f"- Closest prior work: {', '.join(candidate.closest_prior_work_ids) or 'none'}",
            f"- Evidence spans: {', '.join(candidate.evidence_span_ids) or 'none'}",
            f"- Supporting papers: {', '.join(candidate.supporting_paper_ids) or 'none'}",
            f"- Counterevidence papers: {', '.join(candidate.counterevidence_paper_ids) or 'none'}",
        ]
    )
    lines.extend(["", "## Evidence Links", ""])
    if links:
        for link in links:
            target = link.paper_id or link.evidence_span_id or link.claim_id or "missing target"
            lines.append(f"- `{link.link_type}` {target} confidence={link.confidence}: {link.note or 'no note'}")
    else:
        lines.append("- none")
    lines.extend(["", "## Novelty Assessments", ""])
    if assessments:
        for assessment in assessments[-5:]:
            lines.extend(
                [
                    f"### `{assessment.id}`",
                    "",
                    f"- Verdict: `{assessment.verdict}`",
                    f"- Novelty strength: `{assessment.novelty_strength}`",
                    f"- Closest prior work: {', '.join(assessment.closest_prior_work_ids) or 'none'}",
                    f"- Missing searches: {'; '.join(assessment.missing_searches) or 'none'}",
                    f"- Counterevidence: {'; '.join(assessment.counterevidence) or 'none'}",
                    f"- Required mutation: {assessment.required_mutation or 'none'}",
                    f"- Similarity summary: {assessment.similarity_summary or 'not recorded'}",
                    "",
                ]
            )
    else:
        lines.append("- none")
    lines.extend(["", "## Human Reviews", ""])
    if review_records:
        for review in review_records:
            fixes = "; ".join(review.required_fixes) or "none"
            lines.extend(
                [
                    f"### `{review.id}`",
                    "",
                    f"- Reviewer: {review.reviewer}",
                    f"- Status: `{review.status}`",
                    f"- Novelty: {review.novelty_judgment or 'not recorded'}",
                    f"- Feasibility: {review.feasibility_judgment or 'not recorded'}",
                    f"- Impact: {review.impact_judgment or 'not recorded'}",
                    f"- Required fixes: {fixes}",
                    f"- Notes: {review.notes or 'none'}",
                    "",
                ]
            )
    else:
        lines.append("- none")
    if candidate.maturity == "rejected" or candidate.rejection_reason:
        lines.extend(["", "## Rejection", "", candidate.rejection_reason or "Rejected without a recorded reason."])
    return "\n".join(lines).rstrip() + "\n"


def _candidate_line(candidate: IdeaCandidate, *, include_reason: bool = False) -> str:
    reason = f" reason={candidate.rejection_reason}" if include_reason and candidate.rejection_reason else ""
    return (
        f"- `{candidate.id}` {candidate.title} "
        f"[{candidate.contribution_type}, maturity={candidate.maturity}, novelty={candidate.novelty_status}, "
        f"yield={candidate.idea_yield_score:.2f}]{reason}"
    )


def _selected_idea_id(state: IdeaDiscoveryState, metrics: Any | None) -> str:
    if state.idea_bank is not None and state.idea_bank.selected_candidate_id:
        return state.idea_bank.selected_candidate_id
    selected_id = getattr(metrics, "selected_idea_id", None) if metrics is not None else None
    if selected_id:
        return str(selected_id)
    if state.tournaments:
        return state.tournaments[-1].selected_candidate_id
    return ""


def _agenda_id(state: IdeaDiscoveryState, metrics: Any | None) -> str:
    if state.idea_bank is not None and state.idea_bank.agenda_id:
        return state.idea_bank.agenda_id
    agenda_id = getattr(metrics, "agenda_id", None) if metrics is not None else None
    if agenda_id:
        return str(agenda_id)
    if state.agendas:
        return state.agendas[-1].id
    return ""
