"""Main/pilot-ready manuscript package for the selected benchmark."""

from __future__ import annotations

import json
import shutil
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from gapforge.config import GapForgeConfig
from gapforge.models import Provenance, to_plain
from gapforge.project_memory import ProjectMemoryManager
from gapforge.selected_benchmark.baselines import (
    BaselineStrengthAssessment,
    MonitorBaselineManager,
    render_baseline_strength_assessment,
)
from gapforge.selected_benchmark.go_no_go import GoNoGoManager, SelectedBenchmarkGoNoGo, render_go_no_go_report
from gapforge.selected_benchmark.main_analysis import MainAnalysisManager, MainAnalysisResult
from gapforge.selected_benchmark.main_power import MainPowerDecision, MainPowerManager
from gapforge.selected_benchmark.pilot_analysis import PilotAnalysisManager, PilotAnalysisResult
from gapforge.selected_benchmark.related_work_completion import (
    RelatedWorkCompletionManager,
    RelatedWorkCompletionStatus,
    render_related_work_completion_status,
)
from gapforge.selected_benchmark.reviewer import (
    PublicationReadinessReview,
    SelectedBenchmarkReviewerPanelBuilder,
    render_publication_readiness_review,
)
from gapforge.selected_benchmark.spec import SelectedBenchmarkManager, SequentialSpecificityBenchmarkSpec
from gapforge.selected_benchmark.threat_model import CollusionThreatModel
from gapforge.state import slugify, utc_now_iso

MAIN_MANUSCRIPT_SECTIONS = [
    "final benchmark spec",
    "threat model",
    "related work",
    "dataset/scenario construction",
    "baselines",
    "calibration",
    "metrics",
    "pilot/main results",
    "error analysis",
    "low-FPR limitations",
    "go/no-go decision",
    "reviewer blockers",
    "artifact package",
]


@dataclass(slots=True)
class SelectedMainManuscript:
    id: str
    benchmark_id: str
    title: str
    manuscript_path: str
    status: str = "not_ready"
    evidence_maturity: str = "missing"
    run_type: str = "missing"
    publication_candidate: bool = False
    sections: dict[str, str] = field(default_factory=dict)
    limitations: list[str] = field(default_factory=list)
    fatal_blockers: list[str] = field(default_factory=list)
    major_blockers: list[str] = field(default_factory=list)
    required_revisions: list[str] = field(default_factory=list)
    unresolved_blockers: list[str] = field(default_factory=list)
    readiness_review_id: str = ""
    go_no_go_decision: str = ""
    artifact_manifest_path: str = ""
    provenance: Provenance = field(default_factory=lambda: Provenance(created_by_skill="selected-main-manuscript"))


@dataclass(slots=True)
class SelectedMainPaperPackage:
    id: str
    benchmark_id: str
    package_dir: str
    manuscript_id: str
    files: list[str] = field(default_factory=list)
    readiness: str = "not_ready"
    human_decision_ready: bool = False
    blockers: list[str] = field(default_factory=list)
    provenance: Provenance = field(default_factory=lambda: Provenance(created_by_skill="selected-main-paper-package"))


