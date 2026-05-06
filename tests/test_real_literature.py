from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from gapforge.config import GapForgeConfig
from gapforge.models import Paper
from gapforge.real_literature import (
    RealLiteratureCampaignManager,
    build_real_campaign_dry_run,
    default_real_literature_profiles,
    render_real_campaign_dry_run,
)


class HealthySemanticScholar:
    name = "Semantic Scholar"

    def search(self, query: str, *, max_results: int, sort: str, date_from: str | None, date_to: str | None):
        return [
            Paper(
                id=f"s2:{index}",
                title=f"Live paper {index}",
                authors=["A"],
                abstract="Live-looking metadata.",
                year=2025,
                source=self.name,
            )
            for index in range(max_results)
        ]


class FallbackSemanticScholar:
    name = "Semantic Scholar"

    def search(self, query: str, *, max_results: int, sort: str, date_from: str | None, date_to: str | None):
        return [
            Paper(
                id=f"s2:fallback:{index}",
                title=f"Fallback paper {index}",
                authors=[],
                abstract="Fallback metadata.",
                year=2024,
                source=self.name,
                raw_metadata={"fallback": True},
            )
            for index in range(max_results)
        ]


class EmptySemanticScholar:
    name = "Semantic Scholar"

    def search(self, query: str, *, max_results: int, sort: str, date_from: str | None, date_to: str | None):
        return []


def test_real_literature_profile_listing_works() -> None:
    profiles = default_real_literature_profiles()

    assert {profile.id for profile in profiles} >= {
        "live_low_fpr_collusion",
        "live_llm_monitor_evasion",
        "live_multi_agent_covert_channels",
        "live_specificity_cross_domain",
        "live_undercovered_refusal",
    }


def test_offline_profile_refuses_live_validation(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("GAPFORGE_DISABLE_NETWORK", "1")

    record = RealLiteratureCampaignManager(GapForgeConfig.from_cwd(tmp_path)).run(
        "live_undercovered_refusal", sources=[HealthySemanticScholar()]
    )

    assert record.accepted is False
    assert "Live source diagnostics did not run" in record.rejection_reason


def test_mocked_live_campaign_creates_record(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.delenv("GAPFORGE_DISABLE_NETWORK", raising=False)
    manager = RealLiteratureCampaignManager(GapForgeConfig.from_cwd(tmp_path))

    record = manager.run("live_undercovered_refusal", sources=[HealthySemanticScholar()])
    loaded = manager.load_record(record.id)

    assert loaded.id == record.id
    assert loaded.project_id
    assert loaded.campaign_id
    assert loaded.live_source_diagnostic_id
    assert loaded.real_paper_count == 3


def test_fallback_heavy_campaign_fails(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.delenv("GAPFORGE_DISABLE_NETWORK", raising=False)

    record = RealLiteratureCampaignManager(GapForgeConfig.from_cwd(tmp_path)).run(
        "live_undercovered_refusal", sources=[FallbackSemanticScholar()]
    )

    assert record.accepted is False
    assert "fallback" in record.rejection_reason.lower()


def test_undercovered_refusal_can_pass(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.delenv("GAPFORGE_DISABLE_NETWORK", raising=False)

    record = RealLiteratureCampaignManager(GapForgeConfig.from_cwd(tmp_path)).run(
        "live_undercovered_refusal", sources=[EmptySemanticScholar()]
    )

    assert record.accepted is True
    assert record.rejection_reason == ""


def test_real_literature_cli_profiles(tmp_path: Path) -> None:
    env = {"PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src"), "GAPFORGE_DISABLE_NETWORK": "1"}

    result = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "real-literature-profiles"],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "live_low_fpr_collusion" in result.stdout


def test_real_literature_status_loads_record(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("GAPFORGE_DISABLE_NETWORK", "1")
    manager = RealLiteratureCampaignManager(GapForgeConfig.from_cwd(tmp_path))
    record = manager.run("live_undercovered_refusal", sources=[HealthySemanticScholar()])

    raw = json.loads((tmp_path / "data" / "real_literature" / record.id / "record.json").read_text(encoding="utf-8"))

    assert raw["id"] == record.id
    assert manager.load_record(record.id).profile_id == "live_undercovered_refusal"


def test_real_campaign_dry_run_renders_profile_plan(tmp_path: Path) -> None:
    plan = build_real_campaign_dry_run(GapForgeConfig.from_cwd(tmp_path), profile_id="live_low_fpr_collusion")
    rendered = render_real_campaign_dry_run(plan)

    assert plan.profile_id == "live_low_fpr_collusion"
    assert "Expected Source Checks" in rendered
    assert "Planned Search Rounds" in rendered
    assert "Expected Codex Tasks" in rendered
    assert "Estimated Budget" in rendered
    assert "What Counts As Acceptance" in rendered
    assert any(round_item["round_type"] == "novelty" for round_item in plan.planned_search_rounds)


def test_real_campaign_dry_run_offline_mode_shows_live_source_blocker(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("GAPFORGE_DISABLE_NETWORK", "1")

    plan = build_real_campaign_dry_run(GapForgeConfig.from_cwd(tmp_path), profile_id="live_low_fpr_collusion")

    assert any("GAPFORGE_DISABLE_NETWORK=1" in blocker for blocker in plan.likely_blockers)


def test_real_campaign_dry_run_custom_topic_has_budget_estimates(tmp_path: Path) -> None:
    plan = build_real_campaign_dry_run(
        GapForgeConfig.from_cwd(tmp_path),
        topic="low false positive collusion detection",
        source_profile="ai_safety",
    )

    assert plan.profile_id.startswith("custom_")
    assert plan.budget_estimate.max_papers > 0
    assert plan.budget_estimate.planned_search_rounds >= 4
    assert plan.budget_estimate.planned_search_queries > 0
    assert plan.commands_to_run


def test_real_campaign_dry_run_cli_writes_report(tmp_path: Path) -> None:
    env = {"PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src"), "GAPFORGE_DISABLE_NETWORK": "1"}

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "gapforge.cli",
            "real-campaign-dry-run",
            "--profile",
            "live_low_fpr_collusion",
            "--write-report",
        ],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "Real Campaign Dry Run" in result.stdout
    assert "GAPFORGE_DISABLE_NETWORK=1" in result.stdout
    assert (tmp_path / "data" / "real_literature" / "dry_runs" / "latest.md").exists()
