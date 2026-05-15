from __future__ import annotations

from pathlib import Path

from gapforge import api

REPO_ROOT = Path(__file__).resolve().parents[1]


V26_DOCS = [
    "README.md",
    "docs/V2_6_ROADMAP.md",
    "docs/V2_6_DRASTIC_REVIEW_REMEDIATION.md",
    "docs/V2_6_REAL_BENCHMARK_UPGRADE.md",
    "docs/V2_6_ACCEPTANCE_CRITERIA.md",
]

V26_API_NAMES = [
    "load_selected_related_work_matrix",
    "repair_selected_related_work_matrix",
    "load_selected_artifact_package",
    "repair_selected_artifact_package",
    "search_real_benchmark_candidates",
    "assess_real_benchmark_adapter",
    "run_real_benchmark_experiment",
    "integrate_venue_artifacts",
    "rerun_drastic_review",
    "create_venue_revision_package",
    "v26_release_gate",
]

V26_DASHBOARD_PAGES = [
    "matrix_loader.html",
    "artifact_package_loader.html",
    "real_benchmark_search.html",
    "real_benchmark_adapter.html",
    "real_benchmark_experiment.html",
    "venue_artifact_integration.html",
    "drastic_review_rerun.html",
    "venue_revision_package.html",
    "v26_release_gate.html",
]

V26_SKILLS = [
    "skills/matrix-recovery/SKILL.md",
    "skills/artifact-package-repair/SKILL.md",
    "skills/real-benchmark-search/SKILL.md",
    "skills/drastic-review-rerun/SKILL.md",
    "skills/venue-revision-package/SKILL.md",
]


def test_v26_docs_expose_dashboard_api_and_blocker_boundaries() -> None:
    combined = "\n".join((REPO_ROOT / path).read_text(encoding="utf-8") for path in V26_DOCS).lower()

    required_phrases = [
        "gapforge dashboard --project-id <selected-project-id> --include-selected-v26",
        "missing:related_work_matrix",
        "missing:artifact_package",
        "benchmark_no_fit",
        "revise_for_reviews",
        "no_go",
        "camera-ready",
        "deployment validity",
        "synthetic fixture",
        "no fake citations",
        "no fake results",
    ]
    required_phrases.extend(V26_DASHBOARD_PAGES)
    required_phrases.extend(V26_API_NAMES)

    for phrase in required_phrases:
        assert phrase in combined


def test_v26_api_exports_scriptable_workflow() -> None:
    for name in V26_API_NAMES:
        assert hasattr(api, name)
        assert name in api.__all__


def test_v26_skill_docs_preserve_remediation_discipline() -> None:
    for path_text in V26_SKILLS:
        path = REPO_ROOT / path_text
        text = path.read_text(encoding="utf-8")
        lower = text.lower()

        assert text.startswith("---\nname:")
        assert "description: Use when" in text
        assert "v2.6" in lower
        assert "evidence" in lower
        assert "claim" in lower or "readiness" in lower
        assert "fake" in lower or "invent" in lower

    combined = "\n".join((REPO_ROOT / path).read_text(encoding="utf-8").lower() for path in V26_SKILLS)
    assert "missing:related_work_matrix" in combined
    assert "missing:artifact_package" in combined
    assert "no-fit" in combined
    assert "camera-ready" in combined