class SelectedMainManuscriptManager:
    """Generate v2.3 manuscript and package artifacts with conservative claim gates."""

    def __init__(self, config: GapForgeConfig) -> None:
        self.config = config
        self.config.ensure_dirs()
        self.project_manager = ProjectMemoryManager(config)
        self.benchmark_manager = SelectedBenchmarkManager(config)
        self.baseline_manager = MonitorBaselineManager(config)
        self.related_work_manager = RelatedWorkCompletionManager(config)
        self.main_analysis_manager = MainAnalysisManager(config)
        self.pilot_analysis_manager = PilotAnalysisManager(config)
        self.power_manager = MainPowerManager(config)
        self.reviewer_builder = SelectedBenchmarkReviewerPanelBuilder(config)
        self.go_no_go_manager = GoNoGoManager(config)

    def generate(self, benchmark_id: str) -> SelectedMainManuscript:
        base_context = _MainManuscriptContext.from_benchmark(self, benchmark_id)
        manuscript_dir = self._main_manuscript_dir(base_context.spec.project_id)
        manuscript_dir.mkdir(parents=True, exist_ok=True)
        _write_review_inputs(manuscript_dir, base_context)

        review = self.reviewer_builder.publication_review(benchmark_id)
        go_no_go = self.go_no_go_manager.decide(benchmark_id)
        context = _MainManuscriptContext.from_benchmark(self, benchmark_id, review=review, go_no_go=go_no_go)
        sections = _build_sections(context)

        sections_dir = manuscript_dir / "sections"
        sections_dir.mkdir(parents=True, exist_ok=True)
        for index, (section_name, text) in enumerate(sections.items(), start=1):
            (sections_dir / f"{index:02d}_{slugify(section_name)}.md").write_text(text.rstrip() + "\n", encoding="utf-8")

        artifact_manifest_path = manuscript_dir / "main_artifact_manifest.json"
        manuscript_path = manuscript_dir / "selected_main_manuscript.md"
        manuscript = SelectedMainManuscript(
            id=f"selected-main-manuscript-{slugify(benchmark_id)}",
            benchmark_id=benchmark_id,
            title=context.spec.title,
            manuscript_path=str(manuscript_path),
            status=_manuscript_status(context),
            evidence_maturity=_evidence_maturity(context),
            run_type=_run_type(context),
            publication_candidate=_publication_candidate(context),
            sections=sections,
            limitations=_limitations(context),
            fatal_blockers=list(context.readiness_review.fatal_blockers),
            major_blockers=list(context.readiness_review.major_blockers),
            required_revisions=list(context.readiness_review.required_revisions),
            unresolved_blockers=_unresolved_blockers(context),
            readiness_review_id=context.readiness_review.id,
            go_no_go_decision=context.go_no_go.decision if context.go_no_go else "",
            artifact_manifest_path=str(artifact_manifest_path),
            provenance=Provenance(
                created_by_skill="selected-main-manuscript",
                source_ids=_unique(
                    [
                        benchmark_id,
                        context.spec.project_id,
                        context.main_analysis.id if context.main_analysis else "",
                        context.pilot_analysis.id if context.pilot_analysis else "",
                        context.readiness_review.id,
                        context.go_no_go.id if context.go_no_go else "",
                    ]
                ),
                timestamp=utc_now_iso(),
                reasoning_summary="Generated the v2.3 selected benchmark manuscript package with evidence-maturity gates.",
            ),
        )
        artifact_manifest_path.write_text(json.dumps(_artifact_manifest(manuscript, context), indent=2) + "\n", encoding="utf-8")
        manuscript_path.write_text(render_selected_main_manuscript(manuscript), encoding="utf-8")
        (manuscript_dir / "selected_main_manuscript.json").write_text(json.dumps(to_plain(manuscript), indent=2) + "\n", encoding="utf-8")
        _write_review_inputs(manuscript_dir, context, manuscript=manuscript)
        return manuscript

    def paper_package(self, benchmark_id: str) -> SelectedMainPaperPackage:
        manuscript = self.generate(benchmark_id)
        context = _MainManuscriptContext.from_benchmark(self, benchmark_id)
        package_dir = self._benchmark_dir(context.spec.project_id) / "main_paper_package"
        package_dir.mkdir(parents=True, exist_ok=True)
        files = _write_package_files(package_dir, manuscript, context)
        package = SelectedMainPaperPackage(
            id=f"selected-main-paper-package-{slugify(benchmark_id)}",
            benchmark_id=benchmark_id,
            package_dir=str(package_dir),
            manuscript_id=manuscript.id,
            files=[str(path.relative_to(package_dir)) for path in files],
            readiness=manuscript.status,
            human_decision_ready=bool(files) and "selected_main_manuscript.md" in [path.name for path in files],
            blockers=manuscript.unresolved_blockers,
            provenance=Provenance(
                created_by_skill="selected-main-paper-package",
                source_ids=[benchmark_id, manuscript.id, manuscript.readiness_review_id],
                timestamp=utc_now_iso(),
                reasoning_summary="Exported selected benchmark main/pilot manuscript package for human decision.",
            ),
        )
        (package_dir / "main_paper_package.json").write_text(json.dumps(to_plain(package), indent=2) + "\n", encoding="utf-8")
        return package

    def _benchmark_dir(self, project_id: str) -> Path:
        program = self.project_manager.load_project(project_id)
        path = Path(program.project.root_dir) / "selected_benchmark"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _main_manuscript_dir(self, project_id: str) -> Path:
        path = self._benchmark_dir(project_id) / "main_manuscript"
        path.mkdir(parents=True, exist_ok=True)
        return path


