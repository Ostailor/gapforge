from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from gapforge.agents import AgentRuntimeConfig, AgentUnavailableError, CodexAgentClient, FakeAgentClient, create_agent_task_spec
from gapforge.config import GapForgeConfig
from gapforge.models import AgentTaskSpec, EvidenceSpan, Paper, ResearchRunState
from gapforge.state import ResearchStateManager


def test_create_task_spec_and_task_pack(tmp_path: Path) -> None:
    manager, state = _agent_state(tmp_path)

    task = create_agent_task_spec(state, skill_name="novelty-gate", gap_id="gap-1")
    state.agent_task_specs.append(task)
    pack = CodexAgentClient(manager.config, AgentRuntimeConfig(mode="task-pack")).create_task_pack(state, task)
    manager.save_run(state)

    assert task.task_type == "novelty"
    assert task.output_schema_name == "agent-novelty-dossier-patch"
    assert "novelty_dossiers_patch.json" in task.required_output_files
    assert (pack / "TASK.md").exists()
    assert (pack / "input_manifest.json").exists()
    assert (pack / "expected_output_schema.json").exists()
    assert (pack / "evidence_rules.md").exists()
    assert (pack / "uncertainty_rules.md").exists()
    assert (pack / "artifact_links.json").exists()
    assert (pack / "outputs").is_dir()
    assert (pack / "validation.json").exists()
    assert "Do not invent citations" in (pack / "TASK.md").read_text(encoding="utf-8")
    loaded = manager.load_run(state.run_id)
    assert loaded.agent_task_specs[0].id == task.id
    assert (Path(state.run_dir) / "agent_tasks.md").exists()


def test_fake_agent_run_is_deterministic_and_ci_safe(tmp_path: Path) -> None:
    manager, state = _agent_state(tmp_path)
    task = create_agent_task_spec(state, skill_name="deep-reading", paper_id="paper-1")
    state.agent_task_specs.append(task)
    manager.save_run(state)

    record = FakeAgentClient(manager.config).run_task(task)

    assert record.status == "complete"
    assert record.model == "gapforge-fake-agent"
    assert Path(record.output_paths[0]).exists()
    loaded = manager.load_run(state.run_id)
    assert loaded.agent_run_records
    assert loaded.agent_validation_results[0].status == "valid"


