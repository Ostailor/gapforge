"""Recovery and robust loading for selected benchmark artifact packages."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from gapforge.artifact_eval.package import ArtifactEvaluationPackageExporter
from gapforge.config import GapForgeConfig
from gapforge.experiments.workspace import ExperimentWorkspaceManager
from gapforge.manuscript.manager import ManuscriptManager
from gapforge.models import (
    ArtifactEvaluationPackage,
    Provenance,
    ReplicationManifest,
    ReplicationPackage,
    from_dict,
    to_plain,
)
from gapforge.project_memory import ProjectMemoryManager
from gapforge.replication.manifest import safe_to_bundle_dataset
from gapforge.replication.package import ReplicationPackageExporter
from gapforge.selected_benchmark.spec import SelectedBenchmarkManager
from gapforge.state import slugify, utc_now_iso


@dataclass(slots=True)
class ArtifactPackageLoadResult:
    id: str
    benchmark_id: str
    manuscript_id: str
    workspace_id: str
    candidate_paths: list[str] = field(default_factory=list)
    selected_package_id: str = ""
    status: str = "missing"
    required_files_present: bool = False
    missing_files: list[str] = field(default_factory=list)
    expected_outputs_present: bool = False
    replication_package_present: bool = False
    hardware_requirements_present: bool = False
    run_instructions_present: bool = False
    warnings: list[str] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)
    provenance: Provenance = field(default_factory=lambda: Provenance(created_by_skill="selected-artifact-package-loader"))


@dataclass(slots=True)
class ArtifactPackageRepairRecord:
    id: str
    benchmark_id: str
    manuscript_id: str
    source_workspace_id: str
    source_replication_package_id: str
    repaired_package_id: str
    repair_actions: list[str] = field(default_factory=list)
    status: str = "blocked"
    provenance: Provenance = field(default_factory=lambda: Provenance(created_by_skill="selected-artifact-package-loader"))


@dataclass(slots=True)
class _ParsedPackage:
    package: ArtifactEvaluationPackage
    path: Path
    package_dir: Path
    missing_files: list[str] = field(default_factory=list)
    expected_outputs_present: bool = False
    replication_package_present: bool = False
    hardware_requirements_present: bool = False
    run_instructions_present: bool = False
    warnings: list[str] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)


class ArtifactPackageLoader:
    """Find, validate, repair, and expose selected-benchmark artifact packages."""

    def __init__(self, config: GapForgeConfig) -> None:
        self.config = config
        self.config.ensure_dirs()
        self.projects = ProjectMemoryManager(config)
        self.benchmarks = SelectedBenchmarkManager(config)
        self.manuscripts = ManuscriptManager(config)
        self.workspaces = ExperimentWorkspaceManager(config)
        self.replication = ReplicationPackageExporter(config)
        self.artifact_exporter = ArtifactEvaluationPackageExporter(config)

    def load(self, benchmark_id: str, *, write_report: bool = True) -> ArtifactPackageLoadResult:
        context = self._context(benchmark_id)
        parsed, invalid = self._first_valid_package(context)
        if parsed is None:
            result = self._missing_or_invalid_result(context, invalid)
        else:
            status = "repaired" if self._is_repaired_package(benchmark_id, parsed.package.id) else "loaded"
            result = ArtifactPackageLoadResult(
                id=f"artifact-package-load-{slugify(benchmark_id)}",
                benchmark_id=benchmark_id,
                manuscript_id=context["manuscript_id"],
                workspace_id=context["workspace_id"],
                candidate_paths=[str(path) for path in context["candidate_paths"]],
                selected_package_id=parsed.package.id,
                status=status,
                required_files_present=not parsed.missing_files,
                missing_files=list(parsed.missing_files),
                expected_outputs_present=parsed.expected_outputs_present,
                replication_package_present=parsed.replication_package_present,
                hardware_requirements_present=parsed.hardware_requirements_present,
                run_instructions_present=parsed.run_instructions_present,
                warnings=parsed.warnings,
                blockers=parsed.blockers,
                provenance=Provenance(
                    created_by_skill="selected-artifact-package-loader",
                    source_ids=[benchmark_id, context["manuscript_id"], context["workspace_id"], parsed.package.id],
                    timestamp=utc_now_iso(),
                    reasoning_summary="Loaded a selected-manuscript artifact evaluation package from known artifact locations.",
                ),
            )
        if write_report:
            self._write_load_result(result)
        return result

    def repair(self, benchmark_id: str) -> ArtifactPackageRepairRecord:
        context = self._context(benchmark_id)
        replication = self._latest_replication(context["workspace_id"])
        if replication is None:
            result = self._missing_or_invalid_result(context, [])
            result.blockers = _dedupe(
                [
                    *result.blockers,
                    f"No replication package exists for workspace `{context['workspace_id']}`.",
                    f"Run `gapforge export-replication-package --workspace-id {context['workspace_id']}` first.",
                ]
            )
            self._write_load_result(result)
            record = ArtifactPackageRepairRecord(
                id=f"artifact-package-repair-{slugify(benchmark_id)}",
                benchmark_id=benchmark_id,
                manuscript_id=context["manuscript_id"],
                source_workspace_id=context["workspace_id"],
                source_replication_package_id="",
                repaired_package_id="",
                repair_actions=list(result.blockers),
                status="blocked",
                provenance=Provenance(
                    created_by_skill="selected-artifact-package-loader",
                    source_ids=[benchmark_id, context["manuscript_id"], context["workspace_id"]],
                    timestamp=utc_now_iso(),
                    reasoning_summary="Could not repair artifact package because no workspace replication package was loadable.",
                ),
            )
            self._write_repair_record(record)
            return record

        package = self.artifact_exporter.export(context["manuscript_id"])
        parsed = self._parse_package_candidate(self.artifact_exporter.package_dir(package.id) / "artifact_evaluation_package.json", context)
        if parsed is not None:
            self._validate(parsed, context)
        status = "repaired" if parsed is not None and not parsed.blockers else "blocked"
        actions = [
            f"Loaded source workspace `{context['workspace_id']}`.",
            f"Loaded source replication package `{replication.id}`.",
            f"Regenerated artifact evaluation package `{package.id}` for manuscript `{context['manuscript_id']}`.",
            "Kept restricted datasets excluded; package repair copies only exporter-approved replication bundle contents.",
        ]
        if parsed is not None and parsed.blockers:
            actions.extend(parsed.blockers)
        record = ArtifactPackageRepairRecord(
            id=f"artifact-package-repair-{slugify(benchmark_id)}",
            benchmark_id=benchmark_id,
            manuscript_id=context["manuscript_id"],
            source_workspace_id=context["workspace_id"],
            source_replication_package_id=replication.id,
            repaired_package_id=package.id if status == "repaired" else "",
            repair_actions=_dedupe(actions),
            status=status,
            provenance=Provenance(
                created_by_skill="selected-artifact-package-loader",
                source_ids=[benchmark_id, context["manuscript_id"], context["workspace_id"], replication.id, package.id],
                timestamp=utc_now_iso(),
                reasoning_summary=(
                    "Regenerated selected-manuscript artifact package from existing replication state without unsafe data promotion."
                ),
            ),
        )
        self._write_repair_record(record)
        self._write_load_result(self.load(benchmark_id, write_report=False))
        return record

    def status_report(self, benchmark_id: str) -> str:
        result = self.load(benchmark_id)
        report = render_artifact_package_load_result(result)
        self._load_result_path(benchmark_id).with_suffix(".md").write_text(report, encoding="utf-8")
        return report

    def load_consumable_package(self, benchmark_id: str) -> ArtifactEvaluationPackage | None:
        context = self._context(benchmark_id)
        parsed, _invalid = self._first_valid_package(context)
        if parsed is None or parsed.blockers:
            return None
        return parsed.package

    def load_consumable_package_for_manuscript(self, manuscript_id: str) -> ArtifactEvaluationPackage | None:
        benchmark_id = self.benchmark_id_for_manuscript(manuscript_id)
        if not benchmark_id:
            return None
        return self.load_consumable_package(benchmark_id)

    def benchmark_id_for_manuscript(self, manuscript_id: str) -> str:
        try:
            state = self.manuscripts.load_state(manuscript_id)
            program = self.projects.load_project(state.manuscript.project_id)
        except FileNotFoundError:
            return ""
        spec_paths = sorted((Path(program.project.root_dir) / "selected_benchmark").glob("spec.json"))
        for path in spec_paths:
            try:
                raw = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                continue
            spec_id = str(raw.get("id", ""))
            if state.manuscript.direction_id in {spec_id, f"selected-benchmark-{slugify(spec_id)}"}:
                return spec_id
            if slugify(str(raw.get("title", ""))) and slugify(str(raw.get("title", ""))) in slugify(state.manuscript.title):
                return spec_id
        return str(json.loads(spec_paths[0].read_text(encoding="utf-8")).get("id", "")) if len(spec_paths) == 1 else ""

    def _context(self, benchmark_id: str) -> dict[str, Any]:
        spec = self.benchmarks.load_spec(benchmark_id)
        program = self.projects.load_project(spec.project_id)
        project_root = Path(program.project.root_dir)
        benchmark_dir = project_root / "selected_benchmark"
        manuscript_id = self._manuscript_id_for_project(spec.project_id, benchmark_id)
        manuscript_root = self._manuscript_root(manuscript_id)
        workspace_id = self._workspace_id_for_manuscript(manuscript_id, spec.project_id, benchmark_id)
        workspace_root = self._workspace_root(workspace_id)
        package_paths = [
            *((manuscript_root / "artifact_evaluation").glob("*/artifact_evaluation_package.json") if manuscript_root else []),
            *((manuscript_root / "artifact-eval").glob("*/artifact_evaluation_package.json") if manuscript_root else []),
            *((workspace_root / "artifact_evaluation").glob("*/artifact_evaluation_package.json") if workspace_root else []),
            *((workspace_root / "artifact-eval").glob("*/artifact_evaluation_package.json") if workspace_root else []),
            *benchmark_dir.glob("**/artifact_evaluation_package.json"),
            *project_root.glob("manuscripts/*/artifact_evaluation/*/artifact_evaluation_package.json"),
        ]
        source_paths = [
            *((workspace_root / "replication_packages").glob("*/replication_package.json") if workspace_root else []),
            *((workspace_root / "replication_package").glob("replication_package.json") if workspace_root else []),
            *benchmark_dir.glob("**/replication_package.json"),
        ]
        return {
            "benchmark_id": benchmark_id,
            "project_id": spec.project_id,
            "project_root": project_root,
            "benchmark_dir": benchmark_dir,
            "manuscript_id": manuscript_id,
            "manuscript_root": manuscript_root,
            "workspace_id": workspace_id,
            "workspace_root": workspace_root,
            "candidate_paths": _dedupe_paths([*package_paths, *source_paths]),
            "package_paths": _dedupe_paths(package_paths),
            "source_paths": _dedupe_paths(source_paths),
        }

    def _first_valid_package(self, context: dict[str, Any]) -> tuple[_ParsedPackage | None, list[_ParsedPackage]]:
        invalid: list[_ParsedPackage] = []
        for path in context["package_paths"]:
            if not path.exists() or not path.is_file():
                continue
            parsed = self._parse_package_candidate(path, context)
            if parsed is None:
                continue
            self._validate(parsed, context)
            if parsed.blockers:
                invalid.append(parsed)
                continue
            return parsed, invalid
        return None, invalid

    def _parse_package_candidate(self, path: Path, context: dict[str, Any]) -> _ParsedPackage | None:
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            package = from_dict(ArtifactEvaluationPackage, raw)
        except (json.JSONDecodeError, TypeError, ValueError) as exc:
            return _invalid_candidate(path, f"Artifact evaluation package schema error: {exc}", context)
        return _ParsedPackage(package=package, path=path, package_dir=path.parent)

    def _validate(self, parsed: _ParsedPackage, context: dict[str, Any]) -> None:
        package = parsed.package
        package_dir = parsed.package_dir
        required_files = [
            "artifact_evaluation_package.json",
            "README.md",
            "INSTRUCTIONS.md",
            "expected_hashes.json",
            "replication_package/replication_package.json",
            "replication_package/replication_manifest.json",
        ]
        parsed.missing_files = [item for item in required_files if not (package_dir / item).exists()]
        parsed.replication_package_present = bool(
            package.replication_package_id
            and (package_dir / "replication_package" / "replication_package.json").exists()
            and (package_dir / "replication_package" / "replication_manifest.json").exists()
        )
        manifest = _load_replication_manifest(package_dir)
        replication = _load_replication_package(package_dir)
        parsed.expected_outputs_present = bool(package.expected_outputs and _result_hashes(package_dir, manifest))
        parsed.hardware_requirements_present = bool(package.hardware_requirements and package.time_estimates)
        parsed.run_instructions_present = bool(
            package.install_instructions
            and package.run_instructions
            and ((package_dir / "README.md").exists() or (package_dir / "INSTRUCTIONS.md").exists())
        )
        if package.manuscript_id != context["manuscript_id"]:
            parsed.blockers.append(
                f"Artifact package manuscript `{package.manuscript_id}` does not match selected manuscript `{context['manuscript_id']}`."
            )
        if context["workspace_id"] and package.workspace_id != context["workspace_id"]:
            parsed.blockers.append(f"Artifact package workspace `{package.workspace_id}` does not match `{context['workspace_id']}`.")
        if parsed.missing_files:
            parsed.blockers.append("Required artifact evaluation files are missing: " + ", ".join(parsed.missing_files))
        if not parsed.replication_package_present:
            parsed.blockers.append("Artifact evaluation package does not include a loadable copied replication package.")
        if replication is not None and not replication.safe_to_share:
            parsed.blockers.extend(replication.missing_requirements or ["Replication package is not safe to share."])
        if not parsed.expected_outputs_present:
            parsed.blockers.append("Expected outputs and result hashes are required for artifact evaluation loading.")
        if not parsed.hardware_requirements_present:
            parsed.blockers.append("Hardware requirements and time estimates are missing.")
        if not parsed.run_instructions_present:
            parsed.blockers.append("README/install/run instructions are incomplete.")
        labels = _run_type_labels(package, package_dir)
        if not labels.intersection({"smoke", "pilot", "main"}):
            parsed.blockers.append("Artifact package lacks smoke/pilot/main run labels in copied manifests or run instructions.")
        unsafe_files = _unsafe_restricted_files(package_dir, manifest)
        if unsafe_files:
            parsed.blockers.append("Restricted or unsafe dataset files are bundled: " + ", ".join(unsafe_files))
        excluded = _excluded_restricted_records(manifest)
        if excluded and not unsafe_files:
            parsed.warnings.append("Restricted or non-fixture datasets are excluded by default: " + ", ".join(excluded))
        if package.status != "review_ready":
            parsed.blockers.append(f"Artifact package `{package.id}` status is `{package.status}`, not `review_ready`.")
        parsed.warnings = _dedupe(parsed.warnings)
        parsed.blockers = _dedupe(parsed.blockers)

    def _missing_or_invalid_result(
        self,
        context: dict[str, Any],
        invalid: list[_ParsedPackage],
    ) -> ArtifactPackageLoadResult:
        if not invalid:
            blockers = [
                "No loadable artifact evaluation package was found in manuscript, workspace, benchmark, or v0.8 artifact locations.",
                *_repair_commands(context),
            ]
            if context["source_paths"]:
                blockers.append(
                    "Replication package source candidates exist; run selected-artifact-package-repair to regenerate the review package."
                )
            return ArtifactPackageLoadResult(
                id=f"artifact-package-load-{slugify(context['benchmark_id'])}",
                benchmark_id=context["benchmark_id"],
                manuscript_id=context["manuscript_id"],
                workspace_id=context["workspace_id"],
                candidate_paths=[str(path) for path in context["candidate_paths"]],
                status="missing",
                blockers=_dedupe(blockers),
                provenance=Provenance(
                    created_by_skill="selected-artifact-package-loader",
                    source_ids=[context["benchmark_id"], context["manuscript_id"], context["workspace_id"]],
                    timestamp=utc_now_iso(),
                    reasoning_summary="No selected-manuscript artifact evaluation package was found in known locations.",
                ),
            )
        first = invalid[0]
        warnings = _dedupe([warning for item in invalid for warning in item.warnings])
        blockers = _dedupe([blocker for item in invalid for blocker in item.blockers])
        return ArtifactPackageLoadResult(
            id=f"artifact-package-load-{slugify(context['benchmark_id'])}",
            benchmark_id=context["benchmark_id"],
            manuscript_id=context["manuscript_id"],
            workspace_id=context["workspace_id"],
            candidate_paths=[str(path) for path in context["candidate_paths"]],
            selected_package_id=first.package.id,
            status="invalid",
            required_files_present=not first.missing_files,
            missing_files=list(first.missing_files),
            expected_outputs_present=first.expected_outputs_present,
            replication_package_present=first.replication_package_present,
            hardware_requirements_present=first.hardware_requirements_present,
            run_instructions_present=first.run_instructions_present,
            warnings=warnings,
            blockers=[*blockers, *_repair_commands(context)],
            provenance=Provenance(
                created_by_skill="selected-artifact-package-loader",
                source_ids=[context["benchmark_id"], context["manuscript_id"], context["workspace_id"], first.package.id],
                timestamp=utc_now_iso(),
                reasoning_summary="Found artifact evaluation package candidates, but validation blocked loading.",
            ),
        )

    def _latest_replication(self, workspace_id: str) -> ReplicationPackage | None:
        if not workspace_id:
            return None
        try:
            return self.replication.latest_for_workspace(workspace_id)
        except FileNotFoundError:
            return None

    def _manuscript_id_for_project(self, project_id: str, benchmark_id: str) -> str:
        spec = self.benchmarks.load_spec(benchmark_id)
        target_direction_ids = {benchmark_id, f"selected-benchmark-{slugify(benchmark_id)}"}
        try:
            program = self.projects.load_project(project_id)
        except FileNotFoundError:
            return f"manuscript-{slugify(spec.title)}"
        manuscripts_dir = Path(program.project.root_dir) / "manuscripts"
        if manuscripts_dir.exists():
            for state_path in sorted(manuscripts_dir.glob("*/manuscript.json")):
                try:
                    raw = json.loads(state_path.read_text(encoding="utf-8"))
                except json.JSONDecodeError:
                    continue
                manuscript = raw.get("manuscript", {}) if isinstance(raw, dict) else {}
                direction_id = str(manuscript.get("direction_id", ""))
                title = str(manuscript.get("title", "")).lower()
                if direction_id in target_direction_ids or slugify(spec.title) in slugify(title):
                    return str(manuscript.get("id") or state_path.parent.name)
        return f"manuscript-{slugify(spec.title)}"

    def _workspace_id_for_manuscript(self, manuscript_id: str, project_id: str, benchmark_id: str) -> str:
        try:
            return self.manuscripts.load_state(manuscript_id).manuscript.workspace_id
        except FileNotFoundError:
            pass
        target_direction = f"selected-benchmark-{slugify(benchmark_id)}"
        program = self.projects.load_project(project_id)
        for workspace in program.experiment_workspaces:
            if workspace.direction_id == target_direction:
                return workspace.id
        return ""

    def _manuscript_root(self, manuscript_id: str) -> Path | None:
        if not manuscript_id:
            return None
        try:
            return self.manuscripts.manuscript_root(manuscript_id)
        except FileNotFoundError:
            return None

    def _workspace_root(self, workspace_id: str) -> Path | None:
        if not workspace_id:
            return None
        try:
            return Path(self.workspaces.load_workspace(workspace_id).root_dir)
        except FileNotFoundError:
            return None

    def _is_repaired_package(self, benchmark_id: str, package_id: str) -> bool:
        path = self._repair_record_path(benchmark_id)
        if not path.exists():
            return False
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return False
        return raw.get("status") == "repaired" and raw.get("repaired_package_id") == package_id

    def _load_result_path(self, benchmark_id: str) -> Path:
        spec = self.benchmarks.load_spec(benchmark_id)
        program = self.projects.load_project(spec.project_id)
        return Path(program.project.root_dir) / "selected_benchmark" / "artifact_package_loader" / "artifact_package_load_result.json"

    def _repair_record_path(self, benchmark_id: str) -> Path:
        spec = self.benchmarks.load_spec(benchmark_id)
        program = self.projects.load_project(spec.project_id)
        return Path(program.project.root_dir) / "selected_benchmark" / "artifact_package_loader" / "artifact_package_repair_record.json"

    def _write_load_result(self, result: ArtifactPackageLoadResult) -> None:
        path = self._load_result_path(result.benchmark_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(to_plain(result), indent=2) + "\n", encoding="utf-8")
        path.with_suffix(".md").write_text(render_artifact_package_load_result(result), encoding="utf-8")

    def _write_repair_record(self, record: ArtifactPackageRepairRecord) -> None:
        path = self._repair_record_path(record.benchmark_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(to_plain(record), indent=2) + "\n", encoding="utf-8")
        path.with_suffix(".md").write_text(render_artifact_package_repair_record(record), encoding="utf-8")


def render_artifact_package_load_result(result: ArtifactPackageLoadResult) -> str:
    lines = [
        "# Artifact Package Load Result",
        "",
        f"- Benchmark ID: `{result.benchmark_id}`",
        f"- Manuscript ID: `{result.manuscript_id}`",
        f"- Workspace ID: `{result.workspace_id}`",
        f"- Status: `{result.status}`",
        f"- Selected package ID: `{result.selected_package_id or 'none'}`",
        f"- Required files present: {str(result.required_files_present).lower()}",
        f"- Expected outputs present: {str(result.expected_outputs_present).lower()}",
        f"- Replication package present: {str(result.replication_package_present).lower()}",
        f"- Hardware requirements present: {str(result.hardware_requirements_present).lower()}",
        f"- Run instructions present: {str(result.run_instructions_present).lower()}",
        f"- Missing files: {', '.join(result.missing_files) or 'none'}",
        "",
        "## Candidate Paths",
        "",
    ]
    lines.extend([f"- `{path}`" for path in result.candidate_paths] or ["- none"])
    lines.extend(["", "## Warnings", ""])
    lines.extend([f"- {warning}" for warning in result.warnings] or ["- none"])
    lines.extend(["", "## Blockers", ""])
    lines.extend([f"- {blocker}" for blocker in result.blockers] or ["- none"])
    lines.extend(["", "## Claim Boundary", ""])
    lines.extend(
        [
            "- Loaded means a review package is parseable and internally linked; it does not prove badge eligibility.",
            "- Repair regenerates from existing workspace and replication state; it does not invent missing experiments or results.",
            "- Restricted or private datasets must remain excluded unless the replication manifest proves they are safe fixtures.",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def render_artifact_package_repair_record(record: ArtifactPackageRepairRecord) -> str:
    lines = [
        "# Artifact Package Repair Record",
        "",
        f"- Benchmark ID: `{record.benchmark_id}`",
        f"- Manuscript ID: `{record.manuscript_id}`",
        f"- Source workspace ID: `{record.source_workspace_id}`",
        f"- Source replication package ID: `{record.source_replication_package_id or 'none'}`",
        f"- Repaired package ID: `{record.repaired_package_id or 'none'}`",
        f"- Status: `{record.status}`",
        "",
        "## Repair Actions",
        "",
    ]
    lines.extend([f"- {action}" for action in record.repair_actions] or ["- none"])
    lines.extend(["", "## Boundary", ""])
    lines.extend(
        [
            "- Repair only regenerates the artifact package from existing manuscript, workspace, and replication records.",
            "- Repair does not create new result artifacts, expected hashes, or private data permissions.",
            "- Unsafe or restricted source artifacts remain excluded by default.",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def _invalid_candidate(path: Path, blocker: str, context: dict[str, Any]) -> _ParsedPackage:
    package = ArtifactEvaluationPackage(
        id=f"invalid-{slugify(path.stem)}",
        manuscript_id=context["manuscript_id"],
        workspace_id=context["workspace_id"],
    )
    return _ParsedPackage(package=package, path=path, package_dir=path.parent, blockers=[blocker])


def _load_replication_manifest(package_dir: Path) -> ReplicationManifest | None:
    path = package_dir / "replication_package" / "replication_manifest.json"
    if not path.exists():
        return None
    return from_dict(ReplicationManifest, json.loads(path.read_text(encoding="utf-8")))


def _load_replication_package(package_dir: Path) -> ReplicationPackage | None:
    path = package_dir / "replication_package" / "replication_package.json"
    if not path.exists():
        return None
    return from_dict(ReplicationPackage, json.loads(path.read_text(encoding="utf-8")))


def _result_hashes(package_dir: Path, manifest: ReplicationManifest | None) -> dict[str, str]:
    hashes: dict[str, str] = {}
    if manifest is not None:
        hashes.update(manifest.result_hashes)
    path = package_dir / "expected_hashes.json"
    if path.exists():
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            raw = {}
        if isinstance(raw, dict):
            hashes.update({str(key): str(value) for key, value in raw.items()})
    return hashes


def _run_type_labels(package: ArtifactEvaluationPackage, package_dir: Path) -> set[str]:
    labels = {label for label in {"smoke", "pilot", "main"} if any(label in command.lower() for command in package.run_instructions)}
    manifests_path = package_dir / "replication_package" / "records" / "manifests.json"
    if not manifests_path.exists():
        return labels
    try:
        raw = json.loads(manifests_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return labels
    if isinstance(raw, list):
        for item in raw:
            if isinstance(item, dict):
                run_type = str(item.get("run_type", "")).lower()
                if run_type:
                    labels.add(run_type)
    return labels


def _unsafe_restricted_files(package_dir: Path, manifest: ReplicationManifest | None) -> list[str]:
    if manifest is None:
        return []
    data_dir = package_dir / "replication_package" / "data"
    if not data_dir.exists():
        return []
    unsafe_names = {
        Path(record.local_path).name
        for record in manifest.dataset_records
        if getattr(record, "local_path", "") and not safe_to_bundle_dataset(record)
    }
    return sorted(str(path.relative_to(package_dir)) for path in data_dir.iterdir() if path.is_file() and path.name in unsafe_names)


def _excluded_restricted_records(manifest: ReplicationManifest | None) -> list[str]:
    if manifest is None:
        return []
    return sorted(record.id for record in manifest.dataset_records if not safe_to_bundle_dataset(record))


def _repair_commands(context: dict[str, Any]) -> list[str]:
    commands = []
    if context["workspace_id"]:
        commands.append(f"Run `gapforge export-replication-package --workspace-id {context['workspace_id']}` if replication is missing.")
    commands.append(f"Run `gapforge selected-artifact-package-repair --benchmark-id {context['benchmark_id']}`.")
    commands.append(
        f"Run `gapforge selected-artifact-package-load --benchmark-id {context['benchmark_id']}` to verify the repaired package."
    )
    return commands


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            result.append(value)
    return result


def _dedupe_paths(paths: list[Path]) -> list[Path]:
    seen: set[str] = set()
    result: list[Path] = []
    for path in paths:
        key = str(path)
        if key in seen:
            continue
        seen.add(key)
        result.append(path)
    return result
