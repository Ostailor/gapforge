"""Run reproduction attempts from replication packages."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
from pathlib import Path

from gapforge.config import GapForgeConfig
from gapforge.models import Provenance, ReplicationManifest, ReproductionRecord, from_dict, to_plain
from gapforge.replication.manifest import safe_to_bundle_dataset
from gapforge.state import utc_now_iso


class ReproductionRunner:
    """Attempt independent reproduction from an exported replication package."""

    def __init__(self, config: GapForgeConfig) -> None:
        self.config = config

    def reproduce(self, package_path: str | Path, *, dry_run: bool = False, timeout_seconds: int = 300) -> ReproductionRecord:
        package_dir = Path(package_path)
        manifest = _load_manifest(package_dir)
        environment = _manifest_environment(manifest)
        started_at = utc_now_iso()
        record_id = f"reproduction-{_stable_id(manifest.package_id, started_at)}"
        errors = _preflight_errors(package_dir, manifest)
        commands_run: list[str] = []
        result_comparison: dict[str, str] = {}
        status = "planned" if dry_run else "running"
        if dry_run:
            commands_run = list(manifest.commands)
            record = _record(record_id, manifest.package_id, status, environment, started_at, "", commands_run, result_comparison, errors)
            self._write_record(package_dir, record)
            return record
        if errors:
            record = _record(
                record_id, manifest.package_id, "fail", environment, started_at, utc_now_iso(), commands_run, result_comparison, errors
            )
            self._write_record(package_dir, record)
            return record
        for command in manifest.commands:
            commands_run.append(command)
            completed = _run_command(command, package_dir=package_dir, timeout_seconds=timeout_seconds)
            if completed.returncode != 0:
                errors.append(f"Command failed ({completed.returncode}): {command}\n{completed.stderr.strip()}")
                break
        result_comparison = _compare_expected_outputs(package_dir, manifest)
        errors.extend(message for message in result_comparison.values() if message in {"missing", "hash_mismatch"})
        if errors:
            status = "fail"
        elif any(value == "not_checked" for value in result_comparison.values()):
            status = "warning"
        else:
            status = "pass"
        record = _record(
            record_id, manifest.package_id, status, environment, started_at, utc_now_iso(), commands_run, result_comparison, errors
        )
        self._write_record(package_dir, record)
        return record

    def load_record(self, reproduction_id: str) -> ReproductionRecord:
        for package_dir in self.config.project_root.glob("*/experiment_workspaces/*/replication_packages/*"):
            record_path = package_dir / "reproductions" / f"{reproduction_id}.json"
            if record_path.exists():
                return from_dict(ReproductionRecord, json.loads(record_path.read_text(encoding="utf-8")))
        for record_path in self.config.root.glob(f"**/reproductions/{reproduction_id}.json"):
            return from_dict(ReproductionRecord, json.loads(record_path.read_text(encoding="utf-8")))
        raise FileNotFoundError(f"No reproduction record found for {reproduction_id}")

    def _write_record(self, package_dir: Path, record: ReproductionRecord) -> None:
        reproductions = package_dir / "reproductions"
        reproductions.mkdir(parents=True, exist_ok=True)
        (reproductions / f"{record.id}.json").write_text(json.dumps(to_plain(record), indent=2) + "\n", encoding="utf-8")
        (reproductions / f"{record.id}.md").write_text(render_reproduction_record_markdown(record), encoding="utf-8")


def render_reproduction_record_markdown(record: ReproductionRecord) -> str:
    lines = [
        f"# Reproduction Record `{record.id}`",
        "",
        f"- Package ID: `{record.package_id}`",
        f"- Status: `{record.status}`",
        f"- Environment: `{record.environment}`",
        f"- Started: {record.started_at or 'unknown'}",
        f"- Completed: {record.completed_at or 'not completed'}",
        "",
        "## Commands Run",
        "",
    ]
    lines.extend([f"```bash\n{command}\n```" for command in record.commands_run] or ["- none"])
    lines.extend(["", "## Result Comparison", ""])
    lines.extend([f"- `{path}`: {status}" for path, status in sorted(record.result_comparison.items())] or ["- none"])
    lines.extend(["", "## Errors", ""])
    lines.extend([f"- {error}" for error in record.errors] or ["- none"])
    lines.extend(["", "## Boundary", ""])
    lines.append("- This records a reproduction attempt. Scientific replication still requires human review of the reproduced results.")
    return "\n".join(lines).rstrip() + "\n"


def _load_manifest(package_dir: Path) -> ReplicationManifest:
    manifest_path = package_dir / "replication_manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError(f"No replication manifest found at {manifest_path}")
    return from_dict(ReplicationManifest, json.loads(manifest_path.read_text(encoding="utf-8")))


def _preflight_errors(package_dir: Path, manifest: ReplicationManifest) -> list[str]:
    errors: list[str] = []
    if not manifest.commands:
        errors.append("No reproduction commands are recorded.")
    for record in manifest.dataset_records:
        if safe_to_bundle_dataset(record):
            dataset_name = Path(record.local_path).name if record.local_path else ""
            if dataset_name and not (package_dir / "data" / dataset_name).exists():
                errors.append(f"Required bundled dataset is missing: data/{dataset_name}")
        elif not manifest.dataset_download_instructions:
            errors.append(f"Dataset `{record.id}` is excluded and no download instructions are recorded.")
    return errors


def _run_command(command: str, *, package_dir: Path, timeout_seconds: int) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "PYTHONPATH": str(package_dir / "code")}
    return subprocess.run(
        command,
        cwd=package_dir,
        env=env,
        shell=True,
        text=True,
        capture_output=True,
        timeout=timeout_seconds,
        check=False,
    )


def _compare_expected_outputs(package_dir: Path, manifest: ReplicationManifest) -> dict[str, str]:
    comparison: dict[str, str] = {}
    expected_hashes = manifest.result_hashes
    paths = list(dict.fromkeys([*manifest.expected_outputs, *expected_hashes.keys()]))
    for relative_path in paths:
        path = package_dir / relative_path
        if not path.exists():
            comparison[relative_path] = "missing"
            continue
        expected_hash = expected_hashes.get(relative_path)
        if not expected_hash:
            comparison[relative_path] = "not_checked"
            continue
        comparison[relative_path] = "match" if _sha256(path) == expected_hash else "hash_mismatch"
    return comparison


def _record(
    record_id: str,
    package_id: str,
    status: str,
    environment: str,
    started_at: str,
    completed_at: str,
    commands_run: list[str],
    result_comparison: dict[str, str],
    errors: list[str],
) -> ReproductionRecord:
    return ReproductionRecord(
        id=record_id,
        package_id=package_id,
        status=status,
        environment=environment,
        started_at=started_at,
        completed_at=completed_at,
        commands_run=commands_run,
        result_comparison=result_comparison,
        errors=list(dict.fromkeys(errors)),
        provenance=Provenance(
            created_by_skill="reproduction-runner",
            source_ids=[package_id],
            timestamp=utc_now_iso(),
            reasoning_summary="Attempted to rerun replication package commands and compare produced outputs to expected hashes.",
        ),
    )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _stable_id(*parts: str) -> str:
    return hashlib.sha1("|".join(parts).encode("utf-8")).hexdigest()[:12]


def _manifest_environment(manifest: ReplicationManifest) -> str:
    return (
        manifest.environment.get("resource_environment")
        or manifest.environment.get("environment_type")
        or manifest.environment.get("compute_environment")
        or "local"
    )
