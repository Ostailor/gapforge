from __future__ import annotations

import json
from pathlib import Path

from gapforge.config import GapForgeConfig
from gapforge.models import Claim, Evidence, ExperimentPlan, Gap, NoveltyAssessment, Paper, PaperNote, ResearchRunState
from gapforge.state import RUN_ARTIFACTS, ResearchStateManager


def test_create_run_writes_durable_format(tmp_path: Path) -> None:
    manager = ResearchStateManager(GapForgeConfig.from_cwd(tmp_path))

    state = manager.create_run("low false positive collusion detection")

    run_dir = Path(state.run_dir)
    assert run_dir.exists()
    for artifact in RUN_ARTIFACTS:
        assert (run_dir / artifact).exists(), artifact
    assert json.loads((run_dir / "config.json").read_text(encoding="utf-8"))["schema_version"] == 1


def test_save_and_load_state_round_trips(tmp_path: Path) -> None:
    manager = ResearchStateManager(GapForgeConfig.from_cwd(tmp_path))
    state = manager.create_run("calibrated collusion detection")
    paper = Paper(
        id="paper-1",
        title="A paper",
        authors=["A. Author"],
        year=2025,
        venue="TestConf",
        abstract="Abstract",
        url="https://example.test/paper-1",
        source="fixture",
    )
    manager.append_papers(state, [paper])

    loaded = manager.load_run(state.run_id)

    assert isinstance(loaded, ResearchRunState)
    assert loaded.run_id == state.run_id
    assert loaded.papers[0].id == "paper-1"


def test_validation_fails_on_unsupported_supported_claim(tmp_path: Path) -> None:
    manager = ResearchStateManager(GapForgeConfig.from_cwd(tmp_path))
    state = manager.create_run("claim validation")
    state.claims.append(
        Claim(
            id="claim-1",
            text="This claim is incorrectly marked supported.",
            type="background",
            status="supported",
            source_paper_ids=["paper-1"],
        )
    )

    result = manager.validate_state(state)

    assert not result.ok
    assert any(issue.code == "supported-claim-without-evidence" for issue in result.issues)


def test_validation_checks_gap_experiment_and_note_links(tmp_path: Path) -> None:
    manager = ResearchStateManager(GapForgeConfig.from_cwd(tmp_path))
    state = manager.create_run("link validation")
    state.paper_notes.append(PaperNote(paper_id="", summary="Missing ID"))
    state.gaps.append(Gap(id="gap-1", description="Gap", why_it_matters="Matter"))
    state.experiments.append(ExperimentPlan(id="experiment-1", hypothesis_id="missing", title="Experiment", design="Design"))

    result = manager.validate_state(state)
    codes = {issue.code for issue in result.issues}

    assert "paper-note-without-paper-id" in codes
    assert "gap-without-linked-papers-or-reason" in codes
    assert "experiment-without-hypothesis" in codes


def test_append_claims_and_validate_novelty_prior_work(tmp_path: Path) -> None:
    manager = ResearchStateManager(GapForgeConfig.from_cwd(tmp_path))
    state = manager.create_run("novelty validation")
    claim = Claim(
        id="claim-1",
        text="The proposed method is new.",
        type="novelty",
        status="uncertain",
        supporting_evidence=[Evidence(source_id="paper-1", quote="Prior title", locator="url")],
        source_paper_ids=["paper-1"],
    )

    manager.append_claims(state, [claim])
    result = manager.validate_state(state)

    assert not result.ok
    assert any(issue.code == "novelty-claim-without-prior-work" for issue in result.issues)


def test_validation_checks_strong_novelty_requires_prior_work(tmp_path: Path) -> None:
    manager = ResearchStateManager(GapForgeConfig.from_cwd(tmp_path))
    state = manager.create_run("strong novelty validation")
    state.novelty_assessments.append(
        NoveltyAssessment(
            target_gap_or_hypothesis_id="gap-1",
            idea_summary="A claimed strong idea",
            novelty_strength="strong",
            verdict="pursue",
        )
    )

    result = manager.validate_state(state)

    assert not result.ok
    assert any(issue.code == "strong-novelty-without-prior-work" for issue in result.issues)
