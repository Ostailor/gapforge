from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from gapforge.config import GapForgeConfig
from gapforge.export.paper_package import EXPECTED_FILES, PaperPackageExporter
from gapforge.models import (
    Claim,
    Evidence,
    EvidenceSpan,
    ExperimentPlan,
    ExperimentProtocol,
    Gap,
    NoveltyDossier,
    Paper,
    RelatedWorkEntry,
    RelatedWorkMatrix,
    ResearchDirection,
    ReviewerObjection,
)
from gapforge.project_memory import ProjectMemoryManager
from gapforge.state import ResearchStateManager


def test_package_exports_all_expected_files(tmp_path: Path) -> None:
    config, project_id, direction_id = _export_fixture(tmp_path, maturity="experiment_ready")

    package = PaperPackageExporter(config).export_project_direction(project_id, direction_id)
    package_dir = Path(config.project_root, project_id, "paper_packages", direction_id)

    assert sorted(package.files) == sorted(EXPECTED_FILES)
    for filename in EXPECTED_FILES:
        assert (package_dir / filename).exists(), filename
    assert json.loads((package_dir / "paper_package.json").read_text(encoding="utf-8"))["direction_id"] == direction_id


def test_expected_results_are_labeled_hypothetical(tmp_path: Path) -> None:
    config, project_id, direction_id = _export_fixture(tmp_path, maturity="experiment_ready")

    PaperPackageExporter(config).export_project_direction(project_id, direction_id)
    text = Path(config.project_root, project_id, "paper_packages", direction_id, "expected_results.md").read_text(encoding="utf-8")

    assert "hypothetical" in text.lower()
    assert "has not run the experiment" in text
    assert "we found" not in text.lower()


def test_bibliography_includes_doi_and_arxiv(tmp_path: Path) -> None:
    config, project_id, direction_id = _export_fixture(tmp_path, maturity="experiment_ready")

    PaperPackageExporter(config).export_project_direction(project_id, direction_id)
    bib = Path(config.project_root, project_id, "paper_packages", direction_id, "bibliography.bib").read_text(encoding="utf-8")

    assert "doi = {10.1234/baseline}" in bib
    assert "archivePrefix = {arXiv}" in bib
    assert "eprint = {2401.12345}" in bib


def test_rejected_direction_cannot_export_unless_allowed(tmp_path: Path) -> None:
    config, project_id, direction_id = _export_fixture(tmp_path, maturity="rejected")
    exporter = PaperPackageExporter(config)

    with pytest.raises(ValueError, match="Rejected directions cannot be exported"):
        exporter.export_project_direction(project_id, direction_id)

    package = exporter.export_project_direction(project_id, direction_id, allow_rejected=True)
    assert package.readiness == "rejected"


def test_manuscript_ready_direction_has_fewer_warnings_than_candidate(tmp_path: Path) -> None:
    config, ready_project, ready_direction = _export_fixture(tmp_path / "ready", maturity="manuscript_ready")
    config_candidate, candidate_project, candidate_direction = _export_fixture(tmp_path / "candidate", maturity="candidate")

    ready = PaperPackageExporter(config).export_project_direction(ready_project, ready_direction)
    candidate = PaperPackageExporter(config_candidate).export_project_direction(candidate_project, candidate_direction)

    assert len(ready.missing_requirements) < len(candidate.missing_requirements)
    assert any("not experiment_ready or manuscript_ready" in item for item in candidate.missing_requirements)


def test_export_cli_and_bib_cli(tmp_path: Path) -> None:
    config, project_id, direction_id = _export_fixture(tmp_path, maturity="experiment_ready")
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")}

    package = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "export-paper-package", "--project-id", project_id, "--direction-id", direction_id],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    bib = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "export-bib", "--project-id", project_id, "--direction-id", direction_id],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert package.returncode == 0, package.stderr
    assert "Exported paper package" in package.stdout
    assert bib.returncode == 0, bib.stderr
    assert "10.1234/baseline" in bib.stdout
    assert Path(config.project_root, project_id, "paper_packages", direction_id, "README.md").exists()


def test_run_level_export_manuscript(tmp_path: Path) -> None:
    config, project_id, direction_id = _export_fixture(tmp_path, maturity="experiment_ready")
    program = ProjectMemoryManager(config).load_project(project_id)
    run_id = program.run_ids[0]

    package = PaperPackageExporter(config).export_run_gap(run_id, "gap-1")

    assert package.direction_id == "gap-1"
    assert Path(config.runs_dir, run_id, "paper_packages", "gap-1", "abstract.md").exists()
    assert direction_id


