from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


V25_DOCS = [
    "README.md",
    "docs/V2_5_ROADMAP.md",
    "docs/V2_5_REAL_BENCHMARK_GROUNDING.md",
    "docs/V2_5_VENUE_STYLE_MANUSCRIPT.md",
    "docs/V2_5_OPENREVIEW_REVIEWER_DATASET.md",
    "docs/V2_5_ACCEPTANCE_CRITERIA.md",
]

V25_SKILLS = [
    "skills/vetted-benchmark-mapping/SKILL.md",
    "skills/benchmark-adapter/SKILL.md",
    "skills/venue-style-analysis/SKILL.md",
    "skills/openreview-review-dataset/SKILL.md",
    "skills/drastic-reviewer/SKILL.md",
    "skills/drastic-revision/SKILL.md",
]


def test_v25_docs_expose_dashboard_api_and_safety_boundaries() -> None:
    combined = "\n".join((REPO_ROOT / path).read_text(encoding="utf-8") for path in V25_DOCS).lower()

    required_phrases = [
        "gapforge dashboard --project-id <selected-project-id> --include-selected-v25",
        "vetted_benchmarks.html",
        "benchmark_mappings.html",
        "benchmark_adapters.html",
        "venue_profiles.html",
        "style_corpus.html",
        "venue_style_analysis.html",
        "openreview_dataset.html",
        "review_taxonomy.html",
        "reviewer_calibration.html",
        "drastic_review.html",
        "drastic_revision.html",
        "v25_release_gate.html",
        "register_vetted_benchmark",
        "assess_benchmark_fit",
        "create_benchmark_adapter",
        "run_vetted_experiment",
        "select_venue_profile",
        "ingest_style_corpus",
        "analyze_venue_style",
        "rewrite_manuscript_for_venue",
        "create_review_dataset",
        "train_reviewer",
        "evaluate_reviewer",
        "run_drastic_review",
        "create_drastic_revision_plan",
        "v25_release_gate",
        "no-plagiarism",
        "no-fake-citation",
        "no-fake-result",
        "no-fake-review",
        "critique calibration",
        "known datasets do not prove benchmark validity",
        "venue style is structure",
    ]

    for phrase in required_phrases:
        assert phrase in combined


def test_v25_skill_docs_preserve_evidence_discipline() -> None:
    for path_text in V25_SKILLS:
        path = REPO_ROOT / path_text
        text = path.read_text(encoding="utf-8")
        lower = text.lower()

        assert text.startswith("---\nname:")
        assert "description: Use when" in text
        assert "v2.5" in lower
        assert "no fake citation" in lower
        assert "fake result" in lower
        assert "evidence" in lower
        assert "claim" in lower

    combined = "\n".join((REPO_ROOT / path).read_text(encoding="utf-8").lower() for path in V25_SKILLS)
    assert "copied prose" in combined
    assert "fake review" in combined
    assert "vetted status is not fit" in combined
    assert "critique, not a venue decision" in combined