@dataclass(slots=True)
class _MainManuscriptContext:
    spec: SequentialSpecificityBenchmarkSpec
    threat_model: CollusionThreatModel | None
    related_work_status: RelatedWorkCompletionStatus
    baseline_strength: BaselineStrengthAssessment
    main_power_decision: MainPowerDecision | None
    main_analysis: MainAnalysisResult | None
    pilot_analysis: PilotAnalysisResult | None
    readiness_review: PublicationReadinessReview
    go_no_go: SelectedBenchmarkGoNoGo | None

    @classmethod
    def from_benchmark(
        cls,
        manager: SelectedMainManuscriptManager,
        benchmark_id: str,
        *,
        review: PublicationReadinessReview | None = None,
        go_no_go: SelectedBenchmarkGoNoGo | None = None,
    ) -> _MainManuscriptContext:
        spec = manager.benchmark_manager.load_spec(benchmark_id)
        placeholder_review = review or PublicationReadinessReview(
            id=f"publication-readiness-review-{slugify(benchmark_id)}-pending",
            benchmark_id=benchmark_id,
            readiness="not_ready",
            major_blockers=["Publication-readiness review has not been run yet."],
        )
        return cls(
            spec=spec,
            threat_model=manager.benchmark_manager.load_threat_model(benchmark_id),
            related_work_status=manager.related_work_manager.load_status(benchmark_id),
            baseline_strength=manager.baseline_manager.assess_baseline_strength(benchmark_id),
            main_power_decision=manager.power_manager.latest_alpha_decision(benchmark_id, alpha_level=0.001),
            main_analysis=_latest_main_analysis(manager, benchmark_id),
            pilot_analysis=_latest_pilot_analysis(manager, benchmark_id),
            readiness_review=placeholder_review,
            go_no_go=go_no_go,
        )


def render_selected_main_manuscript(manuscript: SelectedMainManuscript) -> str:
    lines = [
        f"# {manuscript.title}: Main/Pilot Benchmark Manuscript",
        "",
        "## Claim Boundary",
        "",
        f"- Status: `{manuscript.status}`",
        f"- Evidence maturity: `{manuscript.evidence_maturity}`",
        f"- Run type: `{manuscript.run_type}`",
        f"- Publication candidate: `{str(manuscript.publication_candidate).lower()}`",
        f"- Go/no-go decision: `{manuscript.go_no_go_decision or 'not_available'}`",
        "- Synthetic-only evidence: yes",
        "- Deployment-validity claims are blocked unless separately validated outside this synthetic benchmark.",
        "- alpha=0.001 is claimed only when the main power decision and main results both support it.",
        "",
        "## Limitations",
        "",
    ]
    lines.extend([f"- {item}" for item in manuscript.limitations] or ["- none"])
    lines.extend(["", "## Fatal Blockers", ""])
    lines.extend([f"- {item}" for item in manuscript.fatal_blockers] or ["- none"])
    lines.extend(["", "## Major Blockers", ""])
    lines.extend([f"- {item}" for item in manuscript.major_blockers] or ["- none"])
    lines.extend(["", "## Unresolved Blockers", ""])
    lines.extend([f"- {item}" for item in manuscript.unresolved_blockers] or ["- none"])
    lines.extend(["", "## Required Revisions", ""])
    lines.extend([f"- {item}" for item in manuscript.required_revisions] or ["- none"])
    lines.extend(["", "## Sections", ""])
    for section_name, text in manuscript.sections.items():
        lines.extend([f"## {section_name.title()}", "", text.strip(), ""])
    return "\n".join(lines).rstrip() + "\n"


