from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from gapforge.config import GapForgeConfig
from gapforge.models import IdeaGateAssessment, PilotRunRecord, Provenance, to_plain
from gapforge.pilots import ExternalPilotReviewManager, PilotStore
from gapforge.release_gate.v09 import V09ReleaseGateEnforcer, render_v09_release_gate_markdown


def test_v09_release_gate_no_pilot_fails(tmp_path: Path) -> None:
    config = GapForgeConfig.from_cwd(tmp_path)
    _write_release_prerequisites(config)

    result = V09ReleaseGateEnforcer(config).evaluate()

    assert result.passed is False
    assert result.requirements["pilot_run_exists"] is False
    assert "No v0.9 pilot run record was found." in result.blockers


def test_v09_release_gate_accepted_direction_passes(tmp_path: Path) -> None:
    config = _complete_v09_fixture(tmp_path, outcome_type="defensible_direction")

    result = V09ReleaseGateEnforcer(config).evaluate()

    assert result.passed is True
    assert result.requirements["accepted_defensible_direction"] is True
    assert result.recommended_next_version == "v1"


def test_v09_release_gate_accepted_refusal_passes(tmp_path: Path) -> None:
    config = _complete_v09_fixture(tmp_path, outcome_type="correct_refusal")

    result = V09ReleaseGateEnforcer(config).evaluate()

    assert result.passed is True
    assert result.requirements["accepted_correct_refusal"] is True
    assert result.pilot_outcome_type == "correct_refusal"


def test_v09_release_gate_product_failure_fails(tmp_path: Path) -> None:
    config = _complete_v09_fixture(tmp_path)
    PilotStore(config).save_record(
        PilotRunRecord(
            id="pilot-v09-product-failure",
            pilot_id="low_fpr_collusion",
            status="product_failure",
            outcome_type="product_failure",
            blockers=["product_failure: report overclaim accepted fake result"],
        )
    )

    result = V09ReleaseGateEnforcer(config).evaluate()

    assert result.passed is False
    assert result.requirements["no_unresolved_product_failure"] is False
    assert result.recommended_next_version == "v0.9.1"


def test_v09_release_gate_missing_review_fails(tmp_path: Path) -> None:
    config = _complete_v09_fixture(tmp_path, with_review=False)

    result = V09ReleaseGateEnforcer(config).evaluate()

    assert result.passed is False
    assert result.requirements["human_external_review_exists"] is False
    assert result.requirements["accepted_direction_or_refusal"] is False


def test_v09_release_gate_missing_audits_fail(tmp_path: Path) -> None:
    config = _complete_v09_fixture(tmp_path, skip_audit="docs_audit_generated")

    result = V09ReleaseGateEnforcer(config).evaluate()

    assert result.passed is False
    assert result.requirements["docs_audit_generated"] is False
    assert "Docs audit has not been generated." in result.blockers


def test_v09_release_gate_writes_report_and_cli_json(tmp_path: Path) -> None:
    config = _complete_v09_fixture(tmp_path)
    enforcer = V09ReleaseGateEnforcer(config)

    result = enforcer.evaluate()
    json_path, md_path = enforcer.write_outputs(result)
    rendered = render_v09_release_gate_markdown(result)

    assert result.passed is True
    assert "v0.9 External Pilot Release Gate" in rendered
    assert json.loads(json_path.read_text(encoding="utf-8"))["passed"] is True
    assert md_path.exists()

    completed = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "v9-release-gate", "--json"],
        cwd=config.root,
        env={"PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")},
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    assert json.loads(completed.stdout)["recommended_next_version"] == "v1"


def _complete_v09_fixture(
    tmp_path: Path,
    *,
    outcome_type: str = "defensible_direction",
    with_review: bool = True,
    skip_audit: str = "",
) -> GapForgeConfig:
    config = GapForgeConfig.from_cwd(tmp_path)
    _write_release_prerequisites(config, skip_audit=skip_audit)
    _write_pilot(config, outcome_type=outcome_type, with_review=with_review)
    return config


def _write_release_prerequisites(config: GapForgeConfig, *, skip_audit: str = "") -> None:
    release_dir = config.data_dir / "release_gate"
    release_dir.mkdir(parents=True, exist_ok=True)
    (release_dir / "v0.8_latest.json").write_text('{"passed": true, "status": "pass"}\n', encoding="utf-8")
    audit_files = {
        "v1_readiness_report_generated": "v1_readiness_latest.json",
        "migration_audit_generated": "migration_audit.json",
        "cli_audit_generated": "cli_audit.json",
        "docs_audit_generated": "docs_audit.json",
        "artifact_hygiene_audit_generated": "artifact_hygiene_audit.json",
    }
    for name, filename in audit_files.items():
        if name == skip_audit:
            continue
        (release_dir / filename).write_text('{"passed": true, "status": "pass"}\n', encoding="utf-8")


def _write_pilot(config: GapForgeConfig, *, outcome_type: str, with_review: bool) -> None:
    record = PilotRunRecord(
        id=f"pilot-v09-{outcome_type}",
        pilot_id="low_fpr_collusion",
        project_id="low-fpr-project",
        status="direction_ready" if outcome_type == "defensible_direction" else "refusal_ready",
        outcome_type=outcome_type,
        artifact_paths=_artifact_paths_for_outcome(outcome_type),
        blockers=["research_refusal: novelty and source coverage blockers prevent a defensible direction"]
        if outcome_type == "correct_refusal"
        else [],
    )
    PilotStore(config).save_record(record)
    if with_review:
        ExternalPilotReviewManager(config).create_review(record.id, accept_outcome=True, reviewer_role="user")
    _write_idea_gate(config, record.id, outcome_type=outcome_type)


def _artifact_paths_for_outcome(outcome_type: str) -> dict[str, str]:
    if outcome_type == "correct_refusal":
        return {
            "explicit_missing_searches_or_experiments": "reports/refusal.md",
        }
    return {
        "accepted_direction_id": "direction-low-fpr-collusion",
        "evidence_backed_gap": "reports/gap.md",
        "related_work_matrix": "related_work_matrix.md",
        "novelty_dossiers": "novelty_dossiers.md",
        "prior_work_recall_assessment": "prior_work_recall.md",
        "experiment_protocol": "experiment_protocols.md",
        "reviewer_panel": "review_panel.md",
    }


def _write_idea_gate(config: GapForgeConfig, pilot_id: str, *, outcome_type: str) -> None:
    assessment = IdeaGateAssessment(
        pilot_id=pilot_id,
        candidate_direction_ids=["direction-low-fpr-collusion"] if outcome_type == "defensible_direction" else [],
        selected_direction_id="direction-low-fpr-collusion" if outcome_type == "defensible_direction" else "",
        rejected_direction_ids=[],
        selection_reason="Fixture idea gate ran.",
        acceptance_status="accepted" if outcome_type == "defensible_direction" else "refusal",
        provenance=Provenance(created_by_skill="idea-gate"),
    )
    path = config.data_dir / "pilots" / pilot_id / "idea_gate_assessment.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(to_plain(assessment), indent=2) + "\n", encoding="utf-8")
