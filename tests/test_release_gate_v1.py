from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from gapforge.config import GapForgeConfig
from gapforge.models import PilotRunRecord
from gapforge.pilots import ExternalPilotReviewManager, PilotStore
from gapforge.release_gate.v1 import V1ReadinessGate, render_v1_readiness_markdown


def test_v1_readiness_missing_pilot_fails(tmp_path: Path) -> None:
    config = GapForgeConfig.from_cwd(tmp_path)
    _write_release_prerequisites(config)
    _write_audits(config)
    _write_full_project_report(config)

    result = V1ReadinessGate(config).evaluate()

    assert result.passed is False
    assert result.requirements["v09_pilot_outcome_accepted"] is False
    assert result.requirements["external_human_pilot_review_exists"] is False
    assert result.recommended_next_version == "v0.9"


def test_v1_readiness_correct_refusal_pilot_can_pass(tmp_path: Path) -> None:
    config = _complete_v1_fixture(tmp_path, outcome_type="correct_refusal")

    result = V1ReadinessGate(config).evaluate()

    assert result.passed is True
    assert result.pilot_outcome_type == "correct_refusal"
    assert result.recommended_next_version == "v1"


def test_v1_readiness_product_failure_blocks(tmp_path: Path) -> None:
    config = _complete_v1_fixture(tmp_path)
    PilotStore(config).save_record(
        PilotRunRecord(
            id="pilot-v09-product-failure",
            pilot_id="low_fpr_collusion",
            status="product_failure",
            outcome_type="product_failure",
            blockers=["product_failure: fake citation accepted by pilot report"],
        )
    )

    result = V1ReadinessGate(config).evaluate()

    assert result.passed is False
    assert result.requirements["no_unresolved_product_failures"] is False
    assert result.recommended_next_version == "v0.9.1"
    assert any("Unresolved product failure" in blocker for blocker in result.blockers)


def test_v1_readiness_missing_migration_audit_blocks(tmp_path: Path) -> None:
    config = _complete_v1_fixture(tmp_path, skip_audit="migration_audit_passed")

    result = V1ReadinessGate(config).evaluate()

    assert result.passed is False
    assert result.requirements["migration_audit_passed"] is False
    assert "Migration/backward compatibility audit has not passed." in result.blockers


def test_v1_readiness_complete_fixture_passes_and_writes_report(tmp_path: Path) -> None:
    config = _complete_v1_fixture(tmp_path, outcome_type="defensible_direction")
    enforcer = V1ReadinessGate(config)

    result = enforcer.evaluate()
    json_path, md_path = enforcer.write_outputs(result)
    rendered = render_v1_readiness_markdown(result)

    assert result.passed is True
    assert all(result.requirements.values())
    assert "v1 Readiness Gate" in rendered
    assert json.loads(json_path.read_text(encoding="utf-8"))["passed"] is True
    assert md_path == config.root / "docs" / "releases" / "v1-readiness-latest.md"
    assert md_path.exists()


def test_v1_readiness_cli_json(tmp_path: Path) -> None:
    config = _complete_v1_fixture(tmp_path)
    env = {"PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")}

    completed = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "v1-readiness", "--json"],
        cwd=config.root,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    assert json.loads(completed.stdout)["recommended_next_version"] == "v1"


def _complete_v1_fixture(
    tmp_path: Path,
    *,
    outcome_type: str = "correct_refusal",
    skip_audit: str = "",
) -> GapForgeConfig:
    config = GapForgeConfig.from_cwd(tmp_path)
    _write_release_prerequisites(config)
    _write_audits(config, skip=skip_audit)
    _write_full_project_report(config)
    _write_accepted_pilot(config, outcome_type=outcome_type)
    return config


def _write_release_prerequisites(config: GapForgeConfig) -> None:
    release_dir = config.data_dir / "release_gate"
    release_dir.mkdir(parents=True, exist_ok=True)
    (release_dir / "deterministic_ci.json").write_text('{"passed": true}\n', encoding="utf-8")
    for version in ["v0.4", "v0.5", "v0.6", "v0.7", "v0.8"]:
        (release_dir / f"{version}_latest.json").write_text('{"passed": true, "status": "pass"}\n', encoding="utf-8")


def _write_audits(config: GapForgeConfig, *, skip: str = "") -> None:
    filenames = {
        "migration_audit_passed": "migration_audit.json",
        "cli_audit_passed": "cli_audit.json",
        "docs_audit_passed": "docs_audit.json",
        "artifact_hygiene_audit_passed": "artifact_hygiene_audit.json",
    }
    release_dir = config.data_dir / "release_gate"
    release_dir.mkdir(parents=True, exist_ok=True)
    for name, filename in filenames.items():
        if name == skip:
            continue
        (release_dir / filename).write_text('{"passed": true, "status": "pass"}\n', encoding="utf-8")


def _write_full_project_report(config: GapForgeConfig) -> None:
    path = config.project_root / "v1-project" / "reports" / "final_pilot_report.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("# Final Pilot Report\n\nEnd-to-end pilot report fixture.\n", encoding="utf-8")


def _write_accepted_pilot(config: GapForgeConfig, *, outcome_type: str) -> None:
    artifact_paths = {"accepted_direction_id": "direction-low-fpr-monitoring"} if outcome_type == "defensible_direction" else {}
    record = PilotRunRecord(
        id=f"pilot-v09-{outcome_type}",
        pilot_id="low_fpr_collusion",
        status="direction_ready" if outcome_type == "defensible_direction" else "refusal_ready",
        outcome_type=outcome_type,
        artifact_paths=artifact_paths,
        blockers=["research_refusal: source coverage blocks novelty claim"] if outcome_type == "correct_refusal" else [],
    )
    PilotStore(config).save_record(record)
    ExternalPilotReviewManager(config).create_review(record.id, accept_outcome=True, reviewer_role="user")