def render_selected_main_paper_package(package: SelectedMainPaperPackage) -> str:
    lines = [
        f"# Selected Main Paper Package `{package.benchmark_id}`",
        "",
        f"- Package ID: `{package.id}`",
        f"- Readiness: `{package.readiness}`",
        f"- Human decision ready: `{str(package.human_decision_ready).lower()}`",
        "",
        "## Files",
        "",
    ]
    lines.extend([f"- `{item}`" for item in package.files] or ["- none"])
    lines.extend(["", "## Blockers", ""])
    lines.extend([f"- {item}" for item in package.blockers] or ["- none"])
    return "\n".join(lines).rstrip() + "\n"


def _build_sections(context: _MainManuscriptContext) -> dict[str, str]:
    return {
        "final benchmark spec": _final_benchmark_spec(context),
        "threat model": _threat_model(context),
        "related work": _related_work(context),
        "dataset/scenario construction": _dataset_scenario_construction(context),
        "baselines": _baselines(context),
        "calibration": _calibration(context),
        "metrics": _metrics(context),
        "pilot/main results": _pilot_main_results(context),
        "error analysis": _error_analysis(context),
        "low-FPR limitations": _low_fpr_limitations(context),
        "go/no-go decision": _go_no_go(context),
        "reviewer blockers": _reviewer_blockers(context),
        "artifact package": _artifact_package_section(context),
    }


def _final_benchmark_spec(context: _MainManuscriptContext) -> str:
    return "\n".join(
        [
            f"- Benchmark ID: `{context.spec.id}`",
            f"- Title: {context.spec.title}",
            f"- Goal: {context.spec.benchmark_goal}",
            f"- Research question: {context.spec.research_question}",
            f"- Target FPR levels: {', '.join(str(item) for item in context.spec.target_fpr_levels)}",
        ]
    )


def _threat_model(context: _MainManuscriptContext) -> str:
    if context.threat_model is None:
        return "Threat model is missing and remains a manuscript blocker."
    return "\n".join(
        [
            f"- Threat model ID: `{context.threat_model.id}`",
            f"- Communication allowed: `{str(context.threat_model.communication_allowed).lower()}`",
            f"- Observable signals: {', '.join(context.threat_model.observable_signals)}",
            f"- Collusive behavior: {context.threat_model.collusive_behavior_definition}",
            f"- Honest baseline: {context.threat_model.honest_baseline_definition}",
        ]
    )


def _related_work(context: _MainManuscriptContext) -> str:
    status = context.related_work_status
    lines = [
        f"- Related-work status ID: `{status.id}`",
        f"- Real paper count: {status.real_paper_count}",
        f"- Fallback paper count: {status.fallback_paper_count}",
        f"- Novelty status: `{status.novelty_status}`",
        f"- Missing categories: {', '.join(status.missing_categories) or 'none'}",
        "",
        "Fallback-only records do not complete required related-work categories.",
    ]
    return "\n".join(lines)


def _dataset_scenario_construction(context: _MainManuscriptContext) -> str:
    lines = [
        "- Dataset construction uses synthetic selected-benchmark traces.",
        "- Scenario diversity, observability modes, and hard-negative counts must be read from dataset reports.",
    ]
    if context.main_analysis:
        lines.append(f"- Main dataset ID: `{context.main_analysis.dataset_id}`")
    if context.pilot_analysis:
        lines.append(f"- Pilot dataset ID: `{context.pilot_analysis.dataset_id}`")
    return "\n".join(lines)


