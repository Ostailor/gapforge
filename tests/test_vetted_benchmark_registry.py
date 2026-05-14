from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from gapforge.config import GapForgeConfig
from gapforge.project_memory import ProjectMemoryManager
from gapforge.vetted_benchmarks import VettedBenchmarkRegistry


def test_register_vetted_benchmark_and_render_card(tmp_path: Path) -> None:
    config = GapForgeConfig.from_cwd(tmp_path)
    registry = VettedBenchmarkRegistry(config)

    record = registry.register(
        name="Low-FPR Monitoring Benchmark",
        domain="multi-agent monitoring",
        source="public benchmark",
        source_url="https://example.org/benchmark",
        benchmark_type="benchmark",
        task_types=["sequential low-FPR collusion monitoring"],
        metric_ids=["false-positive-rate", "specificity"],
        license="CC-BY-4.0",
        terms_of_use="Public research use with attribution.",
        vetted_status="widely_used",
    )
    card = registry.render_card(record.id)
    records = registry.list()

    assert records[0].id == record.id
    assert record.vetted_status == "widely_used"
    assert "Low-FPR Monitoring Benchmark" in card
    assert "Benchmark license is not recorded" not in card
    assert "Grounding in this benchmark does not automatically validate the selected protocol" in card


def test_eligibility_assessment_recommends_fit_without_assuming_validity(tmp_path: Path) -> None:
    config = GapForgeConfig.from_cwd(tmp_path)
    registry = VettedBenchmarkRegistry(config)
    record = registry.register(
        name="Sequential Collusion Audit Benchmark",
        domain="multi-agent collusion monitoring",
        source_url="https://example.org/sequential-collusion-audit",
        benchmark_type="benchmark",
        task_types=["sequential audit", "monitor evasion"],
        metric_ids=["low-FPR specificity"],
        license="MIT",
        terms_of_use="Open research use.",
        vetted_status="canonical",
    )

    assessment = registry.assess_eligibility(
        benchmark_id=record.id,
        selected_idea_id="idea-sequential-specificity-benchmark-for-low-fpr-collusion-audits",
    )
    rendered = registry.render_eligibility(
        benchmark_id=record.id,
        selected_idea_id="idea-sequential-specificity-benchmark-for-low-fpr-collusion-audits",
    )

    assert assessment.can_support_low_fpr is True
    assert assessment.can_support_multi_agent_or_monitoring is True
    assert assessment.can_support_sequential_evaluation is True
    assert assessment.recommended_use == "primary"
    assert "does not automatically mean good fit" in rendered


def test_license_missing_warns(tmp_path: Path) -> None:
    config = GapForgeConfig.from_cwd(tmp_path)
    registry = VettedBenchmarkRegistry(config)
    record = registry.register(
        name="Unlicensed Public Benchmark",
        source_url="https://example.org/unlicensed",
        task_types=["classification"],
        vetted_status="emerging",
    )

    card = registry.render_card(record.id)
    assessment = registry.assess_eligibility(benchmark_id=record.id, selected_idea_id="idea-any")

    assert "Benchmark license is not recorded." in card
    assert "Benchmark terms of use are not recorded." in card
    assert "Benchmark license is not recorded." in assessment.blockers


def test_poor_fit_benchmark_is_not_recommended(tmp_path: Path) -> None:
    config = GapForgeConfig.from_cwd(tmp_path)
    registry = VettedBenchmarkRegistry(config)
    record = registry.register(
        name="Static Image Classification Benchmark",
        domain="computer vision",
        benchmark_type="dataset",
        task_types=["single image classification"],
        metric_ids=["accuracy"],
        license="CC0",
        terms_of_use="Public domain.",
        vetted_status="canonical",
    )

    assessment = registry.assess_eligibility(
        benchmark_id=record.id,
        selected_idea_id="idea-sequential-specificity-benchmark-for-low-fpr-collusion-audits",
    )

    assert assessment.recommended_use == "not_recommended"
    assert assessment.can_support_low_fpr is False
    assert assessment.can_support_multi_agent_or_monitoring is False
    assert assessment.can_support_sequential_evaluation is False
    assert any("Poor fit" in blocker for blocker in assessment.blockers)


def test_vetted_benchmark_cli_register_list_card_eligibility_report(tmp_path: Path) -> None:
    config = GapForgeConfig.from_cwd(tmp_path)
    project = ProjectMemoryManager(config).create_project("Vetted Benchmark Project")
    env = {
        **os.environ,
        "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src"),
        "GAPFORGE_ROOT": str(tmp_path),
    }

    registered = subprocess.run(
        [
            sys.executable,
            "-m",
            "gapforge.cli",
            "vetted-benchmark-register",
            "--name",
            "CLI Sequential Monitoring Benchmark",
            "--domain",
            "multi-agent monitoring",
            "--task-type",
            "sequential low-FPR monitoring",
            "--metric-id",
            "specificity",
            "--license",
            "CC-BY-4.0",
            "--terms-of-use",
            "Research use with attribution.",
            "--vetted-status",
            "widely_used",
        ],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert registered.returncode == 0, registered.stderr
    benchmark_id = json.loads(registered.stdout)["id"]

    card = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "vetted-benchmark-card", "--benchmark-id", benchmark_id],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    listing = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "vetted-benchmark-list"],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    eligibility = subprocess.run(
        [
            sys.executable,
            "-m",
            "gapforge.cli",
            "vetted-benchmark-eligibility",
            "--benchmark-id",
            benchmark_id,
            "--idea-id",
            "idea-sequential-specificity-benchmark-for-low-fpr-collusion-audits",
        ],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    report = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "vetted-benchmark-report", "--project-id", project.project.id],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert card.returncode == 0, card.stderr
    assert listing.returncode == 0, listing.stderr
    assert eligibility.returncode == 0, eligibility.stderr
    assert report.returncode == 0, report.stderr
    assert "CLI Sequential Monitoring Benchmark" in listing.stdout
    assert "Recommended use" in eligibility.stdout
    assert "Vetted Benchmark Grounding Report" in report.stdout
