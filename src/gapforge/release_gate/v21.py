"""v2.1 release gate for selected-idea execution artifacts."""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from gapforge.config import GapForgeConfig
from gapforge.experiments.workspace import ExperimentWorkspaceManager
from gapforge.ideas.selected_project import SelectedIdeaProject, SelectedIdeaProjectManager
from gapforge.models import ExperimentExecutionRecord, ExperimentWorkspace, from_dict
from gapforge.project_memory import ProjectMemoryManager
from gapforge.release_gate.v2 import V2ReleaseGateEnforcer, V2ReleaseGateResult
from gapforge.selected_benchmark.baselines import REQUIRED_BASELINE_TYPES, MonitorBaselineManager
from gapforge.selected_benchmark.metrics import SequentialMetricManager
from gapforge.selected_benchmark.spec import SelectedBenchmarkManager, SequentialSpecificityBenchmarkSpec

DEFAULT_SELECTED_IDEA_ID = "idea-sequential-specificity-benchmark-for-low-fpr-collusion-audits"


@dataclass(slots=True)
class V21ReleaseGateResult:
    passed: bool
    status: str
    recommended_next_version: str
    requirements: dict[str, bool]
    blockers: list[str]
    warnings: list[str]
    project_id: str = ""
    source_idea_id: str = ""
    benchmark_id: str = ""
    smoke_execution_id: str = ""
    artifact_paths: dict[str, list[str]] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class _SmokeContext:
    workspace: ExperimentWorkspace
    execution: ExperimentExecutionRecord
    result_summary_path: Path


