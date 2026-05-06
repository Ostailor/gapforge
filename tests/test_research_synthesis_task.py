from __future__ import annotations

import json
from pathlib import Path

from gapforge.campaigns import CampaignManager
from gapforge.campaigns.importer import CampaignOutputImporter
from gapforge.campaigns.outputs import validate_campaign_outputs
from gapforge.campaigns.research_synthesis_task import create_research_synthesis_task
from gapforge.config import GapForgeConfig
from gapforge.models import EvidenceSpan, Gap, Paper, PaperSection, PriorWorkRecallAssessment, SourceCoverageReport
from gapforge.project_memory import ProjectMemoryManager
from gapforge.state import ResearchStateManager


def test_research_synthesis_task_pack_contains_real_literature_contract(tmp_path: Path) -> None:
    config, campaign_id, _run_id = _synthesis_fixture(tmp_path, recall_passed=True)

    pack_dir = create_research_synthesis_task(config, campaign_id)
    prompt = (pack_dir / "RESEARCH_SYNTHESIS_PROMPT.md").read_text(encoding="utf-8")
    expected = json.loads((pack_dir / "expected_outputs.json").read_text(encoding="utf-8"))

    assert "Propose at most 3 research directions" in prompt
    assert "do not store hidden chain-of-thought" in prompt.lower()
    assert "research_directions_patch.json" in expected["files"]
    assert "search_requests.json" in expected["files"]


def test_valid_research_synthesis_output_imports_direction(tmp_path: Path) -> None:
    config, campaign_id, _run_id = _synthesis_fixture(tmp_path, recall_passed=True)
    pack_dir = create_research_synthesis_task(config, campaign_id)
    paths = _write_valid_synthesis_outputs(pack_dir, direction_count=1)

    record = CampaignOutputImporter(config).import_outputs(campaign_id, pack_dir.name, paths)
    campaign = CampaignManager(config).load_campaign_state(campaign_id).campaign
    program = ProjectMemoryManager(config).load_project(campaign.project_id)

    assert record.status == "applied"
    assert any(direction.id == "direction-1" for direction in program.research_directions)


def test_research_synthesis_rejects_fake_prior_work(tmp_path: Path) -> None:
    config, campaign_id, _run_id = _synthesis_fixture(tmp_path, recall_passed=True)
    pack_dir = create_research_synthesis_task(config, campaign_id)
    output = pack_dir / "outputs" / "research_directions_patch.json"
    output.write_text(
        json.dumps(
            {
                "research_directions_patch": [
                    _direction_payload(
                        "direction-1",
                        closest_prior_work=["Imaginary Prior Work 2099"],
                        evidence_span_ids=["span-1"],
                    )
                ]
            }
        ),
        encoding="utf-8",
    )

    validation = validate_campaign_outputs(config, campaign_id, pack_dir.name, [output])

    assert validation["status"] == "rejected"
    assert any("citation does not resolve" in issue for issue in validation["issues"])


def test_research_synthesis_rejects_unsupported_direction(tmp_path: Path) -> None:
    config, campaign_id, _run_id = _synthesis_fixture(tmp_path, recall_passed=True)
    pack_dir = create_research_synthesis_task(config, campaign_id)
    output = pack_dir / "outputs" / "research_directions_patch.json"
    output.write_text(
        json.dumps({"research_directions_patch": [_direction_payload("direction-1", evidence_span_ids=[])]}),
        encoding="utf-8",
    )

    validation = validate_campaign_outputs(config, campaign_id, pack_dir.name, [output])

    assert validation["status"] == "rejected"
    assert any("research direction lacks evidence" in issue for issue in validation["issues"])


def test_research_synthesis_too_many_directions_is_partial_rejection(tmp_path: Path) -> None:
    config, campaign_id, _run_id = _synthesis_fixture(tmp_path, recall_passed=True)
    pack_dir = create_research_synthesis_task(config, campaign_id)
    output = pack_dir / "outputs" / "research_directions_patch.json"
    output.write_text(
        json.dumps({"research_directions_patch": [_direction_payload(f"direction-{index}") for index in range(1, 5)]}),
        encoding="utf-8",
    )

    validation = validate_campaign_outputs(config, campaign_id, pack_dir.name, [output])

    assert validation["status"] == "partial"
    assert any("more than 3 directions" in issue for issue in validation["issues"])


def test_research_synthesis_blocks_strong_novelty_without_recall_gate(tmp_path: Path) -> None:
    config, campaign_id, _run_id = _synthesis_fixture(tmp_path, recall_passed=False)
    pack_dir = create_research_synthesis_task(config, campaign_id)
    output = pack_dir / "outputs" / "research_directions_patch.json"
    output.write_text(
        json.dumps(
            {
                "research_directions_patch": [
                    _direction_payload(
                        "direction-strong",
                        novelty_strength="strong",
                        source_coverage="high",
                        missing_searches=[],
                    )
                ]
            }
        ),
        encoding="utf-8",
    )

    validation = validate_campaign_outputs(config, campaign_id, pack_dir.name, [output])

    assert validation["status"] == "rejected"
    assert any("recall gate" in issue for issue in validation["issues"])


