"""Turn novelty-checked gaps into experiment-ready plans."""

from __future__ import annotations

from collections import Counter

from gapforge.models import (
    ExperimentPlan,
    Gap,
    Hypothesis,
    NoveltyAssessment,
    PaperNote,
    Provenance,
    RelatedWorkMatrix,
    ResearchRunState,
    TableRecord,
)
from gapforge.review.audit import approved_object_ids, is_rejected, locked_object_ids
from gapforge.skills.base import Skill
from gapforge.state import utc_now_iso


class ExperimentDesigner(Skill):
    name = "experiment-designer"

    def run(self, state: ResearchRunState) -> ResearchRunState:
        return self.design(state)

    def design(
        self,
        state: ResearchRunState,
        *,
        gap_id: str | None = None,
        allow_rejected: bool = False,
        force: bool = False,
    ) -> ResearchRunState:
        gaps = [gap for gap in state.gaps if gap_id is None or gap.id == gap_id]
        novelty_by_target = {assessment.target_gap_or_hypothesis_id: assessment for assessment in state.novelty_assessments}
        hypotheses_by_gap: dict[str, list[Hypothesis]] = {}
        for hypothesis in state.hypotheses:
            hypotheses_by_gap.setdefault(hypothesis.gap_id, []).append(hypothesis)

        experiments: list[ExperimentPlan] = []
        for gap in _prioritize_gaps(gaps, approved_object_ids(state, "gap")):
            if is_rejected(state, "gap", gap.id) and not allow_rejected:
                continue
            assessment = novelty_by_target.get(gap.id)
            if assessment is None:
                assessment = _hypothesis_assessment(novelty_by_target, hypotheses_by_gap.get(gap.id, []))
            if assessment is not None and assessment.verdict == "reject" and not allow_rejected:
                continue
            if assessment is None and gap.novelty_status == "likely_not_new" and not allow_rejected:
                continue
            experiments.append(
                self._experiment_for_gap(
                    state,
                    gap,
                    assessment,
                    hypotheses_by_gap.get(gap.id, []),
                    index=len(experiments) + 1,
                )
            )

        state.experiments = _replace_experiments(
            state.experiments,
            experiments,
            gap_id=gap_id,
            locked_ids=locked_object_ids(state, "experiment") if not force else set(),
        )
        self.mark_complete(state)
        return state

    def _experiment_for_gap(
        self,
        state: ResearchRunState,
        gap: Gap,
        assessment: NoveltyAssessment | None,
        hypotheses: list[Hypothesis],
        *,
        index: int,
    ) -> ExperimentPlan:
        hypothesis = hypotheses[0] if hypotheses else None
        metrics = _metrics_for_gap(gap, state.paper_notes, state.tables)
        baselines = _baselines_for_gap(gap, assessment, state.related_work_matrices)
        datasets = _datasets_for_gap(gap, state.paper_notes)
        title = _experiment_title(gap)
        inline_hypothesis = hypothesis.text if hypothesis is not None else _hypothesis_from_gap(gap)
        minimum_experiment = gap.minimum_experiment_needed or _minimum_experiment(gap)
        failure_modes = _failure_modes(gap, assessment)
        confidence = _experiment_confidence(gap, assessment)
        novelty_id = assessment.target_gap_or_hypothesis_id if assessment is not None else ""

        return ExperimentPlan(
            id=f"experiment-{index}",
            title=title,
            hypothesis_id=hypothesis.id if hypothesis is not None else "",
            linked_gap_ids=[gap.id],
            hypothesis=inline_hypothesis,
            core_claim_being_tested=_core_claim(gap, inline_hypothesis),
            minimum_viable_experiment=minimum_experiment,
            design=minimum_experiment,
            datasets_needed=datasets,
            datasets=datasets,
            baselines=baselines,
            metrics=metrics,
            statistical_tests=_statistical_tests(metrics),
            ablations=_ablations_for_gap(gap),
            failure_modes=failure_modes,
            expected_failure_modes=failure_modes,
            compute_requirements=_compute_requirements(gap),
            implementation_steps=_implementation_steps(gap, metrics, baselines),
            expected_result_patterns=_expected_patterns(metrics, assessment),
            what_result_would_falsify_the_idea=_falsifier(gap, metrics),
            reviewer_killer_result=_reviewer_killer_result(gap, assessment, metrics),
            risks=_risks(gap, assessment),
            ethical_or_safety_considerations=_safety_considerations(state, gap),
            novelty_assessment_id=novelty_id,
            confidence=confidence,
            paper_ready=False,
            provenance=Provenance(
                created_by_skill=self.name,
                source_ids=[gap.id, novelty_id] + [hypothesis.id for hypothesis in hypotheses[:1]],
                timestamp=utc_now_iso(),
                reasoning_summary=(
                    "Converted a non-rejected novelty-checked gap into a falsifiable experiment plan "
                    "with baselines, metrics, ablations, and explicit failure conditions."
                ),
            ),
        )


