"""v0.7 benchmark-specific canary profiles."""

from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path

from gapforge.baselines import BaselineRegistry
from gapforge.benchmarks.comparison import BenchmarkComparisonBuilder
from gapforge.benchmarks.registry import BenchmarkRegistry
from gapforge.config import GapForgeConfig
from gapforge.datasets import DatasetRegistry
from gapforge.datasets.consent import DatasetConsentManager
from gapforge.datasets.download import DatasetDownloadManager
from gapforge.experiment_code import ExperimentCodeScaffolderV2
from gapforge.experiments.runner import ExperimentRunner
from gapforge.experiments.workspace import ExperimentWorkspaceManager
from gapforge.metrics import MetricRegistry
from gapforge.metrics.low_fpr_power import LowFPRPowerChecker
from gapforge.models import ExperimentProtocol, Provenance, ResearchDirection, to_plain
from gapforge.project_memory import ProjectMemoryManager
from gapforge.replication import ReplicationPackageExporter, ReplicationPackageVerifier
from gapforge.results.aggregate import ResultAggregator
from gapforge.results.error_analysis import ErrorAnalysisBuilder
from gapforge.results.parser import ResultParser
from gapforge.state import utc_now_iso

DEFAULT_PUBLIC_SMALL_BENCHMARK_URL = "https://archive.ics.uci.edu/ml/machine-learning-databases/iris/iris.data"


@dataclass(slots=True)
class BenchmarkCanaryProfile:
    id: str
    title: str
    description: str
    ci_safe: bool = True
    requires_real: bool = False
    requires_download_consent: bool = False
    expected_behavior: str = ""
    provenance: Provenance = field(default_factory=lambda: Provenance(created_by_skill="benchmark-canary-profile"))


@dataclass(slots=True)
class BenchmarkCanaryRecord:
    id: str
    profile_id: str
    status: str = "planned"
    project_id: str = ""
    workspace_id: str = ""
    benchmark_id: str = ""
    execution_id: str = ""
    execution_status: str = ""
    replication_package_id: str = ""
    artifact_paths: list[str] = field(default_factory=list)
    validation_summary: dict[str, str] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    issues: list[str] = field(default_factory=list)
    provenance: Provenance = field(default_factory=lambda: Provenance(created_by_skill="benchmark-canary-runner"))


def default_benchmark_canary_profiles() -> list[BenchmarkCanaryProfile]:
    return [
        BenchmarkCanaryProfile(
            id="fixture_benchmark_success",
            title="Fixture Benchmark Success",
            description="CI-safe fixture benchmark with a successful execution and parseable metrics.",
            expected_behavior="complete execution",
        ),
        BenchmarkCanaryProfile(
            id="fixture_benchmark_failure",
            title="Fixture Benchmark Failure",
            description="CI-safe fixture benchmark that preserves a failed execution path.",
            expected_behavior="failed execution preserved",
        ),
        BenchmarkCanaryProfile(
            id="local_public_small_benchmark",
            title="Local Public Small Benchmark",
            description="Optional public small dataset benchmark requiring explicit download consent.",
            ci_safe=False,
            requires_real=True,
            requires_download_consent=True,
            expected_behavior="refuse unless real mode and download consent are explicit",
        ),
        BenchmarkCanaryProfile(
            id="low_fpr_underpowered_benchmark",
            title="Low-FPR Underpowered Benchmark",
            description="CI-safe fixture benchmark showing low-FPR underpowered warnings.",
            expected_behavior="low-FPR warning",
        ),
        BenchmarkCanaryProfile(
            id="replication_package_canary",
            title="Replication Package Canary",
            description="CI-safe fixture benchmark that exports and verifies a replication package.",
            expected_behavior="replication package verified",
        ),
    ]


