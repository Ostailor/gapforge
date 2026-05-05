"""Simulate serious conference-review objections for experiment plans."""

from __future__ import annotations

from gapforge.models import (
    Claim,
    ExperimentPlan,
    ExperimentProtocol,
    NoveltyAssessment,
    PaperNote,
    Provenance,
    ResearchRunState,
    ReviewerObjection,
    ReviewerSimulationSummary,
)
from gapforge.skills.base import Skill
from gapforge.state import utc_now_iso


class ReviewerSimulation(Skill):
    name = "reviewer-simulation"

    def run(self, state: ResearchRunState) -> ResearchRunState:
        return self.review(state)

    def review(self, state: ResearchRunState, *, experiment_id: str | None = None) -> ResearchRunState:
        experiments = [item for item in state.experiments if experiment_id is None or item.id == experiment_id]
        novelty_by_target = {item.target_gap_or_hypothesis_id: item for item in state.novelty_assessments}
        protocols_by_experiment = {item.linked_experiment_plan_id: item for item in state.experiment_protocols}
        objections: list[ReviewerObjection] = []
        summaries: list[ReviewerSimulationSummary] = []

        for experiment in experiments:
            novelty = _novelty_for_experiment(experiment, novelty_by_target)
            experiment_objections = []
            experiment_objections.extend(_reviewer_1_technical(experiment, state.claims))
            experiment_objections.extend(_reviewer_2_novelty(experiment, novelty, state.claims))
            experiment_objections.extend(_reviewer_3_empirical(experiment, state.paper_notes))
            experiment_objections.extend(_reviewer_protocol_completeness(experiment, protocols_by_experiment.get(experiment.id)))
            experiment_objections.extend(_area_chair_positioning(experiment, novelty))
            objections.extend(experiment_objections)
            summaries.append(_summary_for(experiment, experiment_objections))

        state.reviewer_objections = _replace_objections(state.reviewer_objections, objections, experiment_id=experiment_id)
        state.reviewer_summaries = _replace_summaries(state.reviewer_summaries, summaries, experiment_id=experiment_id)
        self.mark_complete(state)
        return state


def _reviewer_1_technical(experiment: ExperimentPlan, claims: list[Claim]) -> list[ReviewerObjection]:
    objections: list[ReviewerObjection] = []
    if not experiment.what_result_would_falsify_the_idea:
        objections.append(
            _objection(
                experiment,
                reviewer_role="Reviewer 1: technical correctness",
                severity="major",
                category="theory",
                objection="The experiment is not falsifiable because it does not state what result would disprove the core claim.",
                why="A top-tier reviewer needs to know which empirical result would make the hypothesis fail.",
                evidence=["Experiment field `what_result_would_falsify_the_idea` is empty."],
                fix="Add a falsification condition tied to the primary metric and strongest baseline.",
                blocks=True,
            )
        )
    if not experiment.statistical_tests:
        objections.append(
            _objection(
                experiment,
                reviewer_role="Reviewer 1: technical correctness",
                severity="major",
                category="reproducibility",
                objection="The plan names metrics but no statistical test or uncertainty estimate.",
                why="Without uncertainty, claimed improvements may be noise from splits, seeds, or label errors.",
                evidence=[f"Metrics named: {', '.join(experiment.metrics) if experiment.metrics else 'none'}"],
                fix="Add paired tests, bootstrap confidence intervals, and seed sensitivity reporting.",
                blocks=True,
            )
        )
    if not experiment.ablations:
        objections.append(
            _objection(
                experiment,
                reviewer_role="Reviewer 1: technical correctness",
                severity="major",
                category="theory",
                objection="The plan lacks ablations, so the proposed mechanism cannot be isolated.",
                why="Reviewers will not accept a result if the winning component is unclear.",
                evidence=["No ablations are specified."],
                fix="Add at least one component-removal ablation and one stress test for the gap condition.",
                blocks=True,
            )
        )
    if not experiment.implementation_steps:
        objections.append(
            _objection(
                experiment,
                reviewer_role="Reviewer 1: technical correctness",
                severity="minor",
                category="reproducibility",
                objection="The plan does not break the experiment into implementation steps.",
                why="Reproducibility starts with an executable protocol, not only a high-level design.",
                evidence=["Experiment field `implementation_steps` is empty."],
                fix="Add ordered steps for dataset preparation, baseline runs, proposed method runs, metric computation, and audit tables.",
                blocks=False,
            )
        )
    unsupported = [claim for claim in claims if claim.status == "unsupported" and _mentions_experiment(claim, experiment)]
    if unsupported:
        objections.append(
            _objection(
                experiment,
                reviewer_role="Reviewer 1: technical correctness",
                severity="major",
                category="clarity",
                objection="The experiment appears to depend on unsupported ledger claims.",
                why="Claims that drive the experiment should be either evidenced or framed as assumptions.",
                evidence=[claim.id for claim in unsupported[:3]],
                fix="Add supporting evidence for these claims or move them into explicit assumptions and risks.",
                blocks=True,
            )
        )
    return objections


