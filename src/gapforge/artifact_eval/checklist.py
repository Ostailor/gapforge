"""Artifact evaluation package checklist."""

from __future__ import annotations

import json
from pathlib import Path

from gapforge.artifact_eval.package import artifact_evaluation_package_dir, load_artifact_evaluation_package
from gapforge.config import GapForgeConfig
from gapforge.models import ArtifactEvaluationChecklist, Provenance, ReplicationManifest, ReplicationPackage, from_dict, to_plain
from gapforge.state import utc_now_iso


class ArtifactEvaluationChecklistManager:
    """Check artifact evaluation packages for review readiness."""

    def __init__(self, config: GapForgeConfig) -> None:
        self.config = config

    def check(self, package_id: str) -> ArtifactEvaluationChecklist:
        package = load_artifact_evaluation_package(self.config, package_id)
        package_dir = artifact_evaluation_package_dir(self.config, package_id)
        checks: dict[str, str] = {}
        blockers: list[str] = []
        warnings: list[str] = []
        replication_dir = package_dir / "replication_package"
        manifest_path = replication_dir / "replication_manifest.json"
        replication_record = replication_dir / "replication_package.json"
        manifest = _load_manifest(manifest_path)

        _check_replication_package(package.replication_package_id, replication_dir, replication_record, manifest, checks, blockers)
        _check_instructions(package, package_dir, checks, blockers)
        _check_expected_outputs(package, manifest, checks, blockers)
        _check_hardware_time(package, checks, blockers)
        _check_restricted_data(replication_dir, checks, blockers, warnings)

        status = "ready" if not blockers else "blocked"
        checklist = ArtifactEvaluationChecklist(
            package_id=package_id,
            checks=checks,
            blockers=_unique(blockers),
            warnings=_unique(warnings),
            status=status,
            provenance=Provenance(
                created_by_skill="artifact-evaluation-checklist",
                source_ids=[package_id, package.replication_package_id],
                timestamp=utc_now_iso(),
                reasoning_summary=(
                    "Checked artifact evaluation package contents against replication, instruction, hash, and safety requirements."
                ),
            ),
        )
        (package_dir / "artifact_evaluation_checklist.json").write_text(json.dumps(to_plain(checklist), indent=2) + "\n", encoding="utf-8")
        (package_dir / "artifact_evaluation_checklist.md").write_text(
            render_artifact_evaluation_checklist_markdown(checklist),
            encoding="utf-8",
        )
        return checklist

    def render_markdown(self, checklist: ArtifactEvaluationChecklist) -> str:
        return render_artifact_evaluation_checklist_markdown(checklist)


def render_artifact_evaluation_checklist_markdown(checklist: ArtifactEvaluationChecklist) -> str:
    lines = [
        f"# Artifact Evaluation Checklist `{checklist.package_id}`",
        "",
        f"- Status: `{checklist.status}`",
        f"- Blockers: {len(checklist.blockers)}",
        f"- Warnings: {len(checklist.warnings)}",
        "",
        "## Checks",
        "",
    ]
    lines.extend(f"- `{key}`: {value}" for key, value in checklist.checks.items())
    if checklist.blockers:
        lines.extend(["", "## Blockers", ""])
        lines.extend(f"- {blocker}" for blocker in checklist.blockers)
    if checklist.warnings:
        lines.extend(["", "## Warnings", ""])
        lines.extend(f"- {warning}" for warning in checklist.warnings)
    return "\n".join(lines).rstrip() + "\n"


def _check_replication_package(
    replication_package_id: str,
    replication_dir: Path,
    replication_record: Path,
    manifest: ReplicationManifest | None,
    checks: dict[str, str],
    blockers: list[str],
) -> None:
    if not replication_package_id:
        checks["replication_package"] = "fail: missing replication package id"
        blockers.append("Artifact evaluation package does not reference a replication package.")
        return
    if not replication_dir.exists() or not replication_record.exists() or manifest is None:
        checks["replication_package"] = "fail: replication package files missing"
        blockers.append("Copied replication package files are missing or incomplete.")
        return
    replication = from_dict(ReplicationPackage, json.loads(replication_record.read_text(encoding="utf-8")))
    if not replication.safe_to_share:
        checks["replication_package"] = "fail: replication package is not safe to share"
        blockers.extend(replication.missing_requirements or ["Replication package is not safe to share."])
        return
    checks["replication_package"] = "pass"


def _check_instructions(
    package,
    package_dir: Path,
    checks: dict[str, str],
    blockers: list[str],
) -> None:
    has_instructions = bool(package.install_instructions and package.run_instructions and (package_dir / "INSTRUCTIONS.md").exists())
    checks["instructions"] = "pass" if has_instructions else "fail: missing install/run instructions"
    if not has_instructions:
        blockers.append("Install and run instructions are incomplete.")


def _check_expected_outputs(
    package,
    manifest: ReplicationManifest | None,
    checks: dict[str, str],
    blockers: list[str],
) -> None:
    has_outputs = bool(package.expected_outputs)
    has_hashes = bool(manifest and manifest.result_hashes)
    if has_outputs and has_hashes:
        checks["expected_outputs_and_hashes"] = "pass"
        return
    checks["expected_outputs_and_hashes"] = "fail: missing expected outputs or hashes"
    blockers.append("Expected outputs and result hashes are required for artifact evaluation.")


def _check_hardware_time(package, checks: dict[str, str], blockers: list[str]) -> None:
    has_estimates = bool(package.hardware_requirements and package.time_estimates)
    checks["hardware_time"] = "pass" if has_estimates else "fail: missing hardware/time estimates"
    if not has_estimates:
        blockers.append("Hardware requirements and time estimates are missing.")


def _check_restricted_data(
    replication_dir: Path,
    checks: dict[str, str],
    blockers: list[str],
    warnings: list[str],
) -> None:
    if not replication_dir.exists():
        checks["restricted_data"] = "fail: replication package missing"
        blockers.append("Cannot check restricted data because replication package is missing.")
        return
    suspicious = [
        path
        for path in replication_dir.rglob("*")
        if path.is_file() and path.suffix.lower() not in {".json", ".md", ".txt", ".py", ".toml", ".yaml", ".yml", ".cfg"}
    ]
    dataset_records = list((replication_dir / "data").glob("*.record.json")) if (replication_dir / "data").exists() else []
    if suspicious and not dataset_records:
        checks["restricted_data"] = "warning: bundled data files found"
        warnings.append("Bundled non-metadata data files are present; verify they are safe fixture/public data.")
        return
    checks["restricted_data"] = "pass"


def _load_manifest(path: Path) -> ReplicationManifest | None:
    if not path.exists():
        return None
    return from_dict(ReplicationManifest, json.loads(path.read_text(encoding="utf-8")))


def _unique(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value and value not in seen:
            result.append(value)
            seen.add(value)
    return result
