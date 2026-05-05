from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from gapforge.config import GapForgeConfig
from gapforge.llm.base import LLMResponse
from gapforge.llm.config import LLMRuntimeConfig
from gapforge.models import (
    CitationEdge,
    CitationGraph,
    EvidenceSpan,
    Gap,
    Paper,
    PaperSection,
    SearchQueryRecord,
    SourceCoverageReport,
)
from gapforge.skills.novelty_gate import NoveltyGate
from gapforge.skills.novelty_gate_llm import NoveltyGateLLM
from gapforge.state import ResearchStateManager


def test_duplicate_idea_still_rejected_with_llm(tmp_path: Path) -> None:
    manager = ResearchStateManager(GapForgeConfig.from_cwd(tmp_path))
    state = _novelty_state(manager, duplicate=True, strong_prereqs=True)
    payload = _payload(
        prior="p-duplicate: False-positive calibrated collusion detector benchmark",
        verdict="reject",
        strength="weak",
        missing=[],
        evidence_locators=["p-duplicate:Evaluation:p3"],
    )

    NoveltyGateLLM(client=StaticJSONClient(payload), runtime_config=LLMRuntimeConfig(mode="fake")).assess(
        state,
        gap_id="gap-1",
        allow_deterministic_fallback=False,
    )

    assessment = state.novelty_assessments[0]
    assert assessment.verdict == "reject"
    assert assessment.novelty_strength == "weak"
    assert state.novelty_dossiers[0].top_prior_work


def test_llm_cannot_upgrade_unknown_to_strong_under_poor_coverage(tmp_path: Path) -> None:
    manager = ResearchStateManager(GapForgeConfig.from_cwd(tmp_path))
    state = _novelty_state(manager, duplicate=False)
    state.source_coverage = SourceCoverageReport(run_id=state.run_id, topic=state.topic.text, confidence="low")
    payload = _payload(verdict="pursue", strength="strong", missing=[])

    NoveltyGateLLM(client=StaticJSONClient(payload), runtime_config=LLMRuntimeConfig(mode="fake")).assess(
        state,
        gap_id="gap-1",
        fake=False,
        allow_deterministic_fallback=False,
    )

    assessment = state.novelty_assessments[0]
    assert assessment.novelty_strength != "strong"
    assert "medium-or-better source coverage" in assessment.missing_searches


def test_invalid_prior_work_id_is_rejected(tmp_path: Path) -> None:
    manager = ResearchStateManager(GapForgeConfig.from_cwd(tmp_path))
    state = _novelty_state(manager, duplicate=False)
    payload = _payload(prior="p-invented: Invented paper", verdict="pursue", strength="strong")

    NoveltyGateLLM(client=StaticJSONClient(payload), runtime_config=LLMRuntimeConfig(mode="fake")).assess(
        state,
        gap_id="gap-1",
        allow_deterministic_fallback=False,
    )

    dossier = state.novelty_dossiers[0]
    assert all("p-invented" not in item for item in dossier.top_prior_work)
    assert "invalid prior-work ID" in (Path(state.run_dir) / "novelty_gate_llm.md").read_text(encoding="utf-8")


def test_evidence_located_comparison_is_accepted(tmp_path: Path) -> None:
    manager = ResearchStateManager(GapForgeConfig.from_cwd(tmp_path))
    state = _novelty_state(manager, duplicate=False, strong_prereqs=True)
    payload = _payload(verdict="pursue", strength="strong", missing=[], evidence_locators=["p-related:Evaluation:p3"])

    NoveltyGateLLM(client=StaticJSONClient(payload), runtime_config=LLMRuntimeConfig(mode="fake")).assess(
        state,
        gap_id="gap-1",
        allow_deterministic_fallback=False,
    )

    dossier = state.novelty_dossiers[0]
    assert dossier.novelty_strength == "strong"
    assert dossier.comparison_table[0]["evidence_locators"] == ["p-related:Evaluation:p3"]
    assert dossier.evidence_spans[0].locator == "p-related:Evaluation:p3"


def test_deterministic_disagreement_becomes_contested(tmp_path: Path) -> None:
    manager = ResearchStateManager(GapForgeConfig.from_cwd(tmp_path))
    state = _novelty_state(manager, duplicate=True, strong_prereqs=True)
    NoveltyGate().run(state)
    payload = _payload(prior="p-duplicate: Duplicate benchmark", verdict="pursue", strength="strong", missing=[])

    NoveltyGateLLM(client=StaticJSONClient(payload), runtime_config=LLMRuntimeConfig(mode="fake")).assess(
        state,
        gap_id="gap-1",
        allow_deterministic_fallback=False,
    )

    dossier = state.novelty_dossiers[0]
    assert dossier.verdict == "revise"
    assert "Contested novelty comparison" in dossier.reviewer_objection
    assert any(claim.created_by_skill == "novelty-gate-llm" and claim.status == "contested" for claim in state.claims)


def test_novelty_check_llm_cli_dry_run_writes_prompt(tmp_path: Path) -> None:
    manager = ResearchStateManager(GapForgeConfig.from_cwd(tmp_path))
    state = _novelty_state(manager, duplicate=False)
    manager.save_run(state)
    env = {**os.environ, "GAPFORGE_DISABLE_NETWORK": "1", "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")}

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "gapforge.cli",
            "novelty-check-llm",
            "--run-id",
            state.run_id,
            "--gap-id",
            "gap-1",
            "--dry-run-prompts",
        ],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert (Path(state.run_dir) / "prompt_packs" / "novelty-gate-llm-gap-1.md").exists()
    assert (Path(state.run_dir) / "novelty_gate_llm.md").exists()