def _reviewer_2_novelty(experiment: ExperimentPlan, novelty: NoveltyAssessment | None, claims: list[Claim]) -> list[ReviewerObjection]:
    objections: list[ReviewerObjection] = []
    novelty_claims = [claim for claim in claims if claim.type == "novelty"]
    if novelty is None:
        objections.append(
            _objection(
                experiment,
                reviewer_role="Reviewer 2: novelty skeptic",
                severity="fatal",
                category="novelty",
                objection="Novelty is unsupported because no novelty assessment is linked to this experiment.",
                why="A serious reviewer will reject an experiment-ready claim if closest prior work has not been checked.",
                evidence=["Experiment has no linked `NoveltyAssessment` target."],
                fix="Run `gapforge novelty-check` for the linked gap or hypothesis and revise the experiment against closest prior work.",
                blocks=True,
                confidence="high",
            )
        )
        return objections
    if novelty.verdict == "reject":
        objections.append(
            _objection(
                experiment,
                reviewer_role="Reviewer 2: novelty skeptic",
                severity="fatal",
                category="novelty",
                objection="The novelty gate rejected this idea as too close to prior work.",
                why="A rejected closest-prior-work comparison means the contribution framing is not submission-ready.",
                evidence=novelty.closest_prior_work or ["Novelty verdict is reject."],
                fix="Do not submit this experiment without a materially different task, metric, setting, or theory claim.",
                blocks=True,
                confidence=novelty.confidence,
            )
        )
    if novelty.verdict == "unknown" or not novelty.closest_prior_work:
        objections.append(
            _objection(
                experiment,
                reviewer_role="Reviewer 2: novelty skeptic",
                severity="fatal",
                category="novelty",
                objection="Novelty is unsupported because closest prior work is missing or unresolved.",
                why="Reviewers frequently reject papers that discover prior work during review rather than before submission.",
                evidence=novelty.missing_searches or ["No closest prior work recorded."],
                fix="Complete the missing searches, read the nearest papers, and update the experiment baselines before submission.",
                blocks=True,
                confidence="high",
            )
        )
    elif novelty.verdict == "revise":
        objections.append(
            _objection(
                experiment,
                reviewer_role="Reviewer 2: novelty skeptic",
                severity="major",
                category="novelty",
                objection="The experiment may be incremental relative to closest prior work.",
                why="The paper needs a decisive difference, not only a new dataset or wording.",
                evidence=novelty.closest_prior_work,
                fix=novelty.decisive_difference_needed or "Sharpen the exact contribution over closest prior work.",
                blocks=True,
                confidence=novelty.confidence,
            )
        )
    if novelty.missing_searches:
        objections.append(
            _objection(
                experiment,
                reviewer_role="Reviewer 2: novelty skeptic",
                severity="major",
                category="novelty",
                objection="The novelty check still lists missing searches.",
                why="A reviewer can invalidate the contribution by finding an unsearched adjacent paper.",
                evidence=novelty.missing_searches[:5],
                fix="Resolve or explicitly scope out each missing search before claiming novelty.",
                blocks=True,
                confidence="medium",
            )
        )
    if novelty_claims and all(not claim.closest_prior_work for claim in novelty_claims):
        objections.append(
            _objection(
                experiment,
                reviewer_role="Reviewer 2: novelty skeptic",
                severity="fatal",
                category="novelty",
                objection="Novelty claims exist in the ledger without closest-prior-work links.",
                why="The claim ledger should not let unsupported novelty claims become paper framing.",
                evidence=[claim.id for claim in novelty_claims[:3]],
                fix="Attach closest prior work and evidence to every novelty claim or remove it from the submission argument.",
                blocks=True,
                confidence="high",
            )
        )
    return objections


