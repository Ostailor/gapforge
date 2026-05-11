from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


V24_DOCS = [
    "README.md",
    "docs/V2_4_ROADMAP.md",
    "docs/V2_4_RELATED_WORK_COMPLETION.md",
    "docs/V2_4_PUBLICATION_REMEDIATION.md",
    "docs/V2_4_ACCEPTANCE_CRITERIA.md",
    "docs/KNOWN_LIMITATIONS.md",
    "docs/RELEASE_PROCESS.md",
]

V24_SKILLS = [
    "skills/selected-related-work-search/SKILL.md",
    "skills/related-work-curation/SKILL.md",
    "skills/prior-work-dossier-refresh/SKILL.md",
    "skills/contribution-positioning/SKILL.md",
    "skills/publication-review-rerun/SKILL.md",
]


def test_v24_docs_expose_dashboard_api_and_no_overclaiming() -> None:
    combined = "\n".join((REPO_ROOT / path).read_text(encoding="utf-8") for path in V24_DOCS).lower()

    required_phrases = [
        "v2.3 synthetic main benchmark completed",
        "publication readiness remained blocked",
        "gapforge dashboard --project-id <selected-project-id> --include-selected-v24",
        "plan_selected_related_work_search",
        "run_selected_related_work_search",
        "revise_selected_manuscript_related_work",
        "fallback-only records do not count",
        "no fake citation",
        "no publication-ready claim",
        "synthetic evidence is not deployment validity",
    ]

    for phrase in required_phrases:
        assert phrase in combined


def test_v24_skill_docs_preserve_related_work_and_publication_discipline() -> None:
    for path_text in V24_SKILLS:
        path = REPO_ROOT / path_text
        text = path.read_text(encoding="utf-8")
        lower = text.lower()

        assert text.startswith("---\nname:")
        assert "description: Use when" in text
        assert "v2.4" in lower
        assert "real paper" in lower
        assert "fallback-only" in lower
        assert "no fake citation" in lower
        assert "synthetic" in lower
        assert "publication-ready" in lower
