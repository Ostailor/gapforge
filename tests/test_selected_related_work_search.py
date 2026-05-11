from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from test_selected_benchmark import _env, _selected_project

from gapforge.config import GapForgeConfig
from gapforge.models import Paper
from gapforge.selected_benchmark import SelectedBenchmarkManager
from gapforge.selected_benchmark.related_work import REQUIRED_RELATED_WORK_CATEGORIES
from gapforge.selected_benchmark.related_work_completion import RelatedWorkCompletionManager
from gapforge.selected_benchmark.related_work_search import (
    RequiredRelatedWorkSearchManager,
    render_required_related_work_search_report,
)


class RealLowFprSource:
    name = "arXiv"

    def search(self, query: str, *, max_results: int, sort: str, date_from: str | None, date_to: str | None):
        if "low false-positive" not in query and "low false positive" not in query:
            return []
        return [
            Paper(
                id="real-low-fpr",
                title="Low false positive specificity evaluation for detectors",
                authors=["A. Researcher"],
                abstract="Evaluates false alarm specificity and low false positive detector behavior.",
                year=2025,
                source=self.name,
                arxiv_id="2501.00001",
            )
        ][:max_results]


class FallbackLowFprSource:
    name = "arXiv"

    def search(self, query: str, *, max_results: int, sort: str, date_from: str | None, date_to: str | None):
        if "low false-positive" not in query and "low false positive" not in query:
            return []
        return [
            Paper(
                id="fallback-low-fpr",
                title="Fallback low false positive specificity evaluation",
                authors=[],
                abstract="Fallback metadata for false alarm specificity.",
                year=2025,
                source=self.name,
                raw_metadata={"fallback": True},
            )
        ][:max_results]


class FailingOpenReviewSource:
    name = "OpenReview"

    def search(self, query: str, *, max_results: int, sort: str, date_from: str | None, date_to: str | None):
        raise RuntimeError("source unavailable")


def test_search_plan_includes_all_required_categories(tmp_path: Path) -> None:
    config, _project_id, benchmark_id = _benchmark(tmp_path)

    campaign = RequiredRelatedWorkSearchManager(config).plan(benchmark_id)

    assert campaign.required_categories == REQUIRED_RELATED_WORK_CATEGORIES
    assert campaign.status == "planned"
    assert len(campaign.search_round_ids) == len(REQUIRED_RELATED_WORK_CATEGORIES)


def test_fallback_only_results_do_not_complete_category(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.delenv("GAPFORGE_DISABLE_NETWORK", raising=False)
    config, _project_id, benchmark_id = _benchmark(tmp_path)

    campaign = RequiredRelatedWorkSearchManager(config, sources=[FallbackLowFprSource()]).run(benchmark_id)
    category = campaign.category_searches["low-FPR detection/evaluation"]

    assert category.status == "partial"
    assert category.accepted_paper_ids == []
    assert category.fallback_paper_ids == ["fallback-low-fpr"]
    assert "fallback-only" in (category.failure_reason or "")


def test_real_paper_fixture_completes_category(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.delenv("GAPFORGE_DISABLE_NETWORK", raising=False)
    config, _project_id, benchmark_id = _benchmark(tmp_path)

    campaign = RequiredRelatedWorkSearchManager(config, sources=[RealLowFprSource()]).run(benchmark_id)
    category = campaign.category_searches["low-FPR detection/evaluation"]

    assert category.status == "complete"
    assert category.accepted_paper_ids == ["real-low-fpr"]
    assert category.result_paper_ids == ["real-low-fpr"]
    assert category.fallback_paper_ids == []

    completion = RelatedWorkCompletionManager(config).complete(benchmark_id)
    assert completion.category_statuses["low-FPR detection/evaluation"].status == "complete"


def test_missing_source_produces_blocker(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.delenv("GAPFORGE_DISABLE_NETWORK", raising=False)
    config, _project_id, benchmark_id = _benchmark(tmp_path)

    campaign = RequiredRelatedWorkSearchManager(config, sources=[FailingOpenReviewSource()]).run(benchmark_id)
    category = campaign.category_searches["low-FPR detection/evaluation"]

    assert category.status == "missing"
    assert "source unavailable" in (category.failure_reason or "").lower()
    assert any("selected-related-work-search-run" in command for command in campaign.next_commands)


def test_search_report_renders_and_cli_status(tmp_path: Path) -> None:
    config, _project_id, benchmark_id = _benchmark(tmp_path)
    manager = RequiredRelatedWorkSearchManager(config)
    campaign = manager.plan(benchmark_id)

    rendered = render_required_related_work_search_report(campaign)

    assert "# Required Related-Work Search Campaign" in rendered
    assert "low-FPR detection/evaluation" in rendered
    assert "Next Commands" in rendered

    cli = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "selected-related-work-search-status", "--benchmark-id", benchmark_id],
        cwd=tmp_path,
        env=_env(),
        text=True,
        capture_output=True,
        check=False,
    )

    assert cli.returncode == 0, cli.stderr
    assert "Required Related-Work Search Campaign" in cli.stdout


def _benchmark(tmp_path: Path) -> tuple[GapForgeConfig, str, str]:
    config, selected_project_id = _selected_project(tmp_path)
    spec = SelectedBenchmarkManager(config).create_spec(selected_project_id)
    return config, selected_project_id, spec.id
