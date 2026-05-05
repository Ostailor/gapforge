"""Generate skeptical cross-domain analogies."""

from __future__ import annotations

from dataclasses import dataclass

from gapforge.models import CrossDomainAnalogy as CrossDomainAnalogyModel
from gapforge.models import Hypothesis, Provenance, ResearchRunState
from gapforge.skills.base import Skill
from gapforge.state import utc_now_iso


@dataclass(frozen=True)
class AnalogyPattern:
    triggers: tuple[str, ...]
    source_field: str
    source_concept: str
    why_it_maps: str
    what_breaks: str
    transfer_candidate: str
    experiment_template: str
    confidence: str = "low"


PATTERNS = [
    AnalogyPattern(
        triggers=("low false positive", "false-positive", "false positive", "specificity", "measurement"),
        source_field="medicine",
        source_concept="screening tests with specificity and confirmatory diagnosis",
        why_it_maps=(
            "Both settings treat false positives as costly interventions that require calibrated thresholds and second-stage confirmation."
        ),
        what_breaks=(
            "Medical screening often has clearer outcome labels, regulated workflows, and prospective follow-up; "
            "collusion labels are noisier and adversarial."
        ),
        transfer_candidate="selective prediction plus confirmatory-review protocols",
        experiment_template="Evaluate a detector with abstention and confirmatory review at fixed false-positive budgets.",
        confidence="medium",
    ),
    AnalogyPattern(
        triggers=("low false positive", "anomaly", "false positive", "monitoring"),
        source_field="industrial monitoring",
        source_concept="alarm fatigue reduction in fault detection",
        why_it_maps="Both domains need rare-event detection while avoiding alert floods that destroy operator trust.",
        what_breaks=(
            "Industrial systems may have stable sensors and physics constraints; social or collusive systems can adapt strategically."
        ),
        transfer_candidate="alert triage thresholds with operator workload constraints",
        experiment_template="Measure recall at fixed analyst-alert volume and compare against unconstrained anomaly scoring.",
        confidence="medium",
    ),
    AnalogyPattern(
        triggers=("hidden communication", "covert", "signal", "communication"),
        source_field="steganography",
        source_concept="detecting hidden messages under cover traffic",
        why_it_maps="Hidden collusive coordination and steganography both separate overt behavior from covert signal channels.",
        what_breaks=(
            "Steganography often assumes explicit encoders and channel models; collusion may emerge from incentives without a fixed code."
        ),
        transfer_candidate="residual-channel tests for suspicious coordination signals",
        experiment_template="Inject controlled covert coordination patterns into benign interaction traces and test residual detectors.",
    ),
    AnalogyPattern(
        triggers=("hidden communication", "cryptography", "covert channel"),
        source_field="cryptography",
        source_concept="covert-channel capacity and indistinguishability",
        why_it_maps="Both fields reason about how much hidden information can pass without detection.",
        what_breaks=(
            "Cryptographic channels are formalized; empirical collusion channels may have ambiguous intent and incomplete observation."
        ),
        transfer_candidate="capacity-style upper bounds on detectable coordination",
        experiment_template="Estimate detectable coordination capacity under different observation and noise constraints.",
    ),
    AnalogyPattern(
        triggers=("multi-agent collusion", "cartel", "economics", "game theory", "collusion"),
        source_field="economics",
        source_concept="cartel detection and tacit collusion in repeated games",
        why_it_maps="Both settings study coordinated agents who benefit from hidden cooperation under monitoring pressure.",
        what_breaks=(
            "Economic cartel models often assume pricing/market observables; digital collusion may involve richer "
            "graph behavior and platform interventions."
        ),
        transfer_candidate="incentive-compatible tests for tacit coordination",
        experiment_template="Compare graph detector alerts against game-theoretic collusion indicators in simulated repeated interactions.",
        confidence="medium",
    ),
    AnalogyPattern(
        triggers=("research drift", "provenance", "forensics", "process"),
        source_field="software provenance",
        source_concept="traceability of changes across artifacts",
        why_it_maps="Both need to identify when a process diverges from its claimed lineage.",
        what_breaks="Software provenance can often observe commits and hashes; research drift may be conceptual and undocumented.",
        transfer_candidate="claim lineage graphs with drift checkpoints",
        experiment_template="Track claim transformations across paper versions and detect unsupported semantic drift.",
    ),
    AnalogyPattern(
        triggers=("optimization instability", "instability", "control", "feedback"),
        source_field="control theory",
        source_concept="stability margins under feedback",
        why_it_maps="Both consider systems where updates can amplify noise or destabilize behavior.",
        what_breaks=(
            "Control systems usually have measurable dynamics; research or detector optimization may have nonstationary incentives."
        ),
        transfer_candidate="stability-margin diagnostics for iterative detector updates",
        experiment_template="Perturb training distributions and measure whether detector updates converge or oscillate.",
    ),
    AnalogyPattern(
        triggers=("optimization instability", "statistical physics", "phase transition"),
        source_field="statistical physics",
        source_concept="phase transitions in high-dimensional systems",
        why_it_maps="Both can exhibit abrupt changes when density, noise, or coupling crosses a threshold.",
        what_breaks="Physics analogies can over-formalize social systems whose mechanisms are not thermodynamic.",
        transfer_candidate="threshold-sensitivity analysis over graph density and noise",
        experiment_template="Sweep graph density and label noise to find abrupt detector failure regimes.",
    ),
    AnalogyPattern(
        triggers=("distribution shift", "deployment", "domain adaptation", "robustness"),
        source_field="statistics",
        source_concept="domain adaptation under covariate shift",
        why_it_maps="Both settings require claims to survive changes between training/evaluation and deployment distributions.",
        what_breaks="Statistical shift assumptions may not hold under adversarial adaptation by colluding agents.",
        transfer_candidate="shift-aware validation splits and importance-weighted evaluation",
        experiment_template="Evaluate candidate detectors across deliberately shifted interaction distributions.",
        confidence="medium",
    ),
    AnalogyPattern(
        triggers=("distribution shift", "epidemiology", "deployment", "population"),
        source_field="epidemiology",
        source_concept="external validity across populations",
        why_it_maps="Both ask whether an observed pattern in one population transfers to another without changing the causal structure.",
        what_breaks=(
            "Epidemiology can rely on study design and population sampling; collusion data may be censored by platform detection itself."
        ),
        transfer_candidate="population-stratified external validity audits",
        experiment_template="Stratify evaluation by platform segment and test whether false-positive behavior changes.",
    ),
]


