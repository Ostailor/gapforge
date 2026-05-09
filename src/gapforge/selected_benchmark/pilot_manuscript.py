"""Pilot-maturity manuscript package for the selected benchmark."""

from __future__ import annotations

import json
import shutil
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from gapforge.config import GapForgeConfig
from gapforge.models import Provenance, from_dict, to_plain
from gapforge.project_memory import ProjectMemoryManager
from gapforge.selected_benchmark.baselines import MonitorBaselineManager, MonitorCalibrationRecord
from gapforge.selected_benchmark.pilot_analysis import PilotAnalysisManager, PilotAnalysisResult
from gapforge.selected_benchmark.pilot_dataset import PilotDatasetBuilder, PilotTraceDataset
from gapforge.selected_benchmark.pilot_power import PilotPowerAssessment, PilotPowerManager
from gapforge.selected_benchmark.related_work import (
    SelectedBenchmarkRelatedWorkManager,
    SelectedNoveltyPositioning,
    SelectedPriorWorkRecall,
    SelectedRelatedWorkMatrix,
    render_novelty_positioning,
    render_prior_work_recall,
    render_related_work_matrix,
)
from gapforge.selected_benchmark.reviewer import (
    SelectedBenchmarkReviewerPanelBuilder,
    SelectedBenchmarkReviewPanel,
    render_pilot_required_fixes,
    render_pilot_review_panel,
)
from gapforge.selected_benchmark.spec import SelectedBenchmarkManager, SequentialSpecificityBenchmarkSpec
from gapforge.selected_benchmark.threat_model import CollusionThreatModel
from gapforge.state import slugify, utc_now_iso

PILOT_MANUSCRIPT_SECTIONS = [
    "motivation",
    "benchmark definition",
    "threat model",
    "pilot trace dataset",
    "baseline monitors",
    "calibration",
    "sequential specificity metrics",
    "pilot results",
    "low-FPR limitations",
    "related work",
    "reviewer blockers",
    "path to main benchmark",
]


@dataclass(slots=True)
class SelectedPilotManuscript:
    id: str
    benchmark_id: str
    title: str
    manuscript_path: str
    run_type: str = "pilot"
    synthetic_data_label: str = "synthetic_pilot_data"
    sections: dict[str, str] = field(default_factory=dict)
    limitations: list[str] = field(default_factory=list)
    reviewer_blockers: list[str] = field(default_factory=list)
    main_benchmark_requirements: list[str] = field(default_factory=list)
    readiness: str = "not_publication_ready"
    publication_ready: bool = False
    provenance: Provenance = field(default_factory=lambda: Provenance(created_by_skill="selected-benchmark-pilot-manuscript"))


@dataclass(slots=True)
class SelectedPilotPaperPackage:
    id: str
    benchmark_id: str
    package_dir: str
    manuscript_id: str
    files: list[str] = field(default_factory=list)
    readiness: str = "not_publication_ready"
    blockers: list[str] = field(default_factory=list)
    provenance: Provenance = field(default_factory=lambda: Provenance(created_by_skill="selected-benchmark-pilot-paper-package"))