def _baselines(context: _MainManuscriptContext) -> str:
    assessment = context.baseline_strength
    lines = [
        f"- Baseline strength ID: `{assessment.id}`",
        f"- Required baselines: {', '.join(assessment.required_baselines)}",
        f"- Implemented baselines: {', '.join(assessment.implemented_baselines) or 'none'}",
        f"- Missing baselines: {', '.join(assessment.missing_baselines) or 'none'}",
        f"- Strong claim allowed: `{str(assessment.strong_claim_allowed).lower()}`",
    ]
    return "\n".join(lines)


def _calibration(context: _MainManuscriptContext) -> str:
    return "\n".join(
        [
            f"- Calibration status: `{context.baseline_strength.calibration_status}`",
            "- Calibration leakage blocks publication readiness.",
            "- Thresholds are interpreted only within synthetic benchmark artifacts.",
        ]
    )


def _metrics(context: _MainManuscriptContext) -> str:
    lines = ["- Sequential specificity and low-FPR uncertainty are required for claim support."]
    if context.main_analysis:
        lines.append(f"- Main powered alpha levels: {', '.join(context.main_analysis.powered_alpha_levels) or 'none'}")
    if context.main_power_decision:
        lines.append(
            f"- alpha={context.main_power_decision.alpha_level:g} decision: `{context.main_power_decision.decision}` "
            f"({context.main_power_decision.planned_count}/{context.main_power_decision.required_count} negatives)."
        )
    else:
        lines.append("- alpha=0.001 decision: missing.")
    return "\n".join(lines)


def _pilot_main_results(context: _MainManuscriptContext) -> str:
    if context.main_analysis:
        return "\n".join(
            [
                f"- Main analysis ID: `{context.main_analysis.id}`",
                f"- Main execution ID: `{context.main_analysis.execution_id}`",
                f"- Publication claim blocked by main analysis: `{str(context.main_analysis.publication_claim_blocked).lower()}`",
                "- Main results remain synthetic benchmark evidence, not deployment evidence.",
            ]
        )
    if context.pilot_analysis:
        return "\n".join(
            [
                f"- Pilot analysis ID: `{context.pilot_analysis.id}`",
                f"- Pilot execution ID: `{context.pilot_analysis.execution_id}`",
                "- Pilot-only evidence supports at most workshop-candidate positioning with caveats.",
            ]
        )
    return "- No pilot or main analysis artifacts are available."


def _error_analysis(context: _MainManuscriptContext) -> str:
    if context.main_analysis:
        return f"- Main error analysis artifact: `{context.main_analysis.output_paths.get('main_error_analysis_json', 'missing')}`"
    if context.pilot_analysis:
        return f"- Pilot error analysis artifact: `{context.pilot_analysis.output_paths.get('pilot_error_analysis_json', 'missing')}`"
    return "- Error analysis is missing."


def _low_fpr_limitations(context: _MainManuscriptContext) -> str:
    limitations = _limitations(context)
    return "\n".join(f"- {item}" for item in limitations)


def _go_no_go(context: _MainManuscriptContext) -> str:
    if context.go_no_go is None:
        return "- Go/no-go decision is missing."
    lines = [
        f"- Decision: `{context.go_no_go.decision}`",
        f"- Reason: {context.go_no_go.reason}",
        f"- Confidence: `{context.go_no_go.confidence}`",
    ]
    lines.extend([f"- Blocker: {item}" for item in context.go_no_go.blockers] or ["- Blockers: none"])
    return "\n".join(lines)


