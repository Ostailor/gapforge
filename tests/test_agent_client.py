from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from gapforge.agents import (
    AgentRuntimeConfig,
    AgentUnavailableError,
    CodexAgentClient,
    CodexRunner,
    FakeAgentClient,
    actual_run_status,
    agent_capabilities,
    create_actual_run_attestation,
    create_agent_task_spec,
)
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


def test_agent_capabilities_report_direct_unavailable_and_task_pack_available(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.delenv("GAPFORGE_ENABLE_REAL_RUNS", raising=False)
    monkeypatch.delenv("GAPFORGE_CODEX_COMMAND", raising=False)
    monkeypatch.delenv("GAPFORGE_CODEX_RUNNER_CMD", raising=False)

    capabilities = {item.mode: item for item in agent_capabilities(AgentRuntimeConfig.from_env())}

    assert capabilities["direct"].available is False
    assert "GAPFORGE_CODEX_COMMAND" in capabilities["direct"].required_env
    assert "GAPFORGE_CODEX_RUNNER_CMD" in capabilities["direct"].required_env
    assert capabilities["task_pack"].available is True
    assert capabilities["task_pack"].can_count_as_actual_run is True
    assert capabilities["fake"].can_count_as_actual_run is False


def test_setup_real_run_cli_renders_missing_environment(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.delenv("GAPFORGE_ENABLE_REAL_RUNS", raising=False)
    monkeypatch.delenv("GAPFORGE_CODEX_COMMAND", raising=False)
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")}

    result = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "setup-real-run"],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "direct" in result.stdout
    assert "task-pack" in result.stdout
    assert "manual-handoff" in result.stdout
    assert "GAPFORGE_ENABLE_REAL_RUNS" in result.stdout
    assert "GAPFORGE_CODEX_COMMAND" in result.stdout


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


def test_missing_attestation_blocks_actual_run_status(tmp_path: Path) -> None:
    manager, state = _agent_state(tmp_path)
    task = create_agent_task_spec(state, skill_name="novelty-gate", gap_id="gap-1")
    state.agent_task_specs.append(task)
    manager.save_run(state)
    _write_valid_novelty_outputs(state, task)

    CodexAgentClient(manager.config, AgentRuntimeConfig(mode="task-pack")).import_outputs(task, [])
    status = actual_run_status(manager.load_run(state.run_id))

    assert status["passed"] is False
    assert "No human attestation records Codex/GPT-5.4 as the producer." in status["blockers"]


def test_attested_task_pack_counts_only_after_validation(tmp_path: Path) -> None:
    manager, state = _agent_state(tmp_path)
    task = create_agent_task_spec(state, skill_name="novelty-gate", gap_id="gap-1")
    state.agent_task_specs.append(task)
    manager.save_run(state)

    before_validation = create_actual_run_attestation(
        state,
        task,
        agent_name="codex",
        model="gpt-5.4",
        execution_method="task_pack",
        attester="Test Reviewer",
    )
    assert before_validation.accepted_as_actual_run is False
    manager.save_run(state)

    _write_valid_novelty_outputs(state, task)
    CodexAgentClient(manager.config, AgentRuntimeConfig(mode="task-pack")).import_outputs(task, [])
    loaded = manager.load_run(state.run_id)
    after_validation = create_actual_run_attestation(
        loaded,
        task,
        agent_name="codex",
        model="gpt-5.4",
        execution_method="task_pack",
        attester="Test Reviewer",
    )
    manager.save_run(loaded)
    status = actual_run_status(manager.load_run(state.run_id))

    assert after_validation.accepted_as_actual_run is True
    assert status["passed"] is True
    assert task.id in status["accepted_task_ids"]


def test_fake_agent_does_not_count_as_actual_run(tmp_path: Path) -> None:
    manager, state = _agent_state(tmp_path)
    task = create_agent_task_spec(state, skill_name="deep-reading", paper_id="paper-1")
    state.agent_task_specs.append(task)
    manager.save_run(state)
    FakeAgentClient(manager.config).run_task(task)
    loaded = manager.load_run(state.run_id)

    create_actual_run_attestation(
        loaded,
        task,
        agent_name="fake-agent",
        model="gapforge-fake-agent",
        execution_method="fake",
        attester="CI",
    )
    status = actual_run_status(loaded)

    assert status["passed"] is False
    assert "Fake agent output never counts as actual-run acceptance." in status["blockers"]


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


def test_invalid_output_generates_repair_task(tmp_path: Path) -> None:
    manager, state = _agent_state(tmp_path)
    task = create_agent_task_spec(state, skill_name="novelty-gate", gap_id="gap-1")
    state.agent_task_specs.append(task)
    manager.save_run(state)
    output = tmp_path / "bad_novelty.json"
    output.write_text(
        json.dumps({"novelty_dossiers": [{"target_id": "gap-1", "top_prior_work": ["Fake Paper"], "verdict": "pursue"}]}),
        encoding="utf-8",
    )
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")}

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "gapforge.cli",
            "repair-agent-output",
            "--task-id",
            task.id,
            "--path",
            str(output),
            "--handoff",
        ],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["repair_created"] is True
    repair_id = payload["repair_record"]["id"]
    loaded = manager.load_run(state.run_id)
    assert loaded.agent_repair_records[0].id == repair_id
    repair_task_id = loaded.agent_repair_records[0].repair_task_id
    pack = Path(state.run_dir) / "agent_tasks" / repair_task_id
    assert (pack / "repair_context.json").exists()
    assert (pack / "REPAIR.md").exists()
    assert (pack / "HANDOFF.md").exists()


