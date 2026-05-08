"""Idea mutation engine for v2 discovery."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from gapforge.config import GapForgeConfig
from gapforge.ideas.models import IDEA_MUTATION_STRATEGIES, IdeaCandidate, IdeaMutationRecord, validate_mutation_strategy
from gapforge.ideas.store import IdeaStore
from gapforge.models import Provenance
from gapforge.project_memory import ProjectMemoryManager
from gapforge.state import utc_now_iso

FATAL_PRIOR_WORK_MARKERS = {
    "fatal prior work",
    "prior work already",
    "already done",
    "duplicate",
    "overlap",
    "closest prior work",
    "not novel",
}


@dataclass(slots=True)
class IdeaMutationResult:
    record: IdeaMutationRecord
    candidate: IdeaCandidate


class IdeaMutationEngine:
    """Reframe weak or rejected ideas without erasing their risks."""

    def __init__(self, config: GapForgeConfig) -> None:
        self.config = config
        self.store = IdeaStore(config)
        self.project_manager = ProjectMemoryManager(config)

    def mutate_idea(self, idea_id: str, *, strategy: str = "") -> IdeaMutationResult:
        _, source = self.store.load_by_idea_id(idea_id)
        chosen_strategy = validate_mutation_strategy(strategy or _choose_strategy(source))
        spec = _mutation_spec(source, chosen_strategy)
        now = utc_now_iso()
        mutated = self.store.add_candidate(
            project_id=source.project_id,
            source_topic_id=source.source_topic_id,
            title=spec.title,
            summary=spec.summary,
            contribution_type=spec.contribution_type,
            core_claim=spec.core_claim,
            proposed_experiment=spec.proposed_experiment,
            expected_baselines=spec.expected_baselines,
            expected_metrics=spec.expected_metrics,
            closest_prior_work_ids=source.closest_prior_work_ids,
            evidence_span_ids=source.evidence_span_ids,
            supporting_paper_ids=source.supporting_paper_ids,
            counterevidence_paper_ids=source.counterevidence_paper_ids,
            novelty_status="unknown" if source.novelty_status == "likely_duplicate" else "unchecked",
            tractability_score=min(max(source.tractability_score + spec.tractability_delta, 0.0), 1.0),
            impact_score=source.impact_score,
            evidence_score=source.evidence_score,
            reviewer_risk_score=max(source.reviewer_risk_score, 0.7 if _has_fatal_prior_work(source) else source.reviewer_risk_score),
            idea_yield_score=min(max(source.idea_yield_score + 0.08, 0.0), 1.0),
            maturity="seed",
            likely_failure_mode=_mutated_failure_mode(source, spec.inherited_risks),
            provenance=Provenance(
                created_by_skill=f"idea-mutation:{chosen_strategy}",
                source_ids=[source.id, *source.provenance.source_ids],
                timestamp=now,
                reasoning_summary=(
                    "Created a mutated seed idea. This is a reframing candidate only; novelty, evidence, and reviewer risks remain open."
                ),
            ),
        )
        record = self.store.add_mutation_record(
            source_idea_id=source.id,
            mutated_idea_id=mutated.id,
            strategy=chosen_strategy,
            what_changed=spec.what_changed,
            why_it_may_help=spec.why_it_may_help,
            inherited_risks=spec.inherited_risks,
            required_new_searches=spec.required_new_searches,
            provenance=Provenance(
                created_by_skill="idea-mutation",
                source_ids=[source.id, mutated.id],
                timestamp=now,
                reasoning_summary=(
                    "Mutation record preserves what changed, why it may help, inherited risks, "
                    "and searches required before any novelty claim."
                ),
            ),
        )
        self.write_report(source.project_id)
        return IdeaMutationResult(record=record, candidate=mutated)

    def mutate_rejected_ideas(self, project_id: str, *, strategy: str = "") -> list[IdeaMutationResult]:
        state = self.store.load_state(project_id)
        rejected = [candidate for candidate in state.candidates if candidate.maturity == "rejected"]
        return [self.mutate_idea(candidate.id, strategy=strategy) for candidate in rejected]

    def render_report(self, project_id: str) -> str:
        return render_mutation_report(self.store.load_state(project_id).mutations)

    def write_report(self, project_id: str) -> str:
        report = self.render_report(project_id)
        reports_dir = Path(self.project_manager.load_project(project_id).project.root_dir) / "ideas" / "reports"
        reports_dir.mkdir(parents=True, exist_ok=True)
        (reports_dir / "mutations.md").write_text(report, encoding="utf-8")
        return report


@dataclass(slots=True)
class _MutationSpec:
    title: str
    summary: str
    contribution_type: str
    core_claim: str
    proposed_experiment: str
    expected_baselines: list[str]
    expected_metrics: list[str]
    what_changed: str
    why_it_may_help: str
    inherited_risks: list[str]
    required_new_searches: list[str]
    tractability_delta: float = 0.0


def render_mutation_report(records: list[IdeaMutationRecord]) -> str:
    lines = [
        "# Idea Mutation Report",
        "",
        "Mutations are auditable reframings. They do not erase prior-work problems or claim novelty.",
        "",
        f"- Mutation records: {len(records)}",
        "",
        "## Records",
        "",
    ]
    if not records:
        lines.append("- none")
        return "\n".join(lines).rstrip() + "\n"
    for record in records:
        lines.extend(
            [
                f"### `{record.id}`",
                "",
                f"- Source idea: `{record.source_idea_id}`",
                f"- Mutated idea: `{record.mutated_idea_id}`",
                f"- Strategy: `{record.strategy}`",
                f"- What changed: {record.what_changed}",
                f"- Why it may help: {record.why_it_may_help}",
                f"- Inherited risks: {'; '.join(record.inherited_risks) or 'none'}",
                f"- Required new searches: {'; '.join(record.required_new_searches) or 'none'}",
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def _choose_strategy(source: IdeaCandidate) -> str:
    if _has_fatal_prior_work(source):
        return "metric_shift"
    if source.maturity == "rejected" and source.rejection_reason:
        return "reviewer_objection_to_new_idea"
    if source.contribution_type == "method":
        return "method_to_measurement"
    if _looks_broad(source.title) or _looks_broad(source.summary):
        return "broad_to_minimum_publishable_unit"
    return "metric_shift"


def _mutation_spec(source: IdeaCandidate, strategy: str) -> _MutationSpec:
    strategy = validate_mutation_strategy(strategy)
    inherited_risks = _inherited_risks(source)
    decisive_change = _decisive_change_sentence(source, strategy)
    title_prefix = strategy.replace("_", " ").title()
    base_title = _short_title(source.title)
    summary = (
        f"Mutation of `{source.id}` using `{strategy}`. It reframes the source idea while preserving inherited risk: "
        f"{'; '.join(inherited_risks)}"
    )
    what_changed, why_it_may_help, contribution_type, metrics, baselines, experiment, delta = _strategy_payload(source, strategy)
    if decisive_change:
        what_changed = f"{what_changed} {decisive_change}"
    return _MutationSpec(
        title=f"{title_prefix} mutation of {base_title}",
        summary=summary,
        contribution_type=contribution_type,
        core_claim=(
            "A reframed seed may expose a more defensible contribution, "
            "but this claim remains unchecked until novelty and evidence gates run."
        ),
        proposed_experiment=experiment,
        expected_baselines=baselines,
        expected_metrics=metrics,
        what_changed=what_changed,
        why_it_may_help=why_it_may_help,
        inherited_risks=inherited_risks,
        required_new_searches=_required_searches(source, strategy),
        tractability_delta=delta,
    )


def _strategy_payload(source: IdeaCandidate, strategy: str) -> tuple[str, str, str, list[str], list[str], str, float]:
    payloads = {
        "metric_shift": (
            "Changed the success criterion to stricter, auditable metrics.",
            "Metric changes can turn a vague idea into a falsifiable evaluation target.",
            source.contribution_type,
            ["false positive rate", "confidence interval", "slice-level error"],
            source.expected_baselines or ["closest prior-work baseline"],
            "Re-run the idea around thresholded metrics and report failure slices before any positive claim.",
            0.05,
        ),
        "observable_shift": (
            "Changed the measured observable rather than the high-level phenomenon.",
            "A better observable can make the idea testable without relying on hidden intent.",
            "measurement",
            ["observable precision", "false positive rate", "annotation agreement"],
            source.expected_baselines or ["simple observable heuristic"],
            "Define observable traces, label criteria, and counterexamples.",
            0.08,
        ),
        "threat_model_shift": (
            "Changed the threat model and attacker assumptions.",
            "A sharper threat model may separate the idea from prior work that assumed a different adversary.",
            source.contribution_type,
            ["attack coverage", "false positive rate", "assumption violation count"],
            source.expected_baselines or ["prior threat-model baseline"],
            "State the new threat model, then test baselines under those assumptions.",
            0.02,
        ),
        "benchmark_shift": (
            "Changed the contribution toward benchmark construction.",
            "A benchmark can be publishable when the method idea is too crowded or under-specified.",
            "benchmark",
            ["benchmark coverage", "false positive rate", "baseline spread"],
            source.expected_baselines or ["published baseline", "simple heuristic"],
            "Build a minimal benchmark card with benign negatives, positives, baselines, and refusal conditions.",
            0.04,
        ),
        "dataset_shift": (
            "Changed the contribution toward dataset construction.",
            "A dataset seed can clarify data availability and labeling limits before method claims.",
            "dataset",
            ["label agreement", "coverage", "known limitation count"],
            source.expected_baselines or ["existing dataset"],
            "Define a dataset scope, collection protocol, label schema, and nearest existing datasets.",
            0.03,
        ),
        "baseline_shift": (
            "Changed the idea around stronger or more diagnostic baselines.",
            "Baseline pressure can reveal whether the contribution survives obvious comparisons.",
            "evaluation_protocol",
            ["baseline win rate", "effect size", "false positive rate"],
            ["strong closest prior work", *source.expected_baselines],
            "Design a baseline-first evaluation protocol and stop if the seed cannot beat or explain the baselines.",
            0.06,
        ),
        "guarantee_shift": (
            "Changed the idea toward explicit assumptions and guarantees.",
            "Guarantees may create a defensible theory contribution when empirical novelty is crowded.",
            "theory",
            ["assumption coverage", "counterexample count"],
            source.expected_baselines or ["closest theoretical prior"],
            "Formalize assumptions and search for guarantees, limits, or counterexamples.",
            -0.05,
        ),
        "domain_transfer": (
            "Changed the source domain used to frame the contribution.",
            "A transfer may expose neglected assumptions, but only if the analogy survives stress testing.",
            "hybrid",
            ["transfer validity", "assumption violation count", "false positive rate"],
            source.expected_baselines or ["target-domain baseline", "source-domain analogue"],
            "Map assumptions from the source domain to the target setting and test where the analogy breaks.",
            -0.02,
        ),
        "contribution_type_shift": (
            "Changed the claimed contribution type.",
            "Switching contribution type can avoid forcing a weak method claim through evidence gates.",
            _alternate_contribution(source.contribution_type),
            ["contribution fit", "prior-work overlap", "evidence sufficiency"],
            source.expected_baselines or ["closest prior work"],
            "Recast the seed under the alternate contribution type and repeat closest-prior-work review.",
            0.04,
        ),
        "positive_to_negative_result": (
            "Changed a positive result framing into a negative-result opportunity.",
            "A careful negative result may be more honest if existing methods fail under stricter conditions.",
            "negative_result",
            ["replication fidelity", "failure slice count", "false positive rate"],
            source.expected_baselines or ["published method", "simple baseline"],
            "Replicate closest prior methods and preserve null or negative outcomes when the protocol is strong.",
            0.02,
        ),
        "method_to_measurement": (
            "Changed a method claim into a measurement study.",
            "Measurement can be defensible when the method itself is not novel enough.",
            "measurement",
            ["error rate", "slice coverage", "uncertainty interval"],
            source.expected_baselines or ["existing method"],
            "Measure the phenomenon across slices without claiming a new method.",
            0.08,
        ),
        "method_to_benchmark": (
            "Changed a method claim into a benchmark contribution.",
            "Benchmark framing can preserve value when method novelty is weak.",
            "benchmark",
            ["benchmark coverage", "baseline spread", "false positive rate"],
            source.expected_baselines or ["existing method"],
            "Create a minimum benchmark around the method's failure mode and evaluate known baselines.",
            0.06,
        ),
        "empirical_to_theory": (
            "Changed an empirical framing into a theory or guarantee framing.",
            "Theory may expose limits or necessary assumptions when experiments are saturated.",
            "theory",
            ["assumption coverage", "counterexample count"],
            source.expected_baselines or ["closest theoretical prior"],
            "State assumptions, derive limits or guarantees, and search for counterexamples.",
            -0.05,
        ),
        "broad_to_minimum_publishable_unit": (
            "Changed a broad idea into the smallest falsifiable unit.",
            "A minimum unit can avoid generic claims and make refusal conditions explicit.",
            "evaluation_protocol",
            ["scope tightness", "false positive rate", "decision clarity"],
            source.expected_baselines or ["simple baseline"],
            "Define one narrow dataset slice, one metric, one baseline, and a clear stop condition.",
            0.1,
        ),
        "reviewer_objection_to_new_idea": (
            "Changed the reviewer objection into the central research object.",
            "A serious objection can become a stronger idea when studied directly instead of patched around.",
            "measurement",
            ["objection closure", "prior-work overlap", "false positive rate"],
            source.expected_baselines or ["closest objected prior work"],
            "Treat the rejection reason as the phenomenon to measure or benchmark.",
            0.04,
        ),
    }
    return payloads[strategy]


def _inherited_risks(source: IdeaCandidate) -> list[str]:
    risks = [
        f"source novelty status was `{source.novelty_status}`",
        f"source maturity was `{source.maturity}`",
    ]
    if source.rejection_reason:
        risks.append(f"source rejection reason: {source.rejection_reason}")
    if source.likely_failure_mode:
        risks.append(f"source likely failure mode: {source.likely_failure_mode}")
    if source.closest_prior_work_ids:
        risks.append(f"closest prior work remains: {', '.join(source.closest_prior_work_ids)}")
    if source.counterevidence_paper_ids:
        risks.append(f"counterevidence remains: {', '.join(source.counterevidence_paper_ids)}")
    if source.evidence_span_ids:
        risks.append(f"evidence spans inherited: {', '.join(source.evidence_span_ids)}")
    return risks


def _required_searches(source: IdeaCandidate, strategy: str) -> list[str]:
    searches = [
        f"closest prior work for `{strategy}` mutation of `{source.title}`",
        f"counterevidence against mutated framing of `{source.title}`",
    ]
    if source.closest_prior_work_ids:
        searches.append(f"compare mutated idea against inherited prior work: {', '.join(source.closest_prior_work_ids)}")
    if _has_fatal_prior_work(source):
        searches.append(f"verify decisive overlap dimension changed for fatal prior work under `{strategy}`")
    searches.append(_strategy_search(strategy))
    return searches


def _strategy_search(strategy: str) -> str:
    return {
        "metric_shift": "search for papers using the new metric or threshold",
        "observable_shift": "search for papers measuring the new observable",
        "threat_model_shift": "search for prior work under the new threat model",
        "benchmark_shift": "search for existing benchmarks and datasets covering the same slice",
        "dataset_shift": "search for existing datasets with equivalent labels or collection protocol",
        "baseline_shift": "search for stronger baselines and ablations",
        "guarantee_shift": "search for formal guarantees, impossibility results, and assumptions",
        "domain_transfer": "search source-domain and target-domain transfer precedents",
        "contribution_type_shift": "search nearest papers with the shifted contribution type",
        "positive_to_negative_result": "search failed replications and negative results",
        "method_to_measurement": "search measurement studies on the same phenomenon",
        "method_to_benchmark": "search benchmark papers around the same method failure mode",
        "empirical_to_theory": "search theory papers around the empirical assumption",
        "broad_to_minimum_publishable_unit": "search narrow scoped variants of the broad claim",
        "reviewer_objection_to_new_idea": "search papers where the reviewer objection is the main contribution",
    }[strategy]


def _has_fatal_prior_work(source: IdeaCandidate) -> bool:
    text = " ".join([source.rejection_reason, source.likely_failure_mode, source.summary, source.novelty_status]).lower()
    return any(marker in text for marker in FATAL_PRIOR_WORK_MARKERS)


def _decisive_change_sentence(source: IdeaCandidate, strategy: str) -> str:
    if not _has_fatal_prior_work(source):
        return ""
    dimension = {
        "metric_shift": "metric and acceptance threshold",
        "observable_shift": "observable trace feature",
        "threat_model_shift": "threat model",
        "benchmark_shift": "benchmark construction target",
        "dataset_shift": "dataset and label scope",
        "baseline_shift": "baseline comparison axis",
        "guarantee_shift": "formal assumption set",
        "domain_transfer": "source domain and transferred assumption",
        "contribution_type_shift": "contribution type",
        "positive_to_negative_result": "result polarity",
        "method_to_measurement": "measurement target",
        "method_to_benchmark": "benchmark artifact",
        "empirical_to_theory": "theoretical assumption",
        "broad_to_minimum_publishable_unit": "scope boundary",
        "reviewer_objection_to_new_idea": "reviewer objection as target",
    }[strategy]
    return f"Decisive overlapping dimension changed: {dimension}."


def _mutated_failure_mode(source: IdeaCandidate, inherited_risks: list[str]) -> str:
    inherited = "; ".join(inherited_risks)
    if _has_fatal_prior_work(source):
        return f"Fatal prior-work risk remains unless the changed overlap dimension survives new search. Inherited risks: {inherited}"
    return f"Mutation may still inherit source weaknesses. Inherited risks: {inherited}"


def _alternate_contribution(contribution_type: str) -> str:
    if contribution_type == "method":
        return "measurement"
    if contribution_type == "measurement":
        return "benchmark"
    if contribution_type == "benchmark":
        return "evaluation_protocol"
    if contribution_type == "theory":
        return "measurement"
    return "evaluation_protocol"


def _looks_broad(text: str) -> bool:
    lowered = text.lower()
    return any(marker in lowered for marker in ["generic", "broad", "general", "overall", "agent safety"])


def _short_title(text: str) -> str:
    words = [word.strip("`.,:;()[]{}") for word in text.split() if word.strip("`.,:;()[]{}")]
    return " ".join(words[:8]) or "untitled idea"


def available_mutation_strategies() -> list[str]:
    return sorted(IDEA_MUTATION_STRATEGIES)