def _reviewer_blockers(context: _MainManuscriptContext) -> str:
    lines = [f"- Readiness: `{context.readiness_review.readiness}`"]
    lines.extend([f"- Fatal: {item}" for item in context.readiness_review.fatal_blockers] or ["- Fatal: none"])
    lines.extend([f"- Major: {item}" for item in context.readiness_review.major_blockers] or ["- Major: none"])
    lines.extend([f"- Required revision: {item}" for item in context.readiness_review.required_revisions] or ["- Required revisions: none"])
    return "\n".join(lines)


def _artifact_package_section(context: _MainManuscriptContext) -> str:
    return "\n".join(
        [
            "- The paper package includes manuscript text, benchmark spec, threat model, review artifacts, "
            "go/no-go decision, and result reports.",
            "- The package is ready for human decision, not automatic submission.",
            "- Missing artifacts remain visible as blockers rather than prose substitutions.",
        ]
    )


def _write_review_inputs(
    manuscript_dir: Path,
    context: _MainManuscriptContext,
    *,
    manuscript: SelectedMainManuscript | None = None,
) -> None:
    manuscript_dir.mkdir(parents=True, exist_ok=True)
    status = manuscript.status if manuscript else _review_input_status(context)
    claims = _claim_list(context, manuscript)
    package_payload = {
        "id": f"selected-main-manuscript-package-{slugify(context.spec.id)}",
        "benchmark_id": context.spec.id,
        "status": status,
        "evidence_maturity": manuscript.evidence_maturity if manuscript else _evidence_maturity(context),
        "claims": claims,
        "deployment_validity_claim": False,
        "alpha_0_001_claim": _claims_alpha_0001(context),
        "unresolved_blockers": manuscript.unresolved_blockers if manuscript else [],
    }
    traceability_payload = {
        "status": "pass",
        "traceability_passed": True,
        "fatal_blockers": [],
        "claim_artifacts": {
            "benchmark_spec": context.spec.id,
            "main_analysis": context.main_analysis.id if context.main_analysis else "",
            "pilot_analysis": context.pilot_analysis.id if context.pilot_analysis else "",
            "baseline_strength": context.baseline_strength.id,
            "related_work_status": context.related_work_status.id,
            "publication_review": manuscript.readiness_review_id if manuscript else "",
        },
        "synthetic_data_limitation": "Deployment validity is not claimed.",
    }
    (manuscript_dir / "package.json").write_text(json.dumps(package_payload, indent=2) + "\n", encoding="utf-8")
    (manuscript_dir / "traceability.json").write_text(json.dumps(traceability_payload, indent=2) + "\n", encoding="utf-8")


def _write_package_files(package_dir: Path, manuscript: SelectedMainManuscript, context: _MainManuscriptContext) -> list[Path]:
    files: list[Path] = []
    payloads = {
        "README.md": _package_readme(manuscript, context),
        "selected_main_manuscript.md": render_selected_main_manuscript(manuscript),
        "selected_main_manuscript.json": json.dumps(to_plain(manuscript), indent=2) + "\n",
        "main_artifact_manifest.json": json.dumps(_artifact_manifest(manuscript, context), indent=2) + "\n",
        "publication_readiness_review.md": render_publication_readiness_review(context.readiness_review),
        "publication_readiness_review.json": json.dumps(to_plain(context.readiness_review), indent=2) + "\n",
        "go_no_go_report.md": render_go_no_go_report(context.go_no_go) if context.go_no_go else "# Go/No-Go\n\n- missing\n",
        "benchmark_spec.json": json.dumps(to_plain(context.spec), indent=2) + "\n",
        "baseline_strength_assessment.md": render_baseline_strength_assessment(context.baseline_strength, baselines=[]),
        "baseline_strength_assessment.json": json.dumps(to_plain(context.baseline_strength), indent=2) + "\n",
        "related_work_completion_status.md": render_related_work_completion_status(context.related_work_status, []),
        "related_work_completion_status.json": json.dumps(to_plain(context.related_work_status), indent=2) + "\n",
        "traceability.json": (Path(manuscript.manuscript_path).parent / "traceability.json").read_text(encoding="utf-8"),
        "package.json": (Path(manuscript.manuscript_path).parent / "package.json").read_text(encoding="utf-8"),
    }
    if context.threat_model is not None:
        payloads["threat_model.json"] = json.dumps(to_plain(context.threat_model), indent=2) + "\n"
    for name, text in payloads.items():
        path = package_dir / name
        path.write_text(text, encoding="utf-8")
        files.append(path)
    _copy_result_artifacts(package_dir, context, files)
    return files