def _prioritize_gaps(gaps: list[Gap], approved_gap_ids: set[str] | None = None) -> list[Gap]:
    approved = approved_gap_ids or set()
    confidence_rank = {"high": 0, "medium": 1, "low": 2}
    novelty_rank = {"strong": 0, "medium": 1, "weak": 2, "unchecked": 3, "likely_not_new": 4}
    return sorted(
        gaps,
        key=lambda gap: (
            0 if gap.id in approved else 1,
            novelty_rank.get(gap.novelty_status, 3),
            confidence_rank.get(gap.confidence, 2),
            gap.id,
        ),
    )


def _hypothesis_assessment(novelty_by_target: dict[str, NoveltyAssessment], hypotheses: list[Hypothesis]) -> NoveltyAssessment | None:
    for hypothesis in hypotheses:
        if hypothesis.id in novelty_by_target:
            return novelty_by_target[hypothesis.id]
    return None


def _experiment_title(gap: Gap) -> str:
    title = gap.title or gap.description or gap.id
    if "benchmark" in gap.type:
        return f"Benchmark audit: {title}"
    if "measurement" in gap.type or "evaluation" in gap.type:
        return f"Measurement study: {title}"
    if "assumption" in gap.type:
        return f"Assumption stress test: {title}"
    return f"Experiment: {title}"


def _hypothesis_from_gap(gap: Gap) -> str:
    return (
        f"If {gap.title or gap.description}, then a focused experiment should expose measurable failure modes "
        "that current work does not resolve."
    )


def _core_claim(gap: Gap, hypothesis: str) -> str:
    if gap.why_existing_work_does_not_solve_it:
        return f"Existing work does not solve this gap because: {gap.why_existing_work_does_not_solve_it}"
    return hypothesis


def _minimum_experiment(gap: Gap) -> str:
    if "false-positive" in gap.description.lower() or "false positive" in gap.description.lower():
        return "Compare candidate methods at fixed false-positive budgets and audit the missed-positive tradeoff."
    if "dataset" in gap.type or "benchmark" in gap.type:
        return "Build a small benchmark slice, run representative baselines, and report failure cases by condition."
    if "assumption" in gap.type:
        return "Run an ablation that violates the shared assumption and compare degradation against normal conditions."
    return "Run the smallest controlled comparison that can distinguish the proposed gap from closest prior work."


def _metrics_for_gap(gap: Gap, notes: list[PaperNote], tables: list[TableRecord] | None = None) -> list[str]:
    text = _gap_text(gap)
    metrics = []
    if "false-positive" in text or "false positive" in text:
        metrics.extend(["false-positive-rate", "recall-at-fixed-fpr", "precision-at-alert-budget"])
    if "calibration" in text:
        metrics.extend(["expected-calibration-error", "brier-score"])
    if "dataset" in text or "benchmark" in text:
        metrics.extend(["coverage-by-scenario", "label-quality-audit-rate"])
    if "scalability" in text or "scale" in text:
        metrics.extend(["runtime", "peak-memory", "throughput"])
    if "reproduc" in text:
        metrics.extend(["seed-variance", "replication-success-rate"])
    observed = [metric for note in notes for metric in note.metrics]
    if observed:
        metrics.extend([item for item, _ in Counter(observed).most_common(3)])
    table_text = " ".join((table.caption + " " + table.text).lower() for table in tables or [])
    for marker, metric in [
        ("f1", "f1"),
        ("auc", "auc"),
        ("precision", "precision"),
        ("recall", "recall"),
        ("false positive", "false-positive-rate"),
        ("specificity", "specificity"),
    ]:
        if marker in table_text:
            metrics.append(metric)
    metrics.extend(["effect-size", "confidence-interval"])
    return _dedupe(metrics)


