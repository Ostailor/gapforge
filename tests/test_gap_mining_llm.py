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
from gapforge.models import EvidenceSpan, Gap, HumanReviewRecord, Paper, PaperNote, PaperSection, SourceCoverageReport
from gapforge.skills.gap_mining_llm import GapMiningLLM
from gapforge.state import ResearchStateManager, utc_now_iso


def test_fake_output_does_not_create_unsupported_gaps(tmp_path: Path) -> None:
    manager = ResearchStateManager(GapForgeConfig.from_cwd(tmp_path))
    state = _gap_llm_state(manager)

    GapMiningLLM().mine_with_llm(state, fake=True)

    assert state.gaps == []
    assert state.gap_evidence_matrices == []
    assert (Path(state.run_dir) / "gap_mining_llm.md").exists()
    transcripts = json.loads((Path(state.run_dir) / "llm_transcripts.json").read_text(encoding="utf-8"))
    assert transcripts[0]["skill_name"] == "gap-mining-llm"


def test_valid_json_with_locators_creates_gap_matrix(tmp_path: Path) -> None:
    manager = ResearchStateManager(GapForgeConfig.from_cwd(tmp_path))
    state = _gap_llm_state(manager)

    GapMiningLLM(client=StaticJSONClient(_payload()), runtime_config=LLMRuntimeConfig(mode="fake")).mine_with_llm(
        state,
        allow_deterministic_fallback=False,
    )

    assert len(state.gaps) == 1
    gap = state.gaps[0]
    assert gap.title == "Deployment-shift false-positive evaluation is under-specified"
    assert gap.supporting_paper_ids == ["p1", "p2"]
    matrix = state.gap_evidence_matrices[0]
    assert matrix.gap_id == gap.id
    assert {"p1", "p2"} <= set(matrix.papers_supporting)
    assert any(row.locator == "p1:Limitations:p7" for row in matrix.evidence_rows)
    assert any(row.evidence_type == "counterevidence-search" for row in matrix.evidence_rows)
    assert any(claim.created_by_skill == "gap-mining-llm" for claim in state.claims)


def test_gap_without_counterevidence_search_is_downgraded(tmp_path: Path) -> None:
    manager = ResearchStateManager(GapForgeConfig.from_cwd(tmp_path))
    state = _gap_llm_state(manager)
    payload = _payload()
    payload["gaps"][0]["counterevidence_search_summary"] = ""
    payload["gaps"][0]["confidence"] = "high"

    GapMiningLLM(client=StaticJSONClient(payload), runtime_config=LLMRuntimeConfig(mode="fake")).mine_with_llm(
        state,
        allow_deterministic_fallback=False,
    )

    assert state.gaps[0].confidence == "low"
    assert "No counterevidence search summary" in state.gaps[0].risk_that_gap_is_fake


def test_abstract_only_gap_cannot_be_high_confidence(tmp_path: Path) -> None:
    manager = ResearchStateManager(GapForgeConfig.from_cwd(tmp_path))
    state = _gap_llm_state(manager)
    state.paper_sections = []
    state.evidence_spans = []
    for note in state.paper_notes:
        note.source_basis = "metadata/abstract only"
    state.source_coverage = SourceCoverageReport(
        run_id=state.run_id,
        topic=state.topic.text,
        searched_sources=["fixture"],
        papers_by_source={"fixture": 2},
        papers_abstract_only=["p1", "p2"],
        confidence="low",
    )
    payload = _payload(supporting_locators=[])
    payload["gaps"][0]["explicit_reason"] = "Abstract-only metadata repeatedly reports deployment-shift limitations."
    payload["gaps"][0]["confidence"] = "high"

    GapMiningLLM(client=StaticJSONClient(payload), runtime_config=LLMRuntimeConfig(mode="fake")).mine_with_llm(
        state,
        allow_deterministic_fallback=False,
    )

    assert state.gaps[0].confidence == "low"
    assert state.gap_evidence_matrices[0].confidence == "low"


def test_human_rejected_gaps_are_respected(tmp_path: Path) -> None:
    manager = ResearchStateManager(GapForgeConfig.from_cwd(tmp_path))
    state = _gap_llm_state(manager)
    existing = Gap(id="gap-human-rejected", title="Deployment-shift false-positive evaluation is under-specified")
    state.gaps = [existing]
    state.human_reviews = [
        HumanReviewRecord(
            id="review-1",
            object_type="gap",
            object_id=existing.id,
            action="reject",
            note="Too broad.",
            timestamp=utc_now_iso(),
        )
    ]

    GapMiningLLM(client=StaticJSONClient(_payload()), runtime_config=LLMRuntimeConfig(mode="fake")).mine_with_llm(
        state,
        allow_deterministic_fallback=False,
    )

    assert state.gaps == [existing]
    assert state.gap_evidence_matrices == []
    assert "human rejected" in (Path(state.run_dir) / "gap_mining_llm.md").read_text(encoding="utf-8")


