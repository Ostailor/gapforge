"""Reproducibility audits for experiment workspaces and executions."""

from __future__ import annotations

import json
from pathlib import Path

from gapforge.baselines import BaselineRegistry
from gapforge.config import GapForgeConfig
from gapforge.datasets import DatasetRegistry
from gapforge.experiments.runner import ExperimentRunner
from gapforge.experiments.workspace import ExperimentWorkspaceManager
from gapforge.metrics import MetricRegistry
from gapforge.models import (
    BaselineRecord,
    DatasetRecord,
    ExperimentExecutionRecord,
    ExperimentResultArtifact,
    ExperimentRunManifest,
    ExperimentWorkspace,
    MetricRecord,
    Provenance,
    ReproducibilityCheckResult,
    ResultSummary,
    to_plain,
)
from gapforge.results import ResultParser
from gapforge.state import utc_now_iso


class ReproducibilityChecker:
    """Audit whether an experiment result is reproducible from durable artifacts."""

    def __init__(self, config: GapForgeConfig) -> None:
        self.config = config
        self.workspace_manager = ExperimentWorkspaceManager(config)
        self.dataset_registry = DatasetRegistry(config)
        self.baseline_registry = BaselineRegistry(config)
        self.metric_registry = MetricRegistry(config)
        self.result_parser = ResultParser(config)

    def check_workspace(self, workspace_id: str) -> ReproducibilityCheckResult:
        workspace = self.workspace_manager.load_workspace(workspace_id)
        executions = self.workspace_manager.list_execution_records(workspace.id)
        if executions:
            return self._check(workspace, executions[-1])
        return self._check(workspace, None)

    def check_execution(self, execution_id: str) -> ReproducibilityCheckResult:
        workspace, execution = ExperimentRunner(self.config).find_execution(execution_id)
        return self._check(workspace, execution)

    def _check(
        self,
        workspace: ExperimentWorkspace,
        execution: ExperimentExecutionRecord | None,
    ) -> ReproducibilityCheckResult:
        checks: dict[str, str] = {}
        blockers: list[str] = []
        warnings: list[str] = []
        manifests = self.workspace_manager.list_manifests(workspace.id)
        manifest = _manifest_for_execution(manifests, execution) if execution is not None else manifests[-1] if manifests else None
        datasets = self.dataset_registry.list_datasets(workspace.id)
        baselines = self.baseline_registry.list_baselines(workspace.id)
        metrics = self.metric_registry.list_metrics(workspace.id)
        artifacts = _execution_artifacts(self.workspace_manager.list_result_artifacts(workspace.id), execution)
        summary = _load_summary(self.result_parser, execution)

        _check_dataset_cards(workspace, datasets, checks, blockers)
        _check_dataset_labels(datasets, checks, blockers)
        _check_baseline_cards(workspace, baselines, checks, blockers)
        _check_metric_definitions(metrics, checks, blockers)
        _check_manifest(manifest, checks, blockers, warnings)
        _check_execution(execution, checks, blockers)
        _check_logs(execution, checks, blockers)
        _check_artifacts(artifacts, checks, blockers)
        _check_confidence_intervals(summary, metrics, checks, blockers, warnings)
        _check_code_scaffold(workspace, checks, warnings)
        _check_expected_outputs(workspace, manifest, execution, checks, blockers)

        status = "fail" if blockers else "warning" if warnings else "pass"
        result = ReproducibilityCheckResult(
            workspace_id=workspace.id,
            execution_id=execution.id if execution is not None else "",
            status=status,
            checks=checks,
            blockers=_unique(blockers),
            warnings=_unique(warnings),
            provenance=Provenance(
                created_by_skill="reproducibility-checker",
                source_ids=[workspace.id, execution.id if execution is not None else ""],
                timestamp=utc_now_iso(),
                reasoning_summary="Audited reproducibility artifacts required before treating experiment results as paper-ready.",
            ),
        )
        self._write_result(workspace, result)
        return result

    def _write_result(self, workspace: ExperimentWorkspace, result: ReproducibilityCheckResult) -> None:
        reports = Path(workspace.root_dir) / "reports"
        reports.mkdir(parents=True, exist_ok=True)
        stem = f"reproducibility_check_{result.execution_id}" if result.execution_id else "reproducibility_check"
        (reports / f"{stem}.json").write_text(json.dumps(to_plain(result), indent=2) + "\n", encoding="utf-8")
        (reports / f"{stem}.md").write_text(render_reproducibility_check_markdown(result), encoding="utf-8")
        (reports / "reproducibility_check.json").write_text(json.dumps(to_plain(result), indent=2) + "\n", encoding="utf-8")
        (reports / "reproducibility_check.md").write_text(render_reproducibility_check_markdown(result), encoding="utf-8")