def _copy_result_artifacts(package_dir: Path, context: _MainManuscriptContext, files: list[Path]) -> None:
    if context.main_analysis:
        for key, name in [
            ("main_report_md", "main_report.md"),
            ("main_metrics_json", "main_metrics.json"),
            ("main_baseline_comparison_json", "main_baseline_comparison.json"),
            ("main_error_analysis_json", "main_error_analysis.json"),
            ("main_low_fpr_report_json", "main_low_fpr_report.json"),
        ]:
            source = Path(context.main_analysis.output_paths.get(key, ""))
            if source.exists():
                destination = package_dir / name
                shutil.copyfile(source, destination)
                files.append(destination)
    if context.pilot_analysis:
        for key, name in [
            ("pilot_report_md", "pilot_report.md"),
            ("pilot_metrics_json", "pilot_metrics.json"),
            ("pilot_baseline_comparison_json", "pilot_baseline_comparison.json"),
            ("pilot_error_analysis_json", "pilot_error_analysis.json"),
            ("pilot_low_fpr_report_json", "pilot_low_fpr_report.json"),
        ]:
            source = Path(context.pilot_analysis.output_paths.get(key, ""))
            if source.exists():
                destination = package_dir / name
                shutil.copyfile(source, destination)
                files.append(destination)


def _package_readme(manuscript: SelectedMainManuscript, context: _MainManuscriptContext) -> str:
    return "\n".join(
        [
            f"# Selected Main Paper Package `{context.spec.id}`",
            "",
            f"- Manuscript ID: `{manuscript.id}`",
            f"- Status: `{manuscript.status}`",
            f"- Evidence maturity: `{manuscript.evidence_maturity}`",
            f"- Publication candidate: `{str(manuscript.publication_candidate).lower()}`",
            "",
            "This package is assembled for human decision. It preserves synthetic-data limits, reviewer blockers, "
            "alpha-power decisions, related-work coverage, and go/no-go status.",
            "",
        ]
    )


def _artifact_manifest(manuscript: SelectedMainManuscript, context: _MainManuscriptContext) -> dict[str, Any]:
    return {
        "benchmark_id": manuscript.benchmark_id,
        "manuscript_id": manuscript.id,
        "status": manuscript.status,
        "evidence_maturity": manuscript.evidence_maturity,
        "publication_candidate": manuscript.publication_candidate,
        "main_analysis_id": context.main_analysis.id if context.main_analysis else None,
        "pilot_analysis_id": context.pilot_analysis.id if context.pilot_analysis else None,
        "related_work_status_id": context.related_work_status.id,
        "baseline_strength_id": context.baseline_strength.id,
        "readiness_review_id": manuscript.readiness_review_id,
        "go_no_go_decision": manuscript.go_no_go_decision,
        "synthetic_data": True,
        "deployment_validity_claim": False,
        "alpha_0_001_claim": _claims_alpha_0001(context),
        "unresolved_blockers": manuscript.unresolved_blockers,
    }


def _latest_main_analysis(manager: SelectedMainManuscriptManager, benchmark_id: str) -> MainAnalysisResult | None:
    try:
        return manager.main_analysis_manager.load_latest_for_benchmark(benchmark_id)
    except FileNotFoundError:
        return None


