from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from gapforge.config import GapForgeConfig
from gapforge.models import Paper
from gapforge.sources.health import check_source_health, check_sources
from gapforge.sources.live_diagnostics import run_live_source_diagnostic, write_live_source_diagnostic


class HealthySource:
    name = "arXiv"

    def search(self, query: str, *, max_results: int, sort: str, date_from: str | None, date_to: str | None):
        return [
            Paper(
                id="arxiv:1",
                title="Live paper",
                authors=["A"],
                abstract="A live-looking result.",
                year=2026,
                source=self.name,
                url="https://arxiv.org/abs/1234.5678",
            )
        ][:max_results]


class FailingSource:
    name = "OpenReview"

    def search(self, query: str, *, max_results: int, sort: str, date_from: str | None, date_to: str | None):
        raise RuntimeError("rate limited")


class FallbackSource:
    name = "Semantic Scholar"

    def search(self, query: str, *, max_results: int, sort: str, date_from: str | None, date_to: str | None):
        return [
            Paper(
                id="s2:fallback",
                title="Fallback",
                authors=[],
                abstract="Fallback metadata.",
                year=2024,
                source=self.name,
                raw_metadata={"fallback": True},
            )
        ][:max_results]


def test_source_health_offline_reports_disabled(monkeypatch) -> None:
    monkeypatch.setenv("GAPFORGE_DISABLE_NETWORK", "1")

    check = check_source_health(HealthySource(), test_query="test")

    assert check.status == "disabled"
    assert "Network disabled" in check.warning
    assert check.result_count == 0


def test_mocked_healthy_source_passes(monkeypatch) -> None:
    monkeypatch.delenv("GAPFORGE_DISABLE_NETWORK", raising=False)

    check = check_source_health(HealthySource(), test_query="test")

    assert check.status == "healthy"
    assert check.result_count == 1
    assert check.error == ""


def test_mocked_failing_source_reports_unavailable(monkeypatch) -> None:
    monkeypatch.delenv("GAPFORGE_DISABLE_NETWORK", raising=False)

    check = check_source_health(FailingSource(), test_query="test")

    assert check.status == "unavailable"
    assert "rate limited" in check.error


def test_fallback_only_source_is_degraded(monkeypatch) -> None:
    monkeypatch.delenv("GAPFORGE_DISABLE_NETWORK", raising=False)

    check = check_source_health(FallbackSource(), test_query="test")

    assert check.status == "degraded"
    assert "fallback" in check.warning.lower()


def test_live_diagnostic_identifies_insufficient_coverage(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.delenv("GAPFORGE_DISABLE_NETWORK", raising=False)
    config = GapForgeConfig.from_cwd(tmp_path)

    diagnostic = run_live_source_diagnostic(
        config,
        topic="low false positive collusion detection",
        source_profile="ai_safety",
        sources=[HealthySource(), FailingSource(), FallbackSource()],
    )

    assert diagnostic.minimum_coverage_met is False
    assert "arXiv" in diagnostic.usable_sources
    assert "OpenReview" in diagnostic.unavailable_sources
    assert "Semantic Scholar" in diagnostic.degraded_sources
    assert any("Required source OpenReview is unavailable" in issue for issue in diagnostic.blocking_issues)
    assert any("Required source Semantic Scholar is degraded" in issue for issue in diagnostic.blocking_issues)


def test_live_diagnostic_writes_ignored_artifacts(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.delenv("GAPFORGE_DISABLE_NETWORK", raising=False)
    config = GapForgeConfig.from_cwd(tmp_path)
    diagnostic = run_live_source_diagnostic(config, topic="x", source_profile="generic", sources=[HealthySource(), FallbackSource()])

    json_path, md_path = write_live_source_diagnostic(config, diagnostic)

    assert Path(json_path).exists()
    assert Path(md_path).exists()
    assert json.loads(Path(json_path).read_text(encoding="utf-8"))["topic"] == "x"


def test_source_health_cli_offline_no_live_api(tmp_path: Path) -> None:
    env = {"PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src"), "GAPFORGE_DISABLE_NETWORK": "1"}

    result = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "source-health", "--source", "arxiv", "--topic", "test"],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "disabled" in result.stdout


def test_check_sources_unknown_source_reports_unavailable(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.delenv("GAPFORGE_DISABLE_NETWORK", raising=False)

    checks = check_sources(GapForgeConfig.from_cwd(tmp_path), source_name="pubmed", test_query="test", sources=[HealthySource()])

    assert checks[0].source_name == "PubMed"
    assert checks[0].status == "unavailable"
    assert "No GapForge connector" in checks[0].error
