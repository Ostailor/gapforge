"""Experiment result artifact helpers."""

from __future__ import annotations

import hashlib
from pathlib import Path

from gapforge.models import ExperimentResultArtifact, ExperimentWorkspace, Provenance
from gapforge.state import utc_now_iso


def sha256_file(path: Path) -> str:
    """Return the SHA-256 digest for an existing artifact."""

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_result_artifact(
    workspace: ExperimentWorkspace,
    execution_id: str,
    artifact_path: Path,
    *,
    artifact_type: str = "",
    summary: str = "",
    safe_to_commit: bool | None = None,
) -> ExperimentResultArtifact:
    if not artifact_path.exists():
        raise FileNotFoundError(f"Result artifact does not exist: {artifact_path}")
    resolved = artifact_path.resolve()
    artifact_kind = artifact_type or infer_artifact_type(resolved)
    artifact_id = f"result-{_stable_id(workspace.id, execution_id, str(resolved))}"
    return ExperimentResultArtifact(
        id=artifact_id,
        workspace_id=workspace.id,
        execution_id=execution_id,
        artifact_type=artifact_kind,
        path=str(resolved),
        sha256=sha256_file(resolved),
        summary=summary or _summary_for_artifact(resolved, artifact_kind),
        safe_to_commit=_default_safe_to_commit(artifact_kind) if safe_to_commit is None else safe_to_commit,
        provenance=Provenance(
            created_by_skill="experiment-artifact",
            source_ids=[workspace.id, execution_id],
            timestamp=utc_now_iso(),
            reasoning_summary="Registered an experiment result artifact with content hash and commit-safety metadata.",
        ),
    )


def infer_artifact_type(path: Path) -> str:
    suffix = path.suffix.lower()
    name = path.name.lower()
    if suffix == ".json" and ("metric" in name or "result" in name):
        return "metrics_json"
    if suffix in {".csv", ".tsv", ".md"} and ("table" in name or "summary" in name):
        return "table" if suffix != ".md" else "report"
    if suffix in {".png", ".jpg", ".jpeg", ".svg", ".pdf"}:
        return "plot"
    if suffix in {".log", ".txt"} or "stdout" in name or "stderr" in name:
        return "log"
    if "prediction" in name:
        return "predictions"
    if suffix in {".pt", ".pth", ".ckpt", ".pkl"}:
        return "checkpoint"
    return "other"


def _default_safe_to_commit(artifact_type: str) -> bool:
    return artifact_type in {"metrics_json", "plot", "table", "report", "log"}


def _summary_for_artifact(path: Path, artifact_type: str) -> str:
    size = path.stat().st_size
    return f"{artifact_type} artifact, {size} bytes."


def _stable_id(*parts: str) -> str:
    digest = hashlib.sha1("::".join(parts).encode("utf-8")).hexdigest()[:12]
    return digest
