from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from test_release_gate_v22 import _complete_v22_fixture, _env

from gapforge.release_gate.v23 import V23ReleaseGateEnforcer
from gapforge.selected_benchmark.main_power import MainPowerManager, render_main_power_report


def test_alpha_001_powered_plan_passes_if_counts_sufficient(tmp_path: Path) -> None:
    config, _project_id, benchmark_id = _complete_v22_fixture(tmp_path)

    manager = MainPowerManager(config)
    plan = manager.create_plan(benchmark_id, planned_negative_count=3000, planned_positive_count=500)
    decision = manager.decide_alpha(benchmark_id, alpha_level=0.001)

    assert plan.required_negative_counts["0.001"] <= plan.planned_negative_count
    assert plan.primary_alpha == 0.001
    assert decision.decision == "power"
    assert decision.required_count == plan.required_negative_counts["0.001"]
    assert decision.planned_count == 3000
    assert decision.blockers == []


def test_alpha_001_downgrade_recorded_if_counts_insufficient(tmp_path: Path) -> None:
    config, _project_id, benchmark_id = _complete_v22_fixture(tmp_path)

    manager = MainPowerManager(config)
    plan = manager.create_plan(benchmark_id, planned_negative_count=300, planned_positive_count=150)
    decision = manager.decide_alpha(benchmark_id, alpha_level=0.001)

    assert plan.primary_alpha == 0.01
    assert plan.feasibility_status == "alpha_0_001_infeasible"
    assert decision.decision == "downgrade"
    assert decision.required_count > decision.planned_count
    assert any("alpha=0.001" in blocker for blocker in decision.blockers)


def test_v23_release_gate_blocks_without_alpha_decision(tmp_path: Path) -> None:
    config, _project_id, benchmark_id = _complete_v22_fixture(tmp_path)
    MainPowerManager(config).create_plan(benchmark_id, planned_negative_count=3000, planned_positive_count=500)

    result = V23ReleaseGateEnforcer(config).evaluate()

    assert result.passed is False
    assert result.requirements["main_alpha_001_decision_exists"] is False
    assert any("main_alpha_001_decision_exists" in blocker for blocker in result.blockers)


def test_main_power_report_renders_and_cli_commands(tmp_path: Path) -> None:
    config, _project_id, benchmark_id = _complete_v22_fixture(tmp_path)
    manager = MainPowerManager(config)
    manager.create_plan(benchmark_id, planned_negative_count=300, planned_positive_count=150)
    manager.decide_alpha(benchmark_id, alpha_level=0.001)

    report = render_main_power_report(manager.load_plan(benchmark_id), manager.load_decisions(benchmark_id))

    assert "# Main-Scale Power Report" in report
    assert "alpha=0.001" in report
    assert "downgrade" in report
    assert "Publication claims must use primary alpha=0.01" in report

    cli = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "selected-main-power-report", "--benchmark-id", benchmark_id],
        cwd=tmp_path,
        env=_env(),
        text=True,
        capture_output=True,
        check=False,
    )

    assert cli.returncode == 0, cli.stderr
    assert "Release Notes Alpha Decision" in cli.stdout
    assert "alpha=0.001" in cli.stdout
