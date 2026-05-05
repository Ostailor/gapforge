from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from gapforge.config import GapForgeConfig
from gapforge.models import Cluster, EvidenceSpan, FieldMap, Gap, Paper, PaperNote, PaperSection
from gapforge.orchestrator import Orchestrator
from gapforge.reporting import write_final_report
from gapforge.skills.cross_domain_analogy import CrossDomainAnalogy


def analogy_fixture_state(tmp_path: Path):
    orchestrator = Orchestrator(GapForgeConfig.from_cwd(tmp_path))
    state = orchestrator.init_topic("low false positive multi-agent collusion under distribution shift")
    state.gaps = [
        Gap(
            id="gap-low-fp",
            title="Low false positive measurement gap",
            type="measurement gap",
            description="Need low false positive evaluation for collusion detection.",
            supporting_paper_ids=["p1"],
            risk_that_gap_is_fake="Prior work may already evaluate this in full text.",
        ),
        Gap(
            id="gap-hidden",
            title="Hidden communication channel gap",
            type="cross-domain gap",
            description="Need methods for hidden communication and covert channels.",
            explicit_reason="Indirect evidence.",
            risk_that_gap_is_fake="Cryptography literature may already cover it.",
        ),
        Gap(
            id="gap-cartel",
            title="Multi-agent collusion incentives",
            type="theory gap",
            description="Multi-agent collusion and game theory cartel behavior are under-modeled.",
            explicit_reason="Indirect evidence.",
            risk_that_gap_is_fake="Economics may already solve it.",
        ),
        Gap(
            id="gap-instability",
            title="Optimization instability under feedback",
            type="deployment gap",
            description="Optimization instability and feedback may break detectors.",
            explicit_reason="Indirect evidence.",
            risk_that_gap_is_fake="Control theory may not transfer.",
        ),
    ]
    state.field_map = FieldMap(
        topic=state.topic.text,
        clusters=[
            Cluster(
                name="Shift",
                description="distribution shift cluster",
                paper_ids=[],
                representative_papers=[],
                dominant_methods=[],
                open_questions=[],
                why_it_matters="shift",
            )
        ],
        adjacent_fields=["medicine", "economics", "control theory"],
        underexplored_areas=["distribution shift", "hidden communication", "research drift"],
        dominant_methods=["calibration"],
        contradictions=["optimization instability appears under feedback"],
    )
    state.paper_notes = [
        PaperNote(
            paper_id="p1",
            possible_connections=["low false positive evaluation"],
            what_it_cannot_answer=["Cannot assess distribution shift"],
            assumptions=["Research drift requires provenance"],
            unstated_limitations=["hidden communication is not modeled"],
        )
    ]
    orchestrator.state_store.save_run(state)
    return orchestrator, state


def test_cross_domain_analogy_generates_at_least_five_source_field_mappings(tmp_path: Path) -> None:
    orchestrator, state = analogy_fixture_state(tmp_path)

    analogized = orchestrator.analogies(run_id=state.run_id)
    fields = {analogy.source_field for analogy in analogized.cross_domain_analogies}

    assert {"medicine", "industrial monitoring", "steganography", "cryptography", "economics"} <= fields
    assert "control theory" in fields
    assert "statistics" in fields


def test_cross_domain_analogies_are_skeptical_and_searchable(tmp_path: Path) -> None:
    orchestrator, state = analogy_fixture_state(tmp_path)

    analogized = orchestrator.analogies(run_id=state.run_id)

    assert analogized.cross_domain_analogies
    for analogy in analogized.cross_domain_analogies:
        assert analogy.what_breaks_in_the_mapping
        assert analogy.risk_of_fake_analogy
        assert analogy.confidence in {"low", "medium"}
        assert analogy.papers_or_sources_to_search
        assert not analogy.confidence == "high"


def test_cross_domain_analogy_writes_artifacts_and_hypotheses(tmp_path: Path) -> None:
    orchestrator, state = analogy_fixture_state(tmp_path)

    analogized = orchestrator.analogies(run_id=state.run_id)
    run_dir = Path(analogized.run_dir)

    assert (run_dir / "cross_domain_analogies.json").exists()
    assert (run_dir / "cross_domain_analogies.md").exists()
    assert (run_dir / "cross_domain_transfers.json").exists()
    assert (run_dir / "cross_domain_transfers.md").exists()
    payload = json.loads((run_dir / "cross_domain_analogies.json").read_text(encoding="utf-8"))
    markdown = (run_dir / "cross_domain_analogies.md").read_text(encoding="utf-8")
    assert payload[0]["what_breaks_in_the_mapping"]
    assert "Query-Only Analogies" in markdown
    assert all(item["status"] == "query_only" for item in payload)
    assert not analogized.hypotheses


