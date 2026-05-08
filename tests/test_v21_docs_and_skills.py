from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


V21_DOCS = [
    "README.md",
    "docs/V2_1_ROADMAP.md",
    "docs/V2_1_SELECTED_IDEA.md",
    "docs/V2_1_BENCHMARK_SPEC.md",
    "docs/V2_1_ACCEPTANCE_CRITERIA.md",
    "docs/KNOWN_LIMITATIONS.md",
    "docs/RELEASE_PROCESS.md",
]

V21_SKILLS = [
    "skills/selected-idea-project/SKILL.md",
    "skills/sequential-specificity-benchmark/SKILL.md",
    "skills/trace-generator/SKILL.md",
    "skills/sequential-audit-metrics/SKILL.md",
    "skills/monitor-baselines/SKILL.md",
    "skills/selected-benchmark-review/SKILL.md",
]


def test_v21_docs_state_maturity_and_nonclaims() -> None:
    combined = "\n".join((REPO_ROOT / path).read_text(encoding="utf-8") for path in V21_DOCS).lower()

    required_phrases = [
        "v2 found",
        "v2.1 executes",
        "synthetic smoke benchmark is not a final research result",
        "low-fpr claims require power",
        "benchmark validity limitations",
        "next steps toward pilot/main benchmark",
        "idea-sequential-specificity-benchmark-for-low-fpr-collusion-audits",
        "smoke versus pilot versus main",
    ]

    for phrase in required_phrases:
        assert phrase in combined


def test_v21_skill_docs_preserve_artifact_result_discipline() -> None:
    for path_text in V21_SKILLS:
        path = REPO_ROOT / path_text
        text = path.read_text(encoding="utf-8")
        lower = text.lower()

        assert text.startswith("---\nname:")
        assert "description: Use when" in text
        assert "synthetic smoke" in lower
        assert "not a final research result" in lower
        assert "low-fpr claims require power" in lower
        assert "artifact-backed" in lower
        assert "no fake results" in lower
