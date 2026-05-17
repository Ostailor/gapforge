"""Hardening reports for real benchmark fit and no-fit arguments."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from gapforge.config import GapForgeConfig
from gapforge.models import Provenance, to_plain
from gapforge.project_memory import ProjectMemoryManager
from gapforge.selected_benchmark.real_benchmark_search import (
    RealBenchmarkCandidate,
    RealBenchmarkCandidateSearch,
    RealBenchmarkSearchManager,
    default_candidates,
)
from gapforge.selected_benchmark.spec import SelectedBenchmarkManager
from gapforge.selected_benchmark.vetted_experiment import SelectedVettedBenchmarkExperimentManager
from gapforge.state import slugify, utc_now_iso
from gapforge.vetted_benchmarks import RealBenchmarkAdapterAssessment


@dataclass(slots=True)
class BenchmarkFitCandidateRow:
    candidate_id: str
    name: str
    source_url: str
    claim_support: str
    use_as: str
    what_it_lacks: list[str] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)
    adapter_assessment_id: str = ""


@dataclass(slots=True)
class BenchmarkFitHardeningReport:
    id: str
    benchmark_id: str
    decision: str
    candidate_rows: list[BenchmarkFitCandidateRow] = field(default_factory=list)
    primary_candidate_ids: list[str] = field(default_factory=list)
    auxiliary_candidate_ids: list[str] = field(default_factory=list)
    no_fit_candidate_ids: list[str] = field(default_factory=list)
    reviewer_objection_answer: str = ""
    manuscript_insertion_text: str = ""
    provenance: Provenance = field(default_factory=lambda: Provenance(created_by_skill="benchmark-fit-hardening"))


class BenchmarkFitHardeningManager:
    """Turn real benchmark search records into a reviewer-facing fit/no-fit argument."""

    def __init__(self, config: GapForgeConfig) -> None:
        self.config = config
        self.config.ensure_dirs()
        self.projects = ProjectMemoryManager(config)
        self.benchmarks = SelectedBenchmarkManager(config)
        self.search = RealBenchmarkSearchManager(config)
        self.assessments = SelectedVettedBenchmarkExperimentManager(config)

    def harden(self, benchmark_id: str) -> BenchmarkFitHardeningReport:
        search = self.search.load_or_search(benchmark_id)
        candidates = self.search.load_candidates(benchmark_id)
        if len(candidates) < 2:
            candidates = _merge_candidates(candidates, default_candidates())
            search = self.search.search(benchmark_id, candidates=candidates)
            candidates = self.search.load_candidates(benchmark_id)
        rows = [self._candidate_row(benchmark_id, candidate) for candidate in candidates]
        report = _report_from_rows(benchmark_id, search, rows)
        self._write_outputs(report)
        return report

    def no_fit_argument(self, benchmark_id: str) -> BenchmarkFitHardeningReport:
        report = self.harden(benchmark_id)
        self._no_fit_path(benchmark_id).write_text(render_no_fit_argument(report), encoding="utf-8")
        self._manuscript_path(benchmark_id).write_text(report.manuscript_insertion_text.rstrip() + "\n", encoding="utf-8")
        return report

    def _candidate_row(self, benchmark_id: str, candidate: RealBenchmarkCandidate) -> BenchmarkFitCandidateRow:
        assessment = self.assessments.assess_real_candidate(benchmark_id, candidate.id)
        return BenchmarkFitCandidateRow(
            candidate_id=candidate.id,
            name=candidate.name,
            source_url=candidate.source_url,
            claim_support=assessment.expected_claim_support,
            use_as=_use_as(assessment),
            what_it_lacks=_what_candidate_lacks(candidate, assessment),
            limitations=_dedupe(
                [*candidate.limitations, *assessment.schema_mismatches, *assessment.label_mismatches, *assessment.blockers]
            ),
            adapter_assessment_id=assessment.id,
        )

    def _write_outputs(self, report: BenchmarkFitHardeningReport) -> None:
        output_dir = self._output_dir(report.benchmark_id)
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "benchmark_fit_hardening_report.json").write_text(json.dumps(to_plain(report), indent=2) + "\n", encoding="utf-8")
        (output_dir / "benchmark_fit_hardening_report.md").write_text(render_benchmark_fit_hardening_report(report), encoding="utf-8")
        (output_dir / "no_fit_argument.md").write_text(render_no_fit_argument(report), encoding="utf-8")
        (output_dir / "manuscript_insertion_text.md").write_text(report.manuscript_insertion_text.rstrip() + "\n", encoding="utf-8")

    def _output_dir(self, benchmark_id: str) -> Path:
        spec = self.benchmarks.load_spec(benchmark_id)
        program = self.projects.load_project(spec.project_id)
        return Path(program.project.root_dir) / "selected_benchmark" / "benchmark_fit_hardening"

    def _no_fit_path(self, benchmark_id: str) -> Path:
        return self._output_dir(benchmark_id) / "no_fit_argument.md"

    def _manuscript_path(self, benchmark_id: str) -> Path:
        return self._output_dir(benchmark_id) / "manuscript_insertion_text.md"


def render_benchmark_fit_hardening_report(report: BenchmarkFitHardeningReport) -> str:
    lines = [
        f"# Benchmark Fit Hardening Report `{report.benchmark_id}`",
        "",
        f"- Decision: `{report.decision}`",
        f"- Primary grounding candidates: {_fmt(report.primary_candidate_ids)}",
        f"- Auxiliary/sanity candidates: {_fmt(report.auxiliary_candidate_ids)}",
        f"- No-fit candidates: {_fmt(report.no_fit_candidate_ids)}",
        "",
        "## Fit Table",
        "",
        "| Benchmark | Claim support | Use as | What existing benchmark lacks | Limitations |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in report.candidate_rows:
        lines.append(
            "| "
            + " | ".join(
                [
                    f"`{row.candidate_id}` {row.name}",
                    f"`{row.claim_support}`",
                    f"`{row.use_as}`",
                    _cell(row.what_it_lacks),
                    _cell(row.limitations),
                ]
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "## Reviewer Objection Answer",
            "",
            report.reviewer_objection_answer,
            "",
            "## Manuscript Insertion Text",
            "",
            report.manuscript_insertion_text,
            "",
            "## Claim Boundary",
            "",
            "- Primary grounding is allowed only for candidates whose labels, task, sequential structure, "
            "and low-FPR denominator map directly.",
            "- Partial fits are auxiliary or sanity checks, not real collusion benchmark validity.",
            "- No-fit evidence supports why a new benchmark is needed, not why synthetic results are real-world validation.",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def render_no_fit_argument(report: BenchmarkFitHardeningReport) -> str:
    direct_fit = bool(report.primary_candidate_ids)
    lines = [
        f"# Benchmark No-Fit Argument `{report.benchmark_id}`",
        "",
        f"- Decision: `{report.decision}`",
        f"- Direct real benchmark fit found: {str(direct_fit).lower()}",
        "",
        "## No-Fit Table",
        "",
        "| Existing benchmark | Candidate use | What existing benchmark lacks | Paper use |",
        "| --- | --- | --- | --- |",
    ]
    for row in report.candidate_rows:
        lines.append(
            "| "
            + " | ".join(
                [
                    f"`{row.candidate_id}` {row.name}",
                    f"`{row.claim_support}`",
                    _cell(row.what_it_lacks),
                    row.use_as,
                ]
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "## Argument",
            "",
            _no_fit_argument_text(report),
            "",
            "## Manuscript Insertion Text",
            "",
            report.manuscript_insertion_text,
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def _report_from_rows(
    benchmark_id: str,
    search: RealBenchmarkCandidateSearch,
    rows: list[BenchmarkFitCandidateRow],
) -> BenchmarkFitHardeningReport:
    primary = [row.candidate_id for row in rows if row.claim_support == "primary"]
    auxiliary = [row.candidate_id for row in rows if row.claim_support in {"auxiliary", "sanity_check"}]
    no_fit = [row.candidate_id for row in rows if row.claim_support == "no_fit"]
    if primary:
        decision = "credible_real_benchmark_grounding"
    else:
        decision = "new_benchmark_needed"
    manuscript = _manuscript_insertion_text(decision, rows, primary, auxiliary)
    return BenchmarkFitHardeningReport(
        id=f"benchmark-fit-hardening-{slugify(benchmark_id)}",
        benchmark_id=benchmark_id,
        decision=decision,
        candidate_rows=rows,
        primary_candidate_ids=primary,
        auxiliary_candidate_ids=auxiliary,
        no_fit_candidate_ids=no_fit,
        reviewer_objection_answer=_reviewer_objection_answer(decision, rows),
        manuscript_insertion_text=manuscript,
        provenance=Provenance(
            created_by_skill="benchmark-fit-hardening",
            source_ids=[benchmark_id, search.id, *[row.adapter_assessment_id for row in rows]],
            timestamp=utc_now_iso(),
            reasoning_summary="Mapped real benchmark candidates into primary, auxiliary, sanity-check, and no-fit roles.",
        ),
    )


def _use_as(assessment: RealBenchmarkAdapterAssessment) -> str:
    if assessment.expected_claim_support == "primary" and not assessment.blockers:
        return "primary_grounding_candidate"
    if assessment.expected_claim_support in {"auxiliary", "sanity_check"}:
        return "auxiliary_sanity_check"
    return "no_fit_evidence"


def _what_candidate_lacks(candidate: RealBenchmarkCandidate, assessment: RealBenchmarkAdapterAssessment) -> list[str]:
    text = _candidate_text(candidate)
    lacks = []
    if not _has_any(text, ["collusion", "collusive", "covert", "coordination", "cartel"]):
        lacks.append("collusion or covert-coordination labels")
    if not _has_any(text, ["low-fpr", "low false", "false-positive", "specificity", "false alarm"]):
        lacks.append("low false-positive specificity denominator")
    if not _has_any(text, ["sequential", "streaming", "time-series", "online", "repeated", "window", "trajectory"]):
        lacks.append("native sequential windows")
    if not _has_any(text, ["agent", "llm", "tool", "multi-agent", "prompt injection", "deception"]):
        lacks.append("LLM-agent or multi-agent trace substrate")
    if not _has_any(text, ["hard negative", "benign", "honest", "negative"]):
        lacks.append("hard-negative benign coordination labels")
    if not _has_any(text, ["monitor evasion", "evasion", "attack", "defense", "jailbreak", "prompt injection"]):
        lacks.append("monitor-evasion stress cases")
    if assessment.sequentialization_needed:
        lacks.append("non-artificial sequentialization")
    lacks.extend(assessment.schema_mismatches)
    lacks.extend(assessment.label_mismatches)
    lacks.extend(assessment.blockers)
    return _dedupe(lacks) or ["No central fit gap identified by metadata assessment."]


def _reviewer_objection_answer(decision: str, rows: list[BenchmarkFitCandidateRow]) -> str:
    if decision == "credible_real_benchmark_grounding":
        primary = [row for row in rows if row.claim_support == "primary"]
        auxiliary = [row for row in rows if row.claim_support in {"auxiliary", "sanity_check"}]
        return (
            "The reviewer objection 'why not use an existing benchmark?' is answered by using the mapped primary candidate(s) "
            f"{_fmt([row.candidate_id for row in primary])} for bounded grounding, while preserving "
            f"{_fmt([row.candidate_id for row in auxiliary])} as auxiliary or sanity-check evidence only."
        )
    return (
        "The reviewer objection 'why not use an existing benchmark?' is answered by the no-fit table: each searched public "
        "benchmark lacks at least one central ingredient of the paper's claim, such as collusion/covert-coordination labels, "
        "low false-positive specificity denominators, native sequential windows, or hard-negative monitor-evasion structure. "
        "Partial fits are retained only as auxiliary or sanity checks."
    )


def _manuscript_insertion_text(
    decision: str,
    rows: list[BenchmarkFitCandidateRow],
    primary: list[str],
    auxiliary: list[str],
) -> str:
    if decision == "credible_real_benchmark_grounding":
        return (
            "Real benchmark grounding. We searched and mapped existing public benchmarks against the selected protocol. "
            f"The only candidate(s) supporting bounded primary grounding are {_fmt(primary)}. "
            f"Other mapped sources ({_fmt(auxiliary)}) are used only as auxiliary or sanity checks because their labels or task "
            "structure do not support the central collusion-specific low-FPR claim. We therefore keep source-specific limitations "
            "visible in all result tables and do not upgrade auxiliary evidence into deployment-valid benchmark evidence."
        )
    return (
        "Benchmark no-fit and need for a new benchmark. We searched and mapped existing public benchmarks, but none provides the "
        "combination required by our claim: collusion or covert-coordination labels, low false-positive specificity denominators, "
        "native sequential windows, hard-negative benign coordination, and monitor-evasion stress cases. Existing benchmarks are "
        "still useful as auxiliary or sanity checks where noted, but they cannot replace the proposed benchmark without changing "
        "the research question. This no-fit result is the reason the paper introduces a new benchmark rather than reporting "
        "synthetic evidence as real benchmark validity."
    )


def _no_fit_argument_text(report: BenchmarkFitHardeningReport) -> str:
    if report.primary_candidate_ids:
        return (
            "A direct fit exists for bounded grounding, so the no-fit argument applies only to candidates outside the primary set. "
            "Those candidates remain useful for reviewer sanity checks but cannot replace the selected benchmark's central protocol."
        )
    return (
        "No searched public benchmark satisfies the central claim scope. The table records the missing ingredients for each "
        "candidate and preserves partial fits as auxiliary/sanity checks. This directly addresses the reviewer question "
        "'why not use X?' by explaining what X lacks and which, if any, narrow role X can still play."
    )


def _candidate_text(candidate: RealBenchmarkCandidate) -> str:
    return " ".join(
        [
            candidate.name,
            candidate.domain,
            candidate.task_type,
            candidate.relevance_to_selected_benchmark,
            candidate.fit_reason,
            candidate.dataset_access,
            " ".join(candidate.adaptation_required),
            " ".join(candidate.limitations),
        ]
    ).lower()


def _has_any(text: str, needles: list[str]) -> bool:
    return any(needle in text for needle in needles)


def _cell(values: list[str]) -> str:
    return "<br>".join(value.replace("|", "/") for value in values) if values else "none"


def _fmt(values: list[str]) -> str:
    return ", ".join(f"`{value}`" for value in values) if values else "none"


def _dedupe(values: list[str]) -> list[str]:
    seen = set()
    result = []
    for value in values:
        if not value or value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def _merge_candidates(existing: list[RealBenchmarkCandidate], defaults: list[RealBenchmarkCandidate]) -> list[RealBenchmarkCandidate]:
    by_id = {candidate.id: candidate for candidate in existing}
    merged = list(existing)
    for candidate in defaults:
        if candidate.id in by_id:
            continue
        merged.append(candidate)
    return merged
