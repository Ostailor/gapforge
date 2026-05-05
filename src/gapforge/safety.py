"""Data-safety and artifact hygiene utilities."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from gapforge.config import GapForgeConfig
from gapforge.models import ArtifactClassification, to_plain
from gapforge.project_memory import ProjectMemoryManager
from gapforge.redaction import contains_secret, redact_text
from gapforge.state import ResearchStateManager, utc_now_iso

TEXT_SUFFIXES = {
    ".bib",
    ".csv",
    ".html",
    ".json",
    ".md",
    ".py",
    ".txt",
    ".yaml",
    ".yml",
}
GENERATED_DIR_NAMES = {"dashboard", "prompt_packs", "retrieval", "paper_packages", "safe_bundle", "safe_bundles"}
TRANSCRIPT_NAMES = {"llm_transcripts.json", "llm_transcripts.md"}
USAGE_NAMES = {"llm_usage.json"}
SAFE_PROJECT_FILES = [
    "project.json",
    "topics.json",
    "corpus_papers.json",
    "memory_records.json",
    "research_directions.json",
    "project_report.md",
    "related_work_matrix.md",
    "review_queue.md",
    "claim_graph.md",
]
SAFE_RUN_REPORTS = [
    "final_report.md",
    "source_coverage.md",
    "full_text_coverage.md",
    "novelty_dossiers.md",
    "gap_evidence_matrix.md",
    "review_queue.md",
]


def audit_run_artifacts(config: GapForgeConfig, run_id: str) -> list[ArtifactClassification]:
    state = ResearchStateManager(config).load_latest() if run_id == "latest" else ResearchStateManager(config).load_run(run_id)
    if state is None:
        raise FileNotFoundError("No run state found.")
    return audit_artifacts(Path(state.run_dir))


def audit_project_artifacts(config: GapForgeConfig, project_id: str) -> list[ArtifactClassification]:
    program = ProjectMemoryManager(config).load_project(project_id)
    return audit_artifacts(Path(program.project.root_dir))


def audit_artifacts(root: Path) -> list[ArtifactClassification]:
    if not root.exists():
        raise FileNotFoundError(f"Artifact root does not exist: {root}")
    classifications = [_classify_file(path, root) for path in sorted(root.rglob("*")) if path.is_file()]
    _write_audit_artifacts(root, classifications)
    return classifications


def render_artifact_audit_markdown(classifications: list[ArtifactClassification]) -> str:
    unsafe = [item for item in classifications if not item.safe_to_commit]
    lines = [
        "# Artifact Safety Audit",
        "",
        f"- Artifacts scanned: {len(classifications)}",
        f"- Unsafe to commit: {len(unsafe)}",
        "",
        "## Unsafe or Sensitive Artifacts",
        "",
    ]
    if not unsafe:
        lines.append("- none")
    for item in unsafe:
        lines.append(f"- `{item.path}` [{item.artifact_type}]: {item.reason}")
    lines.extend(["", "## All Artifacts", ""])
    for item in classifications:
        status = "safe" if item.safe_to_commit else "unsafe"
        lines.append(f"- `{item.path}` {status}: {item.reason or 'no risk detected'}")
    return "\n".join(lines).rstrip() + "\n"


def clean_generated_run_artifacts(config: GapForgeConfig, run_id: str) -> list[Path]:
    state = ResearchStateManager(config).load_latest() if run_id == "latest" else ResearchStateManager(config).load_run(run_id)
    if state is None:
        raise FileNotFoundError("No run state found.")
    run_dir = Path(state.run_dir)
    removed: list[Path] = []
    for name in GENERATED_DIR_NAMES:
        path = run_dir / name
        if path.exists():
            shutil.rmtree(path)
            removed.append(path)
    for name in [*TRANSCRIPT_NAMES, *USAGE_NAMES, "artifacts_audit.json", "artifacts_audit.md"]:
        path = run_dir / name
        if path.exists():
            path.unlink()
            removed.append(path)
    return removed


def export_safe_project_bundle(config: GapForgeConfig, project_id: str, *, include_pdfs: bool = False) -> Path:
    """Export a redacted, commit-safer project subset."""

    project_manager = ProjectMemoryManager(config)
    state_manager = ResearchStateManager(config)
    program = project_manager.load_project(project_id)
    project_root = Path(program.project.root_dir)
    bundle_root = project_root / "safe_bundles" / f"{project_id}-{utc_now_iso().replace(':', '').replace('+', 'Z')}"
    bundle_root.mkdir(parents=True, exist_ok=False)

    _copy_selected_files(project_root, bundle_root, SAFE_PROJECT_FILES)
    evidence_rows: list[dict[str, Any]] = []
    for run_id in program.run_ids:
        state = state_manager.load_run(run_id)
        run_target = bundle_root / "runs" / run_id
        run_target.mkdir(parents=True, exist_ok=True)
        _copy_selected_files(Path(state.run_dir), run_target, SAFE_RUN_REPORTS)
        for span in state.evidence_spans:
            evidence_rows.append(
                {
                    "run_id": run_id,
                    "evidence_span_id": span.id,
                    "paper_id": span.paper_id,
                    "locator": span.locator,
                    "evidence_type": span.evidence_type,
                    "quote": redact_text(span.quote[:500]),
                }
            )
        if include_pdfs:
            for artifact in state.paper_artifacts:
                if artifact.artifact_type == "pdf" and artifact.local_path:
                    source = Path(artifact.local_path)
                    source = source if source.is_absolute() else Path(state.run_dir) / source
                    if source.exists():
                        target = run_target / "pdfs" / source.name
                        target.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(source, target)
    (bundle_root / "evidence_snippets.json").write_text(json.dumps(evidence_rows, indent=2) + "\n", encoding="utf-8")
    manifest = {
        "project_id": project_id,
        "created_at": utc_now_iso(),
        "include_pdfs": include_pdfs,
        "redacted": True,
        "excluded_by_default": ["PDF artifacts", "LLM transcripts", "prompt packs", "dashboards", "retrieval indexes"],
    }
    (bundle_root / "SAFE_BUNDLE_MANIFEST.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    audit_artifacts(bundle_root)
    return bundle_root


def _classify_file(path: Path, root: Path) -> ArtifactClassification:
    relative = str(path.relative_to(root))
    lower = relative.lower()
    parts = set(path.relative_to(root).parts)
    artifact_type = _artifact_type(path, lower, parts)
    contains_user_pdf = path.suffix.lower() == ".pdf" or "pdfs" in parts
    contains_model_transcript = path.name in TRANSCRIPT_NAMES or "transcript" in lower
    text = _read_text_sample(path)
    potential_secret = contains_secret(text) if text else False
    generated = bool(parts & GENERATED_DIR_NAMES) or path.name in USAGE_NAMES
    unsafe_reasons = []
    if contains_user_pdf:
        unsafe_reasons.append("contains user PDF or downloaded PDF")
    if contains_model_transcript:
        unsafe_reasons.append("contains model transcript")
    if potential_secret:
        unsafe_reasons.append("contains potential secret")
    if generated:
        unsafe_reasons.append("generated artifact")
    return ArtifactClassification(
        path=relative,
        artifact_type=artifact_type,
        contains_user_pdf=contains_user_pdf,
        contains_model_transcript=contains_model_transcript,
        contains_potential_secret=potential_secret,
        safe_to_commit=not unsafe_reasons,
        reason="; ".join(unsafe_reasons) or "no risk detected",
    )


def _artifact_type(path: Path, lower: str, parts: set[str]) -> str:
    if path.suffix.lower() == ".pdf":
        return "pdf"
    if "dashboard" in parts or path.suffix.lower() == ".html":
        return "dashboard"
    if path.name in TRANSCRIPT_NAMES:
        return "model_transcript"
    if "prompt_packs" in parts:
        return "prompt_pack"
    if "paper_packages" in parts:
        return "paper_package"
    if "retrieval" in parts:
        return "retrieval_index"
    if "coverage" in lower:
        return "coverage"
    if path.suffix.lower() == ".json":
        return "metadata"
    if path.suffix.lower() == ".md":
        return "report"
    return path.suffix.lower().lstrip(".") or "artifact"


def _read_text_sample(path: Path, *, max_bytes: int = 1_000_000) -> str:
    if path.suffix.lower() not in TEXT_SUFFIXES and path.name not in TRANSCRIPT_NAMES:
        return ""
    try:
        return path.read_bytes()[:max_bytes].decode("utf-8", errors="ignore")
    except OSError:
        return ""


def _write_audit_artifacts(root: Path, classifications: list[ArtifactClassification]) -> None:
    (root / "artifacts_audit.json").write_text(json.dumps(to_plain(classifications), indent=2) + "\n", encoding="utf-8")
    (root / "artifacts_audit.md").write_text(render_artifact_audit_markdown(classifications), encoding="utf-8")


def _copy_selected_files(source_root: Path, target_root: Path, names: list[str]) -> None:
    for name in names:
        source = source_root / name
        if not source.exists() or not source.is_file():
            continue
        target = target_root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        content = _read_text_sample(source)
        if content:
            target.write_text(redact_text(content), encoding="utf-8")
        else:
            shutil.copy2(source, target)