def test_mine_gaps_llm_cli_dry_run_writes_prompt(tmp_path: Path) -> None:
    manager = ResearchStateManager(GapForgeConfig.from_cwd(tmp_path))
    state = _gap_llm_state(manager)
    manager.save_run(state)
    env = {**os.environ, "GAPFORGE_DISABLE_NETWORK": "1", "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")}

    result = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "mine-gaps-llm", "--run-id", state.run_id, "--dry-run-prompts"],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert (Path(state.run_dir) / "prompt_packs" / "gap-mining-llm.md").exists()
    assert (Path(state.run_dir) / "gap_mining_llm.md").exists()


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
        return LLMResponse(text=json.dumps(self.payload), model="static-gap-test")

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


def _gap_llm_state(manager: ResearchStateManager):
    state = manager.create_run("low false positive collusion detection")
    state.papers = [
        Paper(
            id="p1",
            title="Synthetic collusion detector",
            authors=[],
            abstract="Future work should test deployment shift.",
            year=2024,
            source="fixture",
        ),
        Paper(
            id="p2",
            title="Scalable collusion monitor",
            authors=[],
            abstract="Large-scale deployment false positives remain open.",
            year=2025,
            source="fixture",
        ),
    ]
    state.paper_notes = [
        PaperNote(
            paper_id="p1",
            citation_key="p1",
            stated_limitations=["Future work should test deployment shift and false-positive behavior."],
            metrics=["accuracy"],
            source_basis="full text",
            confidence="medium",
        ),
        PaperNote(
            paper_id="p2",
            citation_key="p2",
            stated_limitations=["Large-scale deployment false-positive controls remain an open challenge."],
            metrics=[],
            source_basis="full text",
            confidence="medium",
        ),
    ]
    state.paper_sections = [
        PaperSection(
            id="p1-limitations",
            paper_id="p1",
            title="Limitations",
            section_type="limitations",
            text="Future work should test deployment shift and false-positive behavior.",
            page_start=7,
            page_end=7,
        ),
        PaperSection(
            id="p2-limitations",
            paper_id="p2",
            title="Limitations",
            section_type="limitations",
            text="Large-scale deployment false-positive controls remain an open challenge.",
            page_start=8,
            page_end=8,
        ),
    ]
    state.evidence_spans = [
        EvidenceSpan(
            id="span-p1",
            paper_id="p1",
            section_id="p1-limitations",
            quote="Future work should test deployment shift and false-positive behavior.",
            locator="p1:Limitations:p7",
            evidence_type="limitation",
            confidence="high",
        ),
        EvidenceSpan(
            id="span-p2",
            paper_id="p2",
            section_id="p2-limitations",
            quote="Large-scale deployment false-positive controls remain an open challenge.",
            locator="p2:Limitations:p8",
            evidence_type="limitation",
            confidence="high",
        ),
    ]
    state.source_coverage = SourceCoverageReport(
        run_id=state.run_id,
        topic=state.topic.text,
        searched_sources=["fixture"],
        papers_by_source={"fixture": 2},
        papers_with_full_text=["p1", "p2"],
        confidence="medium",
    )
    return state


def _payload(*, supporting_locators: list[str] | None = None) -> dict[str, Any]:
    locators = supporting_locators if supporting_locators is not None else ["p1:Limitations:p7", "p2:Limitations:p8"]
    return {
        "gaps": [
            {
                "title": "Deployment-shift false-positive evaluation is under-specified",
                "type": "deployment gap",
                "description": "Two papers leave deployment-shift false-positive behavior unresolved.",
                "supporting_evidence": locators,
                "supporting_locators": locators,
                "counterevidence": [],
                "counterevidence_locators": [],
                "counterevidence_search_summary": "Retrieved current-run sections did not show a paper that resolves deployment-shift FPR.",
                "minimum_experiment_needed": "Evaluate under a fixed false-positive budget before and after deployment shift.",
                "why_existing_work_does_not_solve_it": "The cited limitations state the condition remains future work or open.",
                "why_it_matters": "Low false positives are deployment-critical.",
                "possible_research_questions": ["How stable is recall at fixed FPR under deployment shift?"],
                "explicit_reason": "",
                "novelty_status": "unchecked",
                "risk_that_gap_is_fake": "Adjacent anomaly detection may already solve this.",
                "confidence": "high",
                "reasoning_summary": "Public summary: repeated limitations with counterevidence search.",
            }
        ],
        "claim_updates": [],
        "limitations": [],
    }
