"""Artifact evaluation package exporter."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from gapforge.config import GapForgeConfig
from gapforge.manuscript.manager import ManuscriptManager
from gapforge.models import ArtifactEvaluationPackage, Provenance, ReplicationManifest, ReplicationPackage, from_dict, to_plain
from gapforge.replication.package import ReplicationPackageExporter
from gapforge.state import utc_now_iso


class ArtifactEvaluationPackageExporter:
    """Export review-ready artifact evaluation packages from manuscript and replication state."""

    def __init__(self, config: GapForgeConfig) -> None:
        self.config = config
        self.manuscript_manager = ManuscriptManager(config)
        self.replication_exporter = ReplicationPackageExporter(config)

    def export(self, manuscript_id: str) -> ArtifactEvaluationPackage:
        state = self.manuscript_manager.load_state(manuscript_id)
        root = self.manuscript_manager.manuscript_root(manuscript_id)
        package_id = f"artifact-eval-{manuscript_id}"
        package_dir = root / "artifact_evaluation" / package_id
        if package_dir.exists():
            shutil.rmtree(package_dir)
        package_dir.mkdir(parents=True, exist_ok=True)
        replication = _latest_replication_package(self.replication_exporter, state.manuscript.workspace_id)
        manifest = _replication_manifest(replication)
        blockers: list[str] = []
        if replication is None:
            blockers.append("No replication package exists for the manuscript workspace.")
        elif not replication.safe_to_share:
            blockers.extend(replication.missing_requirements)
        copied_replication_files: list[str] = []
        if replication is not None:
            copied_replication_files = _copy_replication_package(
                Path(replication.manifest_path).parent,
                package_dir / "replication_package",
            )
        _write_instructions(package_dir, replication, manifest, blockers)
        package = ArtifactEvaluationPackage(
            id=package_id,
            manuscript_id=manuscript_id,
            workspace_id=state.manuscript.workspace_id,
            replication_package_id=replication.id if replication else "",
            files=[],
            expected_badges=_expected_badges(replication, manifest),
            install_instructions=_install_instructions(manifest),
            run_instructions=_run_instructions(manifest),
            expected_outputs=_expected_outputs(manifest),
            hardware_requirements=_hardware_requirements(manifest),
            time_estimates=_time_estimates(manifest),
            status="review_ready" if replication is not None and not blockers else "blocked",
            provenance=Provenance(
                created_by_skill="artifact-evaluation-package",
                source_ids=[manuscript_id, state.manuscript.workspace_id, replication.id if replication else ""],
                timestamp=utc_now_iso(),
                reasoning_summary=(
                    "Exported artifact evaluation package from manuscript and replication state without adding restricted data."
                ),
            ),
        )
        (package_dir / "expected_hashes.json").write_text(
            json.dumps(manifest.result_hashes if manifest else {}, indent=2) + "\n",
            encoding="utf-8",
        )
        (package_dir / "artifact_evaluation_package.json").write_text(json.dumps(to_plain(package), indent=2) + "\n", encoding="utf-8")
        (package_dir / "README.md").write_text(render_artifact_evaluation_package_markdown(package, blockers), encoding="utf-8")
        package.files = _relative_files(package_dir)
        # Keep copied replication file list observable in README without duplicating model fields.
        if copied_replication_files and "replication_package/replication_package.json" not in package.files:
            package.files.extend(copied_replication_files)
            package.files = sorted(set(package.files))
        (package_dir / "artifact_evaluation_package.json").write_text(json.dumps(to_plain(package), indent=2) + "\n", encoding="utf-8")
        (package_dir / "README.md").write_text(render_artifact_evaluation_package_markdown(package, blockers), encoding="utf-8")
        return package

    def load(self, package_id: str) -> ArtifactEvaluationPackage:
        return load_artifact_evaluation_package(self.config, package_id)

    def package_dir(self, package_id: str) -> Path:
        return artifact_evaluation_package_dir(self.config, package_id)


def load_artifact_evaluation_package(config: GapForgeConfig, package_id: str) -> ArtifactEvaluationPackage:
    path = artifact_evaluation_package_dir(config, package_id) / "artifact_evaluation_package.json"
    return from_dict(ArtifactEvaluationPackage, json.loads(path.read_text(encoding="utf-8")))


def artifact_evaluation_package_dir(config: GapForgeConfig, package_id: str) -> Path:
    for path in config.project_root.glob(f"*/manuscripts/*/artifact_evaluation/{package_id}/artifact_evaluation_package.json"):
        return path.parent
    raise FileNotFoundError(f"No artifact evaluation package found for {package_id}")


def render_artifact_evaluation_package_markdown(package: ArtifactEvaluationPackage, blockers: list[str] | None = None) -> str:
    lines = [
        f"# Artifact Evaluation Package `{package.id}`",
        "",
        "This package is derived from manuscript and replication state. It does not claim badge eligibility without checklist evidence.",
        "",
        f"- Manuscript ID: `{package.manuscript_id}`",
        f"- Workspace ID: `{package.workspace_id}`",
        f"- Replication package: `{package.replication_package_id or 'missing'}`",
        f"- Status: `{package.status}`",
        "",
        "## Install Instructions",
        "",
    ]
    lines.extend(f"- {item}" for item in package.install_instructions)
    lines.extend(["", "## Run Instructions", ""])
    lines.extend(f"- `{item}`" for item in package.run_instructions)
    lines.extend(["", "## Expected Outputs", ""])
    lines.extend(f"- {item}" for item in package.expected_outputs or ["No expected outputs recorded."])
    lines.extend(["", "## Hardware And Time", ""])
    lines.extend(f"- {item}" for item in [*package.hardware_requirements, *package.time_estimates])
    lines.extend(["", "## Expected Badges", ""])
    lines.extend([f"- `{item}`" for item in package.expected_badges] or ["- none"])
    if blockers:
        lines.extend(["", "## Blocking Issues", ""])
        lines.extend(f"- {blocker}" for blocker in blockers)
    return "\n".join(lines).rstrip() + "\n"


def _latest_replication_package(exporter: ReplicationPackageExporter, workspace_id: str) -> ReplicationPackage | None:
    try:
        return exporter.latest_for_workspace(workspace_id)
    except FileNotFoundError:
        return None


def _replication_manifest(replication: ReplicationPackage | None) -> ReplicationManifest | None:
    if replication is None:
        return None
    path = Path(replication.manifest_path)
    if not path.exists():
        return None
    return from_dict(ReplicationManifest, json.loads(path.read_text(encoding="utf-8")))


def _copy_replication_package(source_dir: Path, destination_dir: Path) -> list[str]:
    if destination_dir.exists():
        shutil.rmtree(destination_dir)
    shutil.copytree(source_dir, destination_dir)
    return sorted(f"replication_package/{path.relative_to(destination_dir)}" for path in destination_dir.rglob("*") if path.is_file())


def _write_instructions(
    package_dir: Path,
    replication: ReplicationPackage | None,
    manifest: ReplicationManifest | None,
    blockers: list[str],
) -> None:
    lines = [
        "# Artifact Evaluation Instructions",
        "",
        "## Install",
        "",
        *_install_instructions(manifest),
        "",
        "## Run",
        "",
        *[f"```bash\n{command}\n```" for command in _run_instructions(manifest)],
        "",
        "## Boundary",
        "",
        "- Restricted datasets are not bundled by default. Follow dataset instructions in the replication package.",
        "- Badge eligibility is assessed separately from package export.",
    ]
    if replication is not None:
        lines.extend(["", f"- Source replication package: `{replication.id}`"])
    if blockers:
        lines.extend(["", "## Known Blockers", "", *[f"- {blocker}" for blocker in blockers]])
    (package_dir / "INSTRUCTIONS.md").write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def _install_instructions(manifest: ReplicationManifest | None) -> list[str]:
    if manifest is None:
        return ["No replication manifest is available; export a replication package first."]
    python_version = (
        manifest.environment.get("python") or manifest.environment.get("python_version") or "the recorded project Python version"
    )
    return [
        f"Use {python_version}.",
        "Install dependencies from the project or replication package instructions before running commands.",
        "Do not download restricted datasets unless you have independent authorization.",
    ]


def _run_instructions(manifest: ReplicationManifest | None) -> list[str]:
    if manifest is None or not manifest.commands:
        return ["No run commands are recorded."]
    return list(manifest.commands)


def _expected_outputs(manifest: ReplicationManifest | None) -> list[str]:
    if manifest is None:
        return []
    outputs = list(manifest.expected_outputs)
    for path, digest in sorted(manifest.result_hashes.items()):
        outputs.append(f"{path} sha256={digest}")
    return list(dict.fromkeys(outputs))


def _hardware_requirements(manifest: ReplicationManifest | None) -> list[str]:
    if manifest is None:
        return ["unknown hardware; replication package missing"]
    environment = manifest.environment
    hardware = (
        environment.get("hardware")
        or environment.get("resource_environment")
        or environment.get("compute_environment")
        or "local CPU sufficient unless replication manifest states otherwise"
    )
    return [hardware]


def _time_estimates(manifest: ReplicationManifest | None) -> list[str]:
    if manifest is None:
        return ["unknown time; replication package missing"]
    command_count = len(manifest.commands)
    if command_count == 0:
        return ["unknown time; no commands recorded"]
    return [f"Smoke/dry-run review: under 5 minutes expected for {command_count} recorded command(s) on local fixture data."]


def _expected_badges(replication: ReplicationPackage | None, manifest: ReplicationManifest | None) -> list[str]:
    badges = ["available"] if replication is not None else []
    if replication is not None and manifest is not None and manifest.commands:
        badges.append("functional")
    return badges


def _relative_files(package_dir: Path) -> list[str]:
    return sorted(str(path.relative_to(package_dir)) for path in package_dir.rglob("*") if path.is_file())
