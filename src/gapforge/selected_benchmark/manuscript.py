"""Manuscript-shaped package generation for the selected benchmark idea."""

from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path

from gapforge.config import GapForgeConfig
from gapforge.models import Provenance, from_dict, to_plain
from gapforge.project_memory import ProjectMemoryManager
from gapforge.selected_benchmark.baselines import MonitorBaseline, MonitorBaselineManager
from gapforge.selected_benchmark.metrics import SequentialMetricResult
from gapforge.selected_benchmark.reviewer import (
    SelectedBenchmarkReviewerPanelBuilder,
    SelectedBenchmarkReviewPanel,
    render_selected_benchmark_fix_list,
    render_selected_benchmark_review_panel,
)
from gapforge.selected_benchmark.spec import SelectedBenchmarkManager, SequentialSpecificityBenchmarkSpec
from gapforge.selected_benchmark.threat_model import CollusionThreatModel
from gapforge.selected_benchmark.trace_generator import TraceDataset
from gapforge.state import slugify, utc_now_iso

MANUSCRIPT_SECTION_TYPES = [
    "problem motivation",
    "related work",
    "benchmark definition",
    "threat model",
    "sequential specificity metrics",
    "synthetic smoke setup",
    "baselines",
    "limitations",
    "path to pilot/main benchmark",
    "reviewer concerns",
]


@dataclass(slots=True)
class SelectedBenchmarkManuscript:
    id: str
    benchmark_id: str
    title: str
    manuscript_path: str
    sections: dict[str, str] = field(default_factory=dict)
    smoke_labels: list[str] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)
    reviewer_blockers: list[str] = field(default_factory=list)
    reviewer_required_fixes: list[str] = field(default_factory=list)
    maturity_statement: str = ""
    provenance: Provenance = field(default_factory=lambda: Provenance(created_by_skill="selected-benchmark-manuscript"))


@dataclass(slots=True)
class SelectedBenchmarkPaperPackage:
    id: str
    benchmark_id: str
    package_dir: str
    manuscript_id: str
    files: list[str] = field(default_factory=list)
    readiness: str = "not_publishable"
    blockers: list[str] = field(default_factory=list)
    provenance: Provenance = field(default_factory=lambda: Provenance(created_by_skill="selected-benchmark-paper-package"))