class SelectedPilotManuscriptManager:
    """Generate pilot-labeled manuscript and paper-package artifacts."""

    def __init__(self, config: GapForgeConfig) -> None:
        self.config = config
        self.config.ensure_dirs()
        self.project_manager = ProjectMemoryManager(config)
        self.benchmark_manager = SelectedBenchmarkManager(config)
        self.baseline_manager = MonitorBaselineManager(config)
        self.dataset_builder = PilotDatasetBuilder(config)
        self.power_manager = PilotPowerManager(config)
        self.analysis_manager = PilotAnalysisManager(config)
        self.related_work_manager = SelectedBenchmarkRelatedWorkManager(config)
        self.reviewer_builder = SelectedBenchmarkReviewerPanelBuilder(config)

    def generate(self, benchmark_id: str) -> SelectedPilotManuscript:
        context = _PilotManuscriptContext.from_benchmark(self, benchmark_id)
        manuscript_dir = self._benchmark_dir(context.spec.project_id) / "pilot_manuscript"
        sections_dir = manuscript_dir / "sections"
        sections_dir.mkdir(parents=True, exist_ok=True)
        sections = _build_sections(context)
        for index, (section_name, text) in enumerate(sections.items(), start=1):
            (sections_dir / f"{index:02d}_{slugify(section_name)}.md").write_text(text.rstrip() + "\n", encoding="utf-8")

        manuscript_path = manuscript_dir / "selected_pilot_manuscript.md"
        manuscript = SelectedPilotManuscript(
            id=f"selected-pilot-manuscript-{slugify(benchmark_id)}",
            benchmark_id=benchmark_id,
            title=context.spec.title,
            manuscript_path=str(manuscript_path),
            run_type="pilot",
            synthetic_data_label="synthetic_pilot_data",
            sections=sections,
            limitations=_pilot_limitations(context),
            reviewer_blockers=_unique([*context.review_panel.fatal_blockers, *context.review_panel.required_fixes]),
            main_benchmark_requirements=_main_benchmark_requirements(context),
            readiness=_readiness(context),
            publication_ready=False,
            provenance=Provenance(
                created_by_skill="selected-benchmark-pilot-manuscript",
                source_ids=_unique(
                    [
                        benchmark_id,
                        context.spec.project_id,
                        context.dataset.id if context.dataset else "",
                        context.analysis.id if context.analysis else "",
                        context.power_assessment.id if context.power_assessment else "",
                        context.prior_work.id if context.prior_work else "",
                        context.related_work.id if context.related_work else "",
                        context.review_panel.benchmark_id,
                    ]
                ),
                timestamp=utc_now_iso(),
                reasoning_summary=(
                    "Generated a pilot-maturity manuscript package that preserves synthetic-data, low-FPR power, "
                    "related-work, and reviewer-blocker boundaries."
                ),
            ),
        )
        manuscript_path.write_text(render_selected_pilot_manuscript(manuscript), encoding="utf-8")
        (manuscript_dir / "selected_pilot_manuscript.json").write_text(json.dumps(to_plain(manuscript), indent=2) + "\n", encoding="utf-8")
        return manuscript

    def paper_package(self, benchmark_id: str) -> SelectedPilotPaperPackage:
        manuscript = self.generate(benchmark_id)
        context = _PilotManuscriptContext.from_benchmark(self, benchmark_id)
        package_dir = self._benchmark_dir(context.spec.project_id) / "pilot_paper_package"
        package_dir.mkdir(parents=True, exist_ok=True)
        files = _write_package_files(package_dir, manuscript, context)
        package = SelectedPilotPaperPackage(
            id=f"selected-pilot-paper-package-{slugify(benchmark_id)}",
            benchmark_id=benchmark_id,
            package_dir=str(package_dir),
            manuscript_id=manuscript.id,
            files=[str(path.relative_to(package_dir)) for path in files],
            readiness=manuscript.readiness,
            blockers=manuscript.reviewer_blockers,
            provenance=Provenance(
                created_by_skill="selected-benchmark-pilot-paper-package",
                source_ids=[benchmark_id, manuscript.id, context.review_panel.benchmark_id],
                timestamp=utc_now_iso(),
                reasoning_summary="Exported the selected benchmark pilot paper package without publication-readiness overclaiming.",
            ),
        )
        (package_dir / "pilot_paper_package.json").write_text(json.dumps(to_plain(package), indent=2) + "\n", encoding="utf-8")
        return package

    def _benchmark_dir(self, project_id: str) -> Path:
        program = self.project_manager.load_project(project_id)
        path = Path(program.project.root_dir) / "selected_benchmark"
        path.mkdir(parents=True, exist_ok=True)
        return path


