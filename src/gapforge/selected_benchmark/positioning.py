"""Publication-safe contribution positioning for the selected benchmark."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from gapforge.config import GapForgeConfig
from gapforge.models import Provenance, from_dict, to_plain
from gapforge.project_memory import ProjectMemoryManager
from gapforge.selected_benchmark.prior_work_refresh import (
    SelectedBenchmarkPriorWorkDossier,
    SelectedBenchmarkPriorWorkRefreshManager,
)
from gapforge.selected_benchmark.spec import SelectedBenchmarkManager
from gapforge.state import slugify, utc_now_iso

OVERSTRONG_TERMS = ["first", "novel", "sota", "state-of-the-art", "deployment-valid"]


@dataclass(slots=True)
class ContributionPositioning:
    id: str
    benchmark_id: str
    original_claim: str
    revised_claim: str
    contribution_type: str
    novelty_strength: str
    evidence_basis: list[str] = field(default_factory=list)
    claim_softening_required: bool = False
    reasons: list[str] = field(default_factory=list)
    provenance: Provenance = field(default_factory=lambda: Provenance(created_by_skill="selected-positioning"))


@dataclass(slots=True)
class PositioningReport:
    id: str
    benchmark_id: str
    recommended_claims: list[ContributionPositioning] = field(default_factory=list)
    claims_to_avoid: list[str] = field(default_factory=list)
    reviewer_risks: list[str] = field(default_factory=list)
    citation_requirements: list[str] = field(default_factory=list)
    provenance: Provenance = field(default_factory=lambda: Provenance(created_by_skill="selected-positioning"))


class SelectedBenchmarkPositioningManager:
    """Convert novelty evidence into conservative manuscript contribution claims."""

    def __init__(self, config: GapForgeConfig) -> None:
        self.config = config
        self.config.ensure_dirs()
        self.project_manager = ProjectMemoryManager(config)
        self.benchmark_manager = SelectedBenchmarkManager(config)
        self.prior_work_manager = SelectedBenchmarkPriorWorkRefreshManager(config)

    def build(self, benchmark_id: str) -> PositioningReport:
        spec = self.benchmark_manager.load_spec(benchmark_id)
        dossier = self.prior_work_manager.load_or_refresh(benchmark_id)
        original_claim = "We introduce the first novel SOTA deployment-valid benchmark for sequential low-FPR multi-agent collusion audits."
        positioning = ContributionPositioning(
            id=f"contribution-positioning-{slugify(benchmark_id)}",
            benchmark_id=benchmark_id,
            original_claim=original_claim,
            revised_claim=_revised_claim(dossier.novelty_status),
            contribution_type="evaluation protocol/measurement benchmark",
            novelty_strength=dossier.novelty_status,
            evidence_basis=_evidence_basis(dossier),
            claim_softening_required=_requires_softening(original_claim, dossier.novelty_status),
            reasons=_softening_reasons(dossier.novelty_status, spec.limitations, dossier.closest_prior_work_ids),
            provenance=Provenance(
                created_by_skill="selected-positioning",
                source_ids=[benchmark_id, dossier.id, *dossier.closest_prior_work_ids],
                timestamp=utc_now_iso(),
                reasoning_summary="Softened selected benchmark contribution claims using closest-prior-work dossier evidence.",
            ),
        )
        report = PositioningReport(
            id=f"selected-positioning-report-{slugify(benchmark_id)}",
            benchmark_id=benchmark_id,
            recommended_claims=[positioning],
            claims_to_avoid=_claims_to_avoid(dossier.novelty_status),
            reviewer_risks=_reviewer_risks(dossier, spec.limitations),
            citation_requirements=_citation_requirements(dossier),
            provenance=Provenance(
                created_by_skill="selected-positioning",
                source_ids=[benchmark_id, dossier.id, *dossier.closest_prior_work_ids],
                timestamp=utc_now_iso(),
                reasoning_summary="Rendered publication-safe selected benchmark positioning recommendations.",
            ),
        )
        self._write_report(report)
        return report

    def load_or_build(self, benchmark_id: str) -> PositioningReport:
        path = self.report_path(benchmark_id)
        if not path.exists():
            return self.build(benchmark_id)
        return from_dict(PositioningReport, json.loads(path.read_text(encoding="utf-8")))

    def report_path(self, benchmark_id: str) -> Path:
        spec = self.benchmark_manager.load_spec(benchmark_id)
        return self._positioning_dir(spec.project_id) / "positioning_report.json"

    def _write_report(self, report: PositioningReport) -> None:
        path = self.report_path(report.benchmark_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(to_plain(report), indent=2) + "\n", encoding="utf-8")
        path.with_suffix(".md").write_text(render_positioning_report(report), encoding="utf-8")

    def _positioning_dir(self, project_id: str) -> Path:
        program = self.project_manager.load_project(project_id)
        path = Path(program.project.root_dir) / "selected_benchmark" / "positioning"
        path.mkdir(parents=True, exist_ok=True)
        return path


def render_positioning_report(report: PositioningReport) -> str:
    lines = [
        "# Selected Benchmark Positioning Report",
        "",
        f"- Benchmark ID: `{report.benchmark_id}`",
        "",
        "## Recommended Claims",
        "",
    ]
    for claim in report.recommended_claims:
        lines.extend(
            [
                f"### {claim.contribution_type}",
                "",
                f"- Novelty strength: `{claim.novelty_strength}`",
                f"- Claim softening required: `{claim.claim_softening_required}`",
                f"- Original claim: {claim.original_claim}",
                f"- Revised claim: {claim.revised_claim}",
                f"- Evidence basis: {'; '.join(claim.evidence_basis) or 'none'}",
                f"- Reasons: {'; '.join(claim.reasons) or 'none'}",
                "",
            ]
        )
    lines.extend(["## Claims To Avoid", ""])
    lines.extend([f"- {item}" for item in report.claims_to_avoid] or ["- none"])
    lines.extend(["", "## Reviewer Risks", ""])
    lines.extend([f"- {item}" for item in report.reviewer_risks] or ["- none"])
    lines.extend(["", "## Citation Requirements", ""])
    lines.extend([f"- {item}" for item in report.citation_requirements] or ["- none"])
    return "\n".join(lines).rstrip() + "\n"


def _revised_claim(novelty_strength: str) -> str:
    if novelty_strength == "strong":
        return (
            "We present an evidence-backed evaluation protocol and measurement benchmark for sequential low-FPR "
            "auditing of multi-agent collusion, with explicit synthetic-data limitations."
        )
    if novelty_strength == "duplicate":
        return (
            "We should position the work as an adaptation or replication-oriented benchmark study unless the dossier "
            "identifies a decisive difference from closest prior benchmarks."
        )
    return (
        "We present a candidate evaluation protocol and measurement benchmark for sequential low-FPR multi-agent "
        "collusion audits, supported by curated related work and limited to synthetic benchmark evidence."
    )


def _evidence_basis(dossier: SelectedBenchmarkPriorWorkDossier) -> list[str]:
    basis = [f"Novelty dossier status: {dossier.novelty_status}."]
    if dossier.closest_prior_work_ids:
        basis.append(f"Closest prior work: {', '.join(dossier.closest_prior_work_ids)}.")
    basis.extend(dossier.what_is_new)
    basis.extend(dossier.decisive_difference_needed)
    return _dedupe(basis)


def _requires_softening(original_claim: str, novelty_strength: str) -> bool:
    lowered = original_claim.lower()
    return novelty_strength != "strong" or any(term in lowered for term in OVERSTRONG_TERMS)


def _softening_reasons(novelty_strength: str, limitations: list[str], closest_prior_work_ids: list[str]) -> list[str]:
    reasons: list[str] = []
    if novelty_strength in {"unknown", "plausible", "weak", "duplicate"}:
        reasons.append(f"Novelty is {novelty_strength}, so contribution language must remain careful.")
    if closest_prior_work_ids:
        reasons.append(f"Closest prior work must be cited: {', '.join(closest_prior_work_ids)}.")
    if any("synthetic" in limitation.lower() for limitation in limitations):
        reasons.append("Synthetic-data limitations must remain visible in contribution claims.")
    reasons.append("Avoid first, novel, SOTA, and deployment-valid language unless readiness gates explicitly support it.")
    return _dedupe(reasons)


def _claims_to_avoid(novelty_strength: str) -> list[str]:
    claims = [
        "Do not claim this is the first benchmark unless novelty gates and closest-prior-work dossier support it.",
        "Do not use novel, SOTA, state-of-the-art, or deployment-valid language without explicit evidence gates.",
        "Do not imply real-world deployment validity from synthetic benchmark evidence.",
    ]
    if novelty_strength == "unknown":
        claims.append("Do not use first or novelty language while novelty is unknown.")
    if novelty_strength == "duplicate":
        claims.append("Do not present the core contribution as new while closest prior work appears to cover it.")
    return claims


def _reviewer_risks(dossier: SelectedBenchmarkPriorWorkDossier, limitations: list[str]) -> list[str]:
    risks: list[str] = []
    if dossier.novelty_status == "unknown":
        risks.append("Novelty is unknown because related-work or closest-prior-work coverage remains incomplete.")
    elif dossier.novelty_status in {"plausible", "weak"}:
        risks.append(f"Novelty is only {dossier.novelty_status}; reviewers may ask why closest prior work is not sufficient.")
    elif dossier.novelty_status == "duplicate":
        risks.append("Closest prior work may already cover the core contribution.")
    if dossier.closest_prior_work_ids:
        risks.append(f"Closest prior work citations are mandatory: {', '.join(dossier.closest_prior_work_ids)}.")
    if any("synthetic" in limitation.lower() for limitation in limitations):
        risks.append("Synthetic data does not establish real-world deployment validity.")
    risks.extend(dossier.counterevidence)
    return _dedupe(risks)


def _citation_requirements(dossier: SelectedBenchmarkPriorWorkDossier) -> list[str]:
    if not dossier.closest_prior_work_ids:
        return ["Resolve and cite closest prior work before making contribution or novelty claims."]
    return [f"Closest prior work citation required for paper ID `{paper_id}`." for paper_id in dossier.closest_prior_work_ids]


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            result.append(value)
    return result