def _reviewer_3_empirical(experiment: ExperimentPlan, notes: list[PaperNote]) -> list[ReviewerObjection]:
    objections: list[ReviewerObjection] = []
    if not experiment.baselines:
        objections.append(
            _objection(
                experiment,
                reviewer_role="Reviewer 3: empirical rigor and baselines",
                severity="fatal",
                category="baseline",
                objection="The experiment has no baselines.",
                why="Without baselines, the empirical claim cannot be interpreted.",
                evidence=["Experiment field `baselines` is empty."],
                fix="Add closest-prior-work, simple heuristic, and strongest practical baseline before running the study.",
                blocks=True,
                confidence="high",
            )
        )
    elif len(experiment.baselines) < 2:
        objections.append(
            _objection(
                experiment,
                reviewer_role="Reviewer 3: empirical rigor and baselines",
                severity="major",
                category="baseline",
                objection="The baseline set is too thin for a top-conference empirical claim.",
                why="One baseline cannot show robustness against strong alternatives.",
                evidence=experiment.baselines,
                fix="Add the closest-prior-work baseline plus a simple, well-calibrated baseline.",
                blocks=True,
            )
        )
    if not experiment.metrics:
        objections.append(
            _objection(
                experiment,
                reviewer_role="Reviewer 3: empirical rigor and baselines",
                severity="fatal",
                category="metric",
                objection="The experiment names no metrics.",
                why="A reviewer cannot tell what success means or whether the experiment answers the gap.",
                evidence=["Experiment field `metrics` is empty."],
                fix="Add primary and secondary metrics tied to the gap and report confidence intervals.",
                blocks=True,
                confidence="high",
            )
        )
    if not experiment.datasets_needed and not experiment.datasets:
        objections.append(
            _objection(
                experiment,
                reviewer_role="Reviewer 3: empirical rigor and baselines",
                severity="major",
                category="dataset",
                objection="Dataset requirements are underspecified.",
                why="The result may be impossible to reproduce or may silently rely on unrealistic data.",
                evidence=["No datasets or dataset requirements are specified."],
                fix="Specify dataset sources, split policy, label provenance, leakage checks, and scenario coverage.",
                blocks=True,
            )
        )
    if _abstract_only_notes(notes) and experiment.confidence != "low":
        objections.append(
            _objection(
                experiment,
                reviewer_role="Reviewer 3: empirical rigor and baselines",
                severity="minor",
                category="reproducibility",
                objection="Some supporting notes are abstract-only, so method and result extraction may be incomplete.",
                why="This affects baseline selection and may hide evaluation details in full text.",
                evidence=[note.paper_id for note in notes if note.source_basis == "metadata/abstract only"][:5],
                fix="Deep-read the full text for Tier 1 prior work before finalizing baselines.",
                blocks=False,
                confidence="medium",
            )
        )
    return objections


