from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from gapforge.config import GapForgeConfig
from gapforge.ideas import CrossDomainIdeaTransferEngine, IdeaStore
from gapforge.ideas.cross_domain_transfer import TransferPattern, validate_transfer_pattern
from gapforge.models import ProjectMemoryRecord, Provenance
from gapforge.project_memory import ProjectMemoryManager
from gapforge.state import utc_now_iso

LOW_FPR_TOPIC = "low false-positive collusion detection in LLM multi-agent systems"


def test_medicine_specificity_transfer_creates_search_request(tmp_path: Path) -> None:
    config, project_id = _project(tmp_path)

    result = CrossDomainIdeaTransferEngine(config).transfer_for_project(project_id)
    medicine = next(transfer for transfer in result.transfers if transfer.source_field == "medicine screening/specificity")
    state = IdeaStore(config).load_state(project_id)

    assert medicine.target_idea_id == ""
    assert medicine.supporting_source_papers == []
    assert medicine.required_searches
    assert result.promoted_idea_ids == []
    assert not state.candidates


def test_cartel_detection_transfer_creates_candidate_only_with_evidence(tmp_path: Path) -> None:
    config, project_id = _project(tmp_path)
    manager = ProjectMemoryManager(config)
    program = manager.load_project(project_id)
    program.memory_records.append(
        ProjectMemoryRecord(
            id="memory-cartel-source",
            project_id=project_id,
            record_type="cross_domain_source",
            text="Cartel detection economics uses structural screens for tacit collusion in repeated markets.",
            linked_paper_ids=["paper-cartel-screen"],
            status="active",
        )
    )
    manager.save_project(program)

    result = CrossDomainIdeaTransferEngine(config).transfer_for_project(project_id)
    cartel = next(transfer for transfer in result.transfers if transfer.source_field == "cartel detection economics")
    state = IdeaStore(config).load_state(project_id)

    assert cartel.supporting_source_papers == ["paper-cartel-screen"]
    assert cartel.target_idea_id
    assert cartel.target_idea_id in result.promoted_idea_ids
    assert any(candidate.id == cartel.target_idea_id for candidate in state.candidates)
    assert state.idea_bank is not None
    assert cartel.target_idea_id in state.idea_bank.candidate_ids


def test_shallow_analogy_rejected() -> None:
    shallow = TransferPattern(
        source_field="fraud detection",
        source_concept="fraud alerts",
        triggers=("fraud",),
        transfer_mechanism="Fraud detection is like collusion detection.",
        required_adaptation="Map fraud to collusion.",
        what_breaks="Labels differ.",
        idea_title="Shallow fraud analogy",
        idea_summary="A shallow analogy.",
        expected_metrics=("false positive rate",),
        required_searches=("fraud detection collusion",),
    )

    with pytest.raises(ValueError, match="technical mechanism"):
        validate_transfer_pattern(shallow)


def test_transfer_report_renders_and_topic_cli_creates_project(tmp_path: Path) -> None:
    config = GapForgeConfig.from_cwd(tmp_path)
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")}

    generated = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "transfer-ideas", "--topic", LOW_FPR_TOPIC],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert generated.returncode == 0, generated.stderr
    payload = json.loads(generated.stdout)
    project_id = payload["project_id"]
    assert any(transfer["source_field"] == "medicine screening/specificity" for transfer in payload["transfers"])

    report = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "transfer-report", "--project-id", project_id],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert report.returncode == 0, report.stderr
    assert "# Cross-Domain Idea Transfer Report" in report.stdout
    assert "Transfer mechanism" in report.stdout
    assert "What breaks" in report.stdout
    assert (config.project_root / project_id / "ideas" / "transfer_candidates.json").exists()
    assert (config.project_root / project_id / "ideas" / "reports" / "cross_domain_transfers.md").exists()


def _project(tmp_path: Path) -> tuple[GapForgeConfig, str]:
    config = GapForgeConfig.from_cwd(tmp_path)
    manager = ProjectMemoryManager(config)
    program = manager.create_project(LOW_FPR_TOPIC)
    program.provenance.append(
        Provenance(
            created_by_skill="test",
            timestamp=utc_now_iso(),
            reasoning_summary="Test fixture project for cross-domain idea transfer.",
        )
    )
    manager.save_project(program)
    return config, program.project.id