def test_repair_task_includes_validation_errors(tmp_path: Path) -> None:
    manager, state = _agent_state(tmp_path)
    task = create_agent_task_spec(state, skill_name="novelty-gate", gap_id="gap-1")
    state.agent_task_specs.append(task)
    manager.save_run(state)
    output = tmp_path / "bad_prior.json"
    output.write_text(
        json.dumps({"novelty_dossiers": [{"target_id": "gap-1", "top_prior_work": ["Fake Citation 2099"], "verdict": "pursue"}]}),
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "gapforge.cli",
            "repair-agent-output",
            "--task-id",
            task.id,
            "--path",
            str(output),
        ],
        cwd=tmp_path,
        env={**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")},
        text=True,
        capture_output=True,
        check=False,
    )

    payload = json.loads(result.stdout)
    pack = Path(payload["repair_task_pack"])
    task_text = (pack / "TASK.md").read_text(encoding="utf-8")
    context = json.loads((pack / "repair_context.json").read_text(encoding="utf-8"))
    assert "citation does not resolve" in task_text
    assert "Fake Citation 2099" in task_text
    assert context["validation"]["status"] == "invalid"


def test_fake_repaired_output_validates_and_imports(tmp_path: Path) -> None:
    manager, state = _agent_state(tmp_path)
    original = create_agent_task_spec(state, skill_name="novelty-gate", gap_id="gap-1")
    state.agent_task_specs.append(original)
    manager.save_run(state)
    bad = tmp_path / "bad.json"
    bad.write_text(
        json.dumps({"novelty_dossiers": [{"target_id": "gap-1", "top_prior_work": ["Fake Paper"], "verdict": "pursue"}]}),
        encoding="utf-8",
    )

    repair_result = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "repair-agent-output", "--task-id", original.id, "--path", str(bad)],
        cwd=tmp_path,
        env={**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")},
        text=True,
        capture_output=True,
        check=False,
    )
    repair_task_id = json.loads(repair_result.stdout)["repair_record"]["repair_task_id"]
    loaded = manager.load_run(state.run_id)
    repair_task = next(task for task in loaded.agent_task_specs if task.id == repair_task_id)
    _write_valid_novelty_outputs(loaded, repair_task)

    validation = CodexAgentClient(manager.config, AgentRuntimeConfig(mode="task-pack")).import_outputs(repair_task, [])

    assert validation.status == "valid"
    final_state = manager.load_run(state.run_id)
    assert final_state.novelty_dossiers[0].target_id == "gap-1"


def test_invalid_repaired_output_still_rejected(tmp_path: Path) -> None:
    manager, state = _agent_state(tmp_path)
    original = create_agent_task_spec(state, skill_name="novelty-gate", gap_id="gap-1")
    state.agent_task_specs.append(original)
    manager.save_run(state)
    bad = tmp_path / "bad.json"
    bad.write_text(
        json.dumps({"novelty_dossiers": [{"target_id": "gap-1", "top_prior_work": ["Fake Paper"], "verdict": "pursue"}]}),
        encoding="utf-8",
    )
    repair_result = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "repair-agent-output", "--task-id", original.id, "--path", str(bad)],
        cwd=tmp_path,
        env={**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")},
        text=True,
        capture_output=True,
        check=False,
    )
    repair_task_id = json.loads(repair_result.stdout)["repair_record"]["repair_task_id"]
    loaded = manager.load_run(state.run_id)
    repair_task = next(task for task in loaded.agent_task_specs if task.id == repair_task_id)
    outputs_dir = _task_outputs_dir(loaded, repair_task)
    outputs_dir.mkdir(parents=True, exist_ok=True)
    (outputs_dir / "novelty_dossiers_patch.json").write_text(
        json.dumps({"novelty_dossiers": [{"target_id": "gap-1", "top_prior_work": ["Fake Paper"], "verdict": "pursue"}]}),
        encoding="utf-8",
    )

    validation = CodexAgentClient(manager.config, AgentRuntimeConfig(mode="task-pack")).import_outputs(repair_task, [])

    assert validation.status == "invalid"
    assert not manager.load_run(state.run_id).novelty_dossiers