def _reviewer_protocol_completeness(experiment: ExperimentPlan, protocol: ExperimentProtocol | None) -> list[ReviewerObjection]:
    objections: list[ReviewerObjection] = []
    if protocol is None:
        objections.append(
            _objection(
                experiment,
                reviewer_role="Reviewer 3: empirical rigor and baselines",
                severity="fatal" if experiment.paper_ready else "major",
                category="reproducibility",
                objection="The experiment has no executable protocol.",
                why=(
                    "The plan is not concrete enough to audit implementation modules, artifacts, statistical analysis, and reproducibility."
                ),
                evidence=["No ExperimentProtocol linked to this experiment."],
                fix=(
                    "Run `gapforge experiment-protocol` and revise the protocol until baselines, metrics, artifacts, "
                    "and checks are explicit."
                ),
                blocks=True,
                confidence="high",
            )
        )
        return objections
    if not any(candidate.paper_id or candidate.implementation_available for candidate in protocol.baselines):
        objections.append(
            _objection(
                experiment,
                reviewer_role="Reviewer 3: empirical rigor and baselines",
                severity="major",
                category="baseline",
                objection="The protocol lacks a strong related-work baseline candidate.",
                why="A baseline named only generically is weaker than a paper-linked or implementation-backed comparison.",
                evidence=[candidate.baseline_name for candidate in protocol.baselines] or ["No protocol baselines."],
                fix="Use the related-work matrix to add closest-prior-work or benchmark-provider baselines.",
                blocks=True,
            )
        )
    if not protocol.expected_artifacts or not protocol.evaluation_script_outline:
        objections.append(
            _objection(
                experiment,
                reviewer_role="Reviewer 1: technical correctness",
                severity="major",
                category="reproducibility",
                objection="The protocol does not specify expected artifacts or evaluation script steps.",
                why="Without concrete outputs, replication and debugging cannot be audited.",
                evidence=[
                    f"expected_artifacts={len(protocol.expected_artifacts)}",
                    f"evaluation_script_outline={len(protocol.evaluation_script_outline)}",
                ],
                fix="List exact output files and the evaluation script sequence before running experiments.",
                blocks=True,
            )
        )
    checklist = protocol.reproducibility_checklist
    if not checklist.metric_definitions or not checklist.negative_controls or not checklist.error_analysis_plan:
        objections.append(
            _objection(
                experiment,
                reviewer_role="Reviewer 3: empirical rigor and baselines",
                severity="major",
                category="reproducibility",
                objection="The reproducibility checklist is incomplete.",
                why="A serious empirical paper needs metric definitions, negative controls, and error analysis before implementation.",
                evidence=[
                    f"metric_definitions={len(checklist.metric_definitions)}",
                    f"negative_controls={len(checklist.negative_controls)}",
                    f"error_analysis_plan={'present' if checklist.error_analysis_plan else 'missing'}",
                ],
                fix="Complete the reproducibility checklist and rerun reviewer simulation.",
                blocks=True,
            )
        )
    return objections


def _area_chair_positioning(experiment: ExperimentPlan, novelty: NoveltyAssessment | None) -> list[ReviewerObjection]:
    objections: list[ReviewerObjection] = []
    if not experiment.core_claim_being_tested or not experiment.hypothesis:
        objections.append(
            _objection(
                experiment,
                reviewer_role="Area Chair: positioning and clarity",
                severity="major",
                category="clarity",
                objection="The contribution is not stated as a clear testable claim.",
                why="Area chairs need to summarize the contribution and decide whether the review discussion is coherent.",
                evidence=["Missing core claim or hypothesis."],
                fix="Rewrite the experiment around one claim, one gap, and one decisive comparison.",
                blocks=True,
            )
        )
    if not experiment.reviewer_killer_result:
        objections.append(
            _objection(
                experiment,
                reviewer_role="Area Chair: positioning and clarity",
                severity="major",
                category="clarity",
                objection="The plan does not say what result would make the paper compelling.",
                why="A submission needs a clear win condition, not just an implementation checklist.",
                evidence=["Experiment field `reviewer_killer_result` is empty."],
                fix="Add a publishability threshold tied to the strongest baseline and the claimed gap.",
                blocks=True,
            )
        )
    if novelty is not None and novelty.verdict == "pursue" and experiment.confidence == "low":
        objections.append(
            _objection(
                experiment,
                reviewer_role="Area Chair: positioning and clarity",
                severity="minor",
                category="clarity",
                objection="The novelty gate says pursue, but the experiment confidence remains low.",
                why="This mismatch makes positioning fragile and should be explained in the paper framing.",
                evidence=[f"Novelty verdict: {novelty.verdict}", f"Experiment confidence: {experiment.confidence}"],
                fix="Explain whether low confidence comes from data, baselines, labels, or implementation risk.",
                blocks=False,
            )
        )
    if experiment.ethical_or_safety_considerations == [] and _looks_high_stakes(experiment):
        objections.append(
            _objection(
                experiment,
                reviewer_role="Area Chair: positioning and clarity",
                severity="major",
                category="ethics",
                objection="The experiment is high-stakes but lacks ethical or safety considerations.",
                why="False positives in detection tasks can harm people or organizations.",
                evidence=["No ethical_or_safety_considerations recorded."],
                fix="Add false-positive harm analysis, privacy controls, and limits on releasing evasion details.",
                blocks=True,
            )
        )
    return objections


