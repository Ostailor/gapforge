from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from test_selected_benchmark import _env, _selected_project

from gapforge.manuscript import ManuscriptManager
from gapforge.manuscript.top_conference_revision import TopConferenceRevisionManager
from gapforge.manuscript.traceability import ManuscriptTraceabilityAuditor
from gapforge.selected_benchmark import BenchmarkFitHardeningManager, SelectedAblationManager, SelectedBenchmarkManager


def test_top_conference_revision_reframes_sections_without_new_claims(tmp_path: Path) -> None:
    config, manuscript_id, benchmark_id = _top_conference_fixture(tmp_path)
    BenchmarkFitHardeningManager(config).harden(benchmark_id)
    SelectedAblationManager(config).run(benchmark_id)
    manager = ManuscriptManager(config)
    before_claim_count = len(manager.load_state(manuscript_id).claim_uses)

    report = TopConferenceRevisionManager(config).revise(manuscript_id)
    state = manager.load_state(manuscript_id)
    root = manager.manuscript_root(manuscript_id)
    text = "\n".join((root / section.content_path).read_text(encoding="utf-8") for section in state.sections)
    traceability = ManuscriptTraceabilityAuditor(config).audit(manuscript_id)

    assert report.claim_traceability_passed is True
    assert report.limitations_preserved is True
    assert report.plagiarism_safe is True
    assert len(state.claim_uses) == before_claim_count
    assert traceability.blocking_issues == []
    assert "Contribution Summary" in text
    assert "Benchmark Validity Argument" in text
    assert "Reviewer-Objection-Aware Framing" in text
    assert "does not claim acceptance" in text
    assert "accepted at" not in text.lower()
    assert (root / "submission" / "top_conference_revision" / "top_conference_revision_report.json").exists()
    assert (root / "submission" / "top_conference_revision" / "top_conference_revision_report.md").exists()


def test_top_conference_readiness_keeps_missing_ablations_visible(tmp_path: Path) -> None:
    config, manuscript_id, benchmark_id = _top_conference_fixture(tmp_path)
    BenchmarkFitHardeningManager(config).harden(benchmark_id)

    readiness = TopConferenceRevisionManager(config).readiness(manuscript_id)

    assert readiness.status == "blocked"
    assert any("ablation" in blocker.lower() for blocker in readiness.blockers)
    assert readiness.claim_traceability_passed is True
    assert readiness.conference_candidate_allowed is False


def test_top_conference_revision_cli(tmp_path: Path) -> None:
    config, manuscript_id, benchmark_id = _top_conference_fixture(tmp_path)
    BenchmarkFitHardeningManager(config).harden(benchmark_id)
    SelectedAblationManager(config).run(benchmark_id)

    revise = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "top-conference-revise", "--manuscript-id", manuscript_id],
        cwd=tmp_path,
        env=_env(),
        text=True,
        capture_output=True,
        check=False,
    )
    readiness = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "top-conference-readiness", "--manuscript-id", manuscript_id],
        cwd=tmp_path,
        env=_env(),
        text=True,
        capture_output=True,
        check=False,
    )

    assert revise.returncode == 0, revise.stderr
    payload = json.loads(revise.stdout)
    assert payload["manuscript_id"] == manuscript_id
    assert payload["claim_traceability_passed"] is True
    assert readiness.returncode in {0, 1}
    assert "Top-Conference Readiness" in readiness.stdout
    assert "Claim traceability passed" in readiness.stdout


def _top_conference_fixture(tmp_path: Path) -> tuple[object, str, str]:
    config, project_id = _selected_project(tmp_path)
    benchmark_id = SelectedBenchmarkManager(config).create_spec(project_id).id
    manager = ManuscriptManager(config)
    state = manager.create_manuscript(
        project_id=project_id,
        direction_id="direction-top-conference",
        workspace_id="workspace-top-conference",
        title="Top Conference Draft",
        target_venue="generic_ml_conference",
    )
    section_by_type = {}
    for section_type in ["abstract", "introduction", "related_work", "method", "experiments", "results", "limitations"]:
        section_by_type[section_type] = manager.create_section(
            manuscript_id=state.manuscript.id,
            section_type=section_type,
            title=section_type.replace("_", " ").title(),
            status="drafted",
        )
    manager.link_claim_use(
        manuscript_id=state.manuscript.id,
        section_id=section_by_type["related_work"].id,
        claim_id="claim-related-work-grounding",
        claim_text="Prior work studies low false-positive monitor evaluation.",
        use_type="background",
        support_status="supported",
        evidence_locators=["paper-prior:p1"],
    )
    root = manager.manuscript_root(state.manuscript.id)
    (root / section_by_type["limitations"].content_path).write_text(
        "# Limitations\n\nExisting limitation: deployment validity remains unproven.\n",
        encoding="utf-8",
    )
    return config, state.manuscript.id, benchmark_id