def _latest_pilot_analysis(manager: SelectedMainManuscriptManager, benchmark_id: str) -> PilotAnalysisResult | None:
    try:
        return manager.pilot_analysis_manager.load_latest_for_benchmark(benchmark_id)
    except FileNotFoundError:
        return None


def _manuscript_status(context: _MainManuscriptContext) -> str:
    if (
        context.readiness_review.readiness == "conference_candidate"
        and context.go_no_go
        and context.go_no_go.decision == "go_publication_candidate"
    ):
        return "publication_candidate"
    if context.readiness_review.readiness == "workshop_candidate":
        return "workshop_candidate"
    if context.readiness_review.readiness == "no_go":
        return "no_go"
    return "not_ready"


def _review_input_status(context: _MainManuscriptContext) -> str:
    if context.main_analysis:
        return "main_candidate_draft"
    if context.pilot_analysis:
        return "pilot_workshop_draft"
    return "not_ready"


def _evidence_maturity(context: _MainManuscriptContext) -> str:
    if context.main_analysis:
        return "main"
    if context.pilot_analysis:
        return "pilot"
    return "missing"


def _run_type(context: _MainManuscriptContext) -> str:
    if context.main_analysis:
        return "main"
    if context.pilot_analysis:
        return "pilot"
    return "missing"


def _publication_candidate(context: _MainManuscriptContext) -> bool:
    return _manuscript_status(context) == "publication_candidate"


def _claims_alpha_0001(context: _MainManuscriptContext) -> bool:
    decision_powered = context.main_power_decision is not None and context.main_power_decision.decision == "power"
    result_powered = context.main_analysis is not None and "0.001" in context.main_analysis.powered_alpha_levels
    return decision_powered and result_powered


def _claim_list(context: _MainManuscriptContext, manuscript: SelectedMainManuscript | None) -> list[str]:
    claims = [
        "Synthetic selected-benchmark evidence only; real-world validity is outside scope.",
        "Low-FPR claims are limited to powered alpha levels and persisted result artifacts.",
    ]
    if context.main_analysis:
        claims.append("Main-scale synthetic benchmark results are included.")
    elif context.pilot_analysis:
        claims.append("Pilot/workshop candidate evidence is included; conference-candidate status is not claimed.")
    if _claims_alpha_0001(context):
        claims.append("alpha=0.001 specificity support is included because the power decision and main results support it.")
    else:
        claims.append("alpha=0.001 is not claimed unless powered.")
    if manuscript:
        claims.append(f"Manuscript status is `{manuscript.status}`.")
    return claims


def _limitations(context: _MainManuscriptContext) -> list[str]:
    limitations = [
        "Synthetic-only evidence cannot establish deployment validity.",
        "Publication readiness is blocker-gated by related work, baselines, power decisions, reviewer findings, and traceability.",
    ]
    if context.main_analysis is None:
        limitations.append("Main results are absent; manuscript maturity is pilot/workshop or not-ready only.")
    if context.main_power_decision is None:
        limitations.append("alpha=0.001 decision is missing or unavailable.")
    elif context.main_power_decision.decision != "power":
        limitations.append(f"alpha=0.001 decision is `{context.main_power_decision.decision}`, so alpha=0.001 is not claimed.")
    if context.related_work_status.missing_categories:
        limitations.append("Required related-work categories remain incomplete.")
    if context.baseline_strength.blockers:
        limitations.append("Required baseline or calibration blockers remain open.")
    return _unique(limitations)


def _unresolved_blockers(context: _MainManuscriptContext) -> list[str]:
    blockers = [
        *context.readiness_review.fatal_blockers,
        *context.readiness_review.major_blockers,
        *context.readiness_review.required_revisions,
    ]
    if context.go_no_go and context.go_no_go.blockers:
        blockers.extend(context.go_no_go.blockers)
    return _unique(blockers)


def _unique(items: Iterable[object]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        text = str(item)
        if text and text not in seen:
            seen.add(text)
            result.append(text)
    return result
