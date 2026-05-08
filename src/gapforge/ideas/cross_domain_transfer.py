"""Project-level cross-domain transfer for v2 idea discovery."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from gapforge.config import GapForgeConfig
from gapforge.ideas.models import IdeaTransferCandidate
from gapforge.ideas.store import IdeaStore
from gapforge.models import ProjectMemoryRecord, Provenance, from_dict, to_plain
from gapforge.project_memory import ProjectMemoryManager
from gapforge.state import slugify, utc_now_iso

SOURCE_FIELDS = {
    "medicine screening/specificity",
    "industrial anomaly detection",
    "fraud detection",
    "cartel detection economics",
    "covert channels/steganography",
    "sequential hypothesis testing",
    "statistical process control",
    "safety-critical monitoring",
    "reliability engineering",
}


@dataclass(frozen=True, slots=True)
class TransferPattern:
    source_field: str
    source_concept: str
    triggers: tuple[str, ...]
    transfer_mechanism: str
    required_adaptation: str
    what_breaks: str
    idea_title: str
    idea_summary: str
    expected_metrics: tuple[str, ...]
    required_searches: tuple[str, ...]
    confidence: str = "low"


PATTERNS = [
    TransferPattern(
        source_field="medicine screening/specificity",
        source_concept="screening specificity plus confirmatory testing",
        triggers=("low false positive", "false-positive", "false positive", "specificity", "screening"),
        transfer_mechanism=(
            "Use specificity-first thresholding with a second-stage confirmatory audit, separating screening alerts "
            "from paper claims about collusion."
        ),
        required_adaptation="Replace clinical outcome labels with audited agent-trace labels and explicit benign coordination strata.",
        what_breaks="Medical screening has clearer outcome labels and prospective follow-up; collusion labels are noisier and adversarial.",
        idea_title="Specificity-first two-stage collusion audit",
        idea_summary="Adapt screening-test specificity and confirmatory review into a low-FPR collusion audit seed.",
        expected_metrics=("specificity", "false positive rate", "confirmatory review yield"),
        required_searches=(
            "medical screening specificity confirmatory testing false positive",
            "collusion detection specificity confirmatory audit",
        ),
        confidence="medium",
    ),
    TransferPattern(
        source_field="industrial anomaly detection",
        source_concept="alarm fatigue and operator workload constraints",
        triggers=("anomaly", "monitor", "alert", "false positive"),
        transfer_mechanism="Use alert-budgeted anomaly detection where the operating point is constrained by reviewer workload.",
        required_adaptation="Convert sensor-alert budgets into human or automated audit budgets for multi-agent traces.",
        what_breaks="Industrial sensors can be stable and calibrated; agent communication distributions can shift strategically.",
        idea_title="Alert-budgeted collusion anomaly benchmark",
        idea_summary="Transfer alarm-fatigue constraints into a benchmark for collusion monitor operating points.",
        expected_metrics=("alert volume", "false positive rate", "true positive rate"),
        required_searches=("industrial anomaly detection alarm fatigue false positives", "agent collusion alert budget evaluation"),
    ),
    TransferPattern(
        source_field="fraud detection",
        source_concept="precision-constrained review queues",
        triggers=("fraud", "monitor", "audit", "false positive"),
        transfer_mechanism="Use review-queue precision constraints to evaluate whether alerts are actionable at deployment scale.",
        required_adaptation="Map transaction review queues to agent-trace audit queues with different base rates and costs.",
        what_breaks="Fraud labels often arrive from chargebacks or investigations; collusion labels may remain uncertain.",
        idea_title="Precision-constrained collusion review queue",
        idea_summary="Adapt fraud-review queue constraints into a collusion-monitor evaluation protocol.",
        expected_metrics=("precision at review budget", "false positive rate", "queue coverage"),
        required_searches=("fraud detection review queue precision false positive", "collusion monitor review queue precision"),
    ),
    TransferPattern(
        source_field="cartel detection economics",
        source_concept="screening for tacit collusion in repeated games",
        triggers=("cartel", "collusion", "multi-agent", "incentive", "economics"),
        transfer_mechanism="Transfer structural screens for coordinated behavior into features over repeated agent interactions.",
        required_adaptation="Replace prices and market shares with trace-level communication, action timing, and payoff proxies.",
        what_breaks="Cartel economics assumes market observables and incentives that may not exist in LLM-agent tasks.",
        idea_title="Cartel-screen-inspired collusion trace benchmark",
        idea_summary="Adapt cartel screening mechanisms into a candidate benchmark or measurement study for multi-agent traces.",
        expected_metrics=("false positive rate", "screen stability", "payoff-proxy sensitivity"),
        required_searches=("cartel detection economics structural screens collusion", "LLM agent collusion cartel detection analogy"),
        confidence="medium",
    ),
    TransferPattern(
        source_field="covert channels/steganography",
        source_concept="hidden messages under cover traffic",
        triggers=("covert", "steganography", "hidden communication", "channel"),
        transfer_mechanism="Treat suspicious coordination as residual information transfer above benign cover-traffic expectations.",
        required_adaptation="Define cover traffic for honest agent collaboration and controlled covert-channel injections.",
        what_breaks="Steganography often has explicit encoders; collusion can emerge without fixed codes.",
        idea_title="Residual-channel benchmark for hidden agent coordination",
        idea_summary="Transfer covert-channel residual tests into benchmark construction for hidden collusion.",
        expected_metrics=("channel detectability", "false positive rate", "injection strength"),
        required_searches=("covert channel detection steganography cover traffic", "agent collusion covert channel benchmark"),
        confidence="medium",
    ),
    TransferPattern(
        source_field="sequential hypothesis testing",
        source_concept="sequential tests with controlled error rates",
        triggers=("sequential", "audit", "false positive", "hypothesis testing"),
        transfer_mechanism="Use sequential stopping rules that preserve false-alarm budgets across repeated monitor checks.",
        required_adaptation="Map independent test assumptions to correlated multi-agent trace windows.",
        what_breaks="Sequential tests can assume known error models; collusion traces may be nonstationary and dependent.",
        idea_title="Sequential low-FPR collusion audit protocol",
        idea_summary="Adapt sequential hypothesis testing into a low-FPR audit protocol for repeated agent traces.",
        expected_metrics=("sequential false alarm rate", "power", "stopping time"),
        required_searches=("sequential hypothesis testing false alarm control", "sequential collusion detection audit protocol"),
        confidence="medium",
    ),
    TransferPattern(
        source_field="statistical process control",
        source_concept="control charts under false-alarm budgets",
        triggers=("process control", "control chart", "monitor", "false positive"),
        transfer_mechanism="Use control-chart thresholds to detect sustained deviations while bounding false alarms.",
        required_adaptation="Replace process measurements with trace-derived collusion indicators and account for strategic shifts.",
        what_breaks="Manufacturing processes are more stable than adaptive multi-agent interactions.",
        idea_title="Control-chart collusion monitor evaluation",
        idea_summary="Transfer statistical process control thresholds into collusion monitor evaluation.",
        expected_metrics=("average run length", "false alarm rate", "detection delay"),
        required_searches=("statistical process control false alarm control chart", "collusion monitor control chart evaluation"),
    ),
    TransferPattern(
        source_field="safety-critical monitoring",
        source_concept="high-specificity alarms for costly interventions",
        triggers=("safety", "monitoring", "false positive", "critical"),
        transfer_mechanism="Evaluate monitors at operating points where false alarms trigger costly interventions or shutdowns.",
        required_adaptation="Define intervention cost and escalation policy for agent monitoring deployments.",
        what_breaks="Safety-critical systems often have certified requirements; agent monitoring has weaker operational specifications.",
        idea_title="Safety-critical operating points for collusion monitors",
        idea_summary="Transfer safety-critical alarm evaluation into low-FPR collusion monitor benchmarks.",
        expected_metrics=("false alarm cost", "specificity", "escalation burden"),
        required_searches=("safety critical monitoring false alarm specificity", "agent monitor false alarm intervention cost"),
    ),
    TransferPattern(
        source_field="reliability engineering",
        source_concept="failure modes and effects analysis",
        triggers=("reliability", "failure mode", "monitor", "evaluation"),
        transfer_mechanism="Use failure-mode taxonomies to turn monitor errors into auditable benchmark slices.",
        required_adaptation="Translate component failure modes into trace, incentive, and communication failure slices.",
        what_breaks="Reliability engineering often has physical components; collusion failures are behavioral and contextual.",
        idea_title="Failure-mode taxonomy for collusion monitor false positives",
        idea_summary="Transfer reliability failure-mode analysis into measurement slices for collusion monitor evaluation.",
        expected_metrics=("failure slice coverage", "false positive rate", "reproducibility"),
        required_searches=("reliability engineering failure modes monitoring false alarm", "collusion monitor failure mode taxonomy"),
    ),
]


@dataclass(slots=True)
class IdeaTransferResult:
    project_id: str
    transfers: list[IdeaTransferCandidate]
    promoted_idea_ids: list[str]
    rejected: list[str]


class CrossDomainIdeaTransferEngine:
    """Generate project-level idea transfers only when mechanisms are technically plausible."""

    def __init__(self, config: GapForgeConfig) -> None:
        self.config = config
        self.project_manager = ProjectMemoryManager(config)
        self.idea_store = IdeaStore(config)

    def transfer_for_project(self, project_id: str) -> IdeaTransferResult:
        program = self.project_manager.load_project(project_id)
        return self._transfer(project_id=project_id, topic=program.project.name, memory_records=program.memory_records)

    def transfer_for_topic(self, topic: str) -> IdeaTransferResult:
        program = self.project_manager.create_project(topic, description="Project created for v2 cross-domain idea transfer.")
        self.idea_store.create_bank(project_id=program.project.id, root_topic=topic)
        return self._transfer(project_id=program.project.id, topic=topic, memory_records=program.memory_records)

    def load(self, project_id: str) -> list[IdeaTransferCandidate]:
        return _load_transfer_candidates(_transfer_path(self.project_manager, project_id))

    def render_report(self, project_id: str) -> str:
        return render_transfer_report(self.load(project_id))

    def write_report(self, project_id: str) -> str:
        report = self.render_report(project_id)
        reports_dir = Path(self.project_manager.load_project(project_id).project.root_dir) / "ideas" / "reports"
        reports_dir.mkdir(parents=True, exist_ok=True)
        (reports_dir / "cross_domain_transfers.md").write_text(report, encoding="utf-8")
        return report

    def _transfer(self, *, project_id: str, topic: str, memory_records: list[ProjectMemoryRecord]) -> IdeaTransferResult:
        state = self.idea_store.load_state(project_id)
        if state.idea_bank is None:
            self.idea_store.create_bank(project_id=project_id, root_topic=topic)
        transfers: list[IdeaTransferCandidate] = []
        promoted: list[str] = []
        rejected: list[str] = []
        for pattern in PATTERNS:
            if not _matches(topic, pattern):
                continue
            candidate, reason = _transfer_candidate(project_id, topic, pattern, memory_records)
            if reason:
                rejected.append(reason)
                continue
            if candidate.supporting_source_papers:
                idea = self.idea_store.add_candidate(
                    project_id=project_id,
                    source_topic_id=candidate.id,
                    title=pattern.idea_title,
                    summary=pattern.idea_summary,
                    contribution_type="hybrid",
                    core_claim=(
                        "A cross-domain mechanism may yield a defensible seed idea, but novelty remains unchecked until "
                        "target-domain prior-work review."
                    ),
                    proposed_experiment=(
                        f"Adapt `{pattern.source_concept}` via `{pattern.transfer_mechanism}` and test transfer validity."
                    ),
                    expected_baselines=["closest target-domain baseline", *candidate.supporting_source_papers[:2]],
                    expected_metrics=list(pattern.expected_metrics),
                    closest_prior_work_ids=candidate.supporting_source_papers,
                    supporting_paper_ids=candidate.supporting_source_papers,
                    novelty_status="unchecked",
                    tractability_score=0.35,
                    impact_score=0.45,
                    evidence_score=0.25,
                    reviewer_risk_score=0.75,
                    idea_yield_score=0.35,
                    maturity="seed",
                    likely_failure_mode=f"Transfer may fail because: {candidate.what_breaks}",
                    provenance=Provenance(
                        created_by_skill="idea-cross-domain-transfer",
                        source_ids=[candidate.id, *candidate.supporting_source_papers],
                        timestamp=utc_now_iso(),
                        reasoning_summary=(
                            "Promoted an evidence-backed cross-domain transfer into a seed IdeaCandidate. Promotion is not a novelty claim."
                        ),
                    ),
                )
                candidate.target_idea_id = idea.id
                promoted.append(idea.id)
            transfers.append(candidate)
        self._save(project_id, transfers)
        return IdeaTransferResult(project_id=project_id, transfers=transfers, promoted_idea_ids=promoted, rejected=rejected)

    def _save(self, project_id: str, transfers: list[IdeaTransferCandidate]) -> None:
        existing = {transfer.id: transfer for transfer in self.load(project_id)}
        for transfer in transfers:
            existing[transfer.id] = transfer
        path = _transfer_path(self.project_manager, project_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(to_plain(list(existing.values())), indent=2) + "\n", encoding="utf-8")
        state = self.idea_store.load_state(project_id)
        state.transfer_candidates = list(existing.values())
        self.idea_store._save_state(project_id, state)
        self.write_report(project_id)


def render_transfer_report(transfers: list[IdeaTransferCandidate]) -> str:
    lines = [
        "# Cross-Domain Idea Transfer Report",
        "",
        "Transfers require a technical mechanism. Unsupported transfers remain search requests, not promoted idea candidates.",
        "",
        f"- Transfers: {len(transfers)}",
        f"- Promoted idea candidates: {sum(1 for transfer in transfers if transfer.target_idea_id)}",
        "",
    ]
    if not transfers:
        lines.append("- none")
        return "\n".join(lines).rstrip() + "\n"
    for transfer in transfers:
        status = "promoted" if transfer.target_idea_id else "search_request"
        lines.extend(
            [
                f"## `{transfer.id}` {transfer.source_field}",
                "",
                f"- Status: `{status}`",
                f"- Source concept: {transfer.source_concept}",
                f"- Target problem: {transfer.target_problem}",
                f"- Transfer mechanism: {transfer.transfer_mechanism}",
                f"- Target idea ID: `{transfer.target_idea_id or 'none'}`",
                f"- Required adaptation: {transfer.required_adaptation}",
                f"- What breaks: {transfer.what_breaks}",
                f"- Supporting source papers: {', '.join(transfer.supporting_source_papers) or 'none'}",
                f"- Required searches: {'; '.join(transfer.required_searches) or 'none'}",
                f"- Confidence: `{transfer.confidence}`",
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def validate_transfer_pattern(pattern: TransferPattern) -> None:
    if pattern.source_field not in SOURCE_FIELDS:
        raise ValueError(f"Unsupported transfer source field: {pattern.source_field}")
    if not _has_mechanism(pattern.transfer_mechanism):
        raise ValueError("Transfer must state a technical mechanism, not just an analogy.")
    if not pattern.what_breaks.strip():
        raise ValueError("Transfer must state what breaks.")


def _transfer_candidate(
    project_id: str,
    topic: str,
    pattern: TransferPattern,
    memory_records: list[ProjectMemoryRecord],
) -> tuple[IdeaTransferCandidate, str]:
    try:
        validate_transfer_pattern(pattern)
    except ValueError as exc:
        return _empty_transfer(project_id, topic, pattern), f"{pattern.source_field}: {exc}"
    papers = _supporting_source_papers(pattern, memory_records)
    transfer = IdeaTransferCandidate(
        id=_stable_id("idea-transfer", project_id, pattern.source_field, pattern.source_concept),
        source_field=pattern.source_field,
        source_concept=pattern.source_concept,
        target_problem=topic,
        transfer_mechanism=pattern.transfer_mechanism,
        required_adaptation=pattern.required_adaptation,
        what_breaks=pattern.what_breaks,
        supporting_source_papers=papers,
        required_searches=list(pattern.required_searches),
        confidence=pattern.confidence if papers else "low",
        provenance=Provenance(
            created_by_skill="idea-cross-domain-transfer",
            source_ids=[project_id, *papers],
            timestamp=utc_now_iso(),
            reasoning_summary=(
                "Recorded a cross-domain transfer. Without supporting source papers this remains a search request, not an IdeaCandidate."
            ),
        ),
    )
    return transfer, ""


def _empty_transfer(project_id: str, topic: str, pattern: TransferPattern) -> IdeaTransferCandidate:
    return IdeaTransferCandidate(
        id=_stable_id("idea-transfer", project_id, pattern.source_field, pattern.source_concept),
        source_field=pattern.source_field,
        source_concept=pattern.source_concept,
        target_problem=topic,
        transfer_mechanism=pattern.transfer_mechanism,
        required_adaptation=pattern.required_adaptation,
        what_breaks=pattern.what_breaks,
        required_searches=list(pattern.required_searches),
    )


def _matches(topic: str, pattern: TransferPattern) -> bool:
    lowered = topic.lower()
    return any(trigger in lowered for trigger in pattern.triggers)


def _supporting_source_papers(pattern: TransferPattern, memory_records: list[ProjectMemoryRecord]) -> list[str]:
    papers: list[str] = []
    field_terms = set(_terms(pattern.source_field)) | set(_terms(pattern.source_concept))
    for record in memory_records:
        text_terms = set(_terms(record.text))
        if field_terms & text_terms or pattern.source_field.lower() in record.text.lower():
            papers.extend(record.linked_paper_ids)
    return _unique(papers)


def _has_mechanism(mechanism: str) -> bool:
    lowered = mechanism.strip().lower()
    if len(lowered.split()) < 6:
        return False
    shallow_markers = {"is like", "similar to", "analogous to", "reminds of"}
    if any(marker in lowered for marker in shallow_markers) and not any(
        verb in lowered for verb in ["use", "map", "transfer", "adapt", "replace", "evaluate"]
    ):
        return False
    return any(verb in lowered for verb in ["use", "map", "transfer", "adapt", "replace", "treat", "evaluate"])


def _terms(text: str) -> list[str]:
    return [term for term in slugify(text).split("-") if len(term) > 3]


def _transfer_path(manager: ProjectMemoryManager, project_id: str) -> Path:
    program = manager.load_project(project_id)
    path = Path(program.project.root_dir) / "ideas" / "transfer_candidates.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    (path.parent / "reports").mkdir(parents=True, exist_ok=True)
    return path


def _load_transfer_candidates(path: Path) -> list[IdeaTransferCandidate]:
    if not path.exists():
        return []
    raw = json.loads(path.read_text(encoding="utf-8"))
    return [from_dict(IdeaTransferCandidate, item) for item in raw]


def _stable_id(prefix: str, *parts: str) -> str:
    digest = hashlib.sha1("::".join(parts).encode("utf-8")).hexdigest()[:8]
    readable = slugify(parts[-1])[:48] or "untitled"
    return f"{prefix}-{readable}-{digest}"


def _unique(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value and value not in seen:
            result.append(value)
            seen.add(value)
    return result