class CrossDomainAnalogy(Skill):
    name = "cross-domain-analogy"

    def run(self, state: ResearchRunState) -> ResearchRunState:
        analogies = self.generate(state)
        state.cross_domain_analogies = analogies
        state.hypotheses = self._hypotheses_from_analogies(analogies)
        self.mark_complete(state)
        return state

    def generate(self, state: ResearchRunState) -> list[CrossDomainAnalogyModel]:
        context = _context_text(state)
        target_gap_ids = [gap.id for gap in state.gaps] or ["gap-unknown"]
        analogies: list[CrossDomainAnalogyModel] = []
        for pattern in PATTERNS:
            if not _matches(pattern, context):
                continue
            target_gap_id = _best_gap_id(pattern, state) or target_gap_ids[0]
            analogies.append(_analogy_from_pattern(pattern, state.topic.text, target_gap_id))

        if not analogies and state.field_map is not None:
            for adjacent in state.field_map.adjacent_fields[:3]:
                analogies.append(
                    CrossDomainAnalogyModel(
                        source_field=adjacent,
                        source_concept=f"{adjacent} methods adjacent to {state.topic.text}",
                        target_gap_id=target_gap_ids[0],
                        why_it_maps="The field map lists this adjacent field, so it may share constraints worth checking.",
                        what_breaks_in_the_mapping="The field-map adjacency is weak evidence; the operational mechanism may not transfer.",
                        technical_transfer_candidate=f"search for {adjacent} evaluation or robustness methods",
                        papers_or_sources_to_search=[
                            f"{adjacent} {state.topic.text}",
                            f"{adjacent} evaluation false positives",
                        ],
                        possible_experiment=f"Run a prior-work check before testing any {adjacent} transfer.",
                        risk_of_fake_analogy="This may be a vocabulary overlap rather than a technical analogy.",
                        confidence="low",
                        provenance=_provenance([target_gap_ids[0]], "Generated from field-map adjacent fields."),
                    )
                )
        return _dedupe(analogies)

    def _hypotheses_from_analogies(self, analogies: list[CrossDomainAnalogyModel]) -> list[Hypothesis]:
        hypotheses = []
        for index, analogy in enumerate(analogies[:5], start=1):
            hypotheses.append(
                Hypothesis(
                    id=f"hypothesis-analogy-{index}",
                    gap_id=analogy.target_gap_id,
                    text=f"Test whether {analogy.technical_transfer_candidate} from {analogy.source_field} helps this gap.",
                    rationale=f"Skeptical analogy: {analogy.why_it_maps} Breakage risk: {analogy.what_breaks_in_the_mapping}",
                    provenance=_provenance([analogy.target_gap_id], "Hypothesis generated from skeptical cross-domain analogy."),
                )
            )
        return hypotheses


