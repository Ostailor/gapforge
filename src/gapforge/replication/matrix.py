"""Reproducibility matrix reporting across reproduction environments."""

from __future__ import annotations

import json
from pathlib import Path

from gapforge.config import GapForgeConfig
from gapforge.models import Provenance, ReplicationManifest, ReproducibilityMatrix, ReproductionRecord, from_dict, to_plain
from gapforge.state import utc_now_iso


class ReproducibilityMatrixBuilder:
    """Summarize reproduction attempts for a package or workspace."""

    def __init__(self, config: GapForgeConfig) -> None:
        self.config = config

    def for_workspace(self, workspace_id: str) -> ReproducibilityMatrix:
        package_dir = _latest_package_for_workspace(self.config, workspace_id)
        if package_dir is None:
            raise FileNotFoundError(f"No replication package found for workspace {workspace_id}")
        matrix = self._build(package_dir, workspace_id=workspace_id)
        self._write_matrix(package_dir, matrix)
        return matrix

    def for_package_id(self, package_id: str) -> ReproducibilityMatrix:
        package_dir = _find_package_by_id(self.config, package_id)
        if package_dir is None:
            raise FileNotFoundError(f"No replication package found for package id {package_id}")
        matrix = self._build(package_dir, workspace_id=_workspace_id_from_package_dir(package_dir))
        self._write_matrix(package_dir, matrix)
        return matrix

    def _build(self, package_dir: Path, *, workspace_id: str) -> ReproducibilityMatrix:
        manifest = _load_manifest(package_dir)
        records = _load_reproduction_records(package_dir)
        environments = sorted({*(record.environment or "local" for record in records), _manifest_environment(manifest)})
        differences = _differences(records)
        return ReproducibilityMatrix(
            workspace_id=workspace_id,
            package_id=manifest.package_id,
            environments=environments,
            reproduction_records=records,
            pass_count=sum(record.status == "pass" for record in records),
            warning_count=sum(record.status in {"warning", "planned", "running"} for record in records),
            fail_count=sum(record.status == "fail" for record in records),
            differences=differences,
            provenance=Provenance(
                created_by_skill="reproducibility-matrix",
                source_ids=[manifest.package_id, *[record.id for record in records]],
                timestamp=utc_now_iso(),
                reasoning_summary="Summarized reproduction attempts across environments without generalizing from a single run.",
            ),
        )

    def _write_matrix(self, package_dir: Path, matrix: ReproducibilityMatrix) -> None:
        reports = package_dir / "reproducibility_matrix"
        reports.mkdir(parents=True, exist_ok=True)
        (reports / "reproducibility_matrix.json").write_text(json.dumps(to_plain(matrix), indent=2) + "\n", encoding="utf-8")
        (reports / "reproducibility_matrix.md").write_text(render_reproducibility_matrix_markdown(matrix), encoding="utf-8")


def render_reproducibility_matrix_markdown(matrix: ReproducibilityMatrix) -> str:
    lines = [
        f"# Reproducibility Matrix `{matrix.package_id}`",
        "",
        f"- Workspace ID: `{matrix.workspace_id or 'unknown'}`",
        f"- Environments: {', '.join(f'`{item}`' for item in matrix.environments) or 'none'}",
        f"- Pass: {matrix.pass_count}",
        f"- Warning: {matrix.warning_count}",
        f"- Fail: {matrix.fail_count}",
        "- Interpretation: No single environment result should be generalized to all compute settings.",
        "",
        "## Reproduction Records",
        "",
        "| Record | Environment | Status | Comparisons | Errors |",
        "| --- | --- | --- | --- | --- |",
    ]
    if matrix.reproduction_records:
        for record in matrix.reproduction_records:
            comparisons = ", ".join(f"{path}={status}" for path, status in sorted(record.result_comparison.items())) or "none"
            errors = "; ".join(record.errors) or "none"
            lines.append(f"| `{record.id}` | `{record.environment}` | `{record.status}` | {comparisons} | {errors} |")
    else:
        lines.append("| none | none | none | none | none |")
    lines.extend(["", "## Differences", ""])
    lines.extend([f"- {item}" for item in matrix.differences] or ["- none"])
    return "\n".join(lines).rstrip() + "\n"


def _load_manifest(package_dir: Path) -> ReplicationManifest:
    path = package_dir / "replication_manifest.json"
    if not path.exists():
        raise FileNotFoundError(f"No replication manifest found at {path}")
    return from_dict(ReplicationManifest, json.loads(path.read_text(encoding="utf-8")))


def _load_reproduction_records(package_dir: Path) -> list[ReproductionRecord]:
    records_dir = package_dir / "reproductions"
    if not records_dir.exists():
        return []
    return [from_dict(ReproductionRecord, json.loads(path.read_text(encoding="utf-8"))) for path in sorted(records_dir.glob("*.json"))]


def _differences(records: list[ReproductionRecord]) -> list[str]:
    differences: list[str] = []
    for record in records:
        for output_path, status in sorted(record.result_comparison.items()):
            if status != "match":
                differences.append(f"{record.environment}/{record.id}: `{output_path}` comparison is `{status}`.")
        for error in record.errors:
            differences.append(f"{record.environment}/{record.id}: {error}")
    return list(dict.fromkeys(differences))


def _latest_package_for_workspace(config: GapForgeConfig, workspace_id: str) -> Path | None:
    packages = sorted(config.project_root.glob(f"*/experiment_workspaces/{workspace_id}/replication_packages/*"))
    return next((path for path in reversed(packages) if (path / "replication_manifest.json").exists()), None)


def _find_package_by_id(config: GapForgeConfig, package_id: str) -> Path | None:
    packages = sorted(config.project_root.glob(f"*/experiment_workspaces/*/replication_packages/{package_id}"))
    return next((path for path in packages if (path / "replication_manifest.json").exists()), None)


def _workspace_id_from_package_dir(package_dir: Path) -> str:
    try:
        return package_dir.parents[1].name
    except IndexError:
        return ""


def _manifest_environment(manifest: ReplicationManifest) -> str:
    return (
        manifest.environment.get("resource_environment")
        or manifest.environment.get("environment_type")
        or manifest.environment.get("compute_environment")
        or "local"
    )