def _synthesis_fixture(tmp_path: Path, *, recall_passed: bool):
    config = GapForgeConfig.from_cwd(tmp_path)
    state_manager = ResearchStateManager(config)
    project_manager = ProjectMemoryManager(config)
    program = project_manager.create_project("Research Synthesis Project")
    run_state = state_manager.create_run("low false positive collusion detection")
    run_state.papers.append(
        Paper(
            id="paper-1",
            title="Low False Positive Collusion Detection",
            authors=["A"],
            abstract="Known prior work and evidence for low false positive collusion detection.",
            year=2026,
            source="fixture",
        )
    )
    run_state.paper_sections.append(
        PaperSection(
            id="section-1",
            paper_id="paper-1",
            title="Results",
            section_type="results",
            text="Evidence for low false positive collusion detection.",
        )
    )
    run_state.evidence_spans.append(
        EvidenceSpan(
            id="span-1",
            paper_id="paper-1",
            section_id="section-1",
            quote="Evidence supports specificity-sensitive collusion monitoring.",
            locator="paper-1:Results:p1",
            evidence_type="result",
            confidence="high",
        )
    )
    run_state.gaps.append(
        Gap(
            id="gap-1",
            title="Low-FPR evaluation gap",
            description="Need low false-positive evaluation.",
            supporting_paper_ids=["paper-1"],
            confidence="medium",
        )
    )
    if recall_passed:
        run_state.prior_work_recall_assessments.append(
            PriorWorkRecallAssessment(
                id="recall-1",
                target_id="gap-1",
                required_query_rounds=["exact_phrase_search"],
                completed_query_rounds=["exact_phrase_search"],
                candidate_prior_work_ids=["paper-1"],
                top_prior_work_ids=["paper-1"],
                recall_confidence="medium",
                novelty_allowed=True,
            )
        )
    run_state.source_coverage = SourceCoverageReport(
        run_id=run_state.run_id,
        topic=run_state.topic.text,
        searched_sources=["fixture"],
        papers_by_source={"fixture": 1},
        papers_with_full_text=["paper-1"],
        confidence="medium",
    )
    state_manager.save_run(run_state)
    project_manager.attach_run(program.project.id, run_state.run_id)
    project_manager.sync_project_memory(program.project.id)
    campaign_state = CampaignManager(config).create_campaign(
        "low false positive collusion detection",
        project_id=program.project.id,
        mode="codex_task_pack",
        source_profile="generic",
    )
    CampaignManager(config).attach_run(campaign_state.campaign.id, run_state.run_id)
    return config, campaign_state.campaign.id, run_state.run_id


def _write_valid_synthesis_outputs(pack_dir: Path, *, direction_count: int) -> list[Path]:
    payloads = {
        "research_directions_patch.json": {
            "research_directions_patch": [_direction_payload(f"direction-{index}") for index in range(1, direction_count + 1)]
        },
        "gap_evidence_matrices_patch.json": {
            "gap_evidence_matrices_patch": [
                {
                    "gap_id": "gap-1",
                    "evidence_span_ids": ["span-1"],
                    "papers_supporting": ["paper-1"],
                    "confidence": "medium",
                }
            ]
        },
        "novelty_dossiers_patch.json": {
            "novelty_dossiers_patch": [
                {
                    "target_id": "gap-1",
                    "idea_summary": "Low false positive collusion detection direction.",
                    "top_prior_work": ["paper-1"],
                    "verdict": "pursue",
                    "novelty_strength": "medium",
                    "confidence": "medium",
                    "evidence_span_ids": ["span-1"],
                }
            ]
        },
        "related_work_matrix_patch.json": {
            "related_work_matrix_patch": [
                {
                    "direction_id": "direction-1",
                    "entries": [{"paper_id": "paper-1", "relationship": "closest prior work", "evidence_span_ids": ["span-1"]}],
                }
            ]
        },
        "uncertainty_register.json": {
            "uncertainty_register": [
                {
                    "id": "uncertainty-1",
                    "text": "Novelty remains provisional until broader live searches are complete.",
                    "confidence": "low",
                }
            ]
        },
        "search_requests.json": {
            "search_requests": [
                {
                    "id": "search-1",
                    "query": "low false positive collusion detection benchmark closest prior work",
                    "purpose": "missing prior-work confirmation",
                }
            ]
        },
    }
    paths: list[Path] = []
    for filename, payload in payloads.items():
        path = pack_dir / "outputs" / filename
        path.write_text(json.dumps(payload), encoding="utf-8")
        paths.append(path)
    return paths


def _direction_payload(
    direction_id: str,
    *,
    closest_prior_work: list[str] | None = None,
    evidence_span_ids: list[str] | None = None,
    novelty_strength: str = "medium",
    source_coverage: str = "medium",
    missing_searches: list[str] | None = None,
) -> dict[str, object]:
    return {
        "id": direction_id,
        "title": "Specificity-sensitive collusion monitoring",
        "summary": "Evaluate collusion monitors at low false-positive operating points.",
        "linked_gap_ids": ["gap-1"],
        "supporting_paper_ids": ["paper-1"],
        "evidence_span_ids": ["span-1"] if evidence_span_ids is None else evidence_span_ids,
        "closest_prior_work": ["paper-1"] if closest_prior_work is None else closest_prior_work,
        "risk_that_gap_is_fake": "Closest prior work may already test the same operating point.",
        "novelty_strength": novelty_strength,
        "source_coverage": source_coverage,
        "missing_searches": [] if missing_searches is None else missing_searches,
        "confidence": "medium",
        "maturity": "candidate",
        "readiness_score": 0.45,
    }