def _export_fixture(tmp_path: Path, *, maturity: str) -> tuple[GapForgeConfig, str, str]:
    config = GapForgeConfig.from_cwd(tmp_path)
    state_manager = ResearchStateManager(config)
    state = state_manager.create_run("paper package fixture")
    state.papers = [
        Paper(
            id="p-baseline",
            title="Baseline Paper",
            authors=["Ada Baseline"],
            abstract="Provides the closest baseline.",
            year=2025,
            source="fixture",
            doi="10.1234/baseline",
            url="https://example.test/baseline",
        ),
        Paper(
            id="p-arxiv",
            title="ArXiv Related Work",
            authors=["Theo Archive"],
            abstract="Related arXiv work.",
            year=2024,
            source="fixture",
            arxiv_id="2401.12345",
            url="https://arxiv.org/abs/2401.12345",
        ),
    ]
    state.evidence_spans = [
        EvidenceSpan(
            id="span-1",
            paper_id="p-baseline",
            quote="The baseline evaluates the closest setting.",
            locator="p-baseline:Results:p3",
            evidence_type="result",
        )
    ]
    state.claims = [
        Claim(
            id="claim-1",
            text="Closest prior work partially solves the setting.",
            type="novelty",
            status="supported",
            confidence="medium",
            supporting_evidence=[Evidence(source_id="span-1", quote="closest setting", locator="p-baseline:Results:p3")],
            source_paper_ids=["p-baseline"],
        )
    ]
    state.gaps = [
        Gap(
            id="gap-1",
            title="Package gap",
            description="A workload-sensitive low-FPR evaluation gap.",
            supporting_paper_ids=["p-baseline"],
            risk_that_gap_is_fake="Closest baseline may already cover this.",
            why_existing_work_does_not_solve_it="It does not test the workload metric.",
            novelty_status="medium",
        )
    ]
    state.related_work_matrices = [
        RelatedWorkMatrix(
            direction_id="gap-1",
            entries=[
                RelatedWorkEntry(
                    direction_id="gap-1",
                    paper_id="p-baseline",
                    relationship="partially_solves",
                    relevance_score=0.82,
                    evidence_span_ids=["span-1"],
                    what_it_contributes="Closest baseline and reviewer-risk paper.",
                    what_it_does_not_solve="Does not test the workload metric.",
                    must_cite=True,
                    baseline_candidate=True,
                    reviewer_risk_if_omitted="major positioning risk",
                ),
                RelatedWorkEntry(
                    direction_id="gap-1",
                    paper_id="p-arxiv",
                    relationship="survey_background",
                    relevance_score=0.7,
                    what_it_contributes="Background on related work.",
                    must_cite=True,
                ),
            ],
            coverage_summary="Two relevant papers classified.",
            must_read_paper_ids=["p-baseline", "p-arxiv"],
            baseline_paper_ids=["p-baseline"],
        )
    ]
    state.novelty_dossiers = [
        NoveltyDossier(
            target_id="gap-1",
            idea_summary="Test workload-sensitive low-FPR evaluation.",
            candidates_considered=["p-baseline"],
            top_prior_work=["p-baseline"],
            comparison_table=[{"paper_id": "p-baseline", "overall_similarity": 0.58, "title": "Baseline Paper"}],
            decisive_difference_needed="Use workload metric not covered by the baseline paper.",
            verdict="pursue",
            novelty_strength="medium",
            confidence="medium",
        )
    ]
    state.experiments = [
        ExperimentPlan(
            id="experiment-1",
            title="Package experiment",
            linked_gap_ids=["gap-1"],
            hypothesis="Workload-sensitive low-FPR evaluation changes model selection.",
            core_claim_being_tested="Existing work misses workload-sensitive evaluation.",
            minimum_viable_experiment="Run baseline and proposed method at fixed FPR.",
            baselines=["related-work baseline paper: p-baseline"],
            metrics=["false-positive-rate", "recall-at-fixed-fpr"],
            statistical_tests=["bootstrap confidence intervals"],
            ablations=["remove workload calibration"],
            expected_result_patterns=["Workload metric changes ranking relative to baseline."],
            what_result_would_falsify_the_idea="Baseline matches the proposed method under workload metric.",
            reviewer_killer_result="Clear improvement over baseline at fixed FPR with intervals.",
            novelty_assessment_id="gap-1",
        )
    ]
    state.experiment_protocols = [
        ExperimentProtocol(
            id="protocol-1",
            direction_id="gap-1",
            linked_experiment_plan_id="experiment-1",
            objective="Test the workload-sensitive evaluation gap.",
            hypothesis="Workload-sensitive low-FPR evaluation changes model selection.",
            datasets=["fixture-dataset"],
            metrics=["false-positive-rate", "recall-at-fixed-fpr"],
            statistical_tests=["bootstrap confidence intervals"],
            expected_artifacts=["metrics_summary.csv"],
            evaluation_script_outline=["run baseline", "compute metrics"],
        )
    ]
    state.reviewer_objections = [
        ReviewerObjection(
            id="review-1",
            experiment_id="experiment-1",
            severity="major",
            category="baseline",
            objection="Baseline must be implemented carefully.",
            why_reviewer_would_care="Weak baselines invalidate empirical claims.",
            evidence_or_prior_work=["p-baseline"],
            suggested_fix="Use p-baseline as the primary comparator.",
            blocks_submission=True,
        )
    ]
    state_manager.save_run(state)

    project_manager = ProjectMemoryManager(config)
    program = project_manager.create_project("Paper Package Project")
    project_manager.attach_run(program.project.id, state.run_id)
    direction = ResearchDirection(
        id="direction-1",
        project_id=program.project.id,
        title="Package Direction",
        summary="A paper package fixture direction.",
        linked_gap_ids=["gap-1"],
        linked_experiment_ids=["experiment-1"],
        linked_novelty_dossier_ids=["gap-1"],
        supporting_paper_ids=["p-baseline", "p-arxiv"],
        maturity=maturity,
        readiness_score=0.95 if maturity == "manuscript_ready" else 0.75 if maturity == "experiment_ready" else 0.35,
    )
    program = project_manager.load_project(program.project.id)
    program.research_directions = [direction]
    program.related_work_matrices = state.related_work_matrices
    program.experiment_protocols = state.experiment_protocols
    project_manager.save_project(program)
    return config, program.project.id, direction.id