@dataclass(slots=True)
class _PilotManuscriptContext:
    spec: SequentialSpecificityBenchmarkSpec
    threat_model: CollusionThreatModel | None
    dataset: PilotTraceDataset | None
    power_assessment: PilotPowerAssessment | None
    analysis: PilotAnalysisResult | None
    calibration_records: list[MonitorCalibrationRecord]
    prior_work: SelectedPriorWorkRecall | None
    related_work: SelectedRelatedWorkMatrix | None
    novelty: SelectedNoveltyPositioning | None
    review_panel: SelectedBenchmarkReviewPanel

    @classmethod
    def from_benchmark(cls, manager: SelectedPilotManuscriptManager, benchmark_id: str) -> _PilotManuscriptContext:
        spec = manager.benchmark_manager.load_spec(benchmark_id)
        dataset = _latest_pilot_dataset(manager, spec)
        analysis = _latest_analysis(manager, benchmark_id)
        return cls(
            spec=spec,
            threat_model=manager.benchmark_manager.load_threat_model(benchmark_id),
            dataset=dataset,
            power_assessment=_power_assessment(manager, dataset),
            analysis=analysis,
            calibration_records=_calibration_records(manager, benchmark_id),
            prior_work=_prior_work(manager, benchmark_id),
            related_work=_related_work(manager, benchmark_id),
            novelty=_novelty(manager, benchmark_id),
            review_panel=manager.reviewer_builder.pilot_review(benchmark_id),
        )


def render_selected_pilot_manuscript(manuscript: SelectedPilotManuscript) -> str:
    lines = [
        f"# {manuscript.title}: Pilot Benchmark Study",
        "",
        "## Claim Boundary",
        "",
        "- Run type: `pilot`",
        "- Synthetic pilot data: yes",
        "- Publication-ready claim: blocked",
        f"- Readiness: `{manuscript.readiness}`",
        "- Status: not publication-ready",
        "- This manuscript is a pilot-maturity package, not a main benchmark package.",
        "- It reports bounded false-positive evidence only for alpha levels supported by the pilot data.",
        "",
        "## Prominent Limitations",
        "",
    ]
    lines.extend([f"- {item}" for item in manuscript.limitations] or ["- none"])
    lines.extend(["", "## Reviewer Blockers", ""])
    lines.extend([f"- {item}" for item in manuscript.reviewer_blockers] or ["- none"])
    lines.extend(["", "## Main Benchmark Requirements", ""])
    lines.extend([f"- {item}" for item in manuscript.main_benchmark_requirements] or ["- none"])
    lines.extend(["", "## Sections", ""])
    for section_name, text in manuscript.sections.items():
        lines.extend([f"## {section_name.title()}", "", text.strip(), ""])
    return "\n".join(lines).rstrip() + "\n"


def _build_sections(context: _PilotManuscriptContext) -> dict[str, str]:
    return {
        "motivation": _motivation(context),
        "benchmark definition": _benchmark_definition(context),
        "threat model": _threat_model(context),
        "pilot trace dataset": _pilot_trace_dataset(context),
        "baseline monitors": _baseline_monitors(context),
        "calibration": _calibration(context),
        "sequential specificity metrics": _sequential_metrics(context),
        "pilot results": _pilot_results(context),
        "low-FPR limitations": _low_fpr_limitations(context),
        "related work": _related_work_section(context),
        "reviewer blockers": _reviewer_blockers(context),
        "path to main benchmark": _path_to_main(context),
    }


def _motivation(context: _PilotManuscriptContext) -> str:
    return "\n".join(
        [
            f"The selected idea asks: {context.spec.research_question}",
            "",
            "The pilot study evaluates whether the benchmark machinery can support low false-positive-rate collusion audits "
            "on expanded synthetic honest-null and collusive-alternative traces.",
            "The contribution is positioned as a benchmark/evaluation protocol at pilot maturity.",
        ]
    )


