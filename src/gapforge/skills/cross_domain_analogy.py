"""Generate skeptical cross-domain analogies."""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from gapforge.models import CrossDomainAnalogy as CrossDomainAnalogyModel
from gapforge.models import CrossDomainTransferCandidate, EvidenceSpan, Hypothesis, Paper, PaperNote, Provenance, ResearchRunState
from gapforge.skills.base import Skill
from gapforge.sources.coverage import add_search_query_record
from gapforge.sources.ranking import rank_papers
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
        triggers=("low false positive", "quality", "false positive", "specificity"),
        source_field="quality control",
        source_concept="control charts and defect inspection under false-alarm budgets",
        why_it_maps="Both settings balance rare-event detection against costly false alarms and reviewer workload.",
        what_breaks="Quality-control processes often have stable manufacturing distributions; collusion behavior can adapt.",
        transfer_candidate="false-alarm-budgeted control chart thresholds",
        experiment_template="Evaluate collusion alerts with control-chart-style thresholds under fixed false-positive budgets.",
        confidence="low",
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
        triggers=("monitor evasion", "evasion", "adversarial", "intrusion"),
        source_field="cybersecurity",
        source_concept="intrusion detection under adversarial evasion",
        why_it_maps="Both settings involve actors adapting behavior to avoid detector thresholds.",
        what_breaks="Intrusion detection has different observability and attack tooling than multi-agent social collusion.",
        transfer_candidate="adversarial evasion test suites with adaptive alert thresholds",
        experiment_template="Stress-test collusion detectors against adaptive evasion traces and compare alert stability.",
        confidence="medium",
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
        triggers=("multi-agent collusion", "mechanism design", "incentive", "strategic"),
        source_field="mechanism design",
        source_concept="incentive-compatible mechanisms for strategic agents",
        why_it_maps="Both settings analyze how incentives shape strategic behavior under observability constraints.",
        what_breaks="Mechanism design may assume declared preferences and formal utility models not present in traces.",
        transfer_candidate="incentive-compatible stress tests for collusion monitors",
        experiment_template="Compare detector outcomes under incentives that reward coordinated evasion.",
        confidence="low",
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
        triggers=("reproducibility", "scientific workflow", "workflow", "replication"),
        source_field="software provenance",
        source_concept="scientific workflow provenance and reproducibility traces",
        why_it_maps="Both require auditable lineage from evidence to claims and decisions.",
        what_breaks="Workflow systems can capture execution logs; research ideation may leave informal reasoning traces.",
        transfer_candidate="workflow provenance graphs for evidence-to-gap traceability",
        experiment_template="Audit whether every generated gap can be traced to paper sections, claims, and search records.",
        confidence="medium",
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
        triggers=("distribution shift", "robust statistics", "robustness", "deployment"),
        source_field="statistics",
        source_concept="robust statistics under contaminated distributions",
        why_it_maps="Both ask whether conclusions survive non-ideal samples and shifted observation processes.",
        what_breaks="Robust-statistics contamination assumptions may be too simple for strategic collusion.",
        transfer_candidate="contamination-robust evaluation slices",
        experiment_template="Measure detector performance under controlled contamination and shifted interaction distributions.",
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

    def __init__(self, sources: Iterable[Any] | None = None) -> None:
        self.sources = list(sources or [])

    def run(
        self,
        state: ResearchRunState,
        *,
        search: bool = False,
        promote_evidence_only: bool = False,
    ) -> ResearchRunState:
        analogies = self.generate(state)
        if search:
            self._search_adjacent_sources(state, analogies)
        transfers = self._transfer_candidates(state, analogies)
        transfer_by_id = {transfer.id: transfer for transfer in transfers}
        for analogy in analogies:
            transfer = transfer_by_id.get(_transfer_id(analogy))
            if transfer is None:
                continue
            analogy.transfer_candidate_id = transfer.id
            analogy.status = transfer.status
            analogy.source_paper_ids = transfer.source_paper_ids
            analogy.confidence = transfer.confidence
        if promote_evidence_only:
            analogies = [analogy for analogy in analogies if analogy.status == "promoted"]
        state.cross_domain_analogies = analogies
        state.cross_domain_transfers = _replace_transfers(state.cross_domain_transfers, transfers)
        state.hypotheses = self._hypotheses_from_analogies([analogy for analogy in analogies if analogy.status == "promoted"])
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

    def _search_adjacent_sources(self, state: ResearchRunState, analogies: list[CrossDomainAnalogyModel]) -> None:
        found: list[Paper] = []
        for analogy in analogies:
            for query in analogy.papers_or_sources_to_search[:3]:
                query_found: list[Paper] = []
                failures: list[str] = []
                for source in self.sources:
                    source_name = str(getattr(source, "name", source.__class__.__name__))
                    try:
                        query_found.extend(source.search(query, max_results=5, sort="newest", date_from=None, date_to=None))
                    except Exception as exc:
                        failures.append(f"{source_name} search failed for {query!r}: {exc}")
                add_search_query_record(
                    state,
                    query=query,
                    source_names=[str(getattr(source, "name", source.__class__.__name__)) for source in self.sources],
                    purpose="analogy",
                    max_results=5 * max(1, len(self.sources)),
                    date_from=None,
                    date_to=None,
                    result_paper_ids=[paper.id for paper in query_found],
                    failure_messages=failures,
                )
                found.extend(query_found)
        if found:
            state.papers = rank_papers(state.topic.text, state.papers + found, newest_first=True)

    def _transfer_candidates(
        self,
        state: ResearchRunState,
        analogies: list[CrossDomainAnalogyModel],
    ) -> list[CrossDomainTransferCandidate]:
        transfers = []
        for analogy in analogies:
            source_papers = _source_papers_for_analogy(state, analogy)
            promoted_papers, evidence_span_ids, mechanism = _mechanism_evidence(state, analogy, source_papers)
            status = "query_only"
            confidence = "low"
            if source_papers and not promoted_papers:
                status = "rejected"
            if promoted_papers:
                status = "promoted"
                confidence = "medium" if evidence_span_ids else "low"
                self._create_adjacent_notes(state, promoted_papers, analogy, mechanism)
            transfers.append(
                CrossDomainTransferCandidate(
                    id=_transfer_id(analogy),
                    target_gap_id=analogy.target_gap_id,
                    source_field=analogy.source_field,
                    source_paper_ids=[paper.id for paper in promoted_papers],
                    source_concept=analogy.source_concept,
                    technical_mechanism=mechanism if promoted_papers else "",
                    why_it_maps=analogy.why_it_maps if promoted_papers else "No adjacent-field paper evidence supports the transfer yet.",
                    what_breaks=analogy.what_breaks_in_the_mapping,
                    required_adaptation=_required_adaptation(analogy),
                    proposed_experiment=analogy.possible_experiment,
                    evidence_span_ids=evidence_span_ids,
                    risk_of_fake_analogy=analogy.risk_of_fake_analogy,
                    confidence=confidence,
                    status=status,
                    provenance=_provenance(
                        [analogy.target_gap_id, *[paper.id for paper in promoted_papers]],
                        "Evaluated cross-domain transfer candidate against adjacent-field paper evidence.",
                    ),
                )
            )
        return transfers

    def _create_adjacent_notes(
        self,
        state: ResearchRunState,
        papers: list[Paper],
        analogy: CrossDomainAnalogyModel,
        mechanism: str,
    ) -> None:
        existing = {note.paper_id for note in state.paper_notes}
        for paper in papers:
            if paper.id in existing:
                continue
            state.paper_notes.append(
                PaperNote(
                    paper_id=paper.id,
                    citation_key=paper.id,
                    one_sentence_summary=paper.abstract[:240] or paper.title,
                    core_claims=[mechanism] if mechanism else [],
                    method=[analogy.technical_transfer_candidate],
                    possible_connections=[analogy.why_it_maps],
                    relevance_to_topic=f"Adjacent-field evidence for {analogy.source_field} transfer candidate.",
                    confidence="medium" if paper.abstract else "low",
                    source_basis="metadata/abstract only",
                    created_by_skill=self.name,
                    provenance=_provenance([paper.id, analogy.target_gap_id], "Created adjacent-field abstract note for transfer triage."),
                )
            )

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