def test_repair_context_preserves_safe_accepted_partial_paths(tmp_path: Path) -> None:
    manager, state = _agent_state(tmp_path)
    task = create_agent_task_spec(state, skill_name="deep-reading", paper_id="paper-1")
    state.agent_task_specs.append(task)
    manager.save_run(state)
    good = tmp_path / "paper_notes_patch.json"
    good.write_text(json.dumps({"paper_notes": [{"paper_id": "paper-1", "confidence": "medium"}]}), encoding="utf-8")
    bad = tmp_path / "claims_patch.json"
    bad.write_text(
        json.dumps({"claims": [{"id": "claim-1", "text": "Certain unsupported.", "type": "result", "confidence": "high"}]}),
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "gapforge.cli",
            "repair-agent-output",
            "--task-id",
            task.id,
            "--path",
            str(good),
            "--path",
            str(bad),
        ],
        cwd=tmp_path,
        env={**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")},
        text=True,
        capture_output=True,
        check=False,
    )

    context = json.loads((Path(json.loads(result.stdout)["repair_task_pack"]) / "repair_context.json").read_text(encoding="utf-8"))
    assert str(good.resolve()) in context["validation"]["accepted_output_paths"]
    assert str(bad.resolve()) in context["validation"]["rejected_output_paths"]


def test_repair_status_cli_renders_record(tmp_path: Path) -> None:
    manager, state = _agent_state(tmp_path)
    task = create_agent_task_spec(state, skill_name="novelty-gate", gap_id="gap-1")
    state.agent_task_specs.append(task)
    manager.save_run(state)
    output = tmp_path / "bad.json"
    output.write_text(
        json.dumps({"novelty_dossiers": [{"target_id": "gap-1", "top_prior_work": ["Fake Paper"], "verdict": "pursue"}]}),
        encoding="utf-8",
    )
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")}
    repair_result = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "repair-agent-output", "--task-id", task.id, "--path", str(output)],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    repair_id = json.loads(repair_result.stdout)["repair_record"]["id"]

    status = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "repair-status", "--repair-id", repair_id],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert status.returncode == 0, status.stderr
    assert "Agent Repair Status" in status.stdout
    assert repair_id in status.stdout


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

    capabilities = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "agent-capabilities", "--json"],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert capabilities.returncode == 0, capabilities.stderr
    capability_payload = {item["mode"]: item for item in json.loads(capabilities.stdout)}
    assert capability_payload["direct"]["available"] is False
    assert capability_payload["task_pack"]["available"] is True

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

    codex_handoff = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "codex-run", "--task-id", task_id, "--handoff"],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert codex_handoff.returncode == 0, codex_handoff.stderr
    handoff_record = json.loads(codex_handoff.stdout)
    assert handoff_record["status"] == "planned"
    assert handoff_record["usage_summary"]["mode"] == "handoff"

    codex_status = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "codex-run-status", "--agent-run-id", handoff_record["id"]],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert codex_status.returncode == 0, codex_status.stderr
    assert json.loads(codex_status.stdout)["id"] == handoff_record["id"]

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

    actual_status = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "actual-run-status", "--run-id", state.run_id],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert actual_status.returncode == 0, actual_status.stderr
    assert json.loads(actual_status.stdout)["passed"] is False


def test_codex_runner_no_command_writes_handoff(tmp_path: Path) -> None:
    manager, state = _agent_state(tmp_path)
    task = create_agent_task_spec(state, skill_name="deep-reading", paper_id="paper-1")
    state.agent_task_specs.append(task)
    manager.save_run(state)

    record = CodexRunner(manager.config, AgentRuntimeConfig(mode="direct", enable_real_runs=False)).run(task)

    assert record.status == "planned"
    assert record.usage_summary["mode"] == "handoff"
    assert record.usage_summary["direct_available"] is False
    handoff = Path(state.run_dir) / "agent_tasks" / task.id / "HANDOFF.md"
    assert handoff.exists()
    assert "gapforge validate-agent-output" in handoff.read_text(encoding="utf-8")


def test_codex_runner_require_direct_fails_without_command(tmp_path: Path) -> None:
    manager, state = _agent_state(tmp_path)
    task = create_agent_task_spec(state, skill_name="deep-reading", paper_id="paper-1")
    state.agent_task_specs.append(task)
    manager.save_run(state)

    try:
        CodexRunner(manager.config, AgentRuntimeConfig(mode="direct", enable_real_runs=True)).run(task, require_direct=True)
    except AgentUnavailableError as exc:
        assert "GAPFORGE_CODEX_COMMAND" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("require-direct should fail when no command is configured.")


