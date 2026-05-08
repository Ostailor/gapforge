from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from gapforge.config import GapForgeConfig
from gapforge.ideas import IdeaMutationEngine, IdeaStore
from gapforge.models import Provenance
from gapforge.project_memory import ProjectMemoryManager
from gapforge.state import utc_now_iso


def test_mutation_creates_new_candidate(tmp_path: Path) -> None:
    config, project_id = _project(tmp_path)
    store = IdeaStore(config)
    store.create_bank(project_id=project_id, root_topic="agent collusion monitoring")
    source = store.add_candidate(
        project_id=project_id,
        source_topic_id="topic-collusion",
        title="Monitor collusion in multi-agent traces",
        summary="Detect collusion with an unspecified method.",
        contribution_type="method",
        novelty_status="plausible",
        expected_metrics=["accuracy"],
    )

    result = IdeaMutationEngine(config).mutate_idea(source.id, strategy="metric_shift")
    state = store.load_state(project_id)

    assert result.candidate.id != source.id
    assert result.candidate.maturity == "seed"
    assert result.candidate.novelty_status == "unchecked"
    assert result.record.source_idea_id == source.id
    assert result.record.mutated_idea_id == result.candidate.id
    assert result.record.strategy == "metric_shift"
    assert result.record.what_changed
    assert result.record.required_new_searches
    assert any(candidate.id == result.candidate.id for candidate in state.candidates)


def test_rejected_idea_can_mutate(tmp_path: Path) -> None:
    config, project_id = _project(tmp_path)
    store = IdeaStore(config)
    store.create_bank(project_id=project_id, root_topic="agent collusion monitoring")
    source = store.add_candidate(
        project_id=project_id,
        source_topic_id="topic-collusion",
        title="Generic collusion method",
        summary="Too broad and method-centric.",
        contribution_type="method",
    )
    store.reject_candidate(source.id, "Too generic and under-specified.")

    results = IdeaMutationEngine(config).mutate_rejected_ideas(project_id)

    assert len(results) == 1
    assert results[0].candidate.maturity == "seed"
    assert results[0].record.strategy == "reviewer_objection_to_new_idea"
    assert "Too generic" in "; ".join(results[0].record.inherited_risks)


def test_mutation_preserves_inherited_risks(tmp_path: Path) -> None:
    config, project_id = _project(tmp_path)
    store = IdeaStore(config)
    store.create_bank(project_id=project_id, root_topic="agent collusion monitoring")
    source = store.add_candidate(
        project_id=project_id,
        source_topic_id="topic-collusion",
        title="Crowded collusion detector",
        summary="May overlap known detector papers.",
        contribution_type="method",
        closest_prior_work_ids=["paper-prior"],
        counterevidence_paper_ids=["paper-counter"],
        evidence_span_ids=["span-risk"],
        novelty_status="likely_duplicate",
        likely_failure_mode="Closest prior work may already solve the same problem.",
    )

    result = IdeaMutationEngine(config).mutate_idea(source.id, strategy="domain_transfer")

    assert result.candidate.closest_prior_work_ids == ["paper-prior"]
    assert result.candidate.counterevidence_paper_ids == ["paper-counter"]
    assert result.candidate.evidence_span_ids == ["span-risk"]
    inherited = "; ".join(result.record.inherited_risks)
    assert "paper-prior" in inherited
    assert "paper-counter" in inherited
    assert "span-risk" in inherited
    assert "Closest prior work" in result.candidate.likely_failure_mode


def test_fatal_prior_work_mutation_requires_decisive_change(tmp_path: Path) -> None:
    config, project_id = _project(tmp_path)
    store = IdeaStore(config)
    store.create_bank(project_id=project_id, root_topic="agent collusion monitoring")
    source = store.add_candidate(
        project_id=project_id,
        source_topic_id="topic-collusion",
        title="Duplicate detector idea",
        summary="A likely duplicate detector setup.",
        contribution_type="method",
        closest_prior_work_ids=["paper-fatal-prior"],
        novelty_status="likely_duplicate",
    )
    store.reject_candidate(source.id, "Fatal prior work overlap with paper-fatal-prior.")

    result = IdeaMutationEngine(config).mutate_idea(source.id, strategy="metric_shift")

    assert "Decisive overlapping dimension changed" in result.record.what_changed
    assert any("verify decisive overlap dimension changed" in search for search in result.record.required_new_searches)
    assert "paper-fatal-prior" in result.candidate.closest_prior_work_ids
    assert result.candidate.novelty_status != "strong"


def test_mutation_report_renders_and_cli_works(tmp_path: Path) -> None:
    config, project_id = _project(tmp_path)
    store = IdeaStore(config)
    store.create_bank(project_id=project_id, root_topic="agent collusion monitoring")
    source = store.add_candidate(
        project_id=project_id,
        source_topic_id="topic-collusion",
        title="CLI mutation source",
        summary="A source idea for mutation CLI.",
        contribution_type="method",
    )
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")}

    mutated = subprocess.run(
        [
            sys.executable,
            "-m",
            "gapforge.cli",
            "mutate-idea",
            "--idea-id",
            source.id,
            "--strategy",
            "method_to_benchmark",
        ],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert mutated.returncode == 0, mutated.stderr
    payload = json.loads(mutated.stdout)
    assert payload["record"]["strategy"] == "method_to_benchmark"
    assert payload["candidate"]["maturity"] == "seed"

    report = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "mutation-report", "--project-id", project_id],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert report.returncode == 0, report.stderr
    assert "# Idea Mutation Report" in report.stdout
    assert "method_to_benchmark" in report.stdout
    assert (config.project_root / project_id / "ideas" / "reports" / "mutations.md").exists()


def _project(tmp_path: Path) -> tuple[GapForgeConfig, str]:
    config = GapForgeConfig.from_cwd(tmp_path)
    manager = ProjectMemoryManager(config)
    program = manager.create_project("Idea Mutation Project")
    program.provenance.append(
        Provenance(
            created_by_skill="test",
            timestamp=utc_now_iso(),
            reasoning_summary="Test fixture project for idea mutation.",
        )
    )
    manager.save_project(program)
    return config, program.project.id