def _source_papers_for_analogy(state: ResearchRunState, analogy: CrossDomainAnalogyModel) -> list[Paper]:
    field_terms = _terms(" ".join([analogy.source_field, analogy.source_concept, analogy.technical_transfer_candidate]))
    query_result_ids = {
        paper_id
        for record in state.search_queries
        if record.purpose == "analogy" and _overlaps_field(record.query, analogy)
        for paper_id in record.result_paper_ids
    }
    candidates: list[Paper] = []
    for paper in state.papers:
        text = " ".join([paper.title, paper.abstract, paper.venue, " ".join(paper.keywords), paper.source]).lower()
        paper_terms = _terms(text)
        if paper.id in query_result_ids or len(field_terms & paper_terms) >= 1:
            candidates.append(paper)
    return candidates[:8]


def _mechanism_evidence(
    state: ResearchRunState,
    analogy: CrossDomainAnalogyModel,
    papers: list[Paper],
) -> tuple[list[Paper], list[str], str]:
    promoted: list[Paper] = []
    span_ids: list[str] = []
    mechanism_terms = _mechanism_terms(analogy)
    spans_by_paper: dict[str, list[EvidenceSpan]] = {}
    for span in state.evidence_spans:
        spans_by_paper.setdefault(span.paper_id, []).append(span)
    mechanism_text = ""
    for paper in papers:
        text = " ".join([paper.title, paper.abstract, " ".join(paper.keywords)]).lower()
        matched_terms = sorted(mechanism_terms & _terms(text))
        paper_span_ids = [
            span.id for span in spans_by_paper.get(paper.id, []) if mechanism_terms & _terms(" ".join([span.quote, span.evidence_type]))
        ]
        if matched_terms or paper_span_ids:
            promoted.append(paper)
            span_ids.extend(paper_span_ids)
            if not mechanism_text:
                mechanism_text = _mechanism_summary(analogy, paper, matched_terms)
    return promoted, _dedupe_strings(span_ids), mechanism_text