def _benchmark_definition(context: _PilotManuscriptContext) -> str:
    lines = [
        context.spec.benchmark_goal,
        "",
        f"- Sequential setting: {context.spec.sequential_setting}",
        f"- Target FPR levels in spec: {', '.join(str(level) for level in context.spec.target_fpr_levels)}",
        f"- Observability modes: {', '.join(context.spec.observability_modes)}",
        "- Pilot/main maturity distinction: smoke validates wiring; pilot estimates benchmark behavior; main requires larger evidence.",
    ]
    return "\n".join(lines)


def _threat_model(context: _PilotManuscriptContext) -> str:
    if context.threat_model is None:
        return "Threat model is missing and remains a reviewer blocker for pilot maturity."
    return "\n".join(
        [
            context.threat_model.collusive_behavior_definition,
            "",
            f"- Honest baseline: {context.threat_model.honest_baseline_definition}",
            f"- Observable signals: {', '.join(context.threat_model.observable_signals)}",
            "- Synthetic traces instantiate this threat model but do not validate field behavior.",
        ]
    )


def _pilot_trace_dataset(context: _PilotManuscriptContext) -> str:
    if context.dataset is None:
        return "No pilot trace dataset is attached; pilot evidence is blocked."
    dataset = context.dataset
    lines = [
        f"- Dataset ID: `{dataset.id}`",
        f"- Negative traces: {dataset.negative_count}",
        f"- Positive traces: {dataset.positive_count}",
        f"- Hard-negative traces: {dataset.hard_negative_count}",
        f"- Ambiguous traces excluded from primary metrics: {len(dataset.ambiguous_trace_ids)}",
        f"- Alpha support: {_format_alpha_support(dataset.alpha_targets_supported)}",
        "",
        "Synthetic pilot data limitations are part of the dataset card and remain manuscript-visible.",
    ]
    return "\n".join(lines)


def _baseline_monitors(context: _PilotManuscriptContext) -> str:
    baseline_names = [
        "random detector",
        "fixed-threshold frequency detector",
        "repeated-action detector",
        "lexical similarity detector",
        "statistical anomaly detector",
        "sequential change-point detector",
        "calibrated threshold detector",
        "transcript-visible heuristic monitor",
        "action-only heuristic monitor",
        "optional LLM judge baseline (opt-in, not required in CI)",
    ]
    blockers = [item for item in context.review_panel.fatal_blockers if "baseline" in item.lower()]
    lines = ["The pilot package reports the baseline suite as comparison evidence, not monitor superiority evidence.", ""]
    lines.extend([f"- {name}" for name in baseline_names])
    lines.extend(["", "Baseline reviewer blockers:"])
    lines.extend([f"- {item}" for item in blockers] or ["- none"])
    return "\n".join(lines)


def _calibration(context: _PilotManuscriptContext) -> str:
    if not context.calibration_records:
        return "No calibration records are attached; calibrated low-FPR baseline claims are blocked."
    lines = ["Thresholds are calibrated on honest/null data where appropriate.", ""]
    for record in context.calibration_records:
        lines.append(
            f"- `{record.monitor_id}` target alpha={record.target_alpha:g}, threshold={record.threshold:.6g}, "
            f"observed FPR={record.observed_fpr:.6g}"
        )
        for warning in record.warnings:
            lines.append(f"  Warning: {warning}")
    return "\n".join(lines)


def _sequential_metrics(context: _PilotManuscriptContext) -> str:
    lines = [
        "Pilot metrics include per-monitor FPR/TPR, per-episode false alarm probability, time-to-detection, "
        "detection delay, confidence intervals, zero-false-positive upper bounds, and action-only versus "
        "transcript-visible comparison.",
        "Sequential multiple-testing caveat: repeated audit windows require explicit family-wise false-alarm control.",
    ]
    if context.power_assessment:
        lines.extend(
            [
                "",
                f"- Supported alpha targets: {', '.join(context.power_assessment.alpha_targets_met) or 'none'}",
                f"- Underpowered alpha targets: {', '.join(context.power_assessment.alpha_targets_underpowered) or 'none'}",
                f"- Zero-FP upper bounds: {context.power_assessment.zero_false_positive_upper_bounds}",
            ]
        )
    return "\n".join(lines)