class SelectedBenchmarkManuscriptManager:
    """Generate conservative manuscript and paper-package artifacts for the selected benchmark."""

    def __init__(self, config: GapForgeConfig) -> None:
        self.config = config
        self.config.ensure_dirs()
        self.project_manager = ProjectMemoryManager(config)
        self.benchmark_manager = SelectedBenchmarkManager(config)
        self.baseline_manager = MonitorBaselineManager(config)
        self.reviewer_builder = SelectedBenchmarkReviewerPanelBuilder(config)

    def generate(self, benchmark_id: str) -> SelectedBenchmarkManuscript:
        context = _ManuscriptContext.from_benchmark(self, benchmark_id)
        manuscript_dir = self._benchmark_dir(context.spec.project_id) / "manuscript"
        sections_dir = manuscript_dir / "sections"
        sections_dir.mkdir(parents=True, exist_ok=True)
        sections = _build_sections(context)
        for index, (section_type, text) in enumerate(sections.items(), start=1):
            section_path = sections_dir / f"{index:02d}_{slugify(section_type)}.md"
            section_path.write_text(text.rstrip() + "\n", encoding="utf-8")
        manuscript_path = manuscript_dir / "selected_benchmark_manuscript.md"
        manuscript = SelectedBenchmarkManuscript(
            id=f"selected-benchmark-manuscript-{slugify(benchmark_id)}",
            benchmark_id=benchmark_id,
            title=context.spec.title,
            manuscript_path=str(manuscript_path),
            sections=sections,
            smoke_labels=_smoke_labels(context),
            limitations=context.limitations,
            reviewer_blockers=context.review_panel.fatal_blockers,
            reviewer_required_fixes=context.review_panel.required_fixes,
            maturity_statement=_maturity_statement(context),
            provenance=Provenance(
                created_by_skill="selected-benchmark-manuscript",
                source_ids=_unique(
                    [
                        benchmark_id,
                        context.spec.project_id,
                        context.threat_model.id if context.threat_model else "",
                        context.review_panel.benchmark_id,
                        *[dataset.id for dataset in context.datasets],
                        *[metric.id for metric in context.metrics],
                    ]
                ),
                timestamp=utc_now_iso(),
                reasoning_summary=(
                    "Generated a manuscript-shaped selected-benchmark draft that preserves smoke, synthetic-data, "
                    "and reviewer-blocker boundaries."
                ),
            ),
        )
        manuscript_path.write_text(render_selected_benchmark_manuscript(manuscript), encoding="utf-8")
        (manuscript_dir / "selected_benchmark_manuscript.json").write_text(
            json.dumps(to_plain(manuscript), indent=2) + "\n", encoding="utf-8"
        )
        return manuscript

    def paper_package(self, benchmark_id: str) -> SelectedBenchmarkPaperPackage:
        manuscript = self.generate(benchmark_id)
        context = _ManuscriptContext.from_benchmark(self, benchmark_id)
        package_dir = self._benchmark_dir(context.spec.project_id) / "paper_package"
        package_dir.mkdir(parents=True, exist_ok=True)
        files = _write_package_files(package_dir, manuscript, context)
        package = SelectedBenchmarkPaperPackage(
            id=f"selected-benchmark-paper-package-{slugify(benchmark_id)}",
            benchmark_id=benchmark_id,
            package_dir=str(package_dir),
            manuscript_id=manuscript.id,
            files=[str(path.relative_to(package_dir)) for path in files],
            readiness=context.review_panel.publishability_assessment,
            blockers=[*context.review_panel.fatal_blockers, *context.review_panel.required_fixes],
            provenance=Provenance(
                created_by_skill="selected-benchmark-paper-package",
                source_ids=[benchmark_id, manuscript.id, context.review_panel.benchmark_id],
                timestamp=utc_now_iso(),
                reasoning_summary="Exported a conservative selected-benchmark paper package without upgrading smoke evidence.",
            ),
        )
        package_path = package_dir / "paper_package.json"
        package_path.write_text(json.dumps(to_plain(package), indent=2) + "\n", encoding="utf-8")
        return package

    def _benchmark_dir(self, project_id: str) -> Path:
        program = self.project_manager.load_project(project_id)
        path = Path(program.project.root_dir) / "selected_benchmark"
        path.mkdir(parents=True, exist_ok=True)
        return path


@dataclass(slots=True)
class _ManuscriptContext:
    spec: SequentialSpecificityBenchmarkSpec
    threat_model: CollusionThreatModel | None
    baselines: list[MonitorBaseline]
    datasets: list[TraceDataset]
    metrics: list[SequentialMetricResult]
    review_panel: SelectedBenchmarkReviewPanel
    limitations: list[str]

    @classmethod
    def from_benchmark(cls, manager: SelectedBenchmarkManuscriptManager, benchmark_id: str) -> _ManuscriptContext:
        spec = manager.benchmark_manager.load_spec(benchmark_id)
        threat_model = manager.benchmark_manager.load_threat_model(benchmark_id)
        baselines = manager.baseline_manager.load_baselines(benchmark_id)
        datasets = _datasets(manager, spec)
        metrics = _metrics(manager, datasets)
        review_panel = manager.reviewer_builder.review(benchmark_id)
        limitations = _unique(
            [
                *spec.limitations,
                *([*threat_model.limitations] if threat_model else []),
                *[limitation for dataset in datasets for limitation in dataset.limitations],
                *[limitation for metric in metrics for limitation in metric.limitations],
                *review_panel.limitations,
                "This manuscript draft does not claim deployment validity.",
                "Final benchmark contribution claims require reviewer blockers to be resolved.",
            ]
        )
        return cls(
            spec=spec,
            threat_model=threat_model,
            baselines=baselines,
            datasets=datasets,
            metrics=metrics,
            review_panel=review_panel,
            limitations=limitations,
        )