class BenchmarkCanaryRunner:
    """Run benchmark canaries using real experiment workspace plumbing."""

    def __init__(self, config: GapForgeConfig) -> None:
        self.config = config

    def list_profiles(self) -> list[BenchmarkCanaryProfile]:
        return default_benchmark_canary_profiles()

    def run(self, profile_id: str, *, real: bool = False, download_consent: bool = False) -> BenchmarkCanaryRecord:
        profile = _require_profile(profile_id)
        if profile.requires_real and not real:
            return _refused(profile, ["Real benchmark canary requires --real."])
        if profile.requires_download_consent and not _download_consent_enabled(download_consent):
            return _refused(profile, ["Explicit download consent is required before running this real benchmark canary."])
        if profile.id == "fixture_benchmark_success":
            return self._run_fixture(profile, fail=False, sample_size=75_000, confidence_interval=[0.0008, 0.0012])
        if profile.id == "fixture_benchmark_failure":
            return self._run_fixture(profile, fail=True, sample_size=100, confidence_interval=[])
        if profile.id == "low_fpr_underpowered_benchmark":
            return self._run_fixture(profile, fail=False, sample_size=1_000, confidence_interval=[0.0, 0.002])
        if profile.id == "replication_package_canary":
            record = self._run_fixture(profile, fail=False, sample_size=75_000, confidence_interval=[0.0008, 0.0012])
            workspace = ExperimentWorkspaceManager(self.config).load_workspace(record.workspace_id)
            package = ReplicationPackageExporter(self.config).export_workspace(workspace.id)
            verification = ReplicationPackageVerifier(self.config).verify(Path(package.manifest_path).parent)
            record.replication_package_id = package.id
            record.validation_summary["replication_verification"] = verification.status
            if verification.status != "pass":
                record.status = "failed"
                record.issues.extend(verification.blockers)
            self._write_record(workspace.root_dir, record)
            return record
        if profile.id == "local_public_small_benchmark":
            return self._run_local_public_small(profile)
        raise ValueError(f"Unsupported benchmark canary profile: {profile_id}")

    def _run_local_public_small(self, profile: BenchmarkCanaryProfile) -> BenchmarkCanaryRecord:
        project_id, workspace_id = _create_workspace(self.config, profile)
        workspace = ExperimentWorkspaceManager(self.config).load_workspace(workspace_id)
        dataset, baseline, metric = _register_public_small_dependencies(self.config, workspace_id)
        download = DatasetDownloadManager(self.config).download(
            dataset.id,
            accept_license=True,
            user=os.environ.get("USER", "unknown"),
        )
        if download.status != "downloaded":
            record = BenchmarkCanaryRecord(
                id=f"benchmark-canary-{profile.id}",
                profile_id=profile.id,
                status="failed",
                project_id=project_id,
                workspace_id=workspace_id,
                validation_summary={"dataset_download": download.status},
                issues=[download.error or "Public small benchmark dataset download failed."],
                provenance=Provenance(
                    created_by_skill="benchmark-canary-runner",
                    source_ids=[profile.id, workspace_id, dataset.id],
                    timestamp=utc_now_iso(),
                    reasoning_summary="Real/local public benchmark canary failed before execution because the dataset was unavailable.",
                ),
            )
            self._write_record(workspace.root_dir, record)
            return record
        dataset = DatasetRegistry(self.config).load_dataset(dataset.id)
        benchmark = BenchmarkRegistry(self.config).register_benchmark(
            workspace_id=workspace_id,
            name=profile.title,
            description="Opt-in real/local public small benchmark using the Iris dataset as a binary detection task.",
            domain="public-small",
            task_type="detection",
            source_url=dataset.source_url,
            dataset_ids=[dataset.id],
            baseline_ids=[baseline.id],
            metric_ids=[metric.id],
            license=dataset.license,
            expected_splits=["test"],
            evaluation_protocol=(
                "Treat Iris virginica as the positive class. Compare an always-negative heuristic baseline against "
                "a petal-width threshold detector and report false-positive rate with artifact-backed predictions."
            ),
            limitations=[
                "Small public benchmark canary for execution/replication validation only.",
                "Not evidence of broad benchmark performance or domain research quality.",
            ],
        )
        ExperimentCodeScaffolderV2(self.config).scaffold(workspace_id)
        execution = _run_public_small_execution(
            self.config,
            workspace_id=workspace_id,
            profile=profile,
            dataset_path=Path(dataset.local_path),
            dataset_id=dataset.id,
            baseline_id=baseline.id,
            metric_id=metric.id,
            benchmark_id=benchmark.id,
        )
        artifacts = ExperimentWorkspaceManager(self.config).list_result_artifacts(workspace_id)
        validation_summary = {"dataset_download": download.status, "execution": execution.status}
        warnings: list[str] = []
        issues: list[str] = []
        status = "passed" if execution.status == "complete" else "failed"
        if execution.status != "complete":
            issues.append("Public small benchmark execution failed: " + (execution.failure_reason or "no failure reason recorded."))
        if execution.status == "complete":
            _run_public_small_postprocessing(
                self.config,
                workspace_id=workspace_id,
                benchmark_id=benchmark.id,
                execution_id=execution.id,
                validation_summary=validation_summary,
                warnings=warnings,
                issues=issues,
            )
        package = ReplicationPackageExporter(self.config).latest_for_workspace(workspace_id)
        record = BenchmarkCanaryRecord(
            id=f"benchmark-canary-{profile.id}",
            profile_id=profile.id,
            status=status if not issues else "failed",
            project_id=project_id,
            workspace_id=workspace_id,
            benchmark_id=benchmark.id,
            execution_id=execution.id,
            execution_status=execution.status,
            replication_package_id=package.id if package is not None else "",
            artifact_paths=[artifact.path for artifact in artifacts],
            validation_summary=validation_summary,
            warnings=list(dict.fromkeys(warnings)),
            issues=list(dict.fromkeys(issues)),
            provenance=Provenance(
                created_by_skill="benchmark-canary-runner",
                source_ids=[profile.id, workspace_id, dataset.id, benchmark.id, execution.id],
                timestamp=utc_now_iso(),
                reasoning_summary=(
                    "Ran an opt-in real/local public small benchmark through download consent, execution, parsing, "
                    "comparison, error analysis, and replication export."
                ),
            ),
        )
        self._write_record(workspace.root_dir, record)
        return record

    def _run_fixture(
        self,
        profile: BenchmarkCanaryProfile,
        *,
        fail: bool,
        sample_size: int,
        confidence_interval: list[float],
    ) -> BenchmarkCanaryRecord:
        project_id, workspace_id = _create_workspace(self.config, profile)
        workspace = ExperimentWorkspaceManager(self.config).load_workspace(workspace_id)
        dataset, baseline, metric = _register_dependencies(self.config, workspace_id)
        benchmark = BenchmarkRegistry(self.config).register_benchmark(
            workspace_id=workspace_id,
            name=profile.title,
            description=profile.description,
            domain="fixture",
            task_type="detection",
            dataset_ids=[dataset.id],
            baseline_ids=[baseline.id],
            metric_ids=[metric.id],
            license="CC0",
            expected_splits=["test"],
            evaluation_protocol="Run fixture split and report false positive rate with confidence intervals.",
        )
        ExperimentCodeScaffolderV2(self.config).scaffold(workspace_id)
        execution = _run_canary_execution(
            self.config,
            workspace_id=workspace_id,
            profile=profile,
            fail=fail,
            sample_size=sample_size,
            confidence_interval=confidence_interval,
        )
        artifacts = ExperimentWorkspaceManager(self.config).list_result_artifacts(workspace_id)
        warnings: list[str] = []
        issues: list[str] = []
        validation_summary = {"execution": execution.status}
        status = "passed" if execution.status == "complete" else "failed"
        if execution.status == "failed":
            issues.append("Benchmark canary execution failed: " + (execution.failure_reason or "no failure reason recorded."))
        if profile.id == "low_fpr_underpowered_benchmark":
            low_fpr_check = LowFPRPowerChecker(self.config).check_execution(execution.id)
            validation_summary["low_fpr_power"] = low_fpr_check.status
            warnings.extend(low_fpr_check.warnings)
            issues.extend(low_fpr_check.blockers)
            status = "warning" if low_fpr_check.status == "fail" else low_fpr_check.status
        record = BenchmarkCanaryRecord(
            id=f"benchmark-canary-{profile.id}",
            profile_id=profile.id,
            status=status,
            project_id=project_id,
            workspace_id=workspace_id,
            benchmark_id=benchmark.id,
            execution_id=execution.id,
            execution_status=execution.status,
            artifact_paths=[artifact.path for artifact in artifacts],
            validation_summary=validation_summary,
            warnings=list(dict.fromkeys(warnings)),
            issues=list(dict.fromkeys(issues)),
            provenance=Provenance(
                created_by_skill="benchmark-canary-runner",
                source_ids=[profile.id, workspace_id, benchmark.id, execution.id],
                timestamp=utc_now_iso(),
                reasoning_summary="Ran a v0.7 benchmark canary through fixture-safe experiment execution plumbing.",
            ),
        )
        self._write_record(workspace.root_dir, record)
        return record

    def _write_record(self, workspace_root: str, record: BenchmarkCanaryRecord) -> None:
        canary_dir = Path(workspace_root) / "benchmark_canaries"
        canary_dir.mkdir(parents=True, exist_ok=True)
        (canary_dir / f"{record.id}.json").write_text(json.dumps(to_plain(record), indent=2) + "\n", encoding="utf-8")
        (canary_dir / f"{record.id}.md").write_text(render_benchmark_canary_record(record), encoding="utf-8")


