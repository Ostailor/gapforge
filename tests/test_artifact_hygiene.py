from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from gapforge.artifacts.hygiene import REQUIRED_GITIGNORE_PATTERNS, ArtifactHygieneAuditor, verify_gitignore_patterns
from gapforge.config import GapForgeConfig
from gapforge.project_memory import ProjectMemoryManager
from gapforge.safety import export_safe_project_bundle

REPO_ROOT = Path(__file__).resolve().parents[1]


def run_cli(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["GAPFORGE_DISABLE_NETWORK"] = "1"
    env["PYTHONPATH"] = str(REPO_ROOT / "src")
    return subprocess.run(
        [sys.executable, "-m", "gapforge.cli", *args],
        cwd=cwd,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def test_artifact_hygiene_flags_unsafe_pdf(tmp_path: Path) -> None:
    config = GapForgeConfig.from_cwd(tmp_path)
    program = ProjectMemoryManager(config).create_project("Unsafe PDF")
    project_root = Path(program.project.root_dir)
    (project_root / "paper.pdf").write_bytes(b"%PDF-1.4\n")

    report = ArtifactHygieneAuditor(config).audit_project(program.project.id)

    assert report.pdf_count == 1
    assert report.unsafe_to_commit_count >= 1
    assert any("paper.pdf" in blocker and "restricted" in blocker for blocker in report.blockers)


def test_artifact_hygiene_accepts_redacted_transcript_when_ignored(tmp_path: Path) -> None:
    _write_required_gitignore(tmp_path)
    config = GapForgeConfig.from_cwd(tmp_path)
    program = ProjectMemoryManager(config).create_project("Redacted Transcript")
    project_root = Path(program.project.root_dir)
    (project_root / "llm_transcripts.json").write_text('{"prompt": "[REDACTED]"}\n', encoding="utf-8")

    report = ArtifactHygieneAuditor(config).audit_project(program.project.id)

    assert report.transcript_count == 1
    assert report.secret_risk_count == 0
    assert not report.blockers


def test_artifact_hygiene_generated_dashboard_ignored(tmp_path: Path) -> None:
    _write_required_gitignore(tmp_path)
    config = GapForgeConfig.from_cwd(tmp_path)
    program = ProjectMemoryManager(config).create_project("Dashboard Ignored")
    project_root = Path(program.project.root_dir)
    dashboard = project_root / "dashboard" / "index.html"
    dashboard.parent.mkdir(parents=True)
    dashboard.write_text("<html><body>Generated dashboard</body></html>\n", encoding="utf-8")

    report = ArtifactHygieneAuditor(config).audit_project(program.project.id)

    assert report.ignored_status_summary["ignored"] > 0
    assert not report.blockers


def test_verify_gitignore_patterns_works(tmp_path: Path) -> None:
    _write_required_gitignore(tmp_path)

    result = verify_gitignore_patterns(GapForgeConfig.from_cwd(tmp_path))

    assert result.passed is True
    assert result.missing_patterns == []


def test_verify_gitignore_cli_fails_when_pattern_missing(tmp_path: Path) -> None:
    (tmp_path / ".gitignore").write_text("runs/*\n", encoding="utf-8")

    result = run_cli(tmp_path, "verify-gitignore")

    assert result.returncode == 1
    assert "FAILED" in result.stdout
    assert "projects/*" in result.stdout


def test_artifact_hygiene_safe_bundle_passes_and_writes_release_gate(tmp_path: Path) -> None:
    _write_required_gitignore(tmp_path)
    config = GapForgeConfig.from_cwd(tmp_path)
    program = ProjectMemoryManager(config).create_project("Safe Bundle Hygiene")

    bundle = export_safe_project_bundle(config, program.project.id)
    report = ArtifactHygieneAuditor(config).audit_project(program.project.id, write=True)
    result = run_cli(tmp_path, "artifact-hygiene", "--all", "--write-report")

    assert bundle.exists()
    assert not list(bundle.rglob("*.pdf"))
    assert not report.blockers
    assert result.returncode == 0, result.stderr
    assert (tmp_path / "data" / "release_gate" / "artifact_hygiene_audit.json").exists()


def _write_required_gitignore(root: Path) -> None:
    root.joinpath(".gitignore").write_text("\n".join(REQUIRED_GITIGNORE_PATTERNS) + "\n", encoding="utf-8")
