from __future__ import annotations

from pathlib import Path

from gapforge.config import GapForgeConfig
from gapforge.models import (
    CitationEdge,
    CitationGraph,
    Gap,
    NoveltyAssessment,
    NoveltyDossier,
    Paper,
    SearchRound,
    SearchStrategy,
)
from gapforge.novelty.recall_gate import assess_prior_work_recall, render_prior_work_recall_report, required_query_rounds
from gapforge.reporting import build_final_report, render_markdown_report
from gapforge.state import ResearchStateManager


def _state(tmp_path: Path):
    return ResearchStateManager(GapForgeConfig.from_cwd(tmp_path)).create_run("low false positive collusion detection")


def _completed_rounds(*round_types: str) -> list[SearchRound]:
    return [
        SearchRound(
            id=f"round-{round_type}",
            strategy_id="strategy-1",
            round_type=round_type,
            status="complete",
            result_paper_ids=["paper-1"],
        )
        for round_type in round_types
    ]


def _gap() -> Gap:
    return Gap(
        id="gap-1",
        title="Low false positive collusion detection benchmark",
        description="Detect collusion in LLM agents with monitoring calibration.",
        why_existing_work_does_not_solve_it="Existing work does not evaluate low false positive operation.",
        possible_research_questions=["Can calibrated monitors detect collusion at low false positive rates?"],
        minimum_experiment_needed="Evaluate a monitoring benchmark with false positive FPR metrics and baselines.",
        confidence="medium",
        novelty_status="medium",
    )


def test_missing_required_searches_block_novelty_and_downgrade_existing_dossier(tmp_path: Path) -> None:
    config = GapForgeConfig.from_cwd(tmp_path)
    manager = ResearchStateManager(config)
    state = manager.create_run("low false positive collusion detection")
    state.gaps.append(_gap())
    state.search_rounds = _completed_rounds("initial")
    state.novelty_dossiers.append(
        NoveltyDossier(
            target_id="gap-1",
            idea_summary="low false positive collusion detection benchmark",
            verdict="pursue",
            novelty_strength="medium",
            confidence="medium",
        )
    )
    state.novelty_assessments.append(
        NoveltyAssessment(
            target_gap_or_hypothesis_id="gap-1",
            idea_summary="low false positive collusion detection benchmark",
            verdict="pursue",
            novelty_strength="medium",
            confidence="medium",
        )
    )
    manager.save_run(state)

    from gapforge.novelty.recall_gate import assess_run_prior_work_recall

    assessment = assess_run_prior_work_recall(config, state.run_id, gap_id="gap-1")
    reloaded = manager.load_run(state.run_id)

    assert not assessment.novelty_allowed
    assert "method_metric_search" in assessment.missing_required_searches
    assert "benchmark_dataset_search" in assessment.missing_required_searches
    assert reloaded.novelty_dossiers[0].verdict == "unknown"
    assert reloaded.novelty_dossiers[0].novelty_strength == "weak"
    assert "method_metric_search" in reloaded.novelty_dossiers[0].missing_searches


def test_duplicate_candidate_rejects_or_blocks_direction(tmp_path: Path) -> None:
    state = _state(tmp_path)
    state.gaps.append(_gap())
    state.search_rounds = _completed_rounds("initial", "novelty", "benchmark", "survey")
    state.papers.append(
        Paper(
            id="paper-1",
            title="Low false positive collusion detection benchmark",
            authors=["Ada"],
            abstract=(
                "We evaluate collusion detection in agents using monitoring calibration. "
                "The benchmark reports false positive FPR metrics, baselines, ablations, and evaluation results."
            ),
            year=2025,
        )
    )

    assessment = assess_prior_work_recall(state, target_id="gap-1")

    assert assessment.likely_duplicate
    assert not assessment.novelty_allowed
    assert assessment.top_prior_work_ids == ["paper-1"]
    assert any("paper-1" in issue for issue in assessment.blocking_issues)


def test_completed_required_searches_allow_medium_recall_when_no_duplicate_found(tmp_path: Path) -> None:
    state = _state(tmp_path)
    state.gaps.append(_gap())
    state.search_rounds = _completed_rounds("initial", "novelty", "benchmark", "survey")
    state.papers.append(
        Paper(
            id="paper-distant",
            title="A survey of unrelated robotics planning interfaces",
            authors=["Ada"],
            abstract="This survey studies planning interfaces and workflow tooling.",
            year=2024,
        )
    )

    assessment = assess_prior_work_recall(state, target_id="gap-1")

    assert assessment.missing_required_searches == []
    assert not assessment.likely_duplicate
    assert assessment.recall_confidence == "medium"
    assert assessment.novelty_allowed


def test_source_profile_and_available_context_change_required_rounds(tmp_path: Path) -> None:
    state = _state(tmp_path)

    generic_required = required_query_rounds(state, source_profile="generic")
    ai_safety_required = required_query_rounds(state, source_profile="ai_safety")
    state.citation_graph = CitationGraph(edges=[CitationEdge(source_paper_id="p1", target_paper_id="p2")])
    citation_required = required_query_rounds(state, source_profile="generic")

    assert "adjacent_field_search" not in generic_required
    assert "adjacent_field_search" in ai_safety_required
    assert "citation_neighborhood_search" in citation_required


def test_prior_work_recall_report_and_final_report_include_gate_status(tmp_path: Path) -> None:
    state = _state(tmp_path)
    state.gaps.append(_gap())
    state.search_strategies.append(SearchStrategy(id="strategy-1", topic=state.topic.text, source_profile="generic"))
    assessment = assess_prior_work_recall(state, target_id="gap-1")
    state.prior_work_recall_assessments.append(assessment)

    recall_report = render_prior_work_recall_report([assessment])
    final_report = render_markdown_report(build_final_report(state, strict=False))

    assert "# Prior Work Recall Gate" in recall_report
    assert "method_metric_search" in recall_report
    assert "10a. Prior-Work Recall Gate" in final_report
    assert "No prior-work recall assessments" not in final_report
