from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from gapforge.config import GapForgeConfig
from gapforge.evals.fixtures import load_fixture
from gapforge.models import (
    Claim,
    Evidence,
    EvidenceSpan,
    ExperimentPlan,
    Gap,
    GapEvidenceMatrix,
    NoveltyAssessment,
    NoveltyDossier,
    PaperSection,
    RejectedIdea,
    ReviewerObjection,
    ReviewerSimulationSummary,
)
from gapforge.reporting import build_final_report, write_final_report
from gapforge.skills.literature_cartographer import LiteratureCartographer
from gapforge.state import ResearchStateManager


def test_final_report_markdown_from_fixture_state(tmp_path: Path) -> None:
    state = _fixture_report_state(tmp_path)

    path = write_final_report(state)

    assert path == Path(state.run_dir) / "final_report.md"
    assert path.exists()
    text = path.read_text(encoding="utf-8")
    for heading in [
        "## 1. Executive Summary",
        "## 2. What Was Searched",
        "## 3. Source and Full-Text Coverage",
        "## 4. Field Map",
        "## 5. Important Paper Clusters",
        "## 6. Papers Read Deeply",
        "## 7. Evidence-Backed Research Gaps",
        "## 8. Gap Evidence Matrix Summary",
        "## 9. Cross-Domain Transfer Candidates",
        "## 10. Closest-Prior-Work Dossiers",
        "## 11. Recommended Top Research Direction",
        "## 12. Experiment Plan for Top Direction",
        "## 13. Reviewer Simulation and Blocking Issues",
        "## 14. Claim Ledger Summary",
        "## 15. Human Review Summary",
        "## 16. Rejected Ideas",
        "## 17. What Remains Uncertain",
        "## 18. Next Actions",
    ]:
        assert heading in text
    assert "Direction: **No direction ready**" in text
    assert "`p-lfc-1`" in text
    assert "False-positive calibrated collusion detector benchmark" in text
    assert "Novelty caution" in text
    assert "`rejected-dup-lfc-1`" in text


def test_final_report_json_from_fixture_state(tmp_path: Path) -> None:
    state = _fixture_report_state(tmp_path)

    path = write_final_report(state, output_format="json")

    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["topic"] == "low false positive collusion detection"
    assert payload["report_version"] == "v0.2"
    assert payload["executive_summary"]["recommended_direction"]["readiness"] == "not_ready"
    assert payload["strongest_research_gaps"][0]["supporting_paper_ids"]
    assert "sections" in payload
    assert "source_coverage" in payload
    assert payload["rejected_ideas"][0]["id"] == "rejected-dup-lfc-1"


def test_final_report_uses_v3_label_for_v3_runs(tmp_path: Path) -> None:
    state = _fixture_report_state(tmp_path)
    state.config["v3"] = True

    report = build_final_report(state)

    assert report["report_version"] == "v0.3"


def test_build_final_report_distinguishes_claims_from_hypotheses(tmp_path: Path) -> None:
    state = _fixture_report_state(tmp_path)

    report = build_final_report(state)

    claim_summary = report["claim_ledger_summary"]
    assert claim_summary["evidence_backed_claims"]
    assert report["unsupported_or_uncertain_claims"]
    assert "hypotheses" in claim_summary


def test_report_cli_writes_markdown(tmp_path: Path) -> None:
    state = _fixture_report_state(tmp_path)
    ResearchStateManager(GapForgeConfig.from_cwd(tmp_path)).save_run(state)

    result = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "report", "--run-id", state.run_id],
        cwd=tmp_path,
        env={**os.environ, "GAPFORGE_DISABLE_NETWORK": "1", "PYTHONPATH": str(Path.cwd() / "src")},
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "final_report.md" in result.stdout
    assert (Path(state.run_dir) / "final_report.md").exists()


def test_report_includes_source_coverage_and_evidence_locators(tmp_path: Path) -> None:
    state = _ready_report_state(tmp_path)

    path = write_final_report(state)
    text = path.read_text(encoding="utf-8")

    assert "Source and Full-Text Coverage" in text
    assert "p-lfc-1:Evaluation:p4" in text
    assert "full-text evidence" in text


def test_report_refuses_recommendation_under_poor_coverage_in_strict_mode(tmp_path: Path) -> None:
    state = _fixture_report_state(tmp_path)

    report = build_final_report(state, strict=True)

    direction = report["sections"]["recommended_top_research_direction"]
    assert direction["readiness"] == "not_ready"
    assert direction["gap_id"] == ""
    assert any("coverage" in reason.lower() for reason in direction["blocking_reasons"])