def test_codex_mode_disabled_by_default(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    manager, state = _agent_state(tmp_path)
    task = create_agent_task_spec(state, skill_name="novelty-gate", gap_id="gap-1")
    state.agent_task_specs.append(task)
    manager.save_run(state)
    monkeypatch.delenv("GAPFORGE_ENABLE_REAL_RUNS", raising=False)

    client = CodexAgentClient(manager.config, AgentRuntimeConfig(mode="codex", enable_real_runs=False))

    try:
        client.run_task(task)
    except AgentUnavailableError as exc:
        assert "GAPFORGE_ENABLE_REAL_RUNS=1" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("Codex actual runs should be disabled by default.")


def test_import_valid_output_records_validation(tmp_path: Path) -> None:
    manager, state = _agent_state(tmp_path)
    task = create_agent_task_spec(state, skill_name="novelty-gate", gap_id="gap-1")
    state.agent_task_specs.append(task)
    manager.save_run(state)
    outputs_dir = _task_outputs_dir(state, task)
    outputs_dir.mkdir(parents=True, exist_ok=True)
    (outputs_dir / "novelty_dossiers_patch.json").write_text(
        json.dumps(
            {
                "novelty_dossiers": [
                    {
                        "target_id": "gap-1",
                        "idea_summary": "Evaluate low-FPR collusion detection.",
                        "top_prior_work": ["paper-1"],
                        "comparison_table": [{"paper_id": "paper-1", "overall_similarity": 0.4}],
                        "verdict": "revise",
                        "novelty_strength": "weak",
                        "confidence": "medium",
                    }
                ],
                "public_reasoning_summary": "Compared against known paper only.",
            }
        ),
        encoding="utf-8",
    )
    (outputs_dir / "novelty_assessments_patch.json").write_text(
        json.dumps(
            {
                "novelty_assessments": [
                    {
                        "target_gap_or_hypothesis_id": "gap-1",
                        "idea_summary": "Evaluate low-FPR collusion detection.",
                        "closest_prior_work": ["paper-1"],
                        "verdict": "revise",
                        "novelty_strength": "weak",
                        "confidence": "medium",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    (outputs_dir / "rejected_ideas_patch.json").write_text(json.dumps({"rejected_ideas": []}), encoding="utf-8")

    validation = CodexAgentClient(manager.config, AgentRuntimeConfig(mode="task-pack")).import_outputs(task, [])

    assert validation.status == "valid"
    loaded = manager.load_run(state.run_id)
    assert loaded.novelty_dossiers[0].target_id == "gap-1"
    assert loaded.agent_validation_results[-1].status == "valid"
    assert loaded.agent_run_records[-1].status == "imported"


def test_reject_fake_citation(tmp_path: Path) -> None:
    manager, state = _agent_state(tmp_path)
    task = create_agent_task_spec(state, skill_name="novelty-gate", gap_id="gap-1")
    state.agent_task_specs.append(task)
    manager.save_run(state)
    output = Path(state.run_dir) / "fake_citation_agent_output.json"
    output.write_text(
        json.dumps(
            {
                "novelty_dossiers": [
                    {
                        "target_id": "gap-1",
                        "idea_summary": "A gap.",
                        "top_prior_work": ["Imaginary Paper by Nobody 2099"],
                        "verdict": "pursue",
                        "novelty_strength": "medium",
                        "confidence": "medium",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    validation = CodexAgentClient(manager.config, AgentRuntimeConfig(mode="task-pack")).validate_outputs(task, [output])

    assert validation.status == "invalid"
    assert validation.invalid_prior_work_count >= 1
    assert any("citation does not resolve" in issue for issue in validation.issues)


def test_invalid_output_leaves_state_unchanged(tmp_path: Path) -> None:
    manager, state = _agent_state(tmp_path)
    task = create_agent_task_spec(state, skill_name="novelty-gate", gap_id="gap-1")
    state.agent_task_specs.append(task)
    manager.save_run(state)
    before_dossier_count = len(state.novelty_dossiers)
    output = Path(state.run_dir) / "invalid_import_agent_output.json"
    output.write_text(
        json.dumps(
            {
                "novelty_dossiers": [
                    {
                        "target_id": "gap-1",
                        "idea_summary": "A gap.",
                        "top_prior_work": [{"paper_id": "not-real"}],
                        "verdict": "pursue",
                        "novelty_strength": "medium",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    validation = CodexAgentClient(manager.config, AgentRuntimeConfig(mode="task-pack")).import_outputs(task, [output])

    assert validation.status == "invalid"
    loaded = manager.load_run(state.run_id)
    assert len(loaded.novelty_dossiers) == before_dossier_count
    assert loaded.agent_run_records[-1].status == "rejected"
    assert (Path(state.run_dir) / "agent_tasks" / task.id / "validation.json").exists()


def test_reject_invalid_output_with_missing_evidence_locator(tmp_path: Path) -> None:
    manager, state = _agent_state(tmp_path)
    task = create_agent_task_spec(state, skill_name="deep-reading", paper_id="paper-1")
    state.agent_task_specs.append(task)
    manager.save_run(state)
    output = Path(state.run_dir) / "unsupported_agent_output.json"
    output.write_text(
        json.dumps({"claims": [{"text": "This is certain without evidence.", "confidence": "high"}]}),
        encoding="utf-8",
    )

    validation = CodexAgentClient(manager.config, AgentRuntimeConfig(mode="task-pack")).import_outputs(task, [output])

    assert validation.status == "invalid"
    assert validation.unsupported_claim_count == 1
    assert any("lacks evidence" in issue for issue in validation.issues)
    loaded = manager.load_run(state.run_id)
    assert loaded.agent_run_records[-1].status == "rejected"


def test_invalid_prior_work_ids_are_detected(tmp_path: Path) -> None:
    manager, state = _agent_state(tmp_path)
    task = create_agent_task_spec(state, skill_name="novelty-gate", gap_id="gap-1")
    state.agent_task_specs.append(task)
    manager.save_run(state)
    output = Path(state.run_dir) / "invalid_prior_agent_output.json"
    output.write_text(
        json.dumps({"closest_prior_work": [{"paper_id": "missing-paper", "reason": "not in state"}]}),
        encoding="utf-8",
    )

    validation = CodexAgentClient(manager.config, AgentRuntimeConfig(mode="task-pack")).validate_outputs(task, [output])

    assert validation.status == "invalid"
    assert validation.invalid_prior_work_count == 1
    assert any("missing-paper" in issue for issue in validation.issues)


def test_agent_cli_status_task_fake_and_validate(tmp_path: Path) -> None:
    manager, state = _agent_state(tmp_path)
    env = {**os.environ, "GAPFORGE_DISABLE_NETWORK": "1", "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")}

    status = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "agent-status"],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert status.returncode == 0, status.stderr
    assert json.loads(status.stdout)["codex_model"] == "gpt-5.4"

    task_result = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "agent-task", "--run-id", state.run_id, "--skill", "deep-reading", "--paper-id", "paper-1"],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert task_result.returncode == 0, task_result.stderr
    task_id = task_result.stdout.split("agent task", 1)[1].split("to", 1)[0].strip()

    run_result = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "agent-run", "--task-id", task_id, "--fake"],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert run_result.returncode == 0, run_result.stderr
    assert json.loads(run_result.stdout)["status"] == "complete"


def test_read_llm_agent_task_pack_mode_writes_codex_pack(tmp_path: Path) -> None:
    manager, state = _agent_state(tmp_path)
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
            "--agent",
            "codex",
            "--agent-mode",
            "task-pack",
        ],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "Codex task pack" in result.stdout
    loaded = manager.load_run(state.run_id)
    task = loaded.agent_task_specs[-1]
    pack = Path(state.run_dir) / "agent_tasks" / task.id
    assert (pack / "TASK.md").exists()
    assert (pack / "expected_output_schema.json").exists()


def test_mine_gaps_llm_agent_fake_mode_validates_safely(tmp_path: Path) -> None:
    manager, state = _agent_state(tmp_path)
    env = {**os.environ, "GAPFORGE_DISABLE_NETWORK": "1", "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")}

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "gapforge.cli",
            "mine-gaps-llm",
            "--run-id",
            state.run_id,
            "--agent",
            "codex",
            "--agent-mode",
            "fake",
        ],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["status"] == "complete"
    loaded = manager.load_run(state.run_id)
    assert loaded.agent_validation_results[-1].status == "valid"


def test_novelty_check_llm_codex_mode_disabled_without_env(tmp_path: Path) -> None:
    _, state = _agent_state(tmp_path)
    env = {**os.environ, "GAPFORGE_DISABLE_NETWORK": "1", "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")}
    env.pop("GAPFORGE_ENABLE_REAL_RUNS", None)

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
            "--agent",
            "codex",
            "--agent-mode",
            "codex",
        ],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 1
    assert "GAPFORGE_ENABLE_REAL_RUNS=1" in result.stderr


def test_read_llm_agent_import_output_applies_valid_patch(tmp_path: Path) -> None:
    manager, state = _agent_state(tmp_path)
    patch = tmp_path / "paper_notes_patch.json"
    patch.write_text(
        json.dumps(
            {
                "paper_notes": [
                    {
                        "paper_id": "paper-1",
                        "citation_key": "researcher2025low",
                        "one_sentence_summary": "Codex-backed note with locator discipline.",
                        "confidence": "medium",
                        "created_by_skill": "codex-agent",
                        "source_basis": "Codex-agent-backed full text",
                        "sections_used": ["abstract"],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    claims_patch = tmp_path / "claims_patch.json"
    claims_patch.write_text(json.dumps({"claims": []}), encoding="utf-8")
    spans_patch = tmp_path / "evidence_spans_patch.json"
    spans_patch.write_text(json.dumps({"evidence_spans": []}), encoding="utf-8")
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
            "--agent",
            "codex",
            "--import-output",
            str(patch),
            "--import-output",
            str(claims_patch),
            "--import-output",
            str(spans_patch),
        ],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    loaded = manager.load_run(state.run_id)
    assert loaded.paper_notes[0].created_by_skill == "codex-agent"
    assert loaded.agent_run_records[-1].status == "imported"


def test_report_labels_agent_backed_outputs(tmp_path: Path) -> None:
    manager, state = _agent_state(tmp_path)
    task = create_agent_task_spec(state, skill_name="deep-reading", paper_id="paper-1")
    state.agent_task_specs.append(task)
    manager.save_run(state)
    FakeAgentClient(manager.config).run_task(task)

    result = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "report", "--run-id", state.run_id],
        cwd=tmp_path,
        env={**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")},
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    report = (Path(state.run_dir) / "final_report.md").read_text(encoding="utf-8")
    assert "Skill Execution Provenance" in report
    assert "Codex agent task packs" in report


def _agent_state(tmp_path: Path) -> tuple[ResearchStateManager, ResearchRunState]:
    config = GapForgeConfig.from_cwd(tmp_path)
    manager = ResearchStateManager(config)
    state = manager.create_run("agent client fixture")
    state.papers.append(
        Paper(
            id="paper-1",
            title="Low False Positive Collusion Detection",
            authors=["A. Researcher"],
            abstract="We evaluate low-FPR collusion detection in a synthetic benchmark.",
            year=2025,
            source="fixture",
        )
    )
    state.evidence_spans.append(
        EvidenceSpan(
            id="span-1",
            paper_id="paper-1",
            quote="We evaluate low-FPR collusion detection.",
            locator="paper-1:Abstract:p1",
            evidence_type="result",
            confidence="medium",
        )
    )
    manager.save_run(state)
    return manager, state


def _task_outputs_dir(state: ResearchRunState, task: AgentTaskSpec) -> Path:
    return Path(state.run_dir) / "agent_tasks" / task.id / "outputs"
