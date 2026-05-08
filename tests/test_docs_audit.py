from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from gapforge.config import GapForgeConfig
from gapforge.docs_audit import DocsAuditor, detect_overclaim_phrases, render_docs_audit

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


def test_docs_audit_detects_missing_file(tmp_path: Path) -> None:
    _write_fixture_docs(tmp_path)
    (tmp_path / "docs" / "CODEX_QUICKSTART.md").unlink()

    audit = DocsAuditor(GapForgeConfig.from_cwd(tmp_path)).audit()

    assert audit.passed is False
    assert audit.checks["codex_quickstart_exists"] is False
    assert any("CODEX_QUICKSTART.md" in path for path in audit.missing_files)


def test_docs_audit_passes_fixture_docs(tmp_path: Path) -> None:
    _write_fixture_docs(tmp_path)

    audit = DocsAuditor(GapForgeConfig.from_cwd(tmp_path)).audit(write=True)
    rendered = render_docs_audit(audit)

    assert audit.passed is True
    assert "# GapForge Documentation Usability Audit" in rendered
    assert (tmp_path / "data" / "release_gate" / "docs_audit.json").exists()


def test_overclaim_phrase_detector_catches_known_bad_example(tmp_path: Path) -> None:
    path = tmp_path / "docs" / "releases" / "bad.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("This release guarantees novelty and is publication-ready.\n", encoding="utf-8")

    findings = detect_overclaim_phrases([path])

    assert findings
    assert "guarantees novelty" in findings[0]


def test_docs_audit_cli_write_report(tmp_path: Path) -> None:
    _write_fixture_docs(tmp_path)

    result = run_cli(tmp_path, "docs-audit", "--write-report")

    assert result.returncode == 0, result.stderr
    assert "Passed: true" in result.stdout
    assert (tmp_path / "data" / "docs_audit" / "docs_audit_latest.md").exists()


def _write_fixture_docs(root: Path) -> None:
    docs = root / "docs"
    docs.mkdir(parents=True, exist_ok=True)
    (root / "README.md").write_text(
        "\n".join(
            [
                "# GapForge",
                "## v0.9 External Pilot and v1 Readiness",
                "Use `gapforge pilot-run --name low_fpr_collusion`, `gapforge pilot-review --pilot-id <id>`, and `gapforge v1-readiness`.",
                "## v0.5 Real Literature",
                "`gapforge real-literature-run --profile live_low_fpr_collusion` "
                "then `gapforge real-literature-review --campaign-id <id>`.",
                "## v0.6 Experiment",
                "`gapforge experiment-workspace-create --project-id <id> --direction-id <id>` then `gapforge experiment-run`.",
                "## v0.8 Manuscript",
                "`gapforge manuscript-create --project-id <id> --direction-id <id>` then `gapforge submission-package`.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    files = {
        "CODEX_QUICKSTART.md": "# Codex Quickstart\n",
        "V0_5_REAL_LITERATURE_CAMPAIGNS.md": "# v0.5 Real Literature\n",
        "V0_6_EXPERIMENT_EXECUTION.md": "# v0.6 Experiment Execution\n",
        "V0_8_MANUSCRIPT_WORKFLOW.md": "# v0.8 Manuscript Workflow\n",
        "V0_9_V1_READINESS.md": "# v1 Readiness\n",
        "KNOWN_LIMITATIONS.md": "# Known Limitations\n\n## v0.9\nNo exhaustive claims.\n",
    }
    for name, text in files.items():
        (docs / name).write_text(text, encoding="utf-8")