def _baselines_for_gap(
    gap: Gap, assessment: NoveltyAssessment | None, related_work_matrices: list[RelatedWorkMatrix] | None = None
) -> list[str]:
    text = _gap_text(gap)
    baselines = ["closest-prior-work implementation or reported numbers", "simple supervised baseline"]
    if "collusion" in text:
        baselines.extend(["graph anomaly detector", "rule-based collusion heuristic"])
    if "false-positive" in text or "false positive" in text:
        baselines.extend(["threshold-tuned detector at matched false-positive rate", "abstention-free detector"])
    if "benchmark" in text or "dataset" in text:
        baselines.append("existing public benchmark split")
    if assessment is not None and assessment.closest_prior_work:
        baselines.append(f"nearest prior: {assessment.closest_prior_work[0]}")
    for matrix in related_work_matrices or []:
        if matrix.direction_id == gap.id:
            baselines.extend([f"related-work baseline paper: {paper_id}" for paper_id in matrix.baseline_paper_ids])
    return _dedupe(baselines)


def _datasets_for_gap(gap: Gap, notes: list[PaperNote]) -> list[str]:
    datasets = [dataset for note in notes for dataset in note.datasets]
    text = _gap_text(gap)
    if "synthetic" in text or not datasets:
        datasets.append("small synthetic stress-test dataset with documented generation parameters")
    if "real" in text or "deployment" in text or "collusion" in text:
        datasets.append("public interaction-log or transaction-style dataset with auditable labels")
    if "benchmark" in text:
        datasets.append("benchmark manifest with scenario, label, and split metadata")
    return _dedupe(datasets)


def _statistical_tests(metrics: list[str]) -> list[str]:
    tests = ["bootstrap confidence intervals for primary metrics", "paired permutation test against strongest baseline"]
    if any("false-positive" in metric or "recall" in metric or "precision" in metric for metric in metrics):
        tests.append("McNemar test or paired proportion test for alert-level disagreements")
    if any("runtime" in metric or "memory" in metric for metric in metrics):
        tests.append("median runtime comparison across repeated runs")
    return tests


def _ablations_for_gap(gap: Gap) -> list[str]:
    text = _gap_text(gap)
    ablations = ["remove the proposed mechanism and rerun the primary metric", "vary dataset size and random seed"]
    if "false-positive" in text or "false positive" in text:
        ablations.extend(["sweep alert thresholds", "remove abstention or calibration component"])
    if "assumption" in text:
        ablations.append("violate the target assumption under controlled severity levels")
    if "benchmark" in text or "dataset" in text:
        ablations.append("remove each benchmark scenario family")
    return _dedupe(ablations)


def _failure_modes(gap: Gap, assessment: NoveltyAssessment | None) -> list[str]:
    failures = ["no improvement over strongest baseline", "effect disappears under alternative random seeds"]
    if gap.risk_that_gap_is_fake:
        failures.append(gap.risk_that_gap_is_fake)
    if assessment is not None and assessment.possible_reviewer_objection:
        failures.append(assessment.possible_reviewer_objection)
    return _dedupe(failures)


def _compute_requirements(gap: Gap) -> str:
    text = _gap_text(gap)
    if "large" in text or "scalability" in text or "scale" in text:
        return "Moderate compute: repeated CPU/GPU runs on progressively larger graph or table slices."
    return "Small to moderate compute: reproducible CPU experiments should be sufficient for the minimum viable study."


