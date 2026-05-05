from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from gapforge.config import GapForgeConfig
from gapforge.llm.fake import FakeLLMClient
from gapforge.llm.prompt_pack import PromptPackBuilder, write_prompt_pack
from gapforge.models import EvidenceSpan, Gap, NoveltyAssessment, Paper, PaperNote, PaperSection
from gapforge.state import ResearchStateManager


def test_fake_llm_client_is_deterministic_and_offline() -> None:
    client = FakeLLMClient()

    first = client.complete("Read paper p1.", system="You are GapForge.")
    second = client.complete("Read paper p1.", system="You are GapForge.")
    json_result = client.complete_json("Target ID: gap-1", schema_name="novelty-gate")

    assert first == second
    assert first.model == "gapforge-fake-llm"
    assert json_result["target_id"] == "gap-1"
    assert json_result["verdict"] == "unknown"
    assert json_result["missing_searches"] == ["fake client performs no searches"]


def test_config_llm_mode_defaults_off_and_reads_prompt_pack_env(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("GAPFORGE_LLM_MODE", raising=False)
    assert GapForgeConfig.from_cwd(tmp_path).llm_mode == "off"

    monkeypatch.setenv("GAPFORGE_LLM_MODE", "prompt-pack")
    assert GapForgeConfig.from_cwd(tmp_path).llm_mode == "prompt-pack"


def test_prompt_pack_generation_for_deep_reading(tmp_path: Path) -> None:
    state = _prompt_state(tmp_path)

    path = write_prompt_pack(state, skill_name="deep-reading")

    text = path.read_text(encoding="utf-8")
    assert path.parent == Path(state.run_dir) / "prompt_packs"
    assert "GapForge Prompt Pack: deep-reading" in text
    assert "Do not hallucinate citations" in text
    assert "EvidenceSpan locators" in text
    assert "public reasoning summaries" in text
    assert "paper-1:Results:p4" in text
    assert '"paper_notes"' in text


def test_prompt_pack_generation_for_novelty_gate_with_gap(tmp_path: Path) -> None:
    state = _prompt_state(tmp_path)

    pack = PromptPackBuilder().build(state, skill_name="novelty-gate", gap_id="gap-1")

    rendered = pack.render_markdown()
    assert pack.target_id == "gap-1"
    assert "closest prior work" in rendered.lower()
    assert "Target ID: `gap-1`" in rendered
    assert '"target_gap"' in rendered
    assert '"verdict"' in rendered
    assert "Do not hallucinate citations" in rendered


def test_prompt_pack_cli_writes_file_without_api_keys(tmp_path: Path) -> None:
    manager = ResearchStateManager(GapForgeConfig.from_cwd(tmp_path))
    state = _prompt_state(tmp_path, manager=manager)
    manager.save_run(state)
    env = {**os.environ, "GAPFORGE_DISABLE_NETWORK": "1"}
    env["PYTHONPATH"] = str(Path(__file__).resolve().parents[1] / "src")

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "gapforge.cli",
            "prompt-pack",
            "--run-id",
            state.run_id,
            "--skill",
            "novelty-gate",
            "--gap-id",
            "gap-1",
        ],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "prompt_packs" in result.stdout
    prompt_path = Path(result.stdout.split("to", 1)[1].strip())
    assert prompt_path.exists()
    assert "gap-1" in prompt_path.read_text(encoding="utf-8")


def test_prompt_pack_mode_generates_prompts_without_replacing_deterministic_read(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("GAPFORGE_LLM_MODE", "prompt-pack")
    manager = ResearchStateManager(GapForgeConfig.from_env_or_cwd(tmp_path))
    state = _prompt_state(tmp_path, manager=manager)
    manager.save_run(state)

    env = {**os.environ, "GAPFORGE_DISABLE_NETWORK": "1", "GAPFORGE_LLM_MODE": "prompt-pack"}
    env["PYTHONPATH"] = str(Path(__file__).resolve().parents[1] / "src")
    result = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "read", "--run-id", state.run_id, "--paper-id", "paper-1"],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    run_dir = Path(state.run_dir)
    notes = json.loads((run_dir / "paper_notes.json").read_text(encoding="utf-8"))
    assert notes
    assert (run_dir / "prompt_packs" / "deep-reading.md").exists()


def _prompt_state(tmp_path: Path, manager: ResearchStateManager | None = None):
    manager = manager or ResearchStateManager(GapForgeConfig.from_cwd(tmp_path))
    state = manager.create_run("low false positive collusion detection")
    state.papers = [
        Paper(
            id="paper-1",
            title="False-positive budgeted collusion detection",
            authors=["A. Researcher"],
            abstract="We evaluate collusion detection under fixed false-positive budgets and report recall.",
            year=2025,
            source="fixture",
            doi="10.1234/example",
        )
    ]
    state.paper_sections = [
        PaperSection(
            id="section-results-1",
            paper_id="paper-1",
            title="Results",
            section_type="results",
            text="At 1% false-positive rate, the detector improves recall over a graph baseline.",
            page_start=4,
            page_end=4,
            confidence="medium",
        )
    ]
    state.evidence_spans = [
        EvidenceSpan(
            id="span-1",
            paper_id="paper-1",
            section_id="section-results-1",
            quote="At 1% false-positive rate, the detector improves recall over a graph baseline.",
            locator="paper-1:Results:p4",
            evidence_type="result",
            page_start=4,
            page_end=4,
            confidence="medium",
        )
    ]
    state.paper_notes = [
        PaperNote(
            paper_id="paper-1",
            source_basis="full text",
            confidence="medium",
            one_sentence_summary="The paper evaluates collusion detection under fixed false-positive budgets.",
            main_results=["Improves recall at 1% false-positive rate."],
            metrics=["false-positive-rate", "recall"],
            sections_used=["section-results-1"],
        )
    ]
    state.gaps = [
        Gap(
            id="gap-1",
            title="Fixed false-positive budget evaluation under deployment shift",
            description="Existing collusion detection should be checked under deployment shift at fixed false-positive budgets.",
            supporting_paper_ids=["paper-1"],
            risk_that_gap_is_fake="The same deployment-shift experiment may already exist in adjacent anomaly detection work.",
            confidence="medium",
            novelty_status="unchecked",
        )
    ]
    state.novelty_assessments = [
        NoveltyAssessment(
            target_gap_or_hypothesis_id="gap-1",
            idea_summary="Fixed false-positive budget evaluation under deployment shift",
            closest_prior_work=["paper-1"],
            verdict="revise",
            novelty_strength="weak",
            confidence="medium",
        )
    ]
    return state
