from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from test_release_gate_v26 import _v26_fixture, _write_json

from gapforge.config import GapForgeConfig
from gapforge.release_gate.v27 import V27ReleaseGateEnforcer, render_v27_release_gate_markdown


def test_v27_conference_candidate_requires_all_hardening_artifacts_and_cli(tmp_path: Path) -> None:
    config = _v27_fixture(tmp_path)
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")}

    result = V27ReleaseGateEnforcer(config).evaluate()
    rendered = render_v27_release_gate_markdown(result)
    cli = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "v27-release-gate", "--write-report", "--json"],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.passed is True
    assert result.status == "conference_candidate"
    assert result.requirements["v26_gate_passes"] is True
    assert result.requirements["paper_quality_above_threshold"] is True
    assert result.requirements["external_review_captured_or_explicitly_unavailable"] is True
    assert "GapForge v2.7 Conference-Candidate Gate" in rendered
    assert cli.returncode == 0, cli.stderr
    assert json.loads(cli.stdout)["status"] == "conference_candidate"
    assert (tmp_path / "data" / "release_gate" / "v27_release_gate_latest.json").exists()


def test_v27_workshop_candidate_when_v26_passes_but_paper_quality_not_conference(tmp_path: Path) -> None:
    config = _v27_fixture(tmp_path, package_status="workshop_candidate", likely_decision="revise_before_submission")

    result = V27ReleaseGateEnforcer(config).evaluate()

    assert result.passed is True
    assert result.status == "workshop_candidate"
    assert result.requirements["v26_gate_passes"] is True
    assert result.requirements["paper_quality_above_threshold"] is False
    assert any("paper-quality" in blocker.lower() for blocker in result.blockers)


def test_v27_revise_for_reviews_when_fatal_review_issue_open(tmp_path: Path) -> None:
    config = _v27_fixture(tmp_path, open_fatal_issue=True)

    result = V27ReleaseGateEnforcer(config).evaluate()

    assert result.passed is False
    assert result.status == "revise_for_reviews"
    assert result.requirements["review_issue_tracker_has_no_open_fatal_issues"] is False
    assert any("open fatal" in blocker.lower() for blocker in result.blockers)


def test_v27_no_go_for_fake_citation_or_hidden_fatal(tmp_path: Path) -> None:
    config = _v27_fixture(tmp_path, fake_citation=True)

    result = V27ReleaseGateEnforcer(config).evaluate()

    assert result.passed is False
    assert result.status == "no_go"
    assert result.requirements["no_fake_citations_results_copied_prose"] is False
    assert any("fake" in blocker.lower() for blocker in result.blockers)


def test_v27_external_review_missing_blocks_conference_but_not_hidden(tmp_path: Path) -> None:
    config = _v27_fixture(tmp_path, external_review=False)

    result = V27ReleaseGateEnforcer(config).evaluate()

    assert result.status == "revise_for_reviews"
    assert result.requirements["external_review_captured_or_explicitly_unavailable"] is False
    assert any("external review" in blocker.lower() for blocker in result.blockers)


def _v27_fixture(
    tmp_path: Path,
    *,
    package_status: str = "conference_candidate",
    likely_decision: str = "accept_likely",
    open_fatal_issue: bool = False,
    fake_citation: bool = False,
    external_review: bool = True,
) -> GapForgeConfig:
    config = _v26_fixture(
        tmp_path,
        package_status=package_status,
        likely_decision=likely_decision,
        adapter_support="primary",
        fake_citation=fake_citation,
    )
    project_root = next((tmp_path / "projects").glob("*"))
    benchmark_dir = project_root / "selected_benchmark"
    manuscript_root = project_root / "manuscripts" / "manuscript-v26-fixture"
    _write_benchmark_fit_hardening(benchmark_dir)
    _write_ablation_run(benchmark_dir)
    _write_top_conference_revision(manuscript_root)
    _write_traceability(manuscript_root)
    if open_fatal_issue:
        _write_json(
            manuscript_root / "reviews" / "drastic" / "review_issues.json",
            {
                "manuscript_id": "manuscript-v26-fixture",
                "issues": [
                    {
                        "id": "review-issue-v27-open",
                        "source_review_id": "drastic-review-v27:R1",
                        "issue_type": "baseline_or_empirical",
                        "severity": "fatal",
                        "text": "fatal ablation issue remains open.",
                        "affected_sections": ["experiments"],
                        "required_fix": "artifact: add ablation support.",
                        "status": "open",
                        "resolution_evidence": [],
                        "provenance": {"created_by_skill": "test-fixture"},
                    }
                ],
            },
        )
    if external_review:
        _write_json(
            manuscript_root / "reviews" / "external" / "external_expert_reviews.json",
            {
                "manuscript_id": "manuscript-v26-fixture",
                "reviews": [
                    {
                        "id": "external-review-v27-human",
                        "manuscript_id": "manuscript-v26-fixture",
                        "reviewer_role": "external expert",
                        "expertise_area": "benchmark evaluation",
                        "overall_recommendation": "weak_accept",
                        "key_strengths": ["clear benchmark contribution"],
                        "key_weaknesses": [],
                        "missing_related_work": [],
                        "missing_experiments": [],
                        "claim_overreach": [],
                        "required_revisions": [],
                        "notes": ["human review captured"],
                        "provenance": {"created_by_skill": "external-expert-review-human"},
                    }
                ],
            },
        )
    return config