def _pilot_results(context: _PilotManuscriptContext) -> str:
    if context.analysis is None:
        return "No pilot analysis artifact is attached; pilot result claims are blocked."
    low_fpr = _read_json(context.analysis.output_paths.get("pilot_low_fpr_report_json", ""))
    comparison = _read_json(context.analysis.output_paths.get("pilot_baseline_comparison_json", ""))
    return "\n".join(
        [
            f"- Analysis ID: `{context.analysis.id}`",
            f"- Execution ID: `{context.analysis.execution_id}`",
            f"- Run type: `{context.analysis.run_type}`",
            f"- Supported alpha levels: {', '.join(low_fpr.get('supported_alpha_levels', [])) or 'none'}",
            f"- Underpowered alpha levels: {', '.join(low_fpr.get('underpowered_alpha_levels', [])) or 'none'}",
            f"- Baseline rows: {len(comparison.get('per_monitor', []))}",
            "- Results are pilot-labeled and should not be promoted to main benchmark claims.",
        ]
    )


def _low_fpr_limitations(context: _PilotManuscriptContext) -> str:
    lines = [
        "Zero false positives in finite synthetic pilot traces provide an upper confidence bound, not proof of zero risk.",
        "Low-FPR claims cannot exceed the observed honest/null sample size and predeclared power plan.",
    ]
    if context.power_assessment and "0.001" in context.power_assessment.alpha_targets_underpowered:
        payload = context.power_assessment.alpha_targets_underpowered["0.001"]
        lines.append(
            "alpha=0.001 is blocked at pilot maturity: "
            f"{payload['observed_negative_count']} observed negative traces / {payload['required_negative_count']} required."
        )
    elif not context.power_assessment:
        lines.append("alpha=0.001 is blocked because no pilot power assessment is attached.")
    return "\n".join(lines)


def _related_work_section(context: _PilotManuscriptContext) -> str:
    if context.related_work is None or context.prior_work is None:
        return "Related-work attachment is incomplete; novelty claims remain weak or unknown."
    covered_category_count = len(context.related_work.required_categories) - len(context.related_work.missing_categories)
    lines = [
        "Related work is attached through prior-work recall and a related-work matrix.",
        f"- Required categories covered: {covered_category_count} / {len(context.related_work.required_categories)}",
        f"- Missing categories: {', '.join(context.related_work.missing_categories) or 'none'}",
        f"- Closest prior work IDs: {', '.join(context.related_work.closest_prior_work_ids) or 'none'}",
        f"- Contribution positioning: {context.related_work.contribution_positioning}",
    ]
    if context.novelty:
        lines.extend(
            [
                f"- Novelty strength: {context.novelty.novelty_strength}",
                f"- Strong novelty allowed: {context.novelty.strong_novelty_allowed}",
            ]
        )
    return "\n".join(lines)


def _reviewer_blockers(context: _PilotManuscriptContext) -> str:
    lines = [
        f"- Publishability assessment: `{context.review_panel.publishability_assessment}`",
        f"- Reviewer-risk score: {context.review_panel.reviewer_risk_score:.2f}",
        "",
        "Fatal blockers:",
    ]
    lines.extend([f"- {item}" for item in context.review_panel.fatal_blockers] or ["- none"])
    lines.extend(["", "Required fixes:"])
    lines.extend([f"- {item}" for item in context.review_panel.required_fixes] or ["- none"])
    return "\n".join(lines)


def _path_to_main(context: _PilotManuscriptContext) -> str:
    return "\n".join(f"- {item}" for item in _main_benchmark_requirements(context))