def _mechanism_terms(analogy: CrossDomainAnalogyModel) -> set[str]:
    text = " ".join([analogy.source_concept, analogy.technical_transfer_candidate, analogy.possible_experiment])
    terms = _terms(text)
    domain_terms = {
        "medicine": {"screening", "specificity", "sensitivity", "confirmatory", "diagnosis", "triage", "threshold"},
        "industrial monitoring": {"alarm", "fatigue", "fault", "threshold", "operator", "workload", "triage"},
        "quality control": {"control", "chart", "defect", "inspection", "threshold", "specificity"},
        "steganography": {"steganography", "hidden", "cover", "residual", "channel", "message"},
        "cryptography": {"covert", "channel", "capacity", "indistinguishability", "leakage"},
        "economics": {"cartel", "collusion", "incentive", "repeated", "game", "tacit"},
        "mechanism design": {"incentive", "mechanism", "truthful", "strategic", "game"},
        "cybersecurity": {"intrusion", "adversarial", "evasion", "alert", "detector"},
        "statistics": {"domain", "adaptation", "covariate", "shift", "robust", "importance"},
        "epidemiology": {"external", "validity", "population", "stratified", "sampling"},
        "control theory": {"stability", "feedback", "margin", "perturbation", "convergence"},
        "statistical physics": {"phase", "transition", "threshold", "density", "noise"},
        "software provenance": {"provenance", "traceability", "lineage", "workflow", "reproducibility"},
    }
    return terms | domain_terms.get(analogy.source_field, set())


def _mechanism_summary(analogy: CrossDomainAnalogyModel, paper: Paper, matched_terms: list[str]) -> str:
    terms = ", ".join(matched_terms[:8]) if matched_terms else "locator-backed adjacent-field mechanism"
    return f"{paper.id} supports transfer via {terms}; candidate mechanism: {analogy.technical_transfer_candidate}."


def _required_adaptation(analogy: CrossDomainAnalogyModel) -> str:
    return (
        f"Adapt {analogy.technical_transfer_candidate} from {analogy.source_field} to the target gap, "
        "then verify labels, incentives, observability, and evaluation metrics still match."
    )


def _transfer_id(analogy: CrossDomainAnalogyModel) -> str:
    raw = f"{analogy.target_gap_id}-{analogy.source_field}-{analogy.source_concept}"
    slug = re.sub(r"[^a-z0-9]+", "-", raw.lower()).strip("-")
    return f"transfer-{slug[:90]}"


def _terms(text: str) -> set[str]:
    stop = {"and", "for", "from", "with", "that", "this", "into", "under", "the", "both", "field", "source"}
    return {token for token in re.findall(r"[a-z0-9]+", text.lower()) if token not in stop and len(token) > 3}


def _overlaps_field(query: str, analogy: CrossDomainAnalogyModel) -> bool:
    query_terms = _terms(query)
    analogy_terms = _terms(" ".join([analogy.source_field, analogy.source_concept]))
    return bool(query_terms & analogy_terms)


def _dedupe_strings(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result = []
    for value in values:
        if value and value not in seen:
            result.append(value)
            seen.add(value)
    return result


def _replace_transfers(
    existing: list[CrossDomainTransferCandidate],
    new_items: list[CrossDomainTransferCandidate],
) -> list[CrossDomainTransferCandidate]:
    replacing = {item.id for item in new_items}
    return [item for item in existing if item.id not in replacing] + new_items


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