def render_reproducibility_check_markdown(result: ReproducibilityCheckResult) -> str:
    lines = [
        f"# Reproducibility Check `{result.workspace_id}`",
        "",
        f"- Execution ID: `{result.execution_id or 'none'}`",
        f"- Status: `{result.status}`",
        "",
        "## Checks",
        "",
        "| Check | Status |",
        "| --- | --- |",
    ]
    if result.checks:
        lines.extend(f"| {name} | {status} |" for name, status in result.checks.items())
    else:
        lines.append("| none | not checked |")
    lines.extend(["", "## Blockers", ""])
    lines.extend([f"- {item}" for item in result.blockers] or ["- none"])
    lines.extend(["", "## Warnings", ""])
    lines.extend([f"- {item}" for item in result.warnings] or ["- none"])
    lines.extend(
        [
            "",
            "## Paper-Ready Boundary",
            "",
            (
                "A `pass` result means the execution has reproducibility artifacts. "
                "It does not mean the empirical result is positive, novel, or submission-ready."
            ),
            "",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def _check_dataset_cards(
    workspace: ExperimentWorkspace,
    datasets: list[DatasetRecord],
    checks: dict[str, str],
    blockers: list[str],
) -> None:
    if not datasets:
        checks["dataset_cards"] = "fail: no datasets registered"
        blockers.append("No datasets are registered for the experiment workspace.")
        return
    missing = [record.id for record in datasets if not _dataset_card_path(workspace, record).exists()]
    if missing:
        checks["dataset_cards"] = "fail: missing cards for " + ", ".join(missing)
        blockers.extend(f"Dataset card is missing for `{dataset_id}`." for dataset_id in missing)
    else:
        checks["dataset_cards"] = "pass"


def _check_dataset_labels(datasets: list[DatasetRecord], checks: dict[str, str], blockers: list[str]) -> None:
    suspect = [
        record
        for record in datasets
        if record.dataset_type not in {"fixture", "synthetic", "generated"}
        and any(term in _dataset_text(record) for term in ["fixture", "synthetic", "fake", "generated", "placeholder"])
    ]
    if suspect:
        checks["generated_or_fake_data_labeled"] = "fail: suspected unlabeled generated data"
        blockers.extend(
            f"Dataset `{record.id}` appears fixture/synthetic/generated but is labeled `{record.dataset_type}`." for record in suspect
        )
    else:
        checks["generated_or_fake_data_labeled"] = "pass"


def _check_baseline_cards(
    workspace: ExperimentWorkspace,
    baselines: list[BaselineRecord],
    checks: dict[str, str],
    blockers: list[str],
) -> None:
    if not baselines:
        checks["baseline_cards"] = "fail: no baselines registered"
        blockers.append("No baselines are registered for the experiment workspace.")
        return
    missing = [record.id for record in baselines if not _baseline_card_path(workspace, record).exists()]
    if missing:
        checks["baseline_cards"] = "fail: missing cards for " + ", ".join(missing)
        blockers.extend(f"Baseline card is missing for `{baseline_id}`." for baseline_id in missing)
    else:
        checks["baseline_cards"] = "pass"


def _check_metric_definitions(metrics: list[MetricRecord], checks: dict[str, str], blockers: list[str]) -> None:
    if not metrics:
        checks["metric_definitions"] = "fail: no metrics registered"
        blockers.append("No metric definitions are registered for the experiment workspace.")
    else:
        checks["metric_definitions"] = "pass"


def _check_manifest(
    manifest: ExperimentRunManifest | None,
    checks: dict[str, str],
    blockers: list[str],
    warnings: list[str],
) -> None:
    if manifest is None:
        checks["run_manifest"] = "fail: missing"
        blockers.append("No experiment run manifest exists.")
        return
    checks["run_manifest"] = "pass"
    if manifest.command:
        checks["command_recorded"] = "pass"
    else:
        checks["command_recorded"] = "fail: missing command"
        blockers.append(f"Manifest `{manifest.id}` has no command recorded.")
    if manifest.random_seed:
        checks["random_seed_recorded"] = "pass"
    else:
        checks["random_seed_recorded"] = "warning: random seed missing or default zero"
        warnings.append(f"Manifest `{manifest.id}` has no non-zero random seed recorded.")
    if manifest.environment:
        checks["environment_recorded"] = "pass"
    else:
        checks["environment_recorded"] = "warning: environment missing"
        warnings.append(f"Manifest `{manifest.id}` has no environment metadata recorded.")


def _check_execution(
    execution: ExperimentExecutionRecord | None,
    checks: dict[str, str],
    blockers: list[str],
) -> None:
    if execution is None:
        checks["execution_record"] = "fail: missing"
        blockers.append("No experiment execution record exists.")
    else:
        checks["execution_record"] = "pass" if execution.status in {"complete", "failed"} else f"warning: status {execution.status}"


def _check_logs(
    execution: ExperimentExecutionRecord | None,
    checks: dict[str, str],
    blockers: list[str],
) -> None:
    if execution is None:
        checks["logs_captured"] = "fail: no execution"
        return
    missing = [path for path in [execution.stdout_path, execution.stderr_path] if not path or not Path(path).exists()]
    if missing:
        checks["logs_captured"] = "fail: missing stdout/stderr"
        blockers.append(f"Execution `{execution.id}` is missing captured stdout/stderr logs.")
    else:
        checks["logs_captured"] = "pass"


def _check_artifacts(
    artifacts: list[ExperimentResultArtifact],
    checks: dict[str, str],
    blockers: list[str],
) -> None:
    if not artifacts:
        checks["result_artifacts_hashed"] = "fail: no result artifacts"
        blockers.append("No result artifacts are linked to the execution.")
        return
    missing_hash = [artifact.id for artifact in artifacts if not artifact.sha256 or not Path(artifact.path).exists()]
    if missing_hash:
        checks["result_artifacts_hashed"] = "fail: missing hash/path for " + ", ".join(missing_hash)
        blockers.extend(f"Result artifact `{artifact_id}` is missing a hash or local file." for artifact_id in missing_hash)
    else:
        checks["result_artifacts_hashed"] = "pass"


def _check_confidence_intervals(
    summary: ResultSummary | None,
    metrics: list[MetricRecord],
    checks: dict[str, str],
    blockers: list[str],
    warnings: list[str],
) -> None:
    if summary is None:
        checks["confidence_intervals_when_needed"] = "warning: no parsed result summary"
        warnings.append("No parsed result summary exists; confidence interval requirements could not be audited.")
        return
    metric_lookup = {metric.id: metric for metric in metrics}
    missing = [
        result.metric_id
        for result in summary.metric_results
        if _is_low_fpr(result.metric_id, metric_lookup.get(result.metric_id)) and not result.confidence_interval
    ]
    if missing:
        checks["confidence_intervals_when_needed"] = "fail: missing low-FPR intervals"
        blockers.extend(f"Low-FPR metric `{metric_id}` is missing a confidence interval." for metric_id in missing)
    else:
        checks["confidence_intervals_when_needed"] = "pass"


def _check_code_scaffold(workspace: ExperimentWorkspace, checks: dict[str, str], warnings: list[str]) -> None:
    manifest_path = Path(workspace.root_dir) / "code" / "SCAFFOLD_MANIFEST.json"
    if not manifest_path.exists():
        checks["code_scaffold_version"] = "warning: scaffold manifest missing"
        warnings.append("Code scaffold manifest is missing; scaffold version could not be audited.")
        return
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        checks["code_scaffold_version"] = "warning: invalid scaffold manifest"
        warnings.append("Code scaffold manifest is not valid JSON.")
        return
    version = str(payload.get("scaffold_version", ""))
    if version:
        checks["code_scaffold_version"] = f"pass: {version}"
    else:
        checks["code_scaffold_version"] = "warning: version missing"
        warnings.append("Code scaffold manifest exists but does not record a scaffold version.")


def _check_expected_outputs(
    workspace: ExperimentWorkspace,
    manifest: ExperimentRunManifest | None,
    execution: ExperimentExecutionRecord | None,
    checks: dict[str, str],
    blockers: list[str],
) -> None:
    if manifest is None:
        checks["expected_outputs_present"] = "fail: no manifest"
        return
    if not manifest.expected_outputs:
        checks["expected_outputs_present"] = "fail: no expected outputs recorded"
        blockers.append(f"Manifest `{manifest.id}` has no expected outputs recorded.")
        return
    missing = [item for item in manifest.expected_outputs if not (Path(workspace.root_dir) / item).exists()]
    if missing:
        checks["expected_outputs_present"] = "fail: missing " + ", ".join(missing)
        blockers.extend(f"Expected output `{item}` is missing from workspace `{workspace.id}`." for item in missing)
    elif execution is not None and not execution.result_artifact_ids:
        checks["expected_outputs_present"] = "fail: no linked result artifacts"
        blockers.append(f"Execution `{execution.id}` has no linked result artifacts.")
    else:
        checks["expected_outputs_present"] = "pass"


def _manifest_for_execution(
    manifests: list[ExperimentRunManifest],
    execution: ExperimentExecutionRecord | None,
) -> ExperimentRunManifest | None:
    if execution is None:
        return manifests[-1] if manifests else None
    return next((manifest for manifest in manifests if manifest.id == execution.manifest_id), None)


def _execution_artifacts(
    artifacts: list[ExperimentResultArtifact],
    execution: ExperimentExecutionRecord | None,
) -> list[ExperimentResultArtifact]:
    if execution is None:
        return []
    return [artifact for artifact in artifacts if artifact.id in execution.result_artifact_ids]


def _load_summary(parser: ResultParser, execution: ExperimentExecutionRecord | None) -> ResultSummary | None:
    if execution is None:
        return None
    try:
        return parser.load_or_parse_summary(execution.id)
    except (FileNotFoundError, json.JSONDecodeError, ValueError):
        return None


def _dataset_card_path(workspace: ExperimentWorkspace, record: DatasetRecord) -> Path:
    return Path(workspace.root_dir) / "data" / "cards" / f"{record.id}.card.json"


def _baseline_card_path(workspace: ExperimentWorkspace, record: BaselineRecord) -> Path:
    return Path(workspace.root_dir) / "baselines" / "cards" / f"{record.id}.card.json"


def _dataset_text(record: DatasetRecord) -> str:
    return " ".join([record.id, record.name, record.description, record.source, record.local_path, record.intended_use]).lower()


def _is_low_fpr(metric_id: str, metric: MetricRecord | None) -> bool:
    text = metric_id.lower()
    if metric is not None:
        text += f" {metric.name.lower()} {metric.description.lower()}"
    return any(term in text for term in ["false positive", "false-positive", "false_positive", "fpr", "low-fpr", "low fpr", "specificity"])


def _unique(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result