def _write_package_files(package_dir: Path, manuscript: SelectedPilotManuscript, context: _PilotManuscriptContext) -> list[Path]:
    files: list[Path] = []
    manuscript_path = package_dir / "selected_pilot_manuscript.md"
    manuscript_path.write_text(render_selected_pilot_manuscript(manuscript), encoding="utf-8")
    files.append(manuscript_path)

    manifest_path = package_dir / "pilot_artifact_manifest.json"
    manifest_path.write_text(json.dumps(_artifact_manifest(manuscript, context), indent=2) + "\n", encoding="utf-8")
    files.append(manifest_path)

    review_path = package_dir / "pilot_review_panel.md"
    review_path.write_text(render_pilot_review_panel(context.review_panel), encoding="utf-8")
    files.append(review_path)

    fixes_path = package_dir / "reviewer_blockers.md"
    fixes_path.write_text(render_pilot_required_fixes(context.review_panel), encoding="utf-8")
    files.append(fixes_path)

    if context.analysis:
        for key, name in [
            ("pilot_metrics_md", "pilot_metrics.md"),
            ("pilot_baseline_comparison_md", "pilot_baseline_comparison.md"),
            ("pilot_error_analysis_md", "pilot_error_analysis.md"),
            ("pilot_low_fpr_report_md", "pilot_low_fpr_report.md"),
            ("pilot_limitations_md", "pilot_limitations.md"),
        ]:
            source = Path(context.analysis.output_paths[key])
            destination = package_dir / name
            shutil.copyfile(source, destination)
            files.append(destination)
    if context.related_work:
        path = package_dir / "selected_related_work_matrix.md"
        path.write_text(render_related_work_matrix(context.related_work), encoding="utf-8")
        files.append(path)
    if context.prior_work:
        path = package_dir / "selected_prior_work_recall.md"
        papers = context.prior_work.provenance.source_ids[2:]
        path.write_text(render_prior_work_recall(context.prior_work, [] if papers else []), encoding="utf-8")
        files.append(path)
    if context.novelty:
        path = package_dir / "novelty_positioning.md"
        path.write_text(render_novelty_positioning(context.novelty), encoding="utf-8")
        files.append(path)
    package_json = package_dir / "selected_pilot_manuscript.json"
    package_json.write_text(json.dumps(to_plain(manuscript), indent=2) + "\n", encoding="utf-8")
    files.append(package_json)
    return files


def _artifact_manifest(manuscript: SelectedPilotManuscript, context: _PilotManuscriptContext) -> dict[str, Any]:
    return {
        "run_type": "pilot",
        "synthetic_data_label": manuscript.synthetic_data_label,
        "benchmark_id": manuscript.benchmark_id,
        "dataset_id": context.dataset.id if context.dataset else None,
        "analysis_id": context.analysis.id if context.analysis else None,
        "review_panel": context.review_panel.benchmark_id,
        "publication_ready": False,
        "claim_boundary": "pilot benchmark study only",
        "alpha_001_claim": "blocked unless powered",
        "main_requirements": manuscript.main_benchmark_requirements,
    }


def _latest_pilot_dataset(manager: SelectedPilotManuscriptManager, spec: SequentialSpecificityBenchmarkSpec) -> PilotTraceDataset | None:
    root = manager._benchmark_dir(spec.project_id) / "pilot_dataset"
    candidates = sorted(root.glob("*.json"), key=lambda path: path.stat().st_mtime)
    for path in reversed(candidates):
        dataset = from_dict(PilotTraceDataset, json.loads(path.read_text(encoding="utf-8")))
        if dataset.benchmark_id == spec.id:
            return dataset
    return None


def _latest_analysis(manager: SelectedPilotManuscriptManager, benchmark_id: str) -> PilotAnalysisResult | None:
    try:
        return manager.analysis_manager.load_latest_for_benchmark(benchmark_id)
    except FileNotFoundError:
        return None


def _power_assessment(manager: SelectedPilotManuscriptManager, dataset: PilotTraceDataset | None) -> PilotPowerAssessment | None:
    if dataset is None:
        return None
    try:
        return manager.power_manager.check_dataset(dataset.id)
    except (FileNotFoundError, ValueError):
        return None


