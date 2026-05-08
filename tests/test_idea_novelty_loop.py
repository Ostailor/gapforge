from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from gapforge.config import GapForgeConfig
from gapforge.ideas import IdeaNoveltyLoop, IdeaStore
from gapforge.models import Paper, Provenance
from gapforge.project_memory import ProjectMemoryManager
from gapforge.state import ResearchStateManager, utc_now_iso

LOW_FPR_TOPIC = "low false-positive collusion detection in LLM multi-agent systems"


def test_duplicate_idea_is_rejected(tmp_path: Path) -> None:
    config, project_id = _project(tmp_path)
    candidate = _candidate(
        config,
        project_id,
        title="Low false-positive collusion auditing benchmark",
        contribution_type="benchmark",
    )
    _attach_run(
        config,
        project_id,
        [
            Paper(
                id="paper-duplicate",
                title="Low false-positive collusion auditing benchmark",
                authors=[],
                abstract=(
                    "This paper already solves the core idea by presenting a benchmark for low false-positive "
                    "collusion detection in multi-agent LLM systems with monitor baselines and FPR metrics."
                ),
                year=2026,
                source="fixture",
            )
        ],
    )

    assessment = IdeaNoveltyLoop(config).assess_idea(candidate.id)
    state = IdeaStore(config).load_state(project_id)
    loaded = next(item for item in state.candidates if item.id == candidate.id)

    assert assessment.verdict == "reject"
    assert assessment.closest_prior_work_ids == ["paper-duplicate"]
    assert assessment.required_mutation == "metric_shift"
    assert loaded.maturity == "rejected"
    assert loaded.novelty_status == "likely_duplicate"


def test_missing_searches_keep_novelty_unknown(tmp_path: Path) -> None:
    config, project_id = _project(tmp_path)
    candidate = _candidate(config, project_id)

    assessment = IdeaNoveltyLoop(config).assess_idea(candidate.id)
    loaded = next(item for item in IdeaStore(config).load_state(project_id).candidates if item.id == candidate.id)

    assert assessment.verdict == "unknown"
    assert assessment.novelty_strength == "unknown"
    assert "no attached runs" in " ".join(assessment.missing_searches)
    assert loaded.novelty_status == "unknown"


def test_plausible_idea_can_be_pursued_with_medium_strength(tmp_path: Path) -> None:
    config, project_id = _project(tmp_path)
    candidate = _candidate(
        config,
        project_id,
        title="Sequential low-FPR audit protocol for collusive LLM agents",
        contribution_type="evaluation_protocol",
    )
    _attach_run(
        config,
        project_id,
        [
            Paper(
                id="paper-related",
                title="Calibration metrics for single-agent monitor false positives",
                authors=[],
                abstract=(
                    "Studies false positive rate and specificity for monitor calibration in single-agent safety audits. "
                    "It does not evaluate sequential multi-agent collusion audits or collusive communication traces."
                ),
                year=2025,
                source="fixture",
            )
        ],
    )

    assessment = IdeaNoveltyLoop(config).assess_idea(candidate.id)
    loaded = next(item for item in IdeaStore(config).load_state(project_id).candidates if item.id == candidate.id)

    assert assessment.verdict == "pursue"
    assert assessment.novelty_strength == "medium"
    assert loaded.novelty_status == "plausible"
    assert "paper-related" in loaded.closest_prior_work_ids


def test_counterevidence_is_stored_and_lowers_verdict(tmp_path: Path) -> None:
    config, project_id = _project(tmp_path)
    candidate = _candidate(
        config,
        project_id,
        title="Low-FPR audit protocol for collusion monitors",
        contribution_type="evaluation_protocol",
    )
    _attach_run(
        config,
        project_id,
        [
            Paper(
                id="paper-counter",
                title="Counterevidence for low-FPR collusion monitor protocols",
                authors=[],
                abstract=(
                    "Counterevidence: an existing audit protocol already covers the same benchmark and subsumes "
                    "low false-positive collusion monitor evaluation under benign and collusive traces."
                ),
                year=2026,
                source="fixture",
            )
        ],
    )

    assessment = IdeaNoveltyLoop(config).find_counterevidence(candidate.id)
    state = IdeaStore(config).load_state(project_id)
    loaded = next(item for item in state.candidates if item.id == candidate.id)

    assert assessment.counterevidence
    assert assessment.verdict in {"reject", "revise"}
    assert loaded.novelty_status in {"likely_duplicate", "weak"}
    assert "paper-counter" in loaded.counterevidence_paper_ids
    assert any(link.link_type == "counters" and link.paper_id == "paper-counter" for link in state.evidence_links)


def test_mutation_recommendation_and_cli_render(tmp_path: Path) -> None:
    config, project_id = _project(tmp_path)
    candidate = _candidate(config, project_id, contribution_type="method")
    _attach_run(
        config,
        project_id,
        [
            Paper(
                id="paper-method-overlap",
                title="Low false-positive collusion detector for LLM agents",
                authors=[],
                abstract=(
                    "This detector already solves the core idea using monitor detection, FPR metrics, and multi-agent "
                    "collusion evaluation with baselines."
                ),
                year=2026,
                source="fixture",
            )
        ],
    )

    assessment = IdeaNoveltyLoop(config).assess_idea(candidate.id)
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")}
    cli = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "idea-novelty", "--idea-id", candidate.id],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert assessment.required_mutation == "method_to_measurement"
    assert cli.returncode == 0, cli.stderr
    assert json.loads(cli.stdout)["idea_id"] == candidate.id


def _project(tmp_path: Path) -> tuple[GapForgeConfig, str]:
    config = GapForgeConfig.from_cwd(tmp_path)
    manager = ProjectMemoryManager(config)
    program = manager.create_project("Idea Novelty Project")
    program.provenance.append(
        Provenance(
            created_by_skill="test",
            timestamp=utc_now_iso(),
            reasoning_summary="Test fixture project for idea novelty.",
        )
    )
    manager.save_project(program)
    return config, program.project.id


def _candidate(
    config: GapForgeConfig,
    project_id: str,
    *,
    title: str = "Low false-positive collusion detector for LLM agents",
    contribution_type: str = "benchmark",
) -> object:
    store = IdeaStore(config)
    store.create_bank(project_id=project_id, root_topic=LOW_FPR_TOPIC)
    return store.add_candidate(
        project_id=project_id,
        source_topic_id="topic-low-fpr",
        title=title,
        summary="Assess collusion monitors under strict false-positive constraints for benign and collusive multi-agent traces.",
        contribution_type=contribution_type,
        core_claim="A specificity-first framing can expose false-positive failures in collusion monitoring.",
        proposed_experiment="Compare monitor baselines on benign and collusive traces using FPR and recall metrics.",
        expected_baselines=["LLM judge monitor", "rule-based monitor"],
        expected_metrics=["false positive rate", "recall", "specificity"],
        novelty_status="unchecked",
        idea_yield_score=0.6,
    )


def _attach_run(config: GapForgeConfig, project_id: str, papers: list[Paper]) -> None:
    state_manager = ResearchStateManager(config)
    run = state_manager.create_run(LOW_FPR_TOPIC)
    run.papers = papers
    state_manager.save_run(run)
    ProjectMemoryManager(config).attach_run(project_id, run.run_id)
