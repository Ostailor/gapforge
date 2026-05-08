from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from gapforge.config import GapForgeConfig
from gapforge.ideas import IdeaCodexTaskManager, IdeaStore, TopicPortfolioGenerator
from gapforge.models import ProjectMemoryRecord, Provenance
from gapforge.project_memory import ProjectMemoryManager
from gapforge.state import utc_now_iso

LOW_FPR_TOPIC = "low false-positive collusion detection in LLM multi-agent systems"


def test_idea_codex_task_pack_generated(tmp_path: Path) -> None:
    config, project_id = _project(tmp_path)
    TopicPortfolioGenerator(config).generate(project_id=project_id, root_topic=LOW_FPR_TOPIC)
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")}

    created = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "idea-codex-task", "--project-id", project_id, "--type", "idea_seed_expansion"],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert created.returncode == 0, created.stderr
    task = json.loads(created.stdout)
    task_dir = Path(task["task_dir"])

    prompt = (task_dir / "IDEA_CODEX_TASK.md").read_text(encoding="utf-8")
    assert "topic portfolio" in prompt.lower()
    assert "existing idea bank" in prompt.lower()
    assert "rejected ideas" in prompt.lower()
    assert "prior-work blockers" in prompt.lower()
    assert "source coverage summary" in prompt.lower()
    assert "evidence links" in prompt.lower()
    assert "human preferences" in prompt.lower()
    assert "Do not invent citations" in prompt
    assert "public reasoning summaries only" in prompt
    assert (task_dir / "expected_outputs.json").exists()
    assert (task_dir / "schema_examples.json").exists()
    assert (task_dir / "outputs").is_dir()

    handoff = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "idea-codex-handoff", "--task-id", task["id"]],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert handoff.returncode == 0, handoff.stderr
    assert f"Task ID: `{task['id']}`" in handoff.stdout


def test_valid_candidate_imports(tmp_path: Path) -> None:
    config, project_id = _project(tmp_path)
    manager = IdeaCodexTaskManager(config)
    task = manager.create_task(project_id, "idea_seed_expansion")
    _write_candidate_patch(
        task,
        [
            {
                "title": "Specificity-first benign trace benchmark",
                "summary": "A seed benchmark idea, not a result claim.",
                "contribution_type": "benchmark",
                "proposed_experiment": "Evaluate false positive rate on benign and collusive traces.",
                "expected_baselines": ["rule detector"],
                "expected_metrics": ["false positive rate"],
                "closest_prior_work_ids": ["paper-known"],
                "novelty_status": "unchecked",
                "maturity": "seed",
                "likely_failure_mode": "May duplicate existing benchmarks.",
            }
        ],
    )

    record = manager.import_outputs(task.id)
    state = IdeaStore(config).load_state(project_id)

    assert record.status == "applied"
    assert len(record.accepted_objects) == 1
    assert not record.rejected_objects
    assert any(candidate.title == "Specificity-first benign trace benchmark" for candidate in state.candidates)


def test_fake_citation_rejected(tmp_path: Path) -> None:
    config, project_id = _project(tmp_path)
    manager = IdeaCodexTaskManager(config)
    task = manager.create_task(project_id, "idea_seed_expansion")
    _write_candidate_patch(
        task,
        [
            {
                "title": "Evidence-backed benchmark seed",
                "summary": "Uses an unknown citation.",
                "contribution_type": "benchmark",
                "closest_prior_work_ids": ["paper-fake"],
            }
        ],
    )

    record = manager.import_outputs(task.id)
    state = IdeaStore(config).load_state(project_id)

    assert record.status == "rejected"
    assert any("fake or unresolved citation" in item["reason"] for item in record.rejected_objects)
    assert not state.candidates


def test_generic_idea_downgraded_or_rejected(tmp_path: Path) -> None:
    config, project_id = _project(tmp_path)
    manager = IdeaCodexTaskManager(config)
    task = manager.create_task(project_id, "idea_seed_expansion")
    _write_candidate_patch(
        task,
        [
            {
                "title": "Research idea",
                "summary": "Too generic.",
                "contribution_type": "measurement",
            }
        ],
    )

    record = manager.import_outputs(task.id)

    assert record.status == "rejected"
    assert any("generic idea rejected" in item["reason"] for item in record.rejected_objects)


def test_unsupported_strong_novelty_blocked(tmp_path: Path) -> None:
    config, project_id = _project(tmp_path)
    manager = IdeaCodexTaskManager(config)
    task = manager.create_task(project_id, "idea_seed_expansion")
    _write_candidate_patch(
        task,
        [
            {
                "title": "Low-FPR benign trace audit protocol",
                "summary": "Claims strong novelty without prior-work gates.",
                "contribution_type": "evaluation_protocol",
                "novelty_status": "strong",
            }
        ],
    )

    record = manager.import_outputs(task.id)

    assert record.status == "rejected"
    assert any("strong novelty rejected" in item["reason"] for item in record.rejected_objects)


def test_results_claim_rejected(tmp_path: Path) -> None:
    config, project_id = _project(tmp_path)
    manager = IdeaCodexTaskManager(config)
    task = manager.create_task(project_id, "idea_seed_expansion")
    _write_candidate_patch(
        task,
        [
            {
                "title": "Low-FPR benchmark with claimed win",
                "summary": "Results show this benchmark outperforms prior monitors.",
                "contribution_type": "benchmark",
                "closest_prior_work_ids": ["paper-known"],
            }
        ],
    )

    record = manager.import_outputs(task.id)

    assert record.status == "rejected"
    assert any("results are not accepted" in item["reason"] for item in record.rejected_objects)


def _write_candidate_patch(task, candidates: list[dict]) -> None:  # noqa: ANN001
    outputs = Path(task.outputs_dir)
    outputs.mkdir(parents=True, exist_ok=True)
    (outputs / "idea_candidates_patch.json").write_text(
        json.dumps({"idea_candidates": candidates, "public_reasoning_summary": "Public validation summary."}, indent=2) + "\n",
        encoding="utf-8",
    )


def _project(tmp_path: Path) -> tuple[GapForgeConfig, str]:
    config = GapForgeConfig.from_cwd(tmp_path)
    manager = ProjectMemoryManager(config)
    program = manager.create_project(LOW_FPR_TOPIC)
    program.memory_records.append(
        ProjectMemoryRecord(
            id="memory-known-prior",
            project_id=program.project.id,
            record_type="prior_work",
            text="Known prior work for low-FPR collusion monitoring.",
            linked_paper_ids=["paper-known"],
            status="active",
        )
    )
    program.provenance.append(
        Provenance(
            created_by_skill="test",
            timestamp=utc_now_iso(),
            reasoning_summary="Test fixture project for idea Codex tasks.",
        )
    )
    manager.save_project(program)
    IdeaStore(config).create_bank(project_id=program.project.id, root_topic=LOW_FPR_TOPIC)
    return config, program.project.id