def render_selected_benchmark_manuscript(manuscript: SelectedBenchmarkManuscript) -> str:
    lines = [
        f"# {manuscript.title}",
        "",
        "## Claim Boundary",
        "",
        manuscript.maturity_statement,
        "",
        "This draft is manuscript-shaped, but it does not claim final benchmark contribution status while reviewer blockers remain.",
        "It does not claim deployment validity.",
        "",
        "## Prominent Limitations",
        "",
    ]
    lines.extend([f"- {item}" for item in manuscript.limitations] or ["- none"])
    lines.extend(["", "## Reviewer Blockers", ""])
    lines.extend([f"- {item}" for item in manuscript.reviewer_blockers] or ["- none"])
    lines.extend(["", "## Sections", ""])
    for section_type, text in manuscript.sections.items():
        lines.extend([f"## {section_type.title()}", "", text.strip(), ""])
    return "\n".join(lines).rstrip() + "\n"


def _build_sections(context: _ManuscriptContext) -> dict[str, str]:
    return {
        "problem motivation": _problem_motivation(context),
        "related work": _related_work(context),
        "benchmark definition": _benchmark_definition(context),
        "threat model": _threat_model_section(context),
        "sequential specificity metrics": _metrics_section(context),
        "synthetic smoke setup": _smoke_section(context),
        "baselines": _baselines_section(context),
        "limitations": _limitations_section(context),
        "path to pilot/main benchmark": _path_to_pilot_main(context),
        "reviewer concerns": _reviewer_concerns(context),
    }


def _problem_motivation(context: _ManuscriptContext) -> str:
    return "\n".join(
        [
            f"The accepted v2 idea asks: {context.spec.research_question}",
            "",
            "The manuscript motivation is to evaluate collusion monitors under repeated audit decisions at low false-positive budgets.",
            "The draft treats low false-positive specificity as the central benchmark property, not as an established result.",
        ]
    )


def _related_work(context: _ManuscriptContext) -> str:
    novelty_review = next((review for review in context.review_panel.reviewer_reports if review.role == "skeptical novelty reviewer"), None)
    weaknesses = novelty_review.weaknesses if novelty_review else []
    lines = [
        "Related work is currently represented by prior-work recall and related-work matrix artifacts when available.",
        "Novelty uncertainty remains visible and must not be hidden.",
        "",
        "Reviewer-visible related-work gaps:",
    ]
    lines.extend([f"- {item}" for item in weaknesses] or ["- none recorded"])
    return "\n".join(lines)


def _benchmark_definition(context: _ManuscriptContext) -> str:
    lines = [
        context.spec.benchmark_goal,
        "",
        f"Sequential setting: {context.spec.sequential_setting}",
        "",
        "Observability modes:",
    ]
    lines.extend(f"- {item}" for item in context.spec.observability_modes)
    lines.extend(["", "Honest null distribution:"])
    lines.extend(_dict_lines(context.spec.honest_agent_distribution))
    lines.extend(["", "Collusive alternative distribution:"])
    lines.extend(_dict_lines(context.spec.collusive_agent_distribution))
    return "\n".join(lines)


def _threat_model_section(context: _ManuscriptContext) -> str:
    if context.threat_model is None:
        return "Threat model is missing; this blocks manuscript readiness."
    lines = [
        f"Agents: {context.threat_model.agent_count}",
        f"Communication allowed: {str(context.threat_model.communication_allowed).lower()}",
        f"Adaptive adversary modeled: {str(context.threat_model.adaptive_adversary).lower()}",
        "",
        "Observable signals:",
    ]
    lines.extend(f"- {item}" for item in context.threat_model.observable_signals)
    lines.extend(["", "Hidden channel assumptions:"])
    lines.extend(f"- {item}" for item in context.threat_model.hidden_channel_assumptions)
    lines.extend(["", "Threat-model limitations:"])
    lines.extend(f"- {item}" for item in context.threat_model.limitations)
    return "\n".join(lines)


def _metrics_section(context: _ManuscriptContext) -> str:
    if not context.metrics:
        return "No metric results are available. The draft must not include numerical benchmark claims."
    lines = [
        "Metric artifacts are included as smoke/pilot wiring evidence only when the dataset split says so.",
        "Metrics must be computed from traces and monitor predictions; no manual result claims are included.",
        "",
    ]
    for metric in context.metrics:
        split = metric.run_type or "unknown"
        label = "SMOKE" if split == "smoke" else split.upper()
        lines.append(
            f"- [{label}] `{metric.metric_name}` value={metric.value:.6g}, sample_size={metric.sample_size}, "
            f"negative_traces={metric.negative_trace_count}, positive_traces={metric.positive_trace_count}"
        )
    return "\n".join(lines)


