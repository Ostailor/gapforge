from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from gapforge.config import GapForgeConfig
from gapforge.directions.maturation import DirectionMaturationManager
from gapforge.models import (
    EvidenceSpan,
    ExperimentPlan,
    Gap,
    GapEvidenceMatrix,
    GapEvidenceRow,
    HumanReviewRecord,
    NoveltyDossier,
    Paper,
    RelatedWorkEntry,
    RelatedWorkMatrix,
    ResearchRunState,
    ReviewerObjection,
    SearchQueryRecord,
    SourceCoverageReport,
)
from gapforge.project_memory import ProjectMemoryManager
from gapforge.state import ResearchStateManager


def test_direction_matures_only_when_gates_pass(tmp_path: Path) -> None:
    config, project_id, _run_id = _project_with_gap(tmp_path)
    manager = DirectionMaturationManager(config)

    direction = manager.create_direction(project_id, "gap-1")
    direction = manager.mature_direction(project_id, direction.id)

    assert direction.maturity == "candidate"
    assert any("GapEvidenceMatrix" in issue for issue in direction.blocking_issues)
    assert direction.readiness_score < 0.5


def test_direction_reaches_manuscript_ready_when_all_gates_pass(tmp_path: Path) -> None:
    config, project_id, run_id = _project_with_gap(tmp_path)
    state_manager = ResearchStateManager(config)
    state = state_manager.load_run(run_id)
    _add_full_ready_artifacts(state)
    state_manager.save_run(state)
    manager = DirectionMaturationManager(config)

    direction = manager.create_direction(project_id, "gap-1")
    direction = manager.mature_direction(project_id, direction.id)

    assert direction.maturity == "manuscript_ready"
    assert direction.blocking_issues == []
    assert Path(config.project_root, project_id, "direction_maturity_report.md").exists()


def test_rejected_novelty_blocks_direction_maturity(tmp_path: Path) -> None:
    config, project_id, run_id = _project_with_gap(tmp_path)
    state_manager = ResearchStateManager(config)
    state = state_manager.load_run(run_id)
    _add_full_ready_artifacts(state)
    state.novelty_dossiers[0].verdict = "reject"
    state_manager.save_run(state)
    manager = DirectionMaturationManager(config)

    direction = manager.create_direction(project_id, "gap-1")
    direction = manager.mature_direction(project_id, direction.id)

    assert direction.maturity == "rejected"
    assert direction.readiness_score == 0.0


def test_human_coverage_waiver_promotes_validated_gap(tmp_path: Path) -> None:
    config, project_id, run_id = _project_with_gap(tmp_path)
    state_manager = ResearchStateManager(config)
    state = state_manager.load_run(run_id)
    _add_evidence_matrix(state)
    state.source_coverage = SourceCoverageReport(
        run_id=state.run_id,
        topic=state.topic.text,
        searched_sources=["fixture"],
        confidence="low",
    )
    state.search_queries.append(SearchQueryRecord(id="q-1", query="closest prior work", purpose="novelty"))
    state.human_reviews.append(
        HumanReviewRecord(
            id="review-waiver",
            object_type="gap",
            object_id="gap-1",
            action="approve",
            note="I explicitly waive source coverage for this synthetic fixture.",
            reviewer="researcher",
        )
    )
    state_manager.save_run(state)
    manager = DirectionMaturationManager(config)

    direction = manager.create_direction(project_id, "gap-1")
    direction = manager.mature_direction(project_id, direction.id)

    assert direction.maturity == "validated_gap"
    assert not any("source coverage" in issue.lower() for issue in direction.blocking_issues)
    assert state_manager.load_run(run_id).human_reviews[0].id == "review-waiver"


def test_direction_card_includes_evidence_locators(tmp_path: Path) -> None:
    config, project_id, run_id = _project_with_gap(tmp_path)
    state_manager = ResearchStateManager(config)
    state = state_manager.load_run(run_id)
    _add_full_ready_artifacts(state)
    state_manager.save_run(state)
    manager = DirectionMaturationManager(config)

    direction = manager.create_direction(project_id, "gap-1")
    direction = manager.mature_direction(project_id, direction.id)
    card_path = manager.write_card(project_id, direction.id)
    card = card_path.read_text(encoding="utf-8")

    assert "p1:Results:p2" in card
    assert "p1:Limitations:p3" in card
    assert card_path == Path(config.project_root, project_id, "direction_cards", f"{direction.id}.md")


def test_manuscript_ready_requires_reviewer_gate(tmp_path: Path) -> None:
    config, project_id, run_id = _project_with_gap(tmp_path)
    state_manager = ResearchStateManager(config)
    state = state_manager.load_run(run_id)
    _add_full_ready_artifacts(state, fatal_reviewer=True)
    state_manager.save_run(state)
    manager = DirectionMaturationManager(config)

    direction = manager.create_direction(project_id, "gap-1")
    direction = manager.mature_direction(project_id, direction.id)

    assert direction.maturity == "rejected"
    assert direction.maturity != "manuscript_ready"


