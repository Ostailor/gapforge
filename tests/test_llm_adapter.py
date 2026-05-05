from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from gapforge.config import GapForgeConfig
from gapforge.llm.config import LLMRuntimeConfig
from gapforge.llm.fake import FakeLLMClient
from gapforge.llm.json_guard import JSONGuard, JSONGuardError, extract_json
from gapforge.llm.prompt_pack import PromptPackBuilder, write_prompt_pack
from gapforge.llm.providers import ProviderLLMClient, ProviderUnavailableError, llm_status
from gapforge.llm.transcripts import LLMTranscriptLogger
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

    monkeypatch.setenv("GAPFORGE_LLM_MODE", "provider")
    assert GapForgeConfig.from_cwd(tmp_path).llm_mode == "provider"


def test_llm_runtime_config_reads_provider_env(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("GAPFORGE_LLM_MODE", "provider")
    monkeypatch.setenv("GAPFORGE_LLM_PROVIDER", "openai")
    monkeypatch.setenv("GAPFORGE_LLM_MODEL", "test-model")
    monkeypatch.setenv("GAPFORGE_LLM_MAX_TOKENS", "123")
    monkeypatch.setenv("GAPFORGE_LLM_BUDGET_USD", "0.01")
    monkeypatch.setenv("GAPFORGE_LLM_TIMEOUT_SECONDS", "7.5")

    config = LLMRuntimeConfig.from_env()

    assert config.mode == "provider"
    assert config.provider == "openai"
    assert config.model == "test-model"
    assert config.max_tokens == 123
    assert config.budget_usd == 0.01
    assert config.timeout_seconds == 7.5


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


def test_fake_mode_writes_usage_and_transcripts(tmp_path: Path) -> None:
    manager = ResearchStateManager(GapForgeConfig.from_cwd(tmp_path))
    state = _prompt_state(tmp_path, manager=manager)
    client = FakeLLMClient(run_dir=state.run_dir, skill_name="novelty-gate", prompt_pack_id="pack-1")

    payload = client.complete_json("Target ID: gap-1", schema_name="novelty-gate")

    assert payload["target_id"] == "gap-1"
    usage = json.loads((Path(state.run_dir) / "llm_usage.json").read_text(encoding="utf-8"))
    assert usage["calls"] == 1
    transcripts = json.loads((Path(state.run_dir) / "llm_transcripts.json").read_text(encoding="utf-8"))
    assert transcripts[0]["skill_name"] == "novelty-gate"
    assert transcripts[0]["prompt_pack_id"] == "pack-1"
    assert "Deterministic fake" in transcripts[0]["reasoning_summary"]


def test_provider_mode_without_package_or_key_fails_gracefully(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("GAPFORGE_LLM_MODE", "provider")
    monkeypatch.setenv("GAPFORGE_LLM_PROVIDER", "openai")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    config = LLMRuntimeConfig.from_env()
    client = ProviderLLMClient(config=config, run_dir=tmp_path, skill_name="llm-test")

    try:
        client.complete("hello")
    except ProviderUnavailableError as exc:
        assert "OPENAI_API_KEY" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("Provider mode should fail without OPENAI_API_KEY.")

    transcripts = json.loads((tmp_path / "llm_transcripts.json").read_text(encoding="utf-8"))
    assert transcripts[0]["response_status"] == "failed"
    assert llm_status(config)["provider_ready"] is False


def test_json_guard_extracts_and_rejects_invalid_schema() -> None:
    valid = extract_json(
        "prefix ```json\n"
        '{"target_id":"gap-1","closest_prior_work":[],"verdict":"unknown",'
        '"novelty_strength":"unknown","missing_searches":[],"reasoning_summary":"No claim."}\n'
        "```"
    )

    assert valid["target_id"] == "gap-1"
    guard = JSONGuard()
    try:
        guard.parse_and_validate('{"target_id":"gap-1","verdict":"unknown"}', schema_name="novelty-gate")
    except JSONGuardError as exc:
        assert "missing required fields" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("Invalid schema should be rejected.")

    try:
        guard.parse_and_validate(
            '{"target_id":"gap-1","closest_prior_work":[],"verdict":"unknown","novelty_strength":"unknown","missing_searches":[],"reasoning_summary":"x","extra":true}',
            schema_name="novelty-gate",
        )
    except JSONGuardError as exc:
        assert "unknown fields" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("Unknown fields should be rejected.")


def test_budget_warning_triggers(tmp_path: Path) -> None:
    client = FakeLLMClient(
        run_dir=tmp_path,
        config=LLMRuntimeConfig(mode="fake", budget_usd=0.0),
    )

    client.complete("large prompt " * 100)

    usage = json.loads((tmp_path / "llm_usage.json").read_text(encoding="utf-8"))
    assert usage["warnings"]
    assert "budget exceeded" in usage["warnings"][0].lower()


def test_transcripts_redact_secrets(tmp_path: Path) -> None:
    client = FakeLLMClient(run_dir=tmp_path)

    client.complete("Use api_key: sk-THISSECRET123456789 in prompt")

    transcript_text = (tmp_path / "llm_transcripts.json").read_text(encoding="utf-8")
    markdown = LLMTranscriptLogger(tmp_path).render_markdown()
    assert "sk-THISSECRET" not in transcript_text
    assert "[REDACTED]" in transcript_text
    assert "[REDACTED]" in markdown


def test_llm_cli_status_test_usage_and_transcripts(tmp_path: Path) -> None:
    manager = ResearchStateManager(GapForgeConfig.from_cwd(tmp_path))
    state = _prompt_state(tmp_path, manager=manager)
    manager.save_run(state)
    env = {**os.environ, "GAPFORGE_DISABLE_NETWORK": "1", "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")}

    status = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "llm-status"],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert status.returncode == 0, status.stderr
    assert json.loads(status.stdout)["mode"] in {"off", "prompt-pack", "fake", "provider"}

    test = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "llm-test", "--fake", "--run-id", state.run_id],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert test.returncode == 0, test.stderr
    assert json.loads(test.stdout)["verdict"] == "unknown"

    usage = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "llm-usage", "--run-id", state.run_id],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert usage.returncode == 0, usage.stderr
    assert json.loads(usage.stdout)["calls"] == 1

    transcripts = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "llm-transcripts", "--run-id", state.run_id],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert transcripts.returncode == 0, transcripts.stderr
    assert "LLM Transcripts" in transcripts.stdout


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