def _smoke_section(context: _ManuscriptContext) -> str:
    if not context.datasets:
        return "No trace datasets exist yet. The smoke setup is not run."
    synthetic_only = all(_dataset_is_synthetic(dataset) for dataset in context.datasets)
    lines = [
        "Synthetic smoke setup:",
        f"- Only synthetic traces exist: {str(synthetic_only).lower()}",
        "- Smoke results are labeled smoke and cannot support final scientific claims.",
        "- Synthetic traces do not represent real deployment behavior.",
        "",
        "Datasets:",
    ]
    for dataset in context.datasets:
        smoke = "SMOKE" if dataset.split == "smoke" else dataset.split.upper()
        label_balance = json.dumps(dataset.label_balance, sort_keys=True)
        lines.append(f"- [{smoke}] `{dataset.id}`: {len(dataset.trace_ids)} traces, label balance {label_balance}")
    return "\n".join(lines)


def _baselines_section(context: _ManuscriptContext) -> str:
    if not context.baselines:
        return "No baseline suite is registered. This remains a reviewer-visible blocker."
    lines = ["Baseline suite:"]
    for baseline in context.baselines:
        deployable = not baseline.parameters.get("analysis_only") and baseline.parameters.get("ci_enabled") is not False
        lines.append(
            f"- `{baseline.id}`: {baseline.name}; type={baseline.baseline_type}; input_mode={baseline.input_mode}; "
            f"deployable_baseline={str(deployable).lower()}"
        )
        for limitation in baseline.limitations:
            lines.append(f"  - Limitation: {limitation}")
    return "\n".join(lines)


def _limitations_section(context: _ManuscriptContext) -> str:
    lines = [
        "Limitations are part of the manuscript core, not appendix-only material.",
        "The draft does not claim deployment validity or final benchmark contribution status.",
        "",
    ]
    lines.extend(f"- {item}" for item in context.limitations)
    return "\n".join(lines)


def _path_to_pilot_main(context: _ManuscriptContext) -> str:
    lines = [
        "The next benchmark maturity levels are pilot and main runs.",
        "Pilot/main claims require reviewer blockers to be resolved, sufficient honest negative traces, and related-work recall.",
        "",
        "Required before stronger claims:",
    ]
    fixes = [*context.review_panel.fatal_blockers, *context.review_panel.required_fixes]
    lines.extend([f"- {item}" for item in fixes] or ["- none"])
    return "\n".join(lines)


def _reviewer_concerns(context: _ManuscriptContext) -> str:
    lines = [
        f"Publishability assessment: `{context.review_panel.publishability_assessment}`",
        f"Reviewer-risk score: {context.review_panel.reviewer_risk_score:.2f}",
        "",
        "Fatal blockers:",
    ]
    lines.extend([f"- {item}" for item in context.review_panel.fatal_blockers] or ["- none"])
    lines.extend(["", "Required fixes:"])
    lines.extend([f"- {item}" for item in context.review_panel.required_fixes] or ["- none"])
    return "\n".join(lines)


def _write_package_files(package_dir: Path, manuscript: SelectedBenchmarkManuscript, context: _ManuscriptContext) -> list[Path]:
    files: list[Path] = []
    payloads = {
        "README.md": _package_readme(manuscript, context),
        "manuscript.md": render_selected_benchmark_manuscript(manuscript),
        "limitations.md": _limitations_section(context) + "\n",
        "reviewer_blockers.md": render_selected_benchmark_fix_list(context.review_panel),
        "review_panel.md": render_selected_benchmark_review_panel(context.review_panel),
        "artifact_manifest.json": json.dumps(_artifact_manifest(manuscript, context), indent=2) + "\n",
        "benchmark_spec.json": json.dumps(to_plain(context.spec), indent=2) + "\n",
    }
    if context.threat_model is not None:
        payloads["threat_model.json"] = json.dumps(to_plain(context.threat_model), indent=2) + "\n"
    for name, text in payloads.items():
        path = package_dir / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        files.append(path)
    return files


