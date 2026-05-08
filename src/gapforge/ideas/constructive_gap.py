"""Constructive gap creation for v2 idea discovery."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path

from gapforge.campaigns import CampaignManager
from gapforge.config import GapForgeConfig
from gapforge.ideas.models import ConstructiveGapCandidate, validate_contribution_type
from gapforge.models import ProjectMemoryRecord, Provenance, RelatedWorkMatrix, ResearchCampaign, from_dict, to_plain
from gapforge.project_memory import ProjectMemoryManager
from gapforge.state import ResearchStateManager, slugify, utc_now_iso

CONSTRUCTIVE_CONTRIBUTION_TYPES = {
    "benchmark",
    "measurement",
    "evaluation_protocol",
    "dataset",
    "replication",
    "negative_result",
    "theory",
    "tooling",
}


@dataclass(slots=True)
class ConstructiveGapResult:
    project_id: str
    candidates: list[ConstructiveGapCandidate] = field(default_factory=list)
    blocked: list[str] = field(default_factory=list)


class ConstructiveGapGenerator:
    """Propose evidence-gated paper forms when a clean new-method gap is absent."""

    def __init__(self, config: GapForgeConfig) -> None:
        self.config = config
        self.project_manager = ProjectMemoryManager(config)
        self.campaign_manager = CampaignManager(config)
        self.state_manager = ResearchStateManager(config)

    def generate_for_project(self, project_id: str) -> ConstructiveGapResult:
        program = self.project_manager.load_project(project_id)
        candidates, blocked = _candidate_specs(
            project_id=project_id,
            topic=program.project.name,
            campaigns=program.campaigns,
            memory_records=program.memory_records,
            matrices=program.related_work_matrices,
            source_ids=[project_id],
        )
        return self._save(project_id, candidates, blocked)

    def generate_for_campaign(self, campaign_id: str) -> ConstructiveGapResult:
        campaign_state = self.campaign_manager.load_campaign_state(campaign_id)
        project_id = campaign_state.campaign.project_id
        program = self.project_manager.load_project(project_id)
        matrices = [matrix for matrix in program.related_work_matrices if matrix.direction_id in campaign_state.campaign.decision_ids]
        if not matrices:
            matrices = program.related_work_matrices
        run_records: list[ProjectMemoryRecord] = []
        for run_id in campaign_state.campaign.run_ids:
            try:
                run = self.state_manager.load_run(run_id)
            except FileNotFoundError:
                continue
            run_records.extend(
                ProjectMemoryRecord(
                    id=f"run-gap-{gap.id}",
                    project_id=project_id,
                    record_type="gap",
                    text=gap.description or gap.title,
                    linked_run_ids=[run_id],
                    linked_paper_ids=gap.linked_paper_ids or gap.supporting_paper_ids,
                    status="active",
                    confidence="medium",
                )
                for gap in run.gaps
            )
        candidates, blocked = _candidate_specs(
            project_id=project_id,
            topic=campaign_state.campaign.topic,
            campaigns=[campaign_state.campaign],
            memory_records=[*program.memory_records, *run_records],
            matrices=matrices,
            source_ids=[campaign_id, *campaign_state.campaign.run_ids],
        )
        return self._save(project_id, candidates, blocked)

    def load(self, project_id: str) -> list[ConstructiveGapCandidate]:
        return _load_constructive_gaps(_constructive_gap_path(self.project_manager, project_id))

    def render_report(self, project_id: str) -> str:
        return render_constructive_gap_report(self.load(project_id))

    def write_report(self, project_id: str) -> str:
        report = self.render_report(project_id)
        reports_dir = Path(self.project_manager.load_project(project_id).project.root_dir) / "ideas" / "reports"
        reports_dir.mkdir(parents=True, exist_ok=True)
        (reports_dir / "constructive_gaps.md").write_text(report, encoding="utf-8")
        return report

    def _save(
        self,
        project_id: str,
        candidates: list[ConstructiveGapCandidate],
        blocked: list[str],
    ) -> ConstructiveGapResult:
        existing = {candidate.id: candidate for candidate in self.load(project_id)}
        for candidate in candidates:
            existing[candidate.id] = candidate
        path = _constructive_gap_path(self.project_manager, project_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(to_plain(list(existing.values())), indent=2) + "\n", encoding="utf-8")
        self.write_report(project_id)
        return ConstructiveGapResult(project_id=project_id, candidates=candidates, blocked=blocked)


def validate_constructive_gap_candidate(candidate: ConstructiveGapCandidate) -> ConstructiveGapCandidate:
    validate_contribution_type(candidate.contribution_type)
    if candidate.contribution_type not in CONSTRUCTIVE_CONTRIBUTION_TYPES:
        raise ValueError(f"Unsupported constructive gap contribution type: {candidate.contribution_type}")
    if not candidate.minimum_artifact.strip():
        raise ValueError("Constructive gaps require a minimum artifact.")
    if not candidate.closest_prior_work_ids and not any(link.startswith("missing_search:") for link in candidate.evidence_links):
        raise ValueError("Constructive gaps require closest prior work or an explicit missing search.")
    if candidate.contribution_type in {"benchmark", "measurement"} and not _mentions_metric(candidate.minimum_experiment):
        raise ValueError("Benchmark and measurement constructive gaps must include evaluation metrics.")
    if candidate.contribution_type == "negative_result" and not _is_falsifiable_negative_result(candidate.minimum_experiment):
        raise ValueError("Negative-result constructive gaps must define a falsifiable expectation.")
    return candidate


def render_constructive_gap_report(candidates: list[ConstructiveGapCandidate]) -> str:
    lines = [
        "# Constructive Gap Report",
        "",
        "Constructive gaps are evidence-gated paper-form candidates. They do not claim novelty or results.",
        "",
        f"- Candidates: {len(candidates)}",
        "",
    ]
    for contribution_type in sorted(CONSTRUCTIVE_CONTRIBUTION_TYPES):
        typed = [candidate for candidate in candidates if candidate.contribution_type == contribution_type]
        if not typed:
            continue
        lines.extend([f"## {contribution_type.replace('_', ' ').title()}", ""])
        for candidate in typed:
            lines.extend(
                [
                    f"### `{candidate.id}` {candidate.title}",
                    "",
                    f"- Problem: {candidate.problem}",
                    f"- Why existing work makes this useful: {candidate.why_existing_work_makes_this_useful}",
                    f"- Minimum artifact: {candidate.minimum_artifact}",
                    f"- Minimum experiment: {candidate.minimum_experiment}",
                    f"- Required baselines: {', '.join(candidate.required_baselines) or 'none'}",
                    f"- Closest prior work: {', '.join(candidate.closest_prior_work_ids) or 'none'}",
                    f"- Novelty risk: {candidate.novelty_risk}",
                    f"- Reviewer risk: {candidate.reviewer_risk}",
                    f"- Feasibility: {candidate.feasibility}",
                    f"- Evidence links: {'; '.join(candidate.evidence_links) or 'none'}",
                    "",
                ]
            )
    if len(lines) == 5:
        lines.append("- none")
    return "\n".join(lines).rstrip() + "\n"


def _candidate_specs(
    *,
    project_id: str,
    topic: str,
    campaigns: list[ResearchCampaign],
    memory_records: list[ProjectMemoryRecord],
    matrices: list[RelatedWorkMatrix],
    source_ids: list[str],
) -> tuple[list[ConstructiveGapCandidate], list[str]]:
    context = _Context(project_id=project_id, topic=topic, campaigns=campaigns, memory_records=memory_records, matrices=matrices)
    raw = [
        _benchmark_candidate(context),
        _measurement_candidate(context),
        _evaluation_protocol_candidate(context),
        _dataset_candidate(context),
        _replication_candidate(context),
        _negative_result_candidate(context),
        _theory_candidate(context),
        _tooling_candidate(context),
    ]
    candidates: list[ConstructiveGapCandidate] = []
    blocked: list[str] = []
    for candidate in raw:
        candidate.provenance = Provenance(
            created_by_skill="constructive-gap",
            source_ids=source_ids,
            timestamp=utc_now_iso(),
            reasoning_summary=(
                "Generated a constructive gap candidate. This proposes a paper form and minimum artifact, not a novelty claim."
            ),
        )
        try:
            candidates.append(validate_constructive_gap_candidate(candidate))
        except ValueError as exc:
            blocked.append(f"{candidate.title}: {exc}")
    return candidates, blocked


@dataclass(slots=True)
class _Context:
    project_id: str
    topic: str
    campaigns: list[ResearchCampaign]
    memory_records: list[ProjectMemoryRecord]
    matrices: list[RelatedWorkMatrix]

    @property
    def prior_work_ids(self) -> list[str]:
        return _unique(
            [paper_id for matrix in self.matrices for paper_id in [*matrix.must_read_paper_ids, *matrix.baseline_paper_ids]]
            + [paper_id for record in self.memory_records for paper_id in record.linked_paper_ids]
        )

    @property
    def missing_search(self) -> str:
        missing = [item for matrix in self.matrices for item in matrix.missing_categories]
        if missing:
            return f"missing_search: {'; '.join(missing[:4])}"
        return f"missing_search: closest prior work for constructive paper forms on {self.topic}"

    @property
    def topic_label(self) -> str:
        return self.topic or (self.campaigns[0].topic if self.campaigns else "project topic")


def _benchmark_candidate(context: _Context) -> ConstructiveGapCandidate:
    return _candidate(
        context,
        "benchmark",
        "Benchmark for low-FPR collusion auditing",
        "Existing work may evaluate detection accuracy without a benchmark centered on benign multi-agent false positives.",
        "A benchmark suite with honest-agent negatives, collusive positives, labels, datasheet, and baseline runner.",
        "Evaluate false positive rate, true positive rate, confidence intervals, and slice-level error across required baselines.",
        ["existing monitor", "simple communication-pattern heuristic"],
        "Benchmark novelty may collapse if an equivalent low-FPR benchmark already exists.",
    )


def _measurement_candidate(context: _Context) -> ConstructiveGapCandidate:
    return _candidate(
        context,
        "measurement",
        "Measurement study of monitor false positives under honest multi-agent baselines",
        "Monitor papers can be useful yet incomplete if they under-report specificity on honest coordination traces.",
        "A reproducible measurement harness with benign task traces, monitor outputs, and error taxonomy.",
        "Measure false positive rate, specificity, uncertainty intervals, and common false-alarm categories.",
        ["published monitor", "LLM judge", "rule detector"],
        "A measurement-only paper may be rejected if the phenomenon is already well characterized.",
    )


def _evaluation_protocol_candidate(context: _Context) -> ConstructiveGapCandidate:
    return _candidate(
        context,
        "evaluation_protocol",
        "Evaluation protocol for sequential low-FPR audits",
        "Sequential auditing needs explicit thresholds, stopping rules, and power warnings before claims are credible.",
        "A protocol card defining trace sampling, thresholds, stopping rules, metrics, and refusal conditions.",
        "Run the protocol on a small benchmark and report specificity, sequential false alarm rate, and calibration.",
        ["fixed-threshold audit", "single-shot monitor"],
        "Protocol novelty may be weak unless it resolves concrete evaluation ambiguity in existing work.",
    )


def _dataset_candidate(context: _Context) -> ConstructiveGapCandidate:
    return _candidate(
        context,
        "dataset",
        "Dataset and simulation harness for honest versus collusive agent traces",
        "A dataset paper may be useful if existing work lacks transparent benign/collusive trace splits.",
        "A trace dataset or simulator with generation scripts, labels, metadata, and known limitations.",
        "Evaluate label agreement, split coverage, false positive rate for baseline monitors, and leakage checks.",
        ["existing dataset", "synthetic trace generator"],
        "Dataset novelty depends on whether comparable traces already exist and whether labels are credible.",
    )


def _replication_candidate(context: _Context) -> ConstructiveGapCandidate:
    return _candidate(
        context,
        "replication",
        "Replication study of existing collusion monitors under low-FPR constraints",
        "Replication can be publishable if prior claims were not tested under stringent false-positive requirements.",
        "A replication package with original setup recreation, documented deviations, and reproducible scripts.",
        "Replicate claimed monitor performance, then rerun with low-FPR thresholds and report divergence.",
        ["original reported method", "simple heuristic"],
        "Replication may be too incremental unless it exposes a consequential robustness or specificity issue.",
    )


def _negative_result_candidate(context: _Context) -> ConstructiveGapCandidate:
    return _candidate(
        context,
        "negative_result",
        "Negative result for LLM judges under lexical substitution and covert channels",
        "A negative result is useful if common judge-based monitors fail under simple, reproducible perturbations.",
        "A perturbation suite with lexical substitution, covert-channel prompts, baseline judge outputs, and failure cases.",
        "Falsifiable expectation: if judge monitors are robust, false negatives should not increase "
        "and false positives should stay bounded.",
        ["LLM judge monitor", "keyword monitor", "communication graph heuristic"],
        "Negative results need strong replication fidelity and may be dismissed if perturbations are unrealistic.",
    )


def _theory_candidate(context: _Context) -> ConstructiveGapCandidate:
    return _candidate(
        context,
        "theory",
        "Theory note on limits of low-FPR collusion detection from observable traces",
        "A theory note may be useful if empirical monitor failures reflect distinguishability limits rather than missing engineering.",
        "A formal model, assumptions, toy examples, and counterexamples showing when low-FPR detection is impossible or bounded.",
        "Prove a limit or guarantee under stated assumptions and validate assumptions against a small trace sample.",
        ["closest formal detection model", "anomaly detection bound"],
        "Theory risk is high if assumptions are too detached from LLM agent traces.",
    )


def _tooling_candidate(context: _Context) -> ConstructiveGapCandidate:
    return _candidate(
        context,
        "tooling",
        "System/tooling paper for auditable low-FPR monitor evaluation",
        "Tooling can be useful if existing work lacks reproducible audit infrastructure for specificity-first evaluation.",
        "A command-line or library tool that runs monitors, stores evidence, emits audit reports, and preserves refusal cases.",
        "Run the tool on benchmark traces and report reproducibility, runtime, false-positive metrics, and audit completeness.",
        ["manual evaluation workflow", "existing monitor runner"],
        "Tooling may be seen as engineering-only unless tied to concrete evaluation gaps and reusable artifacts.",
    )


def _candidate(
    context: _Context,
    contribution_type: str,
    title: str,
    why_useful: str,
    artifact: str,
    experiment: str,
    baselines: list[str],
    novelty_risk: str,
) -> ConstructiveGapCandidate:
    prior_work = context.prior_work_ids
    evidence_links = [context.missing_search] if not prior_work else [f"closest_prior_work:{paper_id}" for paper_id in prior_work[:8]]
    return ConstructiveGapCandidate(
        id=_stable_id("constructive-gap", context.project_id, contribution_type, title),
        project_id=context.project_id,
        title=title,
        contribution_type=contribution_type,
        problem=f"No clean new-method gap is assumed for {context.topic_label}; propose a publishable {contribution_type} form instead.",
        why_existing_work_makes_this_useful=why_useful,
        minimum_artifact=artifact,
        minimum_experiment=experiment,
        required_baselines=_unique([*baselines, *context.prior_work_ids[:3]]),
        closest_prior_work_ids=prior_work[:8],
        novelty_risk=novelty_risk,
        reviewer_risk="Reviewer may reject this if it lacks closest-prior-work coverage, artifact quality, or explicit refusal conditions.",
        feasibility="Feasible only if the minimum artifact can be produced without inventing results or citations.",
        evidence_links=evidence_links,
    )


def _mentions_metric(text: str) -> bool:
    lowered = text.lower()
    return any(marker in lowered for marker in ["metric", "rate", "specificity", "precision", "recall", "interval", "coverage"])


def _is_falsifiable_negative_result(text: str) -> bool:
    lowered = text.lower()
    return "falsifiable expectation" in lowered and any(marker in lowered for marker in ["should", "fail", "increase", "bounded"])


def _constructive_gap_path(manager: ProjectMemoryManager, project_id: str) -> Path:
    program = manager.load_project(project_id)
    path = Path(program.project.root_dir) / "ideas" / "constructive_gaps.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    (path.parent / "reports").mkdir(parents=True, exist_ok=True)
    return path


def _load_constructive_gaps(path: Path) -> list[ConstructiveGapCandidate]:
    if not path.exists():
        return []
    raw = json.loads(path.read_text(encoding="utf-8"))
    return [from_dict(ConstructiveGapCandidate, item) for item in raw]


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