def _write_benchmark_fit_hardening(benchmark_dir: Path) -> None:
    output_dir = benchmark_dir / "benchmark_fit_hardening"
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "benchmark_fit_hardening_report.md").write_text(
        "# Benchmark Fit Hardening Report\n\nPrimary real benchmark grounding is available.\n",
        encoding="utf-8",
    )
    (output_dir / "no_fit_argument.md").write_text(
        "# Benchmark No-Fit Argument\n\nPartial no-fit limitations are documented.\n",
        encoding="utf-8",
    )


def _write_ablation_run(benchmark_dir: Path) -> None:
    _write_json(
        benchmark_dir / "ablations" / "selected_ablation_run.json",
        {
            "id": "selected-ablation-run-v27",
            "benchmark_id": "benchmark-v26-fixture",
            "plan_id": "selected-ablation-plan-v27",
            "required_ablation_types": [
                "threshold_calibration",
                "observability_mode",
                "hard_negative_subset",
                "collusion_type_subset",
                "monitor_family_comparison",
                "sequential_vs_non_sequential",
                "sample_size_sensitivity",
                "alpha_sensitivity",
            ],
            "results": [],
            "synthetic": True,
            "missing_ablation_types": [],
            "reviewer_blockers": [],
            "strong_claim_allowed": True,
            "manuscript_insertion_text": "Synthetic ablations are complete and caveated.",
            "provenance": {"created_by_skill": "test-fixture"},
        },
    )


def _write_top_conference_revision(manuscript_root: Path) -> None:
    _write_json(
        manuscript_root / "submission" / "top_conference_revision" / "top_conference_revision_report.json",
        {
            "id": "top-conference-revision-v27",
            "manuscript_id": "manuscript-v26-fixture",
            "benchmark_id": "benchmark-v26-fixture",
            "venue_profile_id": "generic_ml_conference",
            "style_profile_id": "venue-style-generic-ml-conference",
            "status": "revision_ready",
            "revised_sections": [],
            "evidence_inputs": {},
            "paper_quality_score": 0.8,
            "review_issue_count": 1,
            "open_review_issue_count": 0,
            "claim_traceability_passed": True,
            "limitations_preserved": True,
            "plagiarism_safe": True,
            "unsupported_claims_added": False,
            "blockers": [],
            "warnings": [],
            "provenance": {"created_by_skill": "test-fixture"},
        },
    )
    _write_json(
        manuscript_root / "submission" / "top_conference_revision" / "top_conference_readiness.json",
        {
            "id": "top-conference-readiness-v27",
            "manuscript_id": "manuscript-v26-fixture",
            "benchmark_id": "benchmark-v26-fixture",
            "status": "conference_candidate",
            "conference_candidate_allowed": True,
            "claim_traceability_passed": True,
            "paper_quality_score": 0.8,
            "paper_quality_top_ready": True,
            "ablation_strong_claim_allowed": True,
            "benchmark_fit_available": True,
            "limitations_visible": True,
            "blockers": [],
            "warnings": [],
            "provenance": {"created_by_skill": "test-fixture"},
        },
    )


def _write_traceability(manuscript_root: Path) -> None:
    _write_json(
        manuscript_root / "submission" / "traceability_report.json",
        {
            "manuscript_id": "manuscript-v26-fixture",
            "claim_count": 1,
            "supported_claim_count": 1,
            "unsupported_claim_count": 0,
            "empirical_claim_count": 0,
            "novelty_claim_count": 0,
            "limitation_claim_count": 1,
            "unsupported_claims": [],
            "overclaim_warnings": [],
            "blocking_issues": [],
            "provenance": {"created_by_skill": "test-fixture"},
        },
    )