def test_codex_runner_fake_command_imports_valid_output_and_redacts_logs(tmp_path: Path) -> None:
    manager, state = _agent_state(tmp_path)
    task = create_agent_task_spec(state, skill_name="deep-reading", paper_id="paper-1")
    state.agent_task_specs.append(task)
    manager.save_run(state)
    script = tmp_path / "write_valid_agent_output.py"
    script.write_text(
        """
import json
import pathlib
import sys

out = pathlib.Path(sys.argv[1])
out.mkdir(parents=True, exist_ok=True)
(out / "paper_notes_patch.json").write_text(json.dumps({
    "paper_notes": [{
        "paper_id": "paper-1",
        "citation_key": "researcher2025low",
        "one_sentence_summary": "Valid Codex runner output.",
        "confidence": "medium",
        "created_by_skill": "codex-runner"
    }]
}))
(out / "claims_patch.json").write_text(json.dumps({"claims": []}))
(out / "evidence_spans_patch.json").write_text(json.dumps({"evidence_spans": []}))
print("token=sk-testSECRET1234567890")
""".strip(),
        encoding="utf-8",
    )
    runtime = AgentRuntimeConfig(
        mode="direct",
        enable_real_runs=True,
        codex_command=f'"{sys.executable}" "{script}" "{{outputs_dir}}"',
        codex_timeout_seconds=10,
    )

    record = CodexRunner(manager.config, runtime).run(task, prefer_direct=True)

    assert record.status == "complete"
    assert "sk-testSECRET" not in record.usage_summary["stdout_preview"]
    assert "[REDACTED]" in record.usage_summary["stdout_preview"]
    loaded = manager.load_run(state.run_id)
    assert loaded.paper_notes[0].paper_id == "paper-1"
    assert loaded.agent_validation_results[-1].status == "valid"
    assert loaded.agent_run_records[-1].id == record.id


def test_codex_runner_invalid_output_is_rejected(tmp_path: Path) -> None:
    manager, state = _agent_state(tmp_path)
    task = create_agent_task_spec(state, skill_name="novelty-gate", gap_id="gap-1")
    state.agent_task_specs.append(task)
    manager.save_run(state)
    script = tmp_path / "write_invalid_agent_output.py"
    script.write_text(
        """
import json
import pathlib
import sys

out = pathlib.Path(sys.argv[1])
out.mkdir(parents=True, exist_ok=True)
(out / "novelty_dossiers_patch.json").write_text(json.dumps({
    "novelty_dossiers": [{
        "target_id": "gap-1",
        "idea_summary": "Duplicate-looking idea.",
        "top_prior_work": ["Imaginary Prior Work 2099"],
        "verdict": "pursue",
        "novelty_strength": "strong",
        "confidence": "high"
    }]
}))
(out / "novelty_assessments_patch.json").write_text(json.dumps({"novelty_assessments": []}))
(out / "rejected_ideas_patch.json").write_text(json.dumps({"rejected_ideas": []}))
""".strip(),
        encoding="utf-8",
    )
    runtime = AgentRuntimeConfig(
        mode="direct",
        enable_real_runs=True,
        codex_command=f'"{sys.executable}" "{script}" "{{outputs_dir}}"',
        codex_timeout_seconds=10,
    )

    record = CodexRunner(manager.config, runtime).run(task, prefer_direct=True)

    assert record.status == "failed"
    assert "Output validation failed" in record.error
    loaded = manager.load_run(state.run_id)
    assert not loaded.novelty_dossiers
    assert loaded.agent_validation_results[-1].status == "invalid"


def test_codex_runner_timeout_is_recorded(tmp_path: Path) -> None:
    manager, state = _agent_state(tmp_path)
    task = create_agent_task_spec(state, skill_name="deep-reading", paper_id="paper-1")
    state.agent_task_specs.append(task)
    manager.save_run(state)
    runtime = AgentRuntimeConfig(
        mode="direct",
        enable_real_runs=True,
        codex_command=f'"{sys.executable}" -c "import time; time.sleep(2)"',
        codex_timeout_seconds=1,
    )

    record = CodexRunner(manager.config, runtime).run(task, prefer_direct=True)

    assert record.status == "failed"
    assert record.usage_summary["timed_out"] is True
    assert "timed out" in record.error


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


def _write_valid_novelty_outputs(state: ResearchRunState, task: AgentTaskSpec) -> None:
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
                ]
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