def render_benchmark_canary_profiles(profiles: list[BenchmarkCanaryProfile]) -> str:
    lines = ["# Benchmark Canary Profiles", ""]
    for profile in profiles:
        lines.extend(
            [
                f"## `{profile.id}`",
                "",
                f"- Title: {profile.title}",
                f"- CI safe: {str(profile.ci_safe).lower()}",
                f"- Requires real mode: {str(profile.requires_real).lower()}",
                f"- Requires download consent: {str(profile.requires_download_consent).lower()}",
                f"- Expected behavior: {profile.expected_behavior or 'not specified'}",
                "",
                profile.description,
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def render_benchmark_canary_record(record: BenchmarkCanaryRecord) -> str:
    lines = [
        f"# Benchmark Canary Record `{record.id}`",
        "",
        f"- Profile ID: `{record.profile_id}`",
        f"- Status: `{record.status}`",
        f"- Project ID: `{record.project_id or 'none'}`",
        f"- Workspace ID: `{record.workspace_id or 'none'}`",
        f"- Benchmark ID: `{record.benchmark_id or 'none'}`",
        f"- Execution ID: `{record.execution_id or 'none'}`",
        f"- Execution status: `{record.execution_status or 'none'}`",
        f"- Replication package ID: `{record.replication_package_id or 'none'}`",
        "",
        "## Validation Summary",
        "",
    ]
    lines.extend([f"- `{key}`: {value}" for key, value in sorted(record.validation_summary.items())] or ["- none"])
    lines.extend(["", "## Artifact Paths", ""])
    lines.extend([f"- `{path}`" for path in record.artifact_paths] or ["- none"])
    lines.extend(["", "## Warnings", ""])
    lines.extend([f"- {warning}" for warning in record.warnings] or ["- none"])
    lines.extend(["", "## Issues", ""])
    lines.extend([f"- {issue}" for issue in record.issues] or ["- none"])
    return "\n".join(lines).rstrip() + "\n"


def _require_profile(profile_id: str) -> BenchmarkCanaryProfile:
    for profile in default_benchmark_canary_profiles():
        if profile.id == profile_id:
            return profile
    raise ValueError(f"Unknown benchmark canary profile: {profile_id}")


def _refused(profile: BenchmarkCanaryProfile, issues: list[str]) -> BenchmarkCanaryRecord:
    return BenchmarkCanaryRecord(
        id=f"benchmark-canary-{profile.id}",
        profile_id=profile.id,
        status="refused",
        issues=issues,
        provenance=Provenance(
            created_by_skill="benchmark-canary-runner",
            source_ids=[profile.id],
            timestamp=utc_now_iso(),
            reasoning_summary="Refused benchmark canary because required real-mode safety preconditions were absent.",
        ),
    )


def _download_consent_enabled(download_consent: bool) -> bool:
    return download_consent or os.environ.get("GAPFORGE_BENCHMARK_DOWNLOAD_CONSENT") == "1"


def _create_workspace(config: GapForgeConfig, profile: BenchmarkCanaryProfile) -> tuple[str, str]:
    project_manager = ProjectMemoryManager(config)
    program = project_manager.create_project(f"Benchmark Canary {profile.id}")
    direction_id = f"direction-{profile.id}"
    program.research_directions = [
        ResearchDirection(
            id=direction_id,
            project_id=program.project.id,
            title=profile.title,
            summary=profile.description,
            maturity="experiment_ready",
        )
    ]
    program.experiment_protocols.append(
        ExperimentProtocol(
            id=f"protocol-{profile.id}",
            direction_id=direction_id,
            linked_experiment_plan_id=f"experiment-{profile.id}",
            objective=f"Run benchmark canary `{profile.id}`.",
            hypothesis="Benchmark canary exercises v0.7 execution safety paths.",
            datasets=["fixture"],
            metrics=["false positive rate"],
            statistical_tests=["binomial confidence intervals"],
            expected_artifacts=["metrics.json"],
        )
    )
    project_manager.save_project(program)
    workspace = ExperimentWorkspaceManager(config).create_workspace(project_id=program.project.id, direction_id=direction_id)
    return program.project.id, workspace.id


def _register_dependencies(config: GapForgeConfig, workspace_id: str):
    workspace = ExperimentWorkspaceManager(config).load_workspace(workspace_id)
    dataset_path = Path(workspace.root_dir) / "data" / "fixture.csv"
    dataset_path.write_text("id,split,label,pred\n1,test,0,0\n2,test,0,0\n", encoding="utf-8")
    dataset = DatasetRegistry(config).register_dataset(
        workspace_id=workspace_id,
        name="benchmark canary fixture data",
        path=dataset_path,
        dataset_type="fixture",
        license="CC0",
        intended_use="CI-safe benchmark canary validation.",
    )
    baseline = BaselineRegistry(config).register_baseline(
        workspace_id=workspace_id,
        name="canary heuristic baseline",
        baseline_type="heuristic",
        implementation_path="code/src/baselines.py",
        code_available=True,
    )
    metric = MetricRegistry(config).register_metric(workspace_id=workspace_id, name="false positive rate")
    return dataset, baseline, metric


def _register_public_small_dependencies(config: GapForgeConfig, workspace_id: str):
    workspace = ExperimentWorkspaceManager(config).load_workspace(workspace_id)
    placeholder = Path(workspace.root_dir) / "data" / "public_small_download_placeholder.csv"
    placeholder.write_text("downloaded_by_gapforge\n", encoding="utf-8")
    source_url = os.environ.get("GAPFORGE_LOCAL_PUBLIC_BENCHMARK_URL", DEFAULT_PUBLIC_SMALL_BENCHMARK_URL)
    dataset = DatasetRegistry(config).register_dataset(
        workspace_id=workspace_id,
        name="UCI Iris public small benchmark",
        path=placeholder,
        dataset_type="benchmark",
        description="Small public Iris dataset used as an opt-in local benchmark canary.",
        source="UCI Machine Learning Repository",
        source_url=source_url,
        version="iris.data",
        license="UCI ML Repository terms",
        intended_use="Opt-in real/local public benchmark execution validation.",
        limitations=[
            "Small tabular benchmark; validates benchmark execution mechanics, not broad empirical performance.",
            "Terms and citation obligations must be reviewed before redistribution.",
        ],
        safety_notes=["Downloaded data remains cache-managed and should not be committed by default."],
    )
    DatasetConsentManager(config).accept(
        dataset_id=dataset.id,
        user=os.environ.get("USER", "unknown"),
        consent_text=(
            "User explicitly requested broad real benchmark validation and passed benchmark download consent for the "
            "opt-in local public small benchmark canary."
        ),
        accepted_terms=[dataset.license, source_url],
    )
    baseline = BaselineRegistry(config).register_baseline(
        workspace_id=workspace_id,
        name="always-negative iris detector",
        description="Required heuristic baseline that predicts non-virginica for every row.",
        baseline_type="heuristic",
        implementation_path="code/run_local_public_small_benchmark.py",
        code_available=True,
        required_for_submission=True,
        risk_if_missing="Without this baseline, the canary cannot distinguish proposed detector behavior from a trivial detector.",
        expected_inputs=["iris CSV rows"],
        expected_outputs=["binary detection predictions"],
    )
    metric = MetricRegistry(config).register_metric(
        workspace_id=workspace_id,
        name="false positive rate",
        description="Fraction of non-virginica examples incorrectly predicted as virginica.",
        metric_type="detection",
        higher_is_better=False,
        required_inputs=["label", "prediction"],
        edge_cases=["Zero false positives still requires a confidence interval or upper bound."],
    )
    return dataset, baseline, metric


def _run_public_small_execution(
    config: GapForgeConfig,
    *,
    workspace_id: str,
    profile: BenchmarkCanaryProfile,
    dataset_path: Path,
    dataset_id: str,
    baseline_id: str,
    metric_id: str,
    benchmark_id: str,
):
    workspace = ExperimentWorkspaceManager(config).load_workspace(workspace_id)
    metrics_output = Path(workspace.root_dir) / "results" / "metrics.json"
    predictions_output = Path(workspace.root_dir) / "results" / "predictions.json"
    script = Path(workspace.root_dir) / "code" / f"run_{profile.id}.py"
    script.write_text(
        "import csv\n"
        "import json\n"
        "import math\n"
        "from pathlib import Path\n\n"
        f"dataset_path = Path({str(dataset_path)!r})\n"
        f"metrics_output = Path({str(metrics_output)!r})\n"
        f"predictions_output = Path({str(predictions_output)!r})\n"
        f"dataset_id = {dataset_id!r}\n"
        f"baseline_id = {baseline_id!r}\n"
        f"metric_id = {metric_id!r}\n"
        f"benchmark_id = {benchmark_id!r}\n\n"
        "rows = []\n"
        "with dataset_path.open(newline='', encoding='utf-8') as handle:\n"
        "    for raw in csv.reader(handle):\n"
        "        if not raw or len(raw) < 5:\n"
        "            continue\n"
        "        if raw[0].strip().lower() in {'sepal_length', 'sepal_length_cm'}:\n"
        "            continue\n"
        "        try:\n"
        "            sepal_length = float(raw[0])\n"
        "            sepal_width = float(raw[1])\n"
        "            petal_length = float(raw[2])\n"
        "            petal_width = float(raw[3])\n"
        "        except ValueError:\n"
        "            continue\n"
        "        species = raw[4].strip()\n"
        "        label = 1 if species.lower().endswith('virginica') else 0\n"
        "        proposed = 1 if petal_width >= 1.7 else 0\n"
        "        rows.append({\n"
        "            'id': str(len(rows) + 1),\n"
        "            'split': 'test',\n"
        "            'species': species,\n"
        "            'sepal_length': sepal_length,\n"
        "            'sepal_width': sepal_width,\n"
        "            'petal_length': petal_length,\n"
        "            'petal_width': petal_width,\n"
        "            'label': label,\n"
        "            'prediction': proposed,\n"
        "        })\n"
        "if not rows:\n"
        "    raise SystemExit('No parseable Iris rows found in downloaded dataset.')\n\n"
        "def fpr(prediction_key):\n"
        "    negatives = [row for row in rows if row['label'] == 0]\n"
        "    false_positives = sum(1 for row in negatives if row[prediction_key] == 1)\n"
        "    value = false_positives / len(negatives) if negatives else 0.0\n"
        "    # Simple Wilson-style interval for canary uncertainty reporting; this is not a broad benchmark claim.\n"
        "    if not negatives:\n"
        "        return value, []\n"
        "    n = len(negatives)\n"
        "    z = 1.96\n"
        "    denom = 1 + z * z / n\n"
        "    center = (value + z * z / (2 * n)) / denom\n"
        "    margin = z * math.sqrt((value * (1 - value) + z * z / (4 * n)) / n) / denom\n"
        "    return value, [max(0.0, center - margin), min(1.0, center + margin)]\n\n"
        "for row in rows:\n"
        "    row['baseline_prediction'] = 0\n"
        "baseline_fpr, baseline_ci = fpr('baseline_prediction')\n"
        "proposed_fpr, proposed_ci = fpr('prediction')\n"
        "metrics_output.parent.mkdir(parents=True, exist_ok=True)\n"
        "predictions_output.parent.mkdir(parents=True, exist_ok=True)\n"
        "metrics_output.write_text(json.dumps({\n"
        "    'benchmark_id': benchmark_id,\n"
        "    'metric_results': [\n"
        "        {\n"
        "            'benchmark_id': benchmark_id,\n"
        "            'dataset_id': dataset_id,\n"
        "            'baseline_id': baseline_id,\n"
        "            'metric_id': metric_id,\n"
        "            'split_name': 'test',\n"
        "            'value': baseline_fpr,\n"
        "            'sample_size': sum(1 for row in rows if row['label'] == 0),\n"
        "            'confidence_interval': baseline_ci,\n"
        "        },\n"
        "        {\n"
        "            'benchmark_id': benchmark_id,\n"
        "            'dataset_id': dataset_id,\n"
        "            'baseline_id': 'proposed-petal-width-threshold',\n"
        "            'metric_id': metric_id,\n"
        "            'split_name': 'test',\n"
        "            'value': proposed_fpr,\n"
        "            'sample_size': sum(1 for row in rows if row['label'] == 0),\n"
        "            'confidence_interval': proposed_ci,\n"
        "        },\n"
        "    ],\n"
        "    'limitations': ['Opt-in small public benchmark canary; not broad benchmark performance evidence.'],\n"
        "}, indent=2) + '\\n', encoding='utf-8')\n"
        "predictions_output.write_text(json.dumps({'predictions': rows}, indent=2) + '\\n', encoding='utf-8')\n",
        encoding="utf-8",
    )
    manager = ExperimentWorkspaceManager(config)
    manifest = manager.create_manifest(
        workspace_id=workspace_id,
        run_type="main",
        run_name="local_public_small_benchmark",
        dataset_ids=[dataset_id],
        baseline_ids=[baseline_id],
        metric_ids=[metric_id],
        command=f"{sys.executable} {script}",
        expected_outputs=["results/metrics.json", "results/predictions.json"],
        random_seed=123,
    )
    manifest.environment = {"python": sys.version.split()[0], "resource_environment": "local", "dataset_source": "UCI Iris"}
    manifest_path = Path(workspace.root_dir) / "manifests" / f"{manifest.id}.json"
    manifest_path.write_text(json.dumps(to_plain(manifest), indent=2) + "\n", encoding="utf-8")
    return ExperimentRunner(config).run(workspace_id=workspace_id, manifest_id=manifest.id).execution


def _run_public_small_postprocessing(
    config: GapForgeConfig,
    *,
    workspace_id: str,
    benchmark_id: str,
    execution_id: str,
    validation_summary: dict[str, str],
    warnings: list[str],
    issues: list[str],
) -> None:
    try:
        ResultParser(config).parse_execution(execution_id)
        validation_summary["result_parse"] = "pass"
    except Exception as exc:
        validation_summary["result_parse"] = "failed"
        issues.append(f"Result parsing failed: {exc}")
    try:
        ResultAggregator(config).aggregate(workspace_id, include_smoke=True)
        validation_summary["result_aggregation"] = "pass"
    except Exception as exc:
        validation_summary["result_aggregation"] = "failed"
        issues.append(f"Result aggregation failed: {exc}")
    try:
        ErrorAnalysisBuilder(config).analyze_execution(execution_id)
        validation_summary["error_analysis"] = "pass"
    except Exception as exc:
        validation_summary["error_analysis"] = "failed"
        issues.append(f"Error analysis failed: {exc}")
    try:
        comparison = BenchmarkComparisonBuilder(config).compare(workspace_id=workspace_id, benchmark_id=benchmark_id)
        validation_summary["benchmark_comparison"] = "pass"
        warnings.extend(comparison.limitations)
    except Exception as exc:
        validation_summary["benchmark_comparison"] = "failed"
        issues.append(f"Benchmark comparison failed: {exc}")
    try:
        package = ReplicationPackageExporter(config).export_workspace(workspace_id)
        verification = ReplicationPackageVerifier(config).verify(Path(package.manifest_path).parent)
        validation_summary["replication_package"] = package.id
        validation_summary["replication_verification"] = verification.status
        warnings.extend(verification.blockers)
        if verification.status != "pass":
            issues.extend(verification.blockers)
    except Exception as exc:
        validation_summary["replication_verification"] = "failed"
        issues.append(f"Replication export/verification failed: {exc}")


def _run_canary_execution(
    config: GapForgeConfig,
    *,
    workspace_id: str,
    profile: BenchmarkCanaryProfile,
    fail: bool,
    sample_size: int,
    confidence_interval: list[float],
):
    workspace = ExperimentWorkspaceManager(config).load_workspace(workspace_id)
    output = Path(workspace.root_dir) / "results" / "metrics.json"
    script = Path(workspace.root_dir) / "code" / f"run_{profile.id}.py"
    metric_payload = {
        "metric_results": [
            {
                "metric_id": "false positive rate",
                "value": 0.001 if sample_size < 10_000 else 0.0,
                "sample_size": sample_size,
                "confidence_interval": confidence_interval,
            }
        ]
    }
    script.write_text(
        "from pathlib import Path\n"
        f"Path({str(output)!r}).write_text({json.dumps(metric_payload)!r} + '\\n', encoding='utf-8')\n"
        + ("raise SystemExit(2)\n" if fail else ""),
        encoding="utf-8",
    )
    manager = ExperimentWorkspaceManager(config)
    manifest = manager.create_manifest(
        workspace_id=workspace_id,
        run_type="smoke",
        command=f"{sys.executable} {script}",
        expected_outputs=["results/metrics.json"],
        random_seed=123,
    )
    manifest.environment = {"python": sys.version.split()[0], "resource_environment": "local"}
    manifest_path = Path(workspace.root_dir) / "manifests" / f"{manifest.id}.json"
    manifest_path.write_text(json.dumps(to_plain(manifest), indent=2) + "\n", encoding="utf-8")
    return ExperimentRunner(config).run(workspace_id=workspace_id, manifest_id=manifest.id).execution