def _package_readme(manuscript: SelectedBenchmarkManuscript, context: _ManuscriptContext) -> str:
    return "\n".join(
        [
            f"# Selected Benchmark Paper Package `{context.spec.id}`",
            "",
            f"- Manuscript ID: `{manuscript.id}`",
            f"- Readiness: `{context.review_panel.publishability_assessment}`",
            f"- Reviewer-risk score: {context.review_panel.reviewer_risk_score:.2f}",
            f"- Only synthetic traces exist: {str(all(_dataset_is_synthetic(dataset) for dataset in context.datasets)).lower()}",
            "",
            "This package is a manuscript-shaped benchmark artifact, not a publication-ready claim set.",
            "Smoke results remain labeled smoke, deployment validity is not claimed, and reviewer blockers are included.",
            "",
        ]
    )


def _artifact_manifest(manuscript: SelectedBenchmarkManuscript, context: _ManuscriptContext) -> dict[str, object]:
    return {
        "benchmark_id": context.spec.id,
        "manuscript_id": manuscript.id,
        "smoke_labels": manuscript.smoke_labels,
        "dataset_ids": [dataset.id for dataset in context.datasets],
        "metric_result_ids": [metric.id for metric in context.metrics],
        "baseline_ids": [baseline.id for baseline in context.baselines],
        "reviewer_blockers": context.review_panel.fatal_blockers,
        "required_fixes": context.review_panel.required_fixes,
        "claim_boundary": "No deployment validity or final benchmark contribution claim is made.",
    }


def _maturity_statement(context: _ManuscriptContext) -> str:
    if context.review_panel.fatal_blockers:
        return "Current maturity: manuscript-shaped draft with fatal reviewer blockers still open."
    if context.review_panel.required_fixes:
        return "Current maturity: manuscript-shaped draft with required reviewer fixes still open."
    if any(dataset.split == "smoke" for dataset in context.datasets):
        return "Current maturity: smoke-validated draft; smoke evidence is not final benchmark evidence."
    return "Current maturity: draft package pending pilot/main validation."


def _smoke_labels(context: _ManuscriptContext) -> list[str]:
    labels = [f"{dataset.id}:{dataset.split}" for dataset in context.datasets if dataset.split == "smoke"]
    labels.extend([f"{metric.id}:{metric.run_type}" for metric in context.metrics if metric.run_type == "smoke"])
    return _unique(labels)


def _datasets(manager: SelectedBenchmarkManuscriptManager, spec: SequentialSpecificityBenchmarkSpec) -> list[TraceDataset]:
    root = manager._benchmark_dir(spec.project_id) / "trace_datasets"
    datasets: list[TraceDataset] = []
    for path in sorted(root.glob("*/dataset.json")):
        dataset = from_dict(TraceDataset, json.loads(path.read_text(encoding="utf-8")))
        if dataset.benchmark_id == spec.id:
            datasets.append(dataset)
    return datasets


def _metrics(manager: SelectedBenchmarkManuscriptManager, datasets: list[TraceDataset]) -> list[SequentialMetricResult]:
    results: list[SequentialMetricResult] = []
    for dataset in datasets:
        dataset_dir = _dataset_dir(manager, dataset.id)
        metrics_path = dataset_dir / "sequential_metrics.json"
        if metrics_path.exists():
            raw = json.loads(metrics_path.read_text(encoding="utf-8"))
            results.extend(from_dict(SequentialMetricResult, item) for item in raw)
    return results


def _dataset_dir(manager: SelectedBenchmarkManuscriptManager, dataset_id: str) -> Path:
    for project in manager.project_manager.list_projects():
        path = manager._benchmark_dir(project.id) / "trace_datasets" / dataset_id
        if path.exists():
            return path
    raise FileNotFoundError(f"No selected benchmark trace dataset `{dataset_id}` found.")


def _dataset_is_synthetic(dataset: TraceDataset) -> bool:
    text = " ".join([*dataset.limitations, *dataset.trace_ids]).lower()
    return "synthetic" in text or dataset.split in {"smoke", "pilot"}


def _dict_lines(value: dict[str, object]) -> list[str]:
    if not value:
        return ["- missing"]
    return [f"- {key}: {item}" for key, item in value.items()]


def _unique(items: Iterable[object]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        text = str(item)
        if text and text not in seen:
            seen.add(text)
            result.append(text)
    return result
