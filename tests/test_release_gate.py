from __future__ import annotations

from pathlib import Path

from gapforge.release_gate import parse_release_gate


def test_v030_release_gate_reports_actual_run_not_completed() -> None:
    gate = parse_release_gate(Path(__file__).resolve().parents[1] / "docs" / "releases" / "v0.3.0-real-run-acceptance.md")

    assert gate.version == "0.3.0"
    assert gate.actual_run_acceptance == "not_completed"
    assert gate.actual_run_acceptance_passed is False
    assert gate.accepted_real_canary_count == 0
    assert gate.passed is False
    assert {item["profile_id"] for item in gate.real_canaries} == {
        "low_fpr_collusion_codex",
        "manual_pdf_fulltext_codex",
    }


def test_release_gate_requires_accepted_real_canary(tmp_path: Path) -> None:
    path = tmp_path / "release.md"
    path.write_text(
        """---
{
  "version": "0.3.0",
  "actual_run_acceptance": "passed",
  "actual_run_acceptance_passed": true,
  "accepted_real_canary_count": 0,
  "real_canaries": []
}
---
# Release
""",
        encoding="utf-8",
    )

    assert parse_release_gate(path).passed is False