def test_direction_cli_commands(tmp_path: Path) -> None:
    config, project_id, _run_id = _project_with_gap(tmp_path)
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")}

    created = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "create-direction", "--project-id", project_id, "--gap-id", "gap-1"],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert created.returncode == 0, created.stderr
    direction_id = created.stdout.split()[2]

    listed = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "list-directions", "--project-id", project_id],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    card = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "direction-card", "--project-id", project_id, "--direction-id", direction_id],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    rejected = subprocess.run(
        [
            sys.executable,
            "-m",
            "gapforge.cli",
            "reject-direction",
            "--project-id",
            project_id,
            "--direction-id",
            direction_id,
            "--reason",
            "Duplicate idea.",
        ],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert listed.returncode == 0, listed.stderr
    assert direction_id in listed.stdout
    assert card.returncode == 0, card.stderr
    assert "Direction Card" in card.stdout
    assert rejected.returncode == 0, rejected.stderr
    assert "Rejected direction" in rejected.stdout
    assert Path(config.project_root, project_id, "research_directions.json").exists()


def _project_with_gap(tmp_path: Path) -> tuple[GapForgeConfig, str, str]:
    config = GapForgeConfig.from_cwd(tmp_path)
    state_manager = ResearchStateManager(config)
    state = state_manager.create_run("direction fixture topic")
    state.papers = [
        Paper(id="p1", title="Low FPR Monitor", authors=["A"], abstract="Evaluates low FPR monitoring.", year=2025, source="fixture"),
        Paper(id="p2", title="Prior Work Monitor", authors=["B"], abstract="Closest prior work.", year=2024, source="fixture"),
    ]
    state.gaps = [
        Gap(
            id="gap-1",
            title="Low FPR deployment evaluation gap",
            description="Monitoring papers rarely test operator workload at very low false-positive rates.",
            supporting_paper_ids=["p1"],
            linked_paper_ids=["p1"],
            risk_that_gap_is_fake="A closer benchmark paper may already evaluate the low-FPR setting.",
            confidence="medium",
        )
    ]
    state_manager.save_run(state)
    project_manager = ProjectMemoryManager(config)
    program = project_manager.create_project("Direction Project")
    project_manager.attach_run(program.project.id, state.run_id)
    return config, program.project.id, state.run_id


def _add_full_ready_artifacts(state: ResearchRunState, *, fatal_reviewer: bool = False) -> None:
    _add_evidence_matrix(state)
    state.source_coverage = SourceCoverageReport(
        run_id=state.run_id,
        topic=state.topic.text,
        searched_sources=["fixture", "semantic_scholar"],
        papers_with_full_text=["p1", "p2"],
        confidence="medium",
    )
    state.search_queries.append(SearchQueryRecord(id="q-1", query="low fpr monitor prior work", purpose="novelty"))
    state.novelty_dossiers.append(
        NoveltyDossier(
            target_id="gap-1",
            idea_summary="Evaluate monitoring at very low false-positive rates.",
            candidates_considered=["p2"],
            top_prior_work=["p2"],
            comparison_table=[{"paper_id": "p2", "decisive_difference": "Does not test operator workload."}],
            decisive_difference_needed="Show a workload-sensitive metric not covered by closest prior work.",
            verdict="pursue",
            novelty_strength="medium",
            confidence="medium",
            evidence_spans=[
                EvidenceSpan(
                    id="span-1",
                    paper_id="p1",
                    quote="Results report false positive workload.",
                    locator="p1:Results:p2",
                    evidence_type="result",
                    confidence="medium",
                )
            ],
        )
    )
    state.related_work_matrices.append(
        RelatedWorkMatrix(
            direction_id="gap-1",
            entries=[
                RelatedWorkEntry(
                    direction_id="gap-1",
                    paper_id="p2",
                    relationship="partially_solves",
                    relevance_score=0.68,
                    evidence_span_ids=["span-1"],
                    what_it_contributes="Closest related-work baseline.",
                    what_it_does_not_solve="Does not test operator workload.",
                    must_cite=True,
                    baseline_candidate=True,
                )
            ],
            coverage_summary="Fixture related-work matrix.",
            must_read_paper_ids=["p2"],
            baseline_paper_ids=["p2"],
        )
    )
    state.experiments.append(
        ExperimentPlan(
            id="exp-1",
            title="Low-FPR workload benchmark",
            linked_gap_ids=["gap-1"],
            baselines=["threshold monitor", "calibrated detector"],
            metrics=["false positives per hour", "operator workload"],
            what_result_would_falsify_the_idea="No workload difference appears at matched recall.",
        )
    )
    state.reviewer_objections.append(
        ReviewerObjection(
            id="rev-1",
            experiment_id="exp-1",
            severity="fatal" if fatal_reviewer else "major",
            category="baseline",
            objection="Baselines need stronger calibration.",
            suggested_fix="Add calibrated detector baseline.",
            blocks_submission=fatal_reviewer,
        )
    )
    state.human_reviews.append(
        HumanReviewRecord(
            id="review-approve",
            object_type="gap",
            object_id="gap-1",
            action="approve",
            note="Approve direction for maturation.",
            reviewer="researcher",
        )
    )


def _add_evidence_matrix(state: ResearchRunState) -> None:
    state.gap_evidence_matrices.append(
        GapEvidenceMatrix(
            gap_id="gap-1",
            evidence_rows=[
                GapEvidenceRow(
                    paper_id="p1",
                    evidence_span_id="span-1",
                    evidence_type="limitation",
                    text="The paper reports workload limitations.",
                    supports_or_counters="supports",
                    section_type="limitations",
                    locator="p1:Limitations:p3",
                ),
                GapEvidenceRow(
                    paper_id="p2",
                    evidence_span_id="span-2",
                    evidence_type="counterevidence",
                    text="Closest prior work partially evaluates low false positives.",
                    supports_or_counters="counters",
                    section_type="results",
                    locator="p2:Results:p4",
                ),
            ],
            papers_supporting=["p1"],
            papers_countering=["p2"],
            repeated_limitation_count=1,
            confidence="medium",
        )
    )
