"""Verify exported replication package integrity."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from gapforge.config import GapForgeConfig
from gapforge.models import Provenance, ReplicationManifest, ReplicationVerificationResult, from_dict, to_plain
from gapforge.replication.manifest import safe_to_bundle_dataset
from gapforge.state import utc_now_iso


class ReplicationPackageVerifier:
    """Verify that a replication package has the artifacts needed to rerun a study."""

    def __init__(self, config: GapForgeConfig) -> None:
        self.config = config

    def verify(self, package_path: str | Path) -> ReplicationVerificationResult:
        package_dir = Path(package_path)
        manifest_path = package_dir / "replication_manifest.json"
        checks: dict[str, str] = {}
        blockers: list[str] = []
        if not manifest_path.exists():
            return ReplicationVerificationResult(
                package_id=package_dir.name,
                status="fail",
                checks={"manifest": "fail"},
                blockers=[f"Missing replication manifest: {manifest_path}"],
                provenance=_provenance(package_dir.name),
            )
        manifest = from_dict(ReplicationManifest, json.loads(manifest_path.read_text(encoding="utf-8")))
        checks["manifest"] = "pass"
        if manifest.commands:
            checks["commands"] = "pass"
        else:
            blockers.append("No reproduction commands are recorded.")
            checks["commands"] = "fail"
        if manifest.random_seeds:
            checks["random_seeds"] = "pass"
        else:
            checks["random_seeds"] = "warning: no random seeds recorded"
        _verify_result_hashes(package_dir, manifest, checks, blockers)
        _verify_dataset_instructions(manifest, checks, blockers)
        status = (
            "fail"
            if any(value == "fail" for value in checks.values())
            else ("warning" if any("warning" in value for value in checks.values()) else "pass")
        )
        result = ReplicationVerificationResult(
            package_id=manifest.package_id,
            status=status,
            checks=checks,
            blockers=blockers,
            provenance=_provenance(manifest.package_id),
        )
        reports = package_dir / "verification"
        reports.mkdir(parents=True, exist_ok=True)
        (reports / "replication_verification.json").write_text(json.dumps(to_plain(result), indent=2) + "\n", encoding="utf-8")
        (reports / "replication_verification.md").write_text(render_replication_verification_markdown(result), encoding="utf-8")
        return result


def render_replication_verification_markdown(result: ReplicationVerificationResult) -> str:
    lines = [
        f"# Replication Verification Result `{result.package_id}`",
        "",
        f"- Status: `{result.status}`",
        "",
        "## Checks",
        "",
    ]
    lines.extend([f"- `{key}`: {value}" for key, value in sorted(result.checks.items())] or ["- none"])
    lines.extend(["", "## Blockers", ""])
    lines.extend([f"- {item}" for item in result.blockers] or ["- none"])
    lines.extend(["", "## Boundary", ""])
    lines.append("- Passing this verifier means package integrity checks passed; it is not an independent scientific replication.")
    return "\n".join(lines).rstrip() + "\n"


def _verify_result_hashes(
    package_dir: Path,
    manifest: ReplicationManifest,
    checks: dict[str, str],
    blockers: list[str],
) -> None:
    if not manifest.result_hashes:
        checks["result_hashes"] = "fail"
        blockers.append("No result hashes are recorded.")
        return
    for relative_path, expected_hash in manifest.result_hashes.items():
        path = package_dir / relative_path
        if not path.exists():
            checks["result_hashes"] = "fail"
            blockers.append(f"Missing hashed result artifact: {relative_path}")
            return
        if _sha256(path) != expected_hash:
            checks["result_hashes"] = "fail"
            blockers.append(f"Result hash mismatch for {relative_path}.")
            return
    checks["result_hashes"] = "pass"


def _verify_dataset_instructions(
    manifest: ReplicationManifest,
    checks: dict[str, str],
    blockers: list[str],
) -> None:
    excluded = [record for record in manifest.dataset_records if not safe_to_bundle_dataset(record)]
    if not excluded:
        checks["dataset_instructions"] = "pass"
        return
    if manifest.dataset_download_instructions:
        checks["dataset_instructions"] = "pass"
        return
    checks["dataset_instructions"] = "warning: missing download instructions for excluded datasets"
    blockers.append("Dataset download instructions are missing for excluded datasets.")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _provenance(package_id: str) -> Provenance:
    return Provenance(
        created_by_skill="replication-verifier",
        source_ids=[package_id],
        timestamp=utc_now_iso(),
        reasoning_summary="Verified replication package manifest, commands, seeds, dataset instructions, and result hashes.",
    )