def _calibration_records(manager: SelectedPilotManuscriptManager, benchmark_id: str) -> list[MonitorCalibrationRecord]:
    spec = manager.benchmark_manager.load_spec(benchmark_id)
    root = manager._benchmark_dir(spec.project_id) / "monitor_calibrations"
    return [from_dict(MonitorCalibrationRecord, json.loads(path.read_text(encoding="utf-8"))) for path in sorted(root.glob("*.json"))]


def _prior_work(manager: SelectedPilotManuscriptManager, benchmark_id: str) -> SelectedPriorWorkRecall | None:
    try:
        return manager.related_work_manager.load_prior_work_recall(benchmark_id)
    except (FileNotFoundError, ValueError):
        return None


def _related_work(manager: SelectedPilotManuscriptManager, benchmark_id: str) -> SelectedRelatedWorkMatrix | None:
    try:
        return manager.related_work_manager.load_related_work_matrix(benchmark_id)
    except (FileNotFoundError, ValueError):
        return None


def _novelty(manager: SelectedPilotManuscriptManager, benchmark_id: str) -> SelectedNoveltyPositioning | None:
    try:
        return manager.related_work_manager.novelty_report(benchmark_id)
    except (FileNotFoundError, ValueError):
        return None


def _pilot_limitations(context: _PilotManuscriptContext) -> list[str]:
    limitations = [
        "Synthetic pilot data is generated benchmark evidence, not field evidence.",
        "Pilot maturity supports only alpha levels with enough honest/null negative traces.",
        "Zero false positives are reported through confidence upper bounds, not proof of zero risk.",
        "Baseline comparisons are pilot comparisons and may remain weak scientific baselines.",
        "Publication-ready claim remains blocked unless reviewer and release gates allow it.",
    ]
    if context.dataset:
        limitations.extend(context.dataset.limitations)
    if context.power_assessment:
        limitations.extend(context.power_assessment.warnings)
        for alpha, payload in context.power_assessment.alpha_targets_underpowered.items():
            limitations.append(
                f"alpha={alpha} remains blocked: {payload['observed_negative_count']} observed negative traces / "
                f"{payload['required_negative_count']} required."
            )
    if context.related_work and context.related_work.blocking_issues:
        limitations.extend(context.related_work.blocking_issues)
    return _unique(limitations)


def _main_benchmark_requirements(context: _PilotManuscriptContext) -> list[str]:
    requirements = [
        "Collect enough honest/null negative traces for main alpha targets before any alpha=0.001 specificity claim.",
        "Strengthen prior-work baselines before strong contribution claims.",
        "Expand beyond synthetic-only evidence before any field-validity claim.",
        "Preserve ambiguous-trace handling and sequential multiple-testing corrections in the main protocol.",
        "Resolve or explicitly carry forward all pilot reviewer blockers.",
    ]
    if context.related_work and context.related_work.missing_categories:
        requirements.append("Complete missing related-work categories before stronger novelty positioning.")
    return requirements


def _readiness(context: _PilotManuscriptContext) -> str:
    if context.review_panel.fatal_blockers:
        return "not_publication_ready_pilot_blockers"
    if not context.analysis or not context.dataset:
        return "not_publication_ready_missing_pilot_artifacts"
    return "not_publication_ready_pilot_maturity_only"


def _format_alpha_support(alpha_support: dict[str, dict[str, Any]]) -> str:
    if not alpha_support:
        return "none"
    parts = []
    for alpha, payload in sorted(alpha_support.items()):
        parts.append(
            f"alpha={alpha} {payload.get('status')} "
            f"({payload.get('observed_negative_count')} observed / {payload.get('required_negative_count')} required)"
        )
    return "; ".join(parts)


def _read_json(path: str) -> dict[str, Any]:
    if not path:
        return {}
    candidate = Path(path)
    if not candidate.exists():
        return {}
    return json.loads(candidate.read_text(encoding="utf-8"))


def _unique(items: Iterable[object]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        text = str(item)
        if text and text not in seen:
            seen.add(text)
            result.append(text)
    return result