def _objection(
    experiment: ExperimentPlan,
    *,
    reviewer_role: str,
    severity: str,
    category: str,
    objection: str,
    why: str,
    evidence: list[str],
    fix: str,
    blocks: bool,
    confidence: str = "medium",
) -> ReviewerObjection:
    object_id = f"objection-{experiment.id}-{category}-{len(objection)}"
    return ReviewerObjection(
        id=object_id,
        experiment_id=experiment.id,
        target_id=experiment.id,
        severity=severity,
        category=category,
        objection=objection,
        why_reviewer_would_care=why,
        evidence_or_prior_work=evidence,
        suggested_fix=fix,
        mitigation=fix,
        blocks_submission=blocks,
        confidence=confidence,
        reviewer_role=reviewer_role,
        provenance=Provenance(
            created_by_skill="reviewer-simulation",
            source_ids=[experiment.id],
            timestamp=utc_now_iso(),
            reasoning_summary=f"{reviewer_role} generated a {severity} {category} objection from public experiment fields.",
        ),
    )


def _summary_for(experiment: ExperimentPlan, objections: list[ReviewerObjection]) -> ReviewerSimulationSummary:
    penalties = {"fatal": 35, "major": 18, "minor": 6}
    score = 100 - sum(penalties.get(item.severity, 10) for item in objections)
    score = max(0, min(100, score))
    blocking = [item.objection for item in objections if item.blocks_submission]
    required = [item.suggested_fix for item in objections if item.blocks_submission]
    optional = [item.suggested_fix for item in objections if not item.blocks_submission]
    if any(item.severity == "fatal" for item in objections) or score < 45:
        recommendation = "not_ready"
    elif score < 65:
        recommendation = "workshop_ready"
    elif score < 85:
        recommendation = "conference_potential"
    else:
        recommendation = "strong_submission_candidate"
    return ReviewerSimulationSummary(
        experiment_id=experiment.id,
        submission_readiness_score=score,
        blocking_issues=blocking,
        required_fixes=_dedupe(required),
        optional_fixes=_dedupe(optional),
        final_recommendation=recommendation,
        provenance=Provenance(
            created_by_skill="reviewer-simulation",
            source_ids=[experiment.id],
            timestamp=utc_now_iso(),
            reasoning_summary="Aggregated deterministic reviewer objections into a submission readiness score and recommendation.",
        ),
    )


def _novelty_for_experiment(experiment: ExperimentPlan, novelty_by_target: dict[str, NoveltyAssessment]) -> NoveltyAssessment | None:
    candidates = []
    if experiment.novelty_assessment_id:
        candidates.append(experiment.novelty_assessment_id)
    candidates.extend(experiment.linked_gap_ids)
    if experiment.hypothesis_id:
        candidates.append(experiment.hypothesis_id)
    for candidate in candidates:
        if candidate in novelty_by_target:
            return novelty_by_target[candidate]
    return None


def _mentions_experiment(claim: Claim, experiment: ExperimentPlan) -> bool:
    haystack = f"{experiment.title} {experiment.hypothesis} {experiment.core_claim_being_tested}".lower()
    tokens = [token for token in claim.text.lower().split() if len(token) > 5]
    return any(token in haystack for token in tokens[:6])


def _abstract_only_notes(notes: list[PaperNote]) -> bool:
    return any(note.source_basis == "metadata/abstract only" for note in notes)


def _looks_high_stakes(experiment: ExperimentPlan) -> bool:
    text = " ".join(
        [
            experiment.title,
            experiment.hypothesis,
            " ".join(experiment.metrics),
            " ".join(experiment.risks),
        ]
    ).lower()
    return any(term in text for term in ["false-positive", "false positive", "detection", "fraud", "collusion"])


def _replace_objections(
    existing: list[ReviewerObjection], new_items: list[ReviewerObjection], *, experiment_id: str | None
) -> list[ReviewerObjection]:
    return new_items


def _replace_summaries(
    existing: list[ReviewerSimulationSummary], new_items: list[ReviewerSimulationSummary], *, experiment_id: str | None
) -> list[ReviewerSimulationSummary]:
    return new_items


def _dedupe(values: list[str]) -> list[str]:
    output: list[str] = []
    seen: set[str] = set()
    for value in values:
        clean = " ".join(str(value).split())
        if clean and clean.lower() not in seen:
            output.append(clean)
            seen.add(clean.lower())
    return output