def test_report_recommends_one_direction_when_thresholds_are_met(tmp_path: Path) -> None:
    state = _ready_report_state(tmp_path)

    report = build_final_report(state, strict=True)

    direction = report["sections"]["recommended_top_research_direction"]
    assert direction["readiness"] == "ready"
    assert direction["gap_id"] == "good-lfc-1"
    assert direction["experiment_id"] == "experiment-1"
    assert direction["claims_novelty"] is True


def _fixture_report_state(tmp_path: Path):
    fixture = load_fixture("low_fpr_collusion")
    config = GapForgeConfig.from_cwd(tmp_path)
    manager = ResearchStateManager(config)
    state = manager.create_run(fixture.topic)
    state.papers = fixture.papers
    state.paper_notes = fixture.paper_notes
    state.field_map = LiteratureCartographer([]).build_field_map(fixture.topic, fixture.papers)
    state.gaps = fixture.known_good_gaps + [
        Gap(
            id="dup-lfc-1",
            title="False-positive calibrated collusion detector benchmark",
            type="benchmark gap",
            description="Build the same false-positive calibrated collusion detector benchmark.",
            supporting_paper_ids=["p-lfc-1"],
            why_existing_work_does_not_solve_it="This intentionally duplicates closest prior work.",
            minimum_experiment_needed="None until the idea is reframed.",
            risk_that_gap_is_fake="The idea is fake because fixture prior work already names the benchmark.",
            confidence="medium",
            novelty_status="likely_not_new",
        )
    ]
    state.gaps[0].novelty_status = "medium"
    state.novelty_assessments = [
        NoveltyAssessment(
            target_gap_or_hypothesis_id="good-lfc-1",
            idea_summary=state.gaps[0].description,
            closest_prior_work=["p-lfc-1: False-positive calibrated collusion detector benchmark"],
            similarity_to_prior_work=0.35,
            what_is_new=["Focus on recall at fixed analyst alert budgets across detectors."],
            what_is_not_new=["False-positive benchmark framing already exists."],
            possible_reviewer_objection="The work may look incremental unless baselines are decisive.",
            decisive_difference_needed="Show a measurable alert-budget tradeoff not reported by prior work.",
            search_queries_used=["collusion fixed false positive alert budget prior work"],
            missing_searches=["source connector search: fraud alert budget collusion benchmark"],
            verdict="pursue",
            novelty_strength="medium",
            confidence="medium",
        ),
        NoveltyAssessment(
            target_gap_or_hypothesis_id="dup-lfc-1",
            idea_summary="Build the same false-positive calibrated collusion detector benchmark.",
            closest_prior_work=["p-lfc-1: False-positive calibrated collusion detector benchmark"],
            similarity_to_prior_work=0.95,
            what_is_new=["No decisive novelty is visible."],
            what_is_not_new=["The closest prior work already states the benchmark idea."],
            possible_reviewer_objection="This appears duplicative.",
            decisive_difference_needed="Change the task, metric, setting, or theoretical claim.",
            search_queries_used=["false positive calibrated collusion detector benchmark"],
            missing_searches=[],
            verdict="reject",
            novelty_strength="weak",
            confidence="high",
        ),
    ]
    state.experiments = [
        ExperimentPlan(
            id="experiment-1",
            title="Measurement study: Alert-budget evaluation for collusion detectors",
            linked_gap_ids=["good-lfc-1"],
            hypothesis="Detector ranking changes when recall is measured at fixed false-positive alert budgets.",
            core_claim_being_tested="Existing work does not resolve alert-budget tradeoffs for collusion detection.",
            minimum_viable_experiment="Compare collusion detectors at matched false-positive alert budgets.",
            datasets_needed=["public interaction-log benchmark", "synthetic stress-test dataset"],
            baselines=["closest prior work", "graph anomaly detector", "rule-based collusion heuristic"],
            metrics=["false-positive-rate", "recall-at-fixed-fpr", "precision-at-alert-budget"],
            statistical_tests=["paired permutation test", "bootstrap confidence intervals"],
            ablations=["sweep alert thresholds", "remove calibration component"],
            what_result_would_falsify_the_idea="The idea is falsified if closest prior work matches recall at fixed FPR.",
            reviewer_killer_result="Publishable result: robust recall gains at fixed false-positive budgets.",
            risks=["novelty remains provisional because one search is missing"],
            novelty_assessment_id="good-lfc-1",
            confidence="medium",
        )
    ]
    state.reviewer_summaries = [
        ReviewerSimulationSummary(
            experiment_id="experiment-1",
            submission_readiness_score=68,
            blocking_issues=["Novelty search is incomplete."],
            required_fixes=["Resolve missing closest-prior-work search."],
            optional_fixes=["Add more deployment data."],
            final_recommendation="conference_potential",
        )
    ]
    state.reviewer_objections = [
        ReviewerObjection(
            id="obj-1",
            experiment_id="experiment-1",
            severity="major",
            category="novelty",
            objection="The novelty check still lists a missing adjacent search.",
            why_reviewer_would_care="A reviewer can invalidate the contribution by finding omitted prior work.",
            evidence_or_prior_work=["source connector search: fraud alert budget collusion benchmark"],
            suggested_fix="Run and read the missing adjacent search before claiming novelty.",
            blocks_submission=True,
            confidence="medium",
        )
    ]
    state.rejected_ideas = [
        RejectedIdea(
            id="rejected-dup-lfc-1",
            idea="Build the same false-positive calibrated collusion detector benchmark.",
            reason="Closest prior work already states the same benchmark idea.",
        )
    ]
    evidence = Evidence(
        source_id="p-lfc-1",
        source_paper_id="p-lfc-1",
        quote="fixed false-positive budgets and analyst review",
        locator="abstract",
        confidence="medium",
    )
    state.claims = [
        Claim(
            id="claim-1",
            text="At least one fixture paper studies collusion detection at fixed false-positive budgets.",
            type="background",
            status="supported",
            confidence="medium",
            supporting_evidence=[evidence],
            source_paper_ids=["p-lfc-1"],
            created_by_skill="test-fixture",
            needs_verification=False,
        ),
        Claim(
            id="claim-2",
            text="Alert-budget evaluation may be underreported outside the fixture papers.",
            type="gap",
            status="uncertain",
            confidence="low",
            source_paper_ids=["p-lfc-1", "p-lfc-2"],
            created_by_skill="test-fixture",
            needs_verification=True,
        ),
    ]
    return state


