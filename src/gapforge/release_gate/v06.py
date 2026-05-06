"""v0.6 empirical validation release-gate enforcer."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from gapforge.config import GapForgeConfig
from gapforge.datasets import DatasetRegistry
from gapforge.experiments.workspace import ExperimentWorkspaceManager
from gapforge.models import (
    DatasetRecord,
    ExperimentExecutionRecord,
    ExperimentWorkspace,
    from_dict,
)
from gapforge.results import ResultParser

FAKE_DATASET_TYPES = {"fixture", "synthetic", "generated"}


@dataclass(slots=True)
class V06WorkspaceEmpiricalAssessment:
    workspace_id: str
    project_id: str
    direction_id: str
    workspace_status: str
    fixture_or_smoke_workspace: bool = False
    successful_execution_ids: list[str] = field(default_factory=list)
    failed_execution_ids: list[str] = field(default_factory=list)
    result_artifact_ids: list[str] = field(default_factory=list)
    parsed_execution_ids: list[str] = field(default_factory=list)
    empirical_claim_ids: list[str] = field(default_factory=list)
    reproducibility_checker_run: bool = False
    empirical_reviewer_run: bool = False
    paper_package_v2_exported: bool = False
    fake_results_accepted: bool = False
    failed_experiments_hidden: bool = False
    result_scope: str = "none"
    package_readiness: str = ""
    blockers: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass(slots=True)
class V06ReleaseGateResult:
    passed: bool
    status: str
    deterministic_ci_documented: bool
    v4_codex_workflow_gate_documented: bool
    v5_real_literature_gate_documented: bool
    requirements: dict[str, bool]
    blockers: list[str]
    warnings: list[str]
    workspaces: list[V06WorkspaceEmpiricalAssessment]
    successful_fixture_execution_ids: list[str]
    failed_execution_ids: list[str]
    parsed_execution_ids: list[str]
    empirical_claim_ids: list[str]
    paper_package_paths: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class V06ReleaseGateEnforcer:
    """Machine-check v0.6 empirical validation release eligibility."""

    def __init__(self, config: GapForgeConfig) -> None:
        self.config = config
        self.config.ensure_dirs()
        self.workspace_manager = ExperimentWorkspaceManager(config)
        self.dataset_registry = DatasetRegistry(config)
        self.result_parser = ResultParser(config)

    def evaluate(self) -> V06ReleaseGateResult:
        assessments = self._workspace_assessments()
        successful_fixture_execution_ids = [
            execution_id for item in assessments if item.fixture_or_smoke_workspace for execution_id in item.successful_execution_ids
        ]
        failed_execution_ids = [execution_id for item in assessments for execution_id in item.failed_execution_ids]
        parsed_execution_ids = [execution_id for item in assessments for execution_id in item.parsed_execution_ids]
        empirical_claim_ids = [claim_id for item in assessments for claim_id in item.empirical_claim_ids]
        paper_package_paths = [str(self._paper_package_path(item.workspace_id)) for item in assessments if item.paper_package_v2_exported]

        requirements = {
            "deterministic_ci_documented": self._deterministic_ci_documented(),
            "v4_codex_workflow_gate_documented": self._gate_status_documented("v0.4_latest"),
            "v5_real_literature_gate_documented": self._gate_status_documented("v0.5_latest"),
            "successful_fixture_experiment_executed": bool(successful_fixture_execution_ids),
            "failed_experiment_path_recorded": bool(failed_execution_ids),
            "result_artifact_parsed": bool(parsed_execution_ids),
            "empirical_claim_generated_from_artifact": bool(empirical_claim_ids),
            "reproducibility_checker_run": any(item.reproducibility_checker_run for item in assessments),
            "empirical_reviewer_run": any(item.empirical_reviewer_run for item in assessments),
            "paper_package_v2_exported": bool(paper_package_paths),
            "no_fake_results_accepted": not any(item.fake_results_accepted for item in assessments),
            "failed_experiments_not_hidden": bool(failed_execution_ids) and not any(item.failed_experiments_hidden for item in assessments),
        }
        blockers = _gate_blockers(requirements)
        for assessment in assessments:
            blockers.extend(f"{assessment.workspace_id}: {item}" for item in assessment.blockers)
        blockers = _dedupe(blockers)
        warnings = _dedupe(_gate_warnings(requirements) + [warning for item in assessments for warning in item.warnings])
        passed = not blockers
        status = "pass" if passed else "partial" if _has_empirical_progress(assessments) else "fail"
        return V06ReleaseGateResult(
            passed=passed,
            status=status,
            deterministic_ci_documented=requirements["deterministic_ci_documented"],
            v4_codex_workflow_gate_documented=requirements["v4_codex_workflow_gate_documented"],
            v5_real_literature_gate_documented=requirements["v5_real_literature_gate_documented"],
            requirements=requirements,
            blockers=blockers,
            warnings=warnings,
            workspaces=assessments,
            successful_fixture_execution_ids=successful_fixture_execution_ids,
            failed_execution_ids=failed_execution_ids,
            parsed_execution_ids=parsed_execution_ids,
            empirical_claim_ids=empirical_claim_ids,
            paper_package_paths=paper_package_paths,
        )

    def write_outputs(self, result: V06ReleaseGateResult) -> tuple[Path, Path]:
        data_dir = self.config.data_dir / "release_gate"
        data_dir.mkdir(parents=True, exist_ok=True)
        json_path = data_dir / "v0.6_latest.json"
        md_path = data_dir / "v0.6_latest.md"
        json_path.write_text(json.dumps(result.to_dict(), indent=2) + "\n", encoding="utf-8")
        md_path.write_text(render_v06_release_gate_markdown(result), encoding="utf-8")
        return json_path, md_path

    def _workspace_assessments(self) -> list[V06WorkspaceEmpiricalAssessment]:
        assessments: list[V06WorkspaceEmpiricalAssessment] = []
        for workspace in self._workspaces():
            assessments.append(self._assess_workspace(workspace))
        return assessments

    def _workspaces(self) -> list[ExperimentWorkspace]:
        workspaces: list[ExperimentWorkspace] = []
        if not self.config.project_root.exists():
            return workspaces
        for path in sorted(self.config.project_root.glob("*/experiment_workspaces/*/workspace.json")):
            try:
                workspaces.append(from_dict(ExperimentWorkspace, json.loads(path.read_text(encoding="utf-8"))))
            except (OSError, json.JSONDecodeError, TypeError, ValueError):
                continue
        return workspaces

    def _assess_workspace(self, workspace: ExperimentWorkspace) -> V06WorkspaceEmpiricalAssessment:
        executions = self.workspace_manager.list_execution_records(workspace.id)
        datasets = self.dataset_registry.list_datasets(workspace.id)
        artifacts = self.workspace_manager.list_result_artifacts(workspace.id)
        reports_dir = Path(workspace.root_dir) / "reports"
        package_path = Path(workspace.root_dir) / "paper_package_v2" / "paper_package.json"
        successful = [execution.id for execution in executions if execution.status == "complete"]
        failed = [execution.id for execution in executions if _is_failed_execution(execution)]
        parsed_execution_ids, empirical_claim_ids = self._parsed_results(executions)
        result_scope = _result_scope(executions, datasets)
        package_readiness = _package_readiness(package_path)
        assessment = V06WorkspaceEmpiricalAssessment(
            workspace_id=workspace.id,
            project_id=workspace.project_id,
            direction_id=workspace.direction_id,
            workspace_status=workspace.status,
            fixture_or_smoke_workspace=_is_fixture_or_smoke_workspace(executions, datasets),
            successful_execution_ids=successful,
            failed_execution_ids=failed,
            result_artifact_ids=[artifact.id for artifact in artifacts],
            parsed_execution_ids=parsed_execution_ids,
            empirical_claim_ids=empirical_claim_ids,
            reproducibility_checker_run=(reports_dir / "reproducibility_check.json").exists(),
            empirical_reviewer_run=(reports_dir / "empirical_review.json").exists(),
            paper_package_v2_exported=package_path.exists(),
            fake_results_accepted=_fake_results_accepted(package_path, datasets),
            failed_experiments_hidden=_failed_experiments_hidden(workspace, failed),
            result_scope=result_scope,
            package_readiness=package_readiness,
        )
        assessment.blockers = _workspace_blockers(assessment)
        assessment.warnings = _workspace_warnings(assessment)
        return assessment

    def _parsed_results(self, executions: list[ExperimentExecutionRecord]) -> tuple[list[str], list[str]]:
        parsed_execution_ids: list[str] = []
        empirical_claim_ids: list[str] = []
        for execution in executions:
            try:
                summary = self.result_parser.load_or_parse_summary(execution.id)
            except (FileNotFoundError, json.JSONDecodeError, OSError, ValueError):
                continue
            if summary.metric_results:
                parsed_execution_ids.append(execution.id)
            empirical_claim_ids.extend(claim.id for claim in summary.empirical_claims)
        return parsed_execution_ids, _dedupe(empirical_claim_ids)

    def _paper_package_path(self, workspace_id: str) -> Path:
        workspace = self.workspace_manager.load_workspace(workspace_id)
        return Path(workspace.root_dir) / "paper_package_v2" / "paper_package.json"

    def _deterministic_ci_documented(self) -> bool:
        path = self.config.data_dir / "release_gate" / "deterministic_ci.json"
        if not path.exists():
            return False
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return False
        return bool(isinstance(payload, dict) and payload.get("passed") is True)

    def _gate_status_documented(self, stem: str) -> bool:
        release_dir = self.config.data_dir / "release_gate"
        json_path = release_dir / f"{stem}.json"
        md_path = release_dir / f"{stem}.md"
        if json_path.exists():
            try:
                payload = json.loads(json_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                return False
            return bool(isinstance(payload, dict) and "passed" in payload)
        return md_path.exists()


def render_v06_release_gate_markdown(result: V06ReleaseGateResult) -> str:
    lines = [
        "# GapForge v0.6 Empirical Validation Release Gate",
        "",
        f"- Passed: {str(result.passed).lower()}",
        f"- Status: `{result.status}`",
        f"- Deterministic CI documented: {str(result.deterministic_ci_documented).lower()}",
        f"- v0.4 Codex workflow gate documented: {str(result.v4_codex_workflow_gate_documented).lower()}",
        f"- v0.5 real-literature gate documented: {str(result.v5_real_literature_gate_documented).lower()}",
        f"- Successful fixture/smoke executions: {len(result.successful_fixture_execution_ids)}",
        f"- Failed execution paths: {len(result.failed_execution_ids)}",
        f"- Parsed result executions: {len(result.parsed_execution_ids)}",
        f"- Artifact-backed empirical claims: {len(result.empirical_claim_ids)}",
        f"- Paper package v2 exports: {len(result.paper_package_paths)}",
        "",
        "## Requirements",
        "",
    ]
    lines.extend(f"- {name}: {str(passed).lower()}" for name, passed in result.requirements.items())
    lines.extend(["", "## Blocking Failures", ""])
    lines.extend([f"- {item}" for item in result.blockers] or ["- none"])
    lines.extend(["", "## Warnings", ""])
    lines.extend([f"- {item}" for item in result.warnings] or ["- none"])
    lines.extend(["", "## Workspace Assessments", ""])
    for workspace in result.workspaces:
        lines.extend(
            [
                f"### `{workspace.workspace_id}`",
                "",
                f"- Project: `{workspace.project_id}`",
                f"- Direction: `{workspace.direction_id}`",
                f"- Workspace status: `{workspace.workspace_status}`",
                f"- Result scope: `{workspace.result_scope}`",
                f"- Package readiness: `{workspace.package_readiness or 'none'}`",
                f"- Successful executions: {', '.join(f'`{item}`' for item in workspace.successful_execution_ids) or 'none'}",
                f"- Failed executions: {', '.join(f'`{item}`' for item in workspace.failed_execution_ids) or 'none'}",
                f"- Parsed executions: {', '.join(f'`{item}`' for item in workspace.parsed_execution_ids) or 'none'}",
                f"- Empirical claims: {len(workspace.empirical_claim_ids)}",
                f"- Reproducibility checker run: {str(workspace.reproducibility_checker_run).lower()}",
                f"- Empirical reviewer run: {str(workspace.empirical_reviewer_run).lower()}",
                f"- Paper package v2 exported: {str(workspace.paper_package_v2_exported).lower()}",
                f"- Fake results accepted: {str(workspace.fake_results_accepted).lower()}",
                f"- Failed experiments hidden: {str(workspace.failed_experiments_hidden).lower()}",
                "",
                "Blockers:",
                "",
            ]
        )
        lines.extend([f"- {item}" for item in workspace.blockers] or ["- none"])
        lines.extend(["", "Warnings:", ""])
        lines.extend([f"- {item}" for item in workspace.warnings] or ["- none"])
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _gate_blockers(requirements: dict[str, bool]) -> list[str]:
    messages = {
        "deterministic_ci_documented": "Deterministic CI pass evidence is missing or not documented.",
        "v4_codex_workflow_gate_documented": "v0.4 Codex workflow gate status is not documented.",
        "v5_real_literature_gate_documented": "v0.5 real-literature quality gate status is not documented.",
        "successful_fixture_experiment_executed": "No fixture or smoke experiment workspace executed successfully.",
        "failed_experiment_path_recorded": "No failed experiment path was recorded.",
        "result_artifact_parsed": "No result artifact was parsed into metric results.",
        "empirical_claim_generated_from_artifact": "No artifact-backed empirical claim was generated.",
        "reproducibility_checker_run": "Reproducibility checker has not been run.",
        "empirical_reviewer_run": "Empirical reviewer has not been run.",
        "paper_package_v2_exported": "Paper package v2 has not been exported.",
        "no_fake_results_accepted": "A fixture/synthetic/generated result was accepted as paper-ready empirical evidence.",
        "failed_experiments_not_hidden": "Failed experiments are missing or hidden from the paper package.",
    }
    return [message for key, message in messages.items() if not requirements.get(key, False)]


def _gate_warnings(requirements: dict[str, bool]) -> list[str]:
    warnings: list[str] = []
    if not requirements["deterministic_ci_documented"]:
        warnings.append("Write data/release_gate/deterministic_ci.json with passed=true after running CI.")
    if not requirements["v4_codex_workflow_gate_documented"]:
        warnings.append("Run gapforge v4-release-gate --write-report or document why the v4 workflow gate is not applicable.")
    if not requirements["v5_real_literature_gate_documented"]:
        warnings.append("Run gapforge v5-release-gate --write-report or document why the v5 quality gate is not applicable.")
    return warnings


def _workspace_blockers(assessment: V06WorkspaceEmpiricalAssessment) -> list[str]:
    blockers: list[str] = []
    if assessment.fake_results_accepted:
        blockers.append("Fixture/synthetic/generated results are marked as paper-ready empirical evidence.")
    if assessment.failed_experiments_hidden:
        blockers.append("A failed execution exists but is not visible in paper_package_v2/negative_results.md.")
    return blockers


def _workspace_warnings(assessment: V06WorkspaceEmpiricalAssessment) -> list[str]:
    warnings: list[str] = []
    if assessment.result_scope in {"fixture", "synthetic", "generated", "smoke"}:
        warnings.append(
            f"Results are `{assessment.result_scope}` scope; this can validate workflow mechanics "
            "but not broad real-world empirical success."
        )
    if assessment.package_readiness == "planned_experiment" and assessment.successful_execution_ids:
        warnings.append("The workspace has a successful execution but package v2 still reports planned-only readiness.")
    return warnings


def _is_failed_execution(execution: ExperimentExecutionRecord) -> bool:
    return execution.status == "failed" or bool(execution.failure_reason)


def _is_fixture_or_smoke_workspace(executions: list[ExperimentExecutionRecord], datasets: list[DatasetRecord]) -> bool:
    return any(dataset.dataset_type == "fixture" for dataset in datasets) or any(
        _manifest_run_type_from_execution(execution) == "smoke" for execution in executions
    )


def _result_scope(executions: list[ExperimentExecutionRecord], datasets: list[DatasetRecord]) -> str:
    dataset_types = {dataset.dataset_type for dataset in datasets if dataset.dataset_type}
    for candidate in ("fixture", "synthetic", "generated"):
        if candidate in dataset_types:
            return candidate
    run_types = {_manifest_run_type_from_execution(execution) for execution in executions}
    if "smoke" in run_types:
        return "smoke"
    if "pilot" in run_types:
        return "pilot"
    if "main" in run_types:
        return "real"
    return "none"


def _manifest_run_type_from_execution(execution: ExperimentExecutionRecord) -> str:
    # Manifest IDs are built from run names such as manifest-smoke-1. Keep this
    # parser conservative; exact manifest loading is not needed for the gate.
    parts = execution.manifest_id.split("-")
    for value in ("smoke", "pilot", "main", "ablation", "negative_control", "reproduction"):
        if value in parts or value in execution.manifest_id:
            return value
    return ""


def _package_readiness(package_path: Path) -> str:
    if not package_path.exists():
        return ""
    try:
        payload = json.loads(package_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return ""
    return str(payload.get("readiness") or "")


def _fake_results_accepted(package_path: Path, datasets: list[DatasetRecord]) -> bool:
    if not any(dataset.dataset_type in FAKE_DATASET_TYPES for dataset in datasets):
        return False
    return _package_readiness(package_path) == "paper_ready_empirical"


def _failed_experiments_hidden(workspace: ExperimentWorkspace, failed_execution_ids: list[str]) -> bool:
    if not failed_execution_ids:
        return False
    negative_results = Path(workspace.root_dir) / "paper_package_v2" / "negative_results.md"
    if not negative_results.exists():
        return True
    text = negative_results.read_text(encoding="utf-8").lower()
    return not any(execution_id.lower() in text for execution_id in failed_execution_ids)


def _has_empirical_progress(assessments: list[V06WorkspaceEmpiricalAssessment]) -> bool:
    return any(
        item.successful_execution_ids
        or item.failed_execution_ids
        or item.result_artifact_ids
        or item.parsed_execution_ids
        or item.paper_package_v2_exported
        for item in assessments
    )


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        deduped.append(value)
    return deduped
