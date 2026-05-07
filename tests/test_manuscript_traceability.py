from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from gapforge.config import GapForgeConfig
from gapforge.manuscript import ManuscriptManager
from gapforge.manuscript.traceability import ManuscriptTraceabilityAuditor
from gapforge.models import NoveltyDossier, Paper, PriorWorkRecallAssessment
from gapforge.project_memory import ProjectMemoryManager
from gapforge.state import ResearchStateManager


def test_supported_claim_passes(tmp_path: Path) -> None:
    config, manuscript_id, section_id = _traceability_fixture(tmp_path)
    manager = ManuscriptManager(config)
    manager.link_claim_use(
        manuscript_id=manuscript_id,
        section_id=section_id,
        claim_id="claim-supported",
        claim_text="Prior work studies traceable manuscript claims.",
        use_type="background",
        support_status="supported",
        evidence_locators=["paper-1:p2"],
        citation_keys=[],
    )

    report = ManuscriptTraceabilityAuditor(config).audit(manuscript_id)

    assert report.claim_count == 1
    assert report.supported_claim_count == 1
    assert report.unsupported_claim_count == 0
    assert report.blocking_issues == []


def test_result_without_artifact_blocks(tmp_path: Path) -> None:
    config, manuscript_id, section_id = _traceability_fixture(tmp_path)
    ManuscriptManager(config).link_claim_use(
        manuscript_id=manuscript_id,
        section_id=section_id,
        claim_id="claim-result",
        claim_text="The method improves accuracy on the benchmark.",
        use_type="result",
        support_status="supported",
        evidence_locators=["paper-1:p3"],
    )

    report = ManuscriptTraceabilityAuditor(config).audit(manuscript_id)

    assert report.empirical_claim_count == 1
    assert any(warning.warning_type == "result_without_artifact" for warning in report.overclaim_warnings)
    assert any("result artifact" in issue for issue in report.blocking_issues)


def test_fake_sota_claim_blocks(tmp_path: Path) -> None:
    config, manuscript_id, section_id = _traceability_fixture(tmp_path)
    ManuscriptManager(config).link_claim_use(
        manuscript_id=manuscript_id,
        section_id=section_id,
        claim_id="claim-sota",
        claim_text="This is a state-of-the-art result on the leaderboard.",
        use_type="result",
        support_status="supported",
        evidence_locators=["paper-1:p4"],
    )

    report = ManuscriptTraceabilityAuditor(config).audit(manuscript_id)

    assert any(warning.warning_type == "result_without_artifact" for warning in report.overclaim_warnings)
    assert any("SOTA" in warning.text or "state-of-the-art" in warning.text for warning in report.overclaim_warnings)
    assert any("SOTA" in issue for issue in report.blocking_issues)


def test_smoke_result_overclaim_warns(tmp_path: Path) -> None:
    config, manuscript_id, section_id = _traceability_fixture(
        tmp_path,
        section_result_ids=["execution-smoke-1"],
        section_artifact_ids=["artifact-smoke-1"],
    )
    ManuscriptManager(config).link_claim_use(
        manuscript_id=manuscript_id,
        section_id=section_id,
        claim_id="claim-smoke",
        claim_text="The main result shows the method works.",
        use_type="result",
        support_status="supported",
        evidence_locators=["paper-1:p5"],
    )

    report = ManuscriptTraceabilityAuditor(config).audit(manuscript_id)

    assert any(warning.warning_type == "smoke_as_main_result" for warning in report.overclaim_warnings)
    assert any("smoke/pilot" in warning.suggested_fix for warning in report.overclaim_warnings)


def test_strong_novelty_requires_dossier_and_prior_work(tmp_path: Path) -> None:
    config, manuscript_id, section_id = _traceability_fixture(tmp_path)
    ManuscriptManager(config).link_claim_use(
        manuscript_id=manuscript_id,
        section_id=section_id,
        claim_id="claim-novelty",
        claim_text="This is the first traceability method for manuscripts.",
        use_type="novelty",
        support_status="supported",
        evidence_locators=["paper-1:p6"],
    )

    blocked = ManuscriptTraceabilityAuditor(config).audit(manuscript_id)
    _add_novelty_support(config, manuscript_id, "claim-novelty")
    supported = ManuscriptTraceabilityAuditor(config).audit(manuscript_id)

    assert any(warning.warning_type == "overstrong_novelty" for warning in blocked.overclaim_warnings)
    assert supported.blocking_issues == []


