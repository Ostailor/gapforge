"""Offline v0.7 benchmark, aggregation, and replication smoke test."""

from __future__ import annotations

import json
from pathlib import Path

from gapforge.benchmarks.canaries import BenchmarkCanaryRunner
from gapforge.benchmarks.comparison import BenchmarkComparisonBuilder
from gapforge.config import GapForgeConfig
from gapforge.experiments.workspace import ExperimentWorkspaceManager
from gapforge.jobs import JobScheduler
from gapforge.release_gate.v07 import V07ReleaseGateEnforcer
from gapforge.replication import ReplicationPackageExporter, ReplicationPackageVerifier
from gapforge.results import ErrorAnalysisBuilder, ResultAggregator, ResultParser


def main() -> int:
    config = GapForgeConfig.from_cwd(Path.cwd())
    config.ensure_dirs()
    _write_prerequisite_gate_docs(config)

    runner = BenchmarkCanaryRunner(config)
    success = runner.run("fixture_benchmark_success")
    failure = runner.run("fixture_benchmark_failure")
    low_fpr = runner.run("low_fpr_underpowered_benchmark")
    replication_canary = runner.run("replication_package_canary")

    if success.status != "passed":
        raise RuntimeError(f"fixture_benchmark_success did not pass: {success.issues}")
    if failure.status != "failed":
        raise RuntimeError(f"fixture_benchmark_failure did not record the failed path: {failure.status}")
    if low_fpr.status not in {"warning", "failed"}:
        raise RuntimeError(f"low_fpr_underpowered_benchmark did not expose an underpowered warning: {low_fpr.status}")
    if replication_canary.validation_summary.get("replication_verification") != "pass":
        raise RuntimeError("replication_package_canary did not verify its replication package.")

    workspace_manager = ExperimentWorkspaceManager(config)
    manifests = workspace_manager.list_manifests(success.workspace_id)
    if not manifests:
        raise RuntimeError("fixture_benchmark_success did not create an experiment manifest.")

    scheduler = JobScheduler(config)
    job = scheduler.submit(workspace_id=success.workspace_id, manifest_id=manifests[0].id)
    scheduler.run_next(job.queue_id)
    completed_job = scheduler.get_job(job.id)
    if not completed_job.execution_id:
        raise RuntimeError("local job did not create an experiment execution record.")

    ResultParser(config).parse_execution(completed_job.execution_id)
    ResultAggregator(config).aggregate(success.workspace_id, include_smoke=True)
    ErrorAnalysisBuilder(config).analyze_execution(completed_job.execution_id)
    BenchmarkComparisonBuilder(config).compare(workspace_id=success.workspace_id, benchmark_id=success.benchmark_id)
    package = ReplicationPackageExporter(config).export_workspace(success.workspace_id)
    verification = ReplicationPackageVerifier(config).verify(Path(package.manifest_path).parent)
    if verification.status != "pass":
        raise RuntimeError(f"replication package verification did not pass: {verification.blockers}")

    enforcer = V07ReleaseGateEnforcer(config)
    gate = enforcer.evaluate()
    json_path, md_path = enforcer.write_outputs(gate)
    if not gate.passed:
        raise RuntimeError("v0.7 fixture release gate did not pass: " + "; ".join(gate.blockers))

    print("v0.7 smoke completed")
    print(f"success canary: {success.id} workspace={success.workspace_id}")
    print(f"failure canary: {failure.id} status={failure.status}")
    print(f"low-FPR canary: {low_fpr.id} status={low_fpr.status}")
    print(f"replication canary: {replication_canary.id}")
    print(f"local job: {completed_job.id} execution={completed_job.execution_id}")
    print(f"release gate: {json_path} {md_path}")
    return 0


def _write_prerequisite_gate_docs(config: GapForgeConfig) -> None:
    release_dir = config.data_dir / "release_gate"
    release_dir.mkdir(parents=True, exist_ok=True)
    (release_dir / "deterministic_ci.json").write_text(json.dumps({"passed": True}) + "\n", encoding="utf-8")
    (release_dir / "v0.6_latest.json").write_text(
        json.dumps({"passed": True, "status": "pass", "scope": "v7-smoke-prerequisite"}) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    raise SystemExit(main())