def _context_text(state: ResearchRunState) -> str:
    parts = [state.topic.text]
    parts.extend(gap.title + " " + gap.description + " " + gap.type for gap in state.gaps)
    if state.field_map is not None:
        parts.extend(state.field_map.adjacent_fields + state.field_map.underexplored_areas + state.field_map.dominant_methods)
        parts.extend(state.field_map.contradictions)
    for note in state.paper_notes:
        parts.extend(note.possible_connections + note.what_it_cannot_answer + note.assumptions + note.unstated_limitations)
    return " ".join(parts).lower()


def _matches(pattern: AnalogyPattern, context: str) -> bool:
    return any(trigger in context for trigger in pattern.triggers)


def _best_gap_id(pattern: AnalogyPattern, state: ResearchRunState) -> str | None:
    for gap in state.gaps:
        gap_text = " ".join([gap.title, gap.description, gap.type, gap.why_existing_work_does_not_solve_it]).lower()
        if any(trigger in gap_text for trigger in pattern.triggers):
            return gap.id
    return state.gaps[0].id if state.gaps else None


def _analogy_from_pattern(pattern: AnalogyPattern, topic: str, target_gap_id: str) -> CrossDomainAnalogyModel:
    queries = [
        f"{pattern.source_field} {pattern.source_concept}",
        f"{pattern.source_field} {topic}",
        f"{pattern.source_field} {pattern.triggers[0]}",
        f"{pattern.source_concept} false positives evaluation",
    ]
    return CrossDomainAnalogyModel(
        source_field=pattern.source_field,
        source_concept=pattern.source_concept,
        target_gap_id=target_gap_id,
        why_it_maps=pattern.why_it_maps,
        what_breaks_in_the_mapping=pattern.what_breaks,
        technical_transfer_candidate=pattern.transfer_candidate,
        papers_or_sources_to_search=queries,
        possible_experiment=pattern.experiment_template,
        risk_of_fake_analogy="The analogy is only a search and experiment seed until adjacent-field papers are retrieved and compared.",
        confidence=pattern.confidence,
        provenance=_provenance([target_gap_id], "Generated from deterministic cross-domain analogy mapping table."),
    )


def _provenance(source_ids: list[str], summary: str) -> Provenance:
    return Provenance(
        created_by_skill="cross-domain-analogy",
        source_ids=source_ids,
        timestamp=utc_now_iso(),
        reasoning_summary=summary,
    )


def _dedupe(analogies: list[CrossDomainAnalogyModel]) -> list[CrossDomainAnalogyModel]:
    seen = set()
    deduped = []
    for analogy in analogies:
        key = (analogy.source_field, analogy.source_concept, analogy.target_gap_id)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(analogy)
    return deduped