def test_softening_suggestion_generated(tmp_path: Path) -> None:
    config, manuscript_id, section_id = _traceability_fixture(tmp_path)
    ManuscriptManager(config).link_claim_use(
        manuscript_id=manuscript_id,
        section_id=section_id,
        claim_id="claim-unsupported",
        claim_text="The system definitively solves submission readiness.",
        use_type="method",
        support_status="unsupported",
    )

    suggestions = ManuscriptTraceabilityAuditor(config).soften_claims(manuscript_id, dry_run=True)

    assert "claim-unsupported" in suggestions
    assert "Soften" in suggestions
    assert "hypothesis" in suggestions


def test_traceability_cli(tmp_path: Path) -> None:
    _config, manuscript_id, section_id = _traceability_fixture(tmp_path)
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")}
    subprocess.run(
        [
            sys.executable,
            "-m",
            "gapforge.cli",
            "manuscript-soften-claims",
            "--manuscript-id",
            manuscript_id,
            "--dry-run",
        ],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    manager = ManuscriptManager(GapForgeConfig.from_cwd(tmp_path))
    manager.link_claim_use(
        manuscript_id=manuscript_id,
        section_id=section_id,
        claim_id="claim-cli",
        claim_text="A speculative manuscript claim.",
        use_type="future_work",
        support_status="hypothesis",
    )

    traceability = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "manuscript-traceability", "--manuscript-id", manuscript_id],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    overclaims = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "manuscript-overclaims", "--manuscript-id", manuscript_id],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    soften = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "manuscript-soften-claims", "--manuscript-id", manuscript_id, "--dry-run"],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert traceability.returncode == 0, traceability.stderr
    assert overclaims.returncode == 0, overclaims.stderr
    assert soften.returncode == 0, soften.stderr
    assert "Manuscript Traceability" in traceability.stdout
    assert json.loads(overclaims.stdout) == []
    assert "No claim softening suggestions" in soften.stdout


def _traceability_fixture(
    tmp_path: Path,
    *,
    section_result_ids: list[str] | None = None,
    section_artifact_ids: list[str] | None = None,
) -> tuple[GapForgeConfig, str, str]:
    config = GapForgeConfig.from_cwd(tmp_path)
    state_manager = ResearchStateManager(config)
    run = state_manager.create_run("traceability fixture")
    run.papers = [
        Paper(
            id="paper-1",
            title="Traceability Paper",
            authors=["Ada Lovelace"],
            abstract="Traceability evidence.",
            year=2025,
            venue="ICLR",
        )
    ]
    state_manager.save_run(run)
    project_manager = ProjectMemoryManager(config)
    program = project_manager.create_project("Traceability Project")
    program.run_ids.append(run.run_id)
    program.project.run_ids.append(run.run_id)
    project_manager.save_project(program)
    manuscript_manager = ManuscriptManager(config)
    manuscript = manuscript_manager.create_manuscript(
        project_id=program.project.id,
        direction_id="direction-1",
        workspace_id="workspace-1",
        title="Traceability Draft",
    )
    section = manuscript_manager.create_section(
        manuscript_id=manuscript.manuscript.id,
        section_type="results",
        source_paper_ids=["paper-1"],
        source_result_ids=section_result_ids or [],
        source_artifact_ids=section_artifact_ids or [],
    )
    return config, manuscript.manuscript.id, section.id


def _add_novelty_support(config: GapForgeConfig, manuscript_id: str, claim_id: str) -> None:
    manuscript = ManuscriptManager(config).load_state(manuscript_id).manuscript
    project_manager = ProjectMemoryManager(config)
    program = project_manager.load_project(manuscript.project_id)
    run_state = ResearchStateManager(config).load_run(program.run_ids[0])
    run_state.novelty_dossiers.append(
        NoveltyDossier(
            target_id=claim_id,
            idea_summary="Traceability novelty.",
            top_prior_work=["paper-1"],
            verdict="pursue",
            novelty_strength="moderate",
        )
    )
    run_state.prior_work_recall_assessments.append(
        PriorWorkRecallAssessment(
            id="prior-work-claim-novelty",
            target_id=claim_id,
            completed_query_rounds=["novelty", "survey", "benchmark", "counterevidence"],
            candidate_prior_work_ids=["paper-1"],
            top_prior_work_ids=["paper-1"],
            novelty_allowed=True,
            recall_confidence="medium",
        )
    )
    ResearchStateManager(config).save_run(run_state)