class StaticJSONClient:
    def __init__(self, payload: dict[str, Any]) -> None:
        self.payload = payload

    def complete(
        self,
        prompt: str,
        *,
        system: str = "",
        temperature: float = 0.0,
        max_tokens: int | None = None,
    ) -> LLMResponse:
        return LLMResponse(text=json.dumps(self.payload), model="static-novelty-test")

    def complete_json(
        self,
        prompt: str,
        *,
        schema_name: str,
        system: str = "",
        temperature: float = 0.0,
        max_tokens: int | None = None,
    ) -> dict[str, Any]:
        return self.payload


def _novelty_state(manager: ResearchStateManager, *, duplicate: bool, strong_prereqs: bool = False):
    state = manager.create_run("low false positive collusion detection")
    gap_title = "False-positive calibrated collusion detector benchmark" if duplicate else "Abstention-aware collusion detection"
    prior_id = "p-duplicate" if duplicate else "p-related"
    prior_title = (
        "False-positive calibrated collusion detector benchmark"
        if duplicate
        else "Calibrating probabilistic alerts in industrial monitoring"
    )
    state.gaps = [
        Gap(
            id="gap-1",
            title=gap_title,
            description=(
                "Build a false-positive calibrated collusion detector benchmark."
                if duplicate
                else "Evaluate collusion detection under fixed false-positive budgets."
            ),
            supporting_paper_ids=[prior_id],
            minimum_experiment_needed="" if duplicate else "Run a benchmark using fixed false-positive budgets.",
            risk_that_gap_is_fake="Closest prior work may already cover this.",
        )
    ]
    state.papers = [
        Paper(
            id=prior_id,
            title=prior_title,
            authors=["A"],
            abstract=(
                "We build a false-positive calibrated collusion detector benchmark."
                if duplicate
                else "We evaluate false positive budgets, precision, and recall for alert systems."
            ),
            year=2025,
            source="fixture",
        )
    ]
    state.paper_sections = [
        PaperSection(
            id=f"{prior_id}-evaluation",
            paper_id=prior_id,
            title="Evaluation",
            section_type="experiments",
            text="The benchmark evaluates false-positive budgets with precision and recall metrics.",
            page_start=3,
            page_end=3,
        )
    ]
    state.evidence_spans = [
        EvidenceSpan(
            id=f"span-{prior_id}",
            paper_id=prior_id,
            section_id=f"{prior_id}-evaluation",
            quote="The benchmark evaluates false-positive budgets with precision and recall metrics.",
            locator=f"{prior_id}:Evaluation:p3",
            evidence_type="result",
            confidence="high",
        )
    ]
    record = SearchQueryRecord(
        id="query-novelty",
        query=state.topic.text,
        source_names=["fixture"],
        purpose="novelty",
        max_results=10,
        result_paper_ids=[prior_id],
    )
    state.search_queries = [record]
    state.source_coverage = SourceCoverageReport(
        run_id=state.run_id,
        topic=state.topic.text,
        searched_sources=["fixture"],
        query_records=[record],
        papers_by_source={"fixture": 1},
        papers_with_full_text=[prior_id],
        confidence="medium" if strong_prereqs else "low",
    )
    if strong_prereqs:
        state.search_queries.append(
            SearchQueryRecord(
                id="query-citation",
                query="citation expansion",
                source_names=["fixture"],
                purpose="citation_expansion",
                max_results=10,
                result_paper_ids=[prior_id],
            )
        )
        state.citation_graph = CitationGraph(
            paper_ids=[prior_id],
            edges=[
                CitationEdge(
                    source_paper_id=prior_id,
                    target_paper_id=prior_id,
                    edge_type="related",
                    source="fixture",
                    confidence="medium",
                )
            ],
        )
    return state


def _payload(
    *,
    prior: str = "p-related: Calibrating probabilistic alerts in industrial monitoring",
    verdict: str = "pursue",
    strength: str = "medium",
    missing: list[str] | None = None,
    evidence_locators: list[str] | None = None,
) -> dict[str, Any]:
    paper_id = prior.split(":", 1)[0]
    return {
        "target_id": "gap-1",
        "closest_prior_work": [prior],
        "comparison_table": [
            {
                "paper_id": paper_id,
                "title": prior,
                "overall_similarity": 0.31,
                "problem_overlap": 0.4,
                "method_overlap": 0.2,
                "evaluation_overlap": 0.5,
                "what_overlaps": "False-positive budget evaluation.",
                "what_differs": "Collusion-specific deployment setting remains distinct.",
                "evidence_locators": evidence_locators or [],
            }
        ],
        "what_is_new": ["Collusion-specific fixed-FPR deployment evaluation."],
        "what_is_not_new": ["False-positive budget evaluation is related prior work."],
        "possible_reviewer_objection": "Reviewer may argue alert calibration already covers the evaluation idea.",
        "decisive_difference_needed": "Show the closest prior work does not test collusion detection.",
        "missing_searches": [] if missing is None else missing,
        "verdict": verdict,
        "novelty_strength": strength,
        "confidence": "medium",
        "reasoning_summary": "Public summary: compared against listed closest prior work only.",
    }
