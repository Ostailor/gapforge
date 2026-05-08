from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from gapforge.config import GapForgeConfig
from gapforge.ideas import IdeaStore, TopicPortfolioGenerator
from gapforge.models import ProjectMemoryRecord, Provenance
from gapforge.project_memory import ProjectMemoryManager
from gapforge.state import utc_now_iso

LOW_FPR_TOPIC = "low false-positive collusion detection in LLM multi-agent systems"


def test_topic_portfolio_generates_distinct_transformation_types(tmp_path: Path) -> None:
    config, project_id = _project(tmp_path)
    portfolio = TopicPortfolioGenerator(config).generate(project_id=project_id, root_topic=LOW_FPR_TOPIC)

    transformation_types = {variant.transformation_type for variant in portfolio.topic_variants}

    assert len(portfolio.topic_variants) >= 8
    assert {
        "narrower",
        "adjacent",
        "cross_domain",
        "metric_shift",
        "threat_model_shift",
        "benchmark_shift",
        "theory_shift",
    }.issubset(transformation_types)
    assert all(variant.promise for variant in portfolio.topic_variants)
    assert all(variant.risk for variant in portfolio.topic_variants)
    assert all(variant.expected_search_queries for variant in portfolio.topic_variants)


def test_prior_refusals_influence_topic_variants(tmp_path: Path) -> None:
    config, project_id = _project(tmp_path)
    manager = ProjectMemoryManager(config)
    program = manager.load_project(project_id)
    program.memory_records.append(
        ProjectMemoryRecord(
            id="memory-rejected-generic-monitor",
            project_id=project_id,
            record_type="rejected_idea",
            text="Generic LLM monitor benchmark | Reason: too generic and lacked benign negative cases",
            status="rejected",
            provenance=Provenance(
                created_by_skill="test",
                timestamp=utc_now_iso(),
                reasoning_summary="Rejected idea fixture.",
            ),
        )
    )
    manager.save_project(program)

    portfolio = TopicPortfolioGenerator(config).generate(project_id=project_id, root_topic=LOW_FPR_TOPIC)

    combined = "\n".join(f"{variant.rationale}\n{variant.risk}" for variant in portfolio.topic_variants)
    assert "Prior refusal context" in combined
    assert "too generic" in combined
    assert "benign negative cases" in combined


def test_prior_rejected_idea_candidates_influence_topic_variants(tmp_path: Path) -> None:
    config, project_id = _project(tmp_path)
    idea_store = IdeaStore(config)
    idea_store.create_bank(project_id=project_id, root_topic=LOW_FPR_TOPIC)
    candidate = idea_store.add_candidate(
        project_id=project_id,
        source_topic_id="topic-low-fpr",
        title="Vague monitor proposal",
        summary="Generic monitor idea.",
    )
    idea_store.reject_candidate(candidate.id, "already covered by prior monitor papers")

    portfolio = TopicPortfolioGenerator(config).generate(project_id=project_id)

    combined = "\n".join(variant.rationale for variant in portfolio.topic_variants)
    assert "already covered by prior monitor papers" in combined


def test_cross_domain_topics_are_not_shallow_synonyms(tmp_path: Path) -> None:
    config, project_id = _project(tmp_path)
    portfolio = TopicPortfolioGenerator(config).generate(project_id=project_id, root_topic=LOW_FPR_TOPIC)

    cross_domain = [variant.text.lower() for variant in portfolio.topic_variants if variant.transformation_type == "cross_domain"]

    assert any("medical-test specificity" in text for text in cross_domain)
    assert any("cartel detection" in text for text in cross_domain)
    assert all(text != LOW_FPR_TOPIC for text in cross_domain)
    assert portfolio.cross_domain_topics


def test_topic_portfolio_report_renders_without_claiming_novelty(tmp_path: Path) -> None:
    config, project_id = _project(tmp_path)
    generator = TopicPortfolioGenerator(config)
    portfolio = generator.generate(project_id=project_id, root_topic=LOW_FPR_TOPIC)

    report = generator.write_report(portfolio.id)

    assert f"# Topic Portfolio `{portfolio.id}`" in report
    assert "Why it may produce a paper" in report
    assert "Why it may fail" in report
    assert "Search queries" in report
    assert "medical-test specificity" in report.lower()
    assert "cartel detection" in report.lower()
    assert "novel" not in report.lower()


def test_topic_portfolio_cli_creates_project_and_reports(tmp_path: Path) -> None:
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")}

    created = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "topic-portfolio", LOW_FPR_TOPIC],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert created.returncode == 0, created.stderr
    payload = json.loads(created.stdout)
    assert payload["root_topic"] == LOW_FPR_TOPIC
    assert len(payload["topic_variants"]) >= 8
    assert (tmp_path / "projects" / payload["project_id"] / "ideas" / f"{payload['id']}.json").exists()

    report = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "topic-portfolio-report", "--portfolio-id", payload["id"]],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert report.returncode == 0, report.stderr
    assert f"# Topic Portfolio `{payload['id']}`" in report.stdout


def test_topic_portfolio_cli_uses_existing_project(tmp_path: Path) -> None:
    config, project_id = _project(tmp_path)
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")}

    created = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "topic-portfolio", "--project-id", project_id],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert created.returncode == 0, created.stderr
    payload = json.loads(created.stdout)
    assert payload["project_id"] == project_id
    assert payload["root_topic"] == "Idea Portfolio Project"


def _project(tmp_path: Path) -> tuple[GapForgeConfig, str]:
    config = GapForgeConfig.from_cwd(tmp_path)
    manager = ProjectMemoryManager(config)
    program = manager.create_project("Idea Portfolio Project")
    program.provenance.append(
        Provenance(
            created_by_skill="test",
            timestamp=utc_now_iso(),
            reasoning_summary="Test fixture project for topic portfolio generation.",
        )
    )
    manager.save_project(program)
    return config, program.project.id