def test_adjacent_source_fixture_promotes_transfer_candidate(tmp_path: Path) -> None:
    orchestrator, state = analogy_fixture_state(tmp_path)
    source = FixtureAdjacentSource(
        [
            Paper(
                id="med-screening-1",
                title="Specificity calibrated screening with confirmatory diagnosis",
                authors=["A"],
                abstract=(
                    "Medicine screening uses specificity, sensitivity, threshold triage, "
                    "and confirmatory diagnosis to reduce false positives."
                ),
                year=2024,
                source="medicine",
                keywords=["screening", "specificity", "confirmatory"],
            )
        ]
    )
    orchestrator = Orchestrator(GapForgeConfig.from_cwd(tmp_path), sources=[source])

    analogized = orchestrator.analogies(run_id=state.run_id, search=True)

    promoted = [transfer for transfer in analogized.cross_domain_transfers if transfer.status == "promoted"]
    assert promoted
    assert promoted[0].source_paper_ids == ["med-screening-1"]
    assert promoted[0].technical_mechanism
    assert any(analogy.status == "promoted" for analogy in analogized.cross_domain_analogies)
    assert any(note.paper_id == "med-screening-1" for note in analogized.paper_notes)
    assert any(record.purpose == "analogy" for record in analogized.search_queries)


def test_fake_analogy_without_mechanism_is_not_promoted(tmp_path: Path) -> None:
    orchestrator, state = analogy_fixture_state(tmp_path)
    source = FixtureAdjacentSource(
        [
            Paper(
                id="medicine-editorial",
                title="Medicine history editorial",
                authors=["A"],
                abstract="A broad editorial about institutions and history without a transferable technical mechanism.",
                year=2024,
                source="medicine",
            )
        ]
    )
    orchestrator = Orchestrator(GapForgeConfig.from_cwd(tmp_path), sources=[source])

    analogized = orchestrator.analogies(run_id=state.run_id, search=True)

    medicine_transfers = [transfer for transfer in analogized.cross_domain_transfers if transfer.source_field == "medicine"]
    assert medicine_transfers
    assert all(transfer.status in {"query_only", "rejected"} for transfer in medicine_transfers)
    assert not any(transfer.status == "promoted" for transfer in medicine_transfers)


def test_transfer_candidate_links_existing_evidence_spans(tmp_path: Path) -> None:
    orchestrator, state = analogy_fixture_state(tmp_path)
    state.papers.append(
        Paper(
            id="med-span-paper",
            title="Medicine screening threshold triage",
            authors=["A"],
            abstract="Screening threshold triage reduces false positives.",
            year=2024,
            source="medicine",
        )
    )
    state.paper_sections.append(
        PaperSection(
            id="med-section",
            paper_id="med-span-paper",
            title="Methods",
            section_type="method",
            text="Specificity and confirmatory diagnosis are used as threshold triage mechanisms.",
            page_start=3,
            page_end=3,
        )
    )
    state.evidence_spans.append(
        EvidenceSpan(
            id="span-med-mechanism",
            paper_id="med-span-paper",
            section_id="med-section",
            quote="Specificity and confirmatory diagnosis are used as threshold triage mechanisms.",
            locator="med-span-paper:Methods:p3",
            evidence_type="method",
        )
    )
    orchestrator.state_store.save_run(state)

    analogized = orchestrator.analogies(run_id=state.run_id)

    assert any("span-med-mechanism" in transfer.evidence_span_ids for transfer in analogized.cross_domain_transfers)


def test_final_report_marks_query_only_analogies_as_not_conclusions(tmp_path: Path) -> None:
    orchestrator, state = analogy_fixture_state(tmp_path)
    analogized = orchestrator.analogies(run_id=state.run_id)

    path = write_final_report(analogized)
    markdown = path.read_text(encoding="utf-8")

    assert "query-only seed, not an evidence-backed conclusion" in markdown


def test_cross_domain_analogy_generate_directly(tmp_path: Path) -> None:
    skill = CrossDomainAnalogy()
    orchestrator, state = analogy_fixture_state(tmp_path)

    analogies = skill.generate(state)

    assert any(analogy.source_field == "software provenance" for analogy in analogies)
    assert any("research drift" in " ".join(analogy.papers_or_sources_to_search).lower() for analogy in analogies)


def test_analogies_cli(tmp_path: Path) -> None:
    _, state = analogy_fixture_state(tmp_path)
    env = {**os.environ, "GAPFORGE_DISABLE_NETWORK": "1"}

    result = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "analogies", "--run-id", state.run_id],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "cross_domain_analogies.md" in result.stdout


class FixtureAdjacentSource:
    name = "FixtureAdjacent"

    def __init__(self, papers: list[Paper]) -> None:
        self.papers = papers

    def search(
        self,
        query: str,
        *,
        max_results: int,
        sort: str = "newest",
        date_from: str | None = None,
        date_to: str | None = None,
    ) -> list[Paper]:
        return self.papers[:max_results]
