"""Artifact evaluation smoke runner."""

from __future__ import annotations

import json

from gapforge.artifact_eval.package import artifact_evaluation_package_dir, load_artifact_evaluation_package
from gapforge.config import GapForgeConfig
from gapforge.models import ReproductionRecord, to_plain
from gapforge.replication.runner import ReproductionRunner, render_reproduction_record_markdown


class ArtifactEvaluationSmokeRunner:
    """Run a dry-run smoke check for artifact evaluation packages."""

    def __init__(self, config: GapForgeConfig) -> None:
        self.config = config

    def dry_run(self, package_id: str) -> ReproductionRecord:
        package = load_artifact_evaluation_package(self.config, package_id)
        if not package.replication_package_id:
            record = ReproductionRecord(
                id=f"artifact-eval-smoke-{package_id}",
                package_id=package_id,
                status="fail",
                environment="artifact-evaluation",
                errors=["No replication package is included."],
            )
            self._write_record(package_id, record)
            return record
        package_dir = artifact_evaluation_package_dir(self.config, package_id)
        replication_dir = package_dir / "replication_package"
        record = ReproductionRunner(self.config).reproduce(replication_dir, dry_run=True)
        smoke_record = ReproductionRecord(
            id=f"artifact-eval-smoke-{record.id}",
            package_id=package_id,
            status=record.status,
            environment=record.environment,
            started_at=record.started_at,
            completed_at=record.completed_at,
            commands_run=record.commands_run,
            result_comparison=record.result_comparison,
            errors=record.errors,
            provenance=record.provenance,
        )
        self._write_record(package_id, smoke_record)
        return smoke_record

    def render_markdown(self, record: ReproductionRecord) -> str:
        return render_reproduction_record_markdown(record)

    def _write_record(self, package_id: str, record: ReproductionRecord) -> None:
        smoke_dir = artifact_evaluation_package_dir(self.config, package_id) / "smoke"
        smoke_dir.mkdir(parents=True, exist_ok=True)
        (smoke_dir / f"{record.id}.json").write_text(json.dumps(to_plain(record), indent=2) + "\n", encoding="utf-8")
        (smoke_dir / f"{record.id}.md").write_text(render_reproduction_record_markdown(record), encoding="utf-8")