def _ready_report_state(tmp_path: Path):
    state = _fixture_report_state(tmp_path)
    fixture = load_fixture("low_fpr_collusion_v2")
    state.paper_sections = [
        PaperSection(
            id="section-results-1",
            paper_id="p-lfc-1",
            title="Evaluation",
            section_type="experiments",
            text="Evaluation section: graph detector is tested with false-positive rate controls.",
            page_start=4,
            page_end=4,
            confidence="medium",
        )
    ]
    state.evidence_spans = [
        EvidenceSpan(
            id="span-1",
            paper_id="p-lfc-1",
            section_id="section-results-1",
            quote="graph detector is tested with false-positive rate controls",
            locator="p-lfc-1:Evaluation:p4",
            evidence_type="result",
            page_start=4,
            page_end=4,
            confidence="medium",
        )
    ]
    state.paper_notes[0].source_basis = "full text"
    state.paper_notes[0].sections_used = ["section-results-1"]
    state.paper_notes[0].quotes_or_evidence_snippets = [
        Evidence(
            source_id="p-lfc-1",
            source_paper_id="p-lfc-1",
            quote="graph detector is tested with false-positive rate controls",
            locator="p-lfc-1:Evaluation:p4",
            confidence="medium",
        )
    ]
    state.source_coverage = fixture.expected_source_coverage
    state.source_coverage.papers_with_full_text = ["p-lfc-1", "p-lfc-2"]
    state.source_coverage.confidence = "medium"
    state.gap_evidence_matrices = [
        GapEvidenceMatrix(
            gap_id="good-lfc-1",
            evidence_rows=fixture.expected_gap_evidence_matrix[0].evidence_rows,
            papers_supporting=["p-lfc-1", "p-lfc-2"],
            papers_countering=[],
            confidence="medium",
        )
    ]
    state.novelty_dossiers = [
        NoveltyDossier(
            target_id="good-lfc-1",
            idea_summary=state.gaps[0].description,
            query_plan=["collusion fixed false positive alert budget prior work"],
            candidates_considered=["p-lfc-1", "p-lfc-2"],
            top_prior_work=["p-lfc-1: False-positive calibrated collusion detector benchmark (similarity 0.35)"],
            comparison_table=[{"paper_id": "p-lfc-1", "overall_similarity": 0.35}],
            decisive_difference_needed="Show a measurable alert-budget tradeoff not reported by prior work.",
            missing_searches=[],
            verdict="pursue",
            novelty_strength="medium",
            confidence="medium",
            evidence_spans=state.evidence_spans,
            reviewer_objection="Use the closest prior work as a baseline.",
            recommended_action="Pursue with closest prior work as a baseline.",
        )
    ]
    state.novelty_assessments[0].missing_searches = []
    state.reviewer_objections = []
    state.reviewer_summaries = [
        ReviewerSimulationSummary(
            experiment_id="experiment-1",
            submission_readiness_score=82,
            blocking_issues=[],
            required_fixes=[],
            optional_fixes=["Add deployment data."],
            final_recommendation="conference_potential",
        )
    ]
    return state
