from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from gapforge.config import GapForgeConfig
from gapforge.llm.base import LLMResponse
from gapforge.llm.config import LLMRuntimeConfig
from gapforge.llm.json_guard import JSONGuardError
from gapforge.models import EvidenceSpan, Paper, PaperSection
from gapforge.skills.deep_reading_llm import DeepReadingLLM
from gapforge.state import ResearchStateManager


def test_fake_llm_path_creates_safe_low_confidence_note(tmp_path: Path) -> None:
    manager = ResearchStateManager(GapForgeConfig.from_cwd(tmp_path))
    state = _llm_state(manager)

    DeepReadingLLM().read_papers(state, state.papers, fake=True)

    assert state.paper_notes[0].created_by_skill == "deep-reading-llm"
    assert state.paper_notes[0].confidence == "low"
    assert not state.paper_notes[0].main_results
    assert (Path(state.run_dir) / "deep_reading_llm.md").exists()
    transcripts = json.loads((Path(state.run_dir) / "llm_transcripts.json").read_text(encoding="utf-8"))
    assert transcripts[0]["skill_name"] == "deep-reading-llm"


def test_malformed_json_is_rejected_without_state_update(tmp_path: Path) -> None:
    manager = ResearchStateManager(GapForgeConfig.from_cwd(tmp_path))
    state = _llm_state(manager)

    with pytest.raises(JSONGuardError):
        DeepReadingLLM(client=MalformedClient(), runtime_config=LLMRuntimeConfig(mode="fake")).read_papers(
            state,
            state.papers,
            allow_deterministic_fallback=False,
        )

    assert state.paper_notes == []
    assert state.claims == []


def test_unsupported_locator_is_dropped(tmp_path: Path) -> None:
    manager = ResearchStateManager(GapForgeConfig.from_cwd(tmp_path))
    state = _llm_state(manager)

    DeepReadingLLM(
        client=StaticJSONClient(_payload(evidence_locators=["not-a-real-locator"])),
        runtime_config=LLMRuntimeConfig(mode="fake"),
    ).read_papers(
        state,
        state.papers,
        allow_deterministic_fallback=False,
    )

    note = state.paper_notes[0]
    assert note.confidence == "low"
    assert not note.main_results
    assert not state.claims
    assert "no valid EvidenceSpan" in note.what_it_cannot_answer[0]


def test_valid_locator_creates_supported_claim(tmp_path: Path) -> None:
    manager = ResearchStateManager(GapForgeConfig.from_cwd(tmp_path))
    state = _llm_state(manager)

    DeepReadingLLM(
        client=StaticJSONClient(_payload(evidence_locators=["paper-1:Results:p4"])),
        runtime_config=LLMRuntimeConfig(mode="fake"),
    ).read_papers(
        state,
        state.papers,
        allow_deterministic_fallback=False,
    )

    note = state.paper_notes[0]
    assert note.source_basis == "llm full text"
    assert note.main_results == ["The detector improves recall at a fixed 1% false-positive rate."]
    assert note.quotes_or_evidence_snippets[0].locator == "paper-1:Results:p4"
    assert len(state.claims) == 1
    assert state.claims[0].status == "supported"
    assert state.claims[0].supporting_evidence[0].locator == "paper-1:Results:p4"


def test_deterministic_fallback_still_works_when_llm_mode_off(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GAPFORGE_LLM_MODE", raising=False)
    manager = ResearchStateManager(GapForgeConfig.from_cwd(tmp_path))
    state = _llm_state(manager)

    DeepReadingLLM().read_papers(state, state.papers)

    assert state.paper_notes
    assert state.paper_notes[0].created_by_skill == "deep-reading"


def test_read_llm_cli_dry_run_writes_prompts_without_api(tmp_path: Path) -> None:
    manager = ResearchStateManager(GapForgeConfig.from_cwd(tmp_path))
    state = _llm_state(manager)
    manager.save_run(state)
    env = {**os.environ, "GAPFORGE_DISABLE_NETWORK": "1", "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")}

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "gapforge.cli",
            "read-llm",
            "--run-id",
            state.run_id,
            "--paper-id",
            "paper-1",
            "--dry-run-prompts",
        ],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert (Path(state.run_dir) / "prompt_packs" / "deep-reading-llm-paper-1.md").exists()
    assert (Path(state.run_dir) / "deep_reading_llm.md").exists()


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
        return LLMResponse(text=json.dumps(self.payload), model="static-test")

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


class MalformedClient(StaticJSONClient):
    def __init__(self) -> None:
        super().__init__({})

    def complete_json(
        self,
        prompt: str,
        *,
        schema_name: str,
        system: str = "",
        temperature: float = 0.0,
        max_tokens: int | None = None,
    ) -> dict[str, Any]:
        raise JSONGuardError("No valid JSON object found in model response.")


def _llm_state(manager: ResearchStateManager):
    state = manager.create_run("low false positive collusion detection")
    state.papers = [
        Paper(
            id="paper-1",
            title="False-positive budgeted collusion detection",
            authors=["A. Researcher"],
            abstract="We evaluate collusion detection under fixed false-positive budgets.",
            year=2025,
            source="fixture",
        )
    ]
    state.paper_sections = [
        PaperSection(
            id="section-method-1",
            paper_id="paper-1",
            title="Method",
            normalized_title="method",
            section_type="method",
            text="We use a calibrated graph detector with abstention.",
            page_start=3,
            page_end=3,
            confidence="medium",
        ),
        PaperSection(
            id="section-results-1",
            paper_id="paper-1",
            title="Results",
            normalized_title="results",
            section_type="results",
            text="At 1% false-positive rate, the detector improves recall over a graph baseline.",
            page_start=4,
            page_end=4,
            confidence="medium",
        ),
    ]
    state.evidence_spans = [
        EvidenceSpan(
            id="span-method-1",
            paper_id="paper-1",
            section_id="section-method-1",
            quote="We use a calibrated graph detector with abstention.",
            locator="paper-1:Method:p3",
            evidence_type="method",
            page_start=3,
            page_end=3,
            confidence="medium",
        ),
        EvidenceSpan(
            id="span-results-1",
            paper_id="paper-1",
            section_id="section-results-1",
            quote="At 1% false-positive rate, the detector improves recall over a graph baseline.",
            locator="paper-1:Results:p4",
            evidence_type="result",
            page_start=4,
            page_end=4,
            confidence="medium",
        ),
    ]
    return state


def _payload(*, evidence_locators: list[str]) -> dict[str, Any]:
    return {
        "paper_notes": [
            {
                "paper_id": "paper-1",
                "source_basis": "full text",
                "confidence": "high",
                "sections_used": ["section-results-1"],
                "missing_sections": [],
                "core_claims": ["The paper evaluates fixed false-positive-rate collusion detection."],
                "method": ["calibrated graph detector"],
                "datasets": [],
                "metrics": ["false-positive rate", "recall"],
                "main_results": ["The detector improves recall at a fixed 1% false-positive rate."],
                "limitations": [],
                "evidence_locators": evidence_locators,
                "reasoning_summary": "Public summary: accepted only if locators validate.",
            }
        ],
        "claims": [
            {
                "text": "The paper reports improved recall at a fixed false-positive rate.",
                "type": "result",
                "confidence": "medium",
                "evidence_locators": evidence_locators,
            }
        ],
        "evidence_spans": [],
        "limitations": [],
    }
