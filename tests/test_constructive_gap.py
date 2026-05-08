from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from gapforge.campaigns import CampaignManager
from gapforge.config import GapForgeConfig
from gapforge.ideas import ConstructiveGapCandidate, ConstructiveGapGenerator, validate_constructive_gap_candidate
from gapforge.models import ProjectMemoryRecord, Provenance, RelatedWorkMatrix
from gapforge.project_memory import ProjectMemoryManager
from gapforge.state import utc_now_iso

LOW_FPR_TOPIC = "low false-positive collusion detection in LLM multi-agent systems"


def test_benchmark_candidate_generated(tmp_path: Path) -> None:
    config, project_id = _project(tmp_path)

    result = ConstructiveGapGenerator(config).generate_for_project(project_id)

    benchmark = next(candidate for candidate in result.candidates if candidate.contribution_type == "benchmark")
    assert "Benchmark" in benchmark.title
    assert benchmark.minimum_artifact
    assert "false positive rate" in benchmark.minimum_experiment
    assert benchmark.closest_prior_work_ids or any(link.startswith("missing_search:") for link in benchmark.evidence_links)


def test_measurement_candidate_generated(tmp_path: Path) -> None:
    config, project_id = _project(tmp_path)

    result = ConstructiveGapGenerator(config).generate_for_project(project_id)

    measurement = next(candidate for candidate in result.candidates if candidate.contribution_type == "measurement")
    assert "Measurement" in measurement.title
    assert "specificity" in measurement.minimum_experiment
    assert measurement.required_baselines


def test_negative_result_candidate_generated(tmp_path: Path) -> None:
    config, project_id = _project(tmp_path)

    result = ConstructiveGapGenerator(config).generate_for_project(project_id)

    negative = next(candidate for candidate in result.candidates if candidate.contribution_type == "negative_result")
    assert "Negative result" in negative.title
    assert "Falsifiable expectation" in negative.minimum_experiment
    assert "LLM judge" in ", ".join(negative.required_baselines)


def test_missing_minimum_artifact_blocks() -> None:
    candidate = ConstructiveGapCandidate(
        id="constructive-gap-invalid",
        project_id="project-invalid",
        title="Invalid benchmark",
        contribution_type="benchmark",
        problem="No artifact is specified.",
        why_existing_work_makes_this_useful="Existing work leaves a gap.",
        minimum_artifact="",
        minimum_experiment="Evaluate false positive rate and specificity.",
        required_baselines=["baseline"],
        evidence_links=["missing_search: invalid benchmark prior work"],
    )

    with pytest.raises(ValueError, match="minimum artifact"):
        validate_constructive_gap_candidate(candidate)


def test_constructive_gap_report_renders_and_cli_supports_campaign(tmp_path: Path) -> None:
    config, project_id = _project(tmp_path)
    campaign = CampaignManager(config).create_campaign(LOW_FPR_TOPIC, project_id=project_id)
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")}

    generated = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "constructive-gaps", "--campaign-id", campaign.campaign.id],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert generated.returncode == 0, generated.stderr
    payload = json.loads(generated.stdout)
    assert payload["project_id"] == project_id
    assert any(candidate["contribution_type"] == "benchmark" for candidate in payload["candidates"])

    report = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "constructive-gap-report", "--project-id", project_id],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert report.returncode == 0, report.stderr
    assert "# Constructive Gap Report" in report.stdout
    assert "Benchmark" in report.stdout
    assert "Negative Result" in report.stdout
    assert (config.project_root / project_id / "ideas" / "constructive_gaps.json").exists()
    assert (config.project_root / project_id / "ideas" / "reports" / "constructive_gaps.md").exists()


def _project(tmp_path: Path) -> tuple[GapForgeConfig, str]:
    config = GapForgeConfig.from_cwd(tmp_path)
    manager = ProjectMemoryManager(config)
    program = manager.create_project(LOW_FPR_TOPIC)
    program.memory_records.append(
        ProjectMemoryRecord(
            id="memory-low-fpr-gap",
            project_id=program.project.id,
            record_type="gap",
            text="Existing monitors under-report benign multi-agent false positives.",
            linked_paper_ids=["paper-monitor-a"],
            status="active",
        )
    )
    program.related_work_matrices.append(
        RelatedWorkMatrix(
            direction_id="direction-low-fpr",
            missing_categories=["low-FPR benchmark", "sequential evaluation protocol"],
            must_read_paper_ids=["paper-monitor-a"],
            baseline_paper_ids=["paper-baseline-b"],
        )
    )
    program.provenance.append(
        Provenance(
            created_by_skill="test",
            timestamp=utc_now_iso(),
            reasoning_summary="Test fixture project for constructive gap creation.",
        )
    )
    manager.save_project(program)
    return config, program.project.id