class V21ReleaseGateEnforcer:
    """Machine-check whether v2.1 selected-idea execution is releasable."""

    def __init__(self, config: GapForgeConfig) -> None:
        self.config = config
        self.config.ensure_dirs()
        self.release_dir = config.data_dir / "release_gate"
        self.projects = ProjectMemoryManager(config)
        self.selected_projects = SelectedIdeaProjectManager(config)
        self.benchmark_manager = SelectedBenchmarkManager(config)
        self.baseline_manager = MonitorBaselineManager(config)
        self.metric_manager = SequentialMetricManager(config)
        self.workspaces = ExperimentWorkspaceManager(config)

    def evaluate(self) -> V21ReleaseGateResult:
        v2_result = self._v2_result()
        selected_project = self._resolve_selected_project(v2_result.selected_idea_id or DEFAULT_SELECTED_IDEA_ID)
        project_id = selected_project.project_id if selected_project is not None else ""
        source_idea_id = selected_project.source_idea_id if selected_project is not None else v2_result.selected_idea_id
        project_root = self._project_root(project_id) if project_id else None
        benchmark_dir = project_root / "selected_benchmark" if project_root else None
        spec = self._load_project_spec(project_id) if project_id else None
        benchmark_id = spec.id if spec is not None else ""
        smoke_context = self._latest_complete_smoke_context(project_id, benchmark_id) if benchmark_id else None
        underpowered_warning = self._underpowered_warning_present(smoke_context)
        artifact_text_paths = self._claim_scan_paths(benchmark_dir, smoke_context.workspace if smoke_context else None)
        fake_result_paths = self._paths_with_disallowed_text(artifact_text_paths, _has_fake_result_marker)
        deployment_overclaim_paths = self._paths_with_disallowed_text(artifact_text_paths, _has_deployment_overclaim)
        low_fpr_overclaim_paths = (
            self._paths_with_disallowed_text(artifact_text_paths, _has_underpowered_low_fpr_overclaim) if underpowered_warning else []
        )

        requirements = {
            "v2_release_gate_passes": v2_result.passed,
            "selected_idea_locked": self._selected_lock_exists(project_id, source_idea_id) if project_id else False,
            "selected_idea_project_exists": selected_project is not None,
            "benchmark_spec_exists": spec is not None,
            "threat_model_exists": self._threat_model_exists(benchmark_id) if benchmark_id else False,
            "trace_generator_exists": self._trace_generator_exists(benchmark_dir),
            "monitor_baseline_suite_exists": self._baseline_suite_exists(benchmark_id) if benchmark_id else False,
            "sequential_metric_plan_exists": self._metric_plan_exists(benchmark_id) if benchmark_id else False,
            "benchmark_workspace_exists": bool(self._selected_workspaces(project_id, benchmark_id)) if benchmark_id else False,
            "smoke_run_completed": smoke_context is not None,
            "result_artifacts_parsed": self._result_artifacts_parsed(smoke_context),
            "low_fpr_underpowered_warning_generated_if_applicable": underpowered_warning if smoke_context is not None else False,
            "reviewer_panel_generated": self._reviewer_panel_exists(benchmark_dir),
            "manuscript_paper_package_generated": self._manuscript_package_exists(benchmark_dir),
            "no_fake_results": not fake_result_paths,
            "no_deployment_validity_overclaim": not deployment_overclaim_paths,
            "no_strong_low_fpr_claim_from_underpowered_smoke": not low_fpr_overclaim_paths,
        }
        blockers = _requirement_blockers(requirements)
        if v2_result.blockers and not v2_result.passed:
            blockers.extend(f"v2 gate blocker: {blocker}" for blocker in v2_result.blockers)
        blockers.extend(f"Disallowed fake-result marker found in {path}" for path in fake_result_paths)
        blockers.extend(f"Deployment-validity overclaim found in {path}" for path in deployment_overclaim_paths)
        blockers.extend(f"Underpowered smoke low-FPR overclaim found in {path}" for path in low_fpr_overclaim_paths)
        warnings = []
        if smoke_context is not None and underpowered_warning:
            warnings.append("Smoke run is underpowered; v2.1 may only claim runnable benchmark scaffolding, not low-FPR validity.")
        if benchmark_id and self._reviewer_panel_exists(benchmark_dir):
            warnings.append("Reviewer panel may contain blockers; release notes must preserve them as required fixes.")

        passed = all(requirements.values())
        return V21ReleaseGateResult(
            passed=passed,
            status="pass" if passed else "fail",
            recommended_next_version="v2.1" if passed else "v2.1-blocked",
            requirements=requirements,
            blockers=_unique(blockers),
            warnings=_unique(warnings),
            project_id=project_id,
            source_idea_id=source_idea_id,
            benchmark_id=benchmark_id,
            smoke_execution_id=smoke_context.execution.id if smoke_context else "",
            artifact_paths=self._artifact_paths(v2_result, project_root, benchmark_dir, smoke_context),
        )

    def write_outputs(self, result: V21ReleaseGateResult) -> tuple[Path, Path]:
        self.release_dir.mkdir(parents=True, exist_ok=True)
        json_path = self.release_dir / "v21_release_gate_latest.json"
        data_md_path = self.release_dir / "v21-release-gate-latest.md"
        report = render_v21_release_gate_markdown(result)
        json_path.write_text(json.dumps(result.to_dict(), indent=2) + "\n", encoding="utf-8")
        data_md_path.write_text(report, encoding="utf-8")
        docs_dir = self.config.root / "docs" / "releases"
        docs_dir.mkdir(parents=True, exist_ok=True)
        docs_md_path = docs_dir / "v21-release-gate-latest.md"
        docs_md_path.write_text(report, encoding="utf-8")
        return json_path, docs_md_path

    def _v2_result(self) -> V2ReleaseGateResult:
        return V2ReleaseGateEnforcer(self.config).evaluate()

    def _resolve_selected_project(self, idea_id: str) -> SelectedIdeaProject | None:
        if idea_id:
            try:
                found = self.selected_projects.find_selected_project(idea_id)
            except (FileNotFoundError, json.JSONDecodeError, TypeError, ValueError):
                found = None
            if found is not None:
                return found
        candidates: list[tuple[float, SelectedIdeaProject]] = []
        for project in self.projects.list_projects():
            path = Path(project.root_dir) / "ideas" / "selected_idea_project.json"
            if not path.exists():
                continue
            try:
                selected = from_dict(SelectedIdeaProject, json.loads(path.read_text(encoding="utf-8")))
                candidates.append((path.stat().st_mtime, selected))
            except (OSError, json.JSONDecodeError, TypeError, ValueError):
                continue
        return sorted(candidates, key=lambda item: item[0])[-1][1] if candidates else None

    def _project_root(self, project_id: str) -> Path:
        return Path(self.projects.load_project(project_id).project.root_dir)

    def _load_project_spec(self, project_id: str) -> SequentialSpecificityBenchmarkSpec | None:
        path = self._project_root(project_id) / "selected_benchmark" / "spec.json"
        if not path.exists():
            return None
        try:
            return from_dict(SequentialSpecificityBenchmarkSpec, json.loads(path.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, TypeError, ValueError):
            return None

    def _selected_lock_exists(self, project_id: str, source_idea_id: str) -> bool:
        try:
            lock = self.selected_projects.load_project_lock(project_id)
        except (FileNotFoundError, json.JSONDecodeError, TypeError, ValueError):
            return False
        return lock.idea_id == source_idea_id and source_idea_id != ""

    def _threat_model_exists(self, benchmark_id: str) -> bool:
        try:
            return self.benchmark_manager.load_threat_model(benchmark_id) is not None
        except (FileNotFoundError, json.JSONDecodeError, TypeError, ValueError):
            return False

    def _trace_generator_exists(self, benchmark_dir: Path | None) -> bool:
        try:
            from gapforge.selected_benchmark.trace_generator import SyntheticTraceGenerator  # noqa: F401
        except ImportError:
            return False
        if benchmark_dir is None:
            return False
        trace_root = benchmark_dir / "trace_datasets"
        return trace_root.exists() and any(path.name == "dataset.json" for path in trace_root.glob("*/dataset.json"))

    def _baseline_suite_exists(self, benchmark_id: str) -> bool:
        try:
            baselines = self.baseline_manager.load_baselines(benchmark_id)
        except (FileNotFoundError, json.JSONDecodeError, TypeError, ValueError):
            return False
        present = {baseline.baseline_type for baseline in baselines if baseline.parameters.get("required", False)}
        return REQUIRED_BASELINE_TYPES.issubset(present)

    def _metric_plan_exists(self, benchmark_id: str) -> bool:
        try:
            spec = self.benchmark_manager.load_spec(benchmark_id)
            path = self._project_root(spec.project_id) / "selected_benchmark" / "metric_plan.json"
            return path.exists()
        except (FileNotFoundError, json.JSONDecodeError, TypeError, ValueError):
            return False

    def _selected_workspaces(self, project_id: str, benchmark_id: str) -> list[ExperimentWorkspace]:
        if not project_id or not benchmark_id:
            return []
        root = self._project_root(project_id) / "experiment_workspaces"
        workspaces: list[ExperimentWorkspace] = []
        for config_path in sorted(root.glob("*/configs/selected_benchmark_workspace.json")):
            try:
                payload = json.loads(config_path.read_text(encoding="utf-8"))
                if payload.get("benchmark_id") != benchmark_id:
                    continue
                workspace = self.workspaces.load_workspace(payload["workspace_id"])
                workspaces.append(workspace)
            except (FileNotFoundError, json.JSONDecodeError, KeyError, TypeError, ValueError):
                continue
        return workspaces

    def _latest_complete_smoke_context(self, project_id: str, benchmark_id: str) -> _SmokeContext | None:
        matches: list[tuple[float, _SmokeContext]] = []
        for workspace in self._selected_workspaces(project_id, benchmark_id):
            manifests = {manifest.id: manifest for manifest in self.workspaces.list_manifests(workspace.id)}
            for execution in self.workspaces.list_execution_records(workspace.id):
                manifest = manifests.get(execution.manifest_id)
                if execution.status != "complete" or manifest is None or manifest.run_type != "smoke":
                    continue
                summary_path = Path(workspace.root_dir) / "reports" / f"result_summary_{execution.id}.json"
                matches.append(
                    (summary_path.stat().st_mtime if summary_path.exists() else 0.0, _SmokeContext(workspace, execution, summary_path))
                )
        return sorted(matches, key=lambda item: item[0])[-1][1] if matches else None

    def _result_artifacts_parsed(self, smoke_context: _SmokeContext | None) -> bool:
        if smoke_context is None:
            return False
        if not smoke_context.execution.result_artifact_ids:
            return False
        if not smoke_context.result_summary_path.exists():
            return False
        try:
            payload = json.loads(smoke_context.result_summary_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return False
        return payload.get("execution_id") == smoke_context.execution.id

    def _underpowered_warning_present(self, smoke_context: _SmokeContext | None) -> bool:
        if smoke_context is None:
            return False
        paths = [
            smoke_context.result_summary_path,
            Path(smoke_context.workspace.root_dir) / "results" / "smoke_summary.json",
            Path(smoke_context.workspace.root_dir) / "reports" / "smoke_report.md",
        ]
        text = "\n".join(path.read_text(encoding="utf-8", errors="ignore") for path in paths if path.exists()).lower()
        return "underpowered" in text and "low-fpr" in text

    def _reviewer_panel_exists(self, benchmark_dir: Path | None) -> bool:
        return bool(benchmark_dir and (benchmark_dir / "reviews" / "selected_benchmark_review_panel.json").exists())

    def _manuscript_package_exists(self, benchmark_dir: Path | None) -> bool:
        return bool(
            benchmark_dir
            and (benchmark_dir / "manuscript" / "selected_benchmark_manuscript.json").exists()
            and (benchmark_dir / "paper_package" / "paper_package.json").exists()
        )

    def _claim_scan_paths(self, benchmark_dir: Path | None, workspace: ExperimentWorkspace | None) -> list[Path]:
        roots: list[Path] = []
        if benchmark_dir is not None:
            roots.extend(
                [
                    benchmark_dir / "reports",
                    benchmark_dir / "reviews",
                    benchmark_dir / "manuscript",
                    benchmark_dir / "paper_package",
                ]
            )
        if workspace is not None:
            workspace_root = Path(workspace.root_dir)
            roots.extend([workspace_root / "results", workspace_root / "reports"])
        paths: list[Path] = []
        for root in roots:
            if not root.exists():
                continue
            paths.extend(path for path in root.rglob("*") if path.is_file() and path.suffix.lower() in {".json", ".md", ".txt"})
        return sorted(set(paths))

    def _paths_with_disallowed_text(self, paths: list[Path], predicate) -> list[str]:
        matches: list[str] = []
        for path in paths:
            try:
                text = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            if predicate(text):
                matches.append(str(path))
        return matches

    def _artifact_paths(
        self,
        v2_result: V2ReleaseGateResult,
        project_root: Path | None,
        benchmark_dir: Path | None,
        smoke_context: _SmokeContext | None,
    ) -> dict[str, list[str]]:
        paths: dict[str, list[str]] = {
            "v2_release_gate": [str(self.release_dir / "v2_release_gate_latest.json")],
            "v2_artifacts": [item for values in v2_result.artifact_paths.values() for item in values],
        }
        if project_root is not None:
            paths["selected_idea_project"] = [
                str(project_root / "ideas" / "selected_idea_project.json"),
                str(project_root / "ideas" / "selected_idea_lock.json"),
                str(project_root / "ideas" / "selected_idea_snapshot.json"),
            ]
        if benchmark_dir is not None:
            paths["benchmark"] = [
                str(benchmark_dir / "spec.json"),
                str(benchmark_dir / "threat_model.json"),
                str(benchmark_dir / "task_families.json"),
                str(benchmark_dir / "monitor_baselines.json"),
                str(benchmark_dir / "metric_plan.json"),
            ]
            paths["review_and_manuscript"] = [
                str(benchmark_dir / "reviews" / "selected_benchmark_review_panel.json"),
                str(benchmark_dir / "manuscript" / "selected_benchmark_manuscript.json"),
                str(benchmark_dir / "paper_package" / "paper_package.json"),
            ]
        if smoke_context is not None:
            workspace_root = Path(smoke_context.workspace.root_dir)
            paths["smoke_workspace"] = [
                str(workspace_root / "workspace.json"),
                str(workspace_root / "results" / "smoke_run_result.json"),
                str(workspace_root / "results" / "smoke_metrics.json"),
                str(workspace_root / "results" / "smoke_summary.json"),
                str(smoke_context.result_summary_path),
            ]
        return paths


def render_v21_release_gate_markdown(result: V21ReleaseGateResult) -> str:
    lines = [
        "# GapForge v2.1 Release Gate",
        "",
        f"- Passed: {str(result.passed).lower()}",
        f"- Status: `{result.status}`",
        f"- Recommended next version: `{result.recommended_next_version}`",
        f"- Selected project: `{result.project_id or 'missing'}`",
        f"- Source idea: `{result.source_idea_id or 'missing'}`",
        f"- Benchmark: `{result.benchmark_id or 'missing'}`",
        f"- Smoke execution: `{result.smoke_execution_id or 'missing'}`",
        "",
        "## Requirements",
        "",
    ]
    lines.extend(f"- `{name}`: {str(passed).lower()}" for name, passed in result.requirements.items())
    lines.extend(["", "## Blocking Failures", ""])
    lines.extend([f"- {blocker}" for blocker in result.blockers] or ["- none"])
    lines.extend(["", "## Warnings", ""])
    lines.extend([f"- {warning}" for warning in result.warnings] or ["- none"])
    lines.extend(["", "## Artifact Counts", ""])
    lines.extend(f"- `{name}`: {len(paths)}" for name, paths in sorted(result.artifact_paths.items()))
    lines.extend(
        [
            "",
            "## Claim Boundary",
            "",
            "- v2.1 validates selected idea execution scaffolding and a runnable benchmark smoke path.",
            "- Smoke outputs do not establish final scientific results, deployment validity, or strong low-FPR claims.",
            "- Reviewer blockers and synthetic-data limitations remain visible release artifacts.",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def _requirement_blockers(requirements: dict[str, bool]) -> list[str]:
    return [
        f"`{name}` is required for the v2.1 selected-idea execution release gate." for name, passed in requirements.items() if not passed
    ]


def _has_fake_result_marker(text: str) -> bool:
    lowered = _strip_allowed_phrases(text.lower())
    return bool(
        re.search(r"\bfake result\b", lowered)
        or re.search(r"\bfaked result\b", lowered)
        or re.search(r"\bfabricated result\b", lowered)
        or re.search(r"\bplaceholder result\b", lowered)
        or re.search(r"\bsimulated result presented as empirical\b", lowered)
    )


def _has_deployment_overclaim(text: str) -> bool:
    lowered = text.lower()
    patterns = [
        r"\bprove[sd]? deployment validity\b",
        r"\bdeployment validity (is|has been|was) (established|proven|confirmed|validated)\b",
        r"\breal deployment behavior (is|was) represented\b",
        r"\bsynthetic traces represent real deployment\b",
        r"\bvalid for production deployment\b",
    ]
    return any(re.search(pattern, lowered) for pattern in patterns)


def _has_underpowered_low_fpr_overclaim(text: str) -> bool:
    lowered = text.lower()
    patterns = [
        r"\bsupports strong low-fpr claims\b",
        r"\bstrong low-fpr claims? (is|are) supported\b",
        r"\boperationally meaningful low false-positive rates (are )?(achieved|validated|proven)\b",
        r"\blow-fpr claims? (passes|passed|validated|proven)\b",
        r"\bpublication-ready low-fpr\b",
    ]
    return any(re.search(pattern, lowered) for pattern in patterns)


def _strip_allowed_phrases(text: str) -> str:
    for phrase in [
        "no fake results",
        "fake results remain blocked",
        "fake result not included",
        "cannot be faked",
        "generated results cannot be faked",
        "fake result rejected",
    ]:
        text = text.replace(phrase, "")
    return text


def _unique(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        result.append(item)
    return result