def _implementation_steps(gap: Gap, metrics: list[str], baselines: list[str]) -> list[str]:
    return [
        "Freeze the exact gap statement, closest-prior-work baseline, and exclusion criteria.",
        "Create a dataset manifest with splits, labels, leakage checks, and known limitations.",
        f"Implement baselines: {', '.join(baselines[:3])}.",
        "Implement the proposed variant with configuration logged for every run.",
        f"Compute primary metrics: {', '.join(metrics[:4])}.",
        "Run ablations and seed sensitivity checks.",
        "Write a failure-case table linking each result back to the original gap.",
    ]


def _expected_patterns(metrics: list[str], assessment: NoveltyAssessment | None) -> list[str]:
    patterns = [
        f"Improvement on {metrics[0]} without degrading {metrics[1] if len(metrics) > 1 else 'secondary metrics'}.",
        "The strongest baseline fails in the exact condition named by the gap.",
    ]
    if assessment is not None and assessment.verdict == "unknown":
        patterns.append("Results remain preliminary until missing novelty searches are completed.")
    return patterns


def _falsifier(gap: Gap, metrics: list[str]) -> str:
    primary = metrics[0] if metrics else "the primary metric"
    return (
        f"The idea is falsified if the closest-prior-work baseline matches or beats the proposed method on {primary}, "
        "or if the claimed gap disappears after full-text or benchmark audit."
    )


def _reviewer_killer_result(gap: Gap, assessment: NoveltyAssessment | None, metrics: list[str]) -> str:
    baseline = "closest prior work"
    if assessment is not None and assessment.closest_prior_work:
        baseline = assessment.closest_prior_work[0]
    primary = metrics[0] if metrics else "the primary metric"
    return (
        f"Publishable result: a statistically robust improvement over {baseline} on {primary}, plus a documented "
        "failure mode that existing work does not explain."
    )


def _risks(gap: Gap, assessment: NoveltyAssessment | None) -> list[str]:
    risks = ["dataset labels may be noisy", "baseline implementation may not match prior work exactly"]
    if gap.risk_that_gap_is_fake:
        risks.append(gap.risk_that_gap_is_fake)
    if assessment is not None:
        if assessment.missing_searches:
            risks.append("novelty remains provisional because some closest-prior-work searches are missing")
        if assessment.verdict == "revise":
            risks.append("idea needs sharper differentiation before paper framing")
        if assessment.verdict == "unknown":
            risks.append("experiment may be premature because novelty verdict is unknown")
    return _dedupe(risks)


def _safety_considerations(state: ResearchRunState, gap: Gap) -> list[str]:
    text = f"{state.topic.text} {_gap_text(gap)}".lower()
    considerations = ["avoid overstating unsupported claims; report uncertainty and failure cases"]
    if "collusion" in text or "fraud" in text or "detection" in text:
        considerations.append("avoid releasing operational evasion details or deanonymized interaction data")
        considerations.append("audit false positives because incorrect accusation can harm users or organizations")
    return considerations


def _experiment_confidence(gap: Gap, assessment: NoveltyAssessment | None) -> str:
    if assessment is None:
        return "low"
    if assessment.verdict == "pursue" and gap.confidence in {"medium", "high"}:
        return "medium"
    if assessment.verdict == "revise":
        return "low"
    if assessment.verdict == "unknown":
        return "low"
    return "low"


def _gap_text(gap: Gap) -> str:
    return " ".join(
        [
            gap.id,
            gap.title,
            gap.type,
            gap.description,
            gap.why_existing_work_does_not_solve_it,
            gap.minimum_experiment_needed,
            gap.why_it_matters,
        ]
    ).lower()


def _dedupe(values: list[str]) -> list[str]:
    output: list[str] = []
    seen: set[str] = set()
    for value in values:
        clean = " ".join(str(value).split())
        key = clean.lower()
        if clean and key not in seen:
            output.append(clean)
            seen.add(key)
    return output


def _replace_experiments(
    existing: list[ExperimentPlan],
    new_items: list[ExperimentPlan],
    *,
    gap_id: str | None,
    locked_ids: set[str],
) -> list[ExperimentPlan]:
    locked = [experiment for experiment in existing if experiment.id in locked_ids]
    if gap_id is None:
        return locked + [experiment for experiment in new_items if experiment.id not in locked_ids]
    return locked + [experiment for experiment in new_items if experiment.id not in locked_ids]
