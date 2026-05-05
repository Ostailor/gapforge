from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from gapforge.config import GapForgeConfig
from gapforge.models import (
    Claim,
    EvidenceSpan,
    Gap,
    NoveltyDossier,
    Paper,
    PaperNote,
    PaperSection,
    ProjectMemoryRecord,
)
from gapforge.project_memory import ProjectMemoryManager
from gapforge.retrieval.documents import documents_from_state
from gapforge.retrieval.embeddings import FakeEmbeddingClient
from gapforge.retrieval.hybrid import HybridRetriever, build_project_index, build_run_index, search_project_index, search_run_index
from gapforge.retrieval.index_store import RetrievalIndexStore
from gapforge.retrieval.lexical import LexicalRetriever
from gapforge.skills.novelty_gate import NoveltyGate
from gapforge.state import ResearchStateManager


def test_build_index_from_fixture_state_persists_documents(tmp_path: Path) -> None:
    manager = ResearchStateManager(GapForgeConfig.from_cwd(tmp_path))
    state = _retrieval_state(manager)

    manifest = build_run_index(state)
    manager.save_run(state)

    store = RetrievalIndexStore.for_run(state.run_dir)
    assert manifest.document_count >= 8
    assert store.exists()
    assert store.load_manifest().id == manifest.id
    assert len(store.load_documents()) == manifest.document_count
    assert len(store.load_embeddings()) == manifest.document_count
    assert (Path(state.run_dir) / "retrieval" / "retrieval_coverage.md").exists()


def test_query_returns_relevant_sections(tmp_path: Path) -> None:
    manager = ResearchStateManager(GapForgeConfig.from_cwd(tmp_path))
    state = _retrieval_state(manager)
    build_run_index(state)
    manager.save_run(state)

    results = search_run_index(manager.config, state.run_id, "operator workload false positive evaluation", top_k=5)

    assert results
    assert any(result.object_type == "paper_section" and result.object_id == "section-results" for result in results[:3])
    assert any("operator workload" in result.text_snippet.lower() for result in results[:3])


def test_evidence_spans_rank_above_generic_metadata_for_specific_query(tmp_path: Path) -> None:
    manager = ResearchStateManager(GapForgeConfig.from_cwd(tmp_path))
    state = _retrieval_state(manager)
    build_run_index(state)
    manager.save_run(state)

    results = search_run_index(manager.config, state.run_id, "false positive operator workload", top_k=3)

    assert results[0].object_type == "evidence_span"
    assert results[0].object_id == "span-result"


def test_fake_embedding_path_works_offline_and_improves_fixture_case(tmp_path: Path) -> None:
    manager = ResearchStateManager(GapForgeConfig.from_cwd(tmp_path))
    state = _retrieval_state(manager)
    documents = documents_from_state(state)
    lexical_results = LexicalRetriever(documents).score("specificity")
    lexical_top_id = max(lexical_results, key=lexical_results.get)
    lexical_top = next(document for document in documents if document.id == lexical_top_id)
    lexical_order = sorted(documents, key=lambda document: lexical_results[document.id], reverse=True)
    lexical_span_rank = [document.object_id for document in lexical_order].index("span-result")

    retriever = HybridRetriever(documents, embedding_client=FakeEmbeddingClient())
    hybrid_results = retriever.search("specificity", top_k=3)
    hybrid_span_rank = [result.object_id for result in hybrid_results].index("span-result")

    assert lexical_top.object_type == "paper"
    assert hybrid_span_rank < lexical_span_rank
    assert hybrid_results[hybrid_span_rank].object_type == "evidence_span"


def test_project_index_searches_project_memory(tmp_path: Path) -> None:
    config = GapForgeConfig.from_cwd(tmp_path)
    project_manager = ProjectMemoryManager(config)
    program = project_manager.create_project("Retrieval Project")
    program.memory_records.append(
        ProjectMemoryRecord(
            id="memory-1",
            project_id=program.project.id,
            record_type="rejected_idea",
            text="Rejected duplicate idea: false-positive collusion benchmark already covered in prior run.",
            linked_run_ids=["run-a"],
            linked_object_ids=["gap-a"],
            linked_paper_ids=["paper-1"],
            status="rejected",
            confidence="high",
        )
    )
    project_manager.save_project(program)

    manifest = build_project_index(program)
    results = search_project_index(config, program.project.id, "duplicate false positive prior run", top_k=5)

    assert manifest.document_count >= 1
    assert results[0].object_type == "project_memory"
    assert results[0].object_id == "memory-1"


def test_novelty_gate_consumes_retrieval_candidates(tmp_path: Path) -> None:
    manager = ResearchStateManager(GapForgeConfig.from_cwd(tmp_path))
    state = _retrieval_state(manager)
    state.gaps.append(
        Gap(
            id="gap-duplicate",
            title="Low false-positive collusion benchmark",
            description="Evaluate collusion detectors at low false-positive rates with operator workload.",
            supporting_paper_ids=["paper-1"],
            confidence="medium",
            novelty_status="unchecked",
            risk_that_gap_is_fake="A prior benchmark may already test this.",
        )
    )
    build_run_index(state)

    NoveltyGate().assess(state, gap_id="gap-duplicate")

    assert state.novelty_dossiers
    assert "paper-1" in " ".join(state.novelty_dossiers[0].top_prior_work)
    assert state.config["retrieval_last_query"]["result_count"] > 0


def test_retrieval_cli_build_search_and_explain(tmp_path: Path) -> None:
    manager = ResearchStateManager(GapForgeConfig.from_cwd(tmp_path))
    state = _retrieval_state(manager)
    manager.save_run(state)
    env = {**os.environ, "GAPFORGE_DISABLE_NETWORK": "1"}

    build = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "build-index", "--run-id", state.run_id],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert build.returncode == 0, build.stderr
    assert "retrieval index" in build.stdout

    search = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "search-index", "--run-id", state.run_id, "false positive workload"],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert search.returncode == 0, search.stderr
    assert "span-result" in search.stdout

    explain = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "explain-retrieval", "--run-id", state.run_id, "false positive workload"],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert explain.returncode == 0, explain.stderr
    assert "lexical=" in explain.stdout

    manifest = json.loads((Path(state.run_dir) / "retrieval" / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["document_count"] >= 8


def _retrieval_state(manager: ResearchStateManager):
    state = manager.create_run("low false positive collusion detection")
    state.papers.extend(
        [
            Paper(
                id="paper-1",
                title="Low False-Positive Collusion Detection Benchmark",
                authors=["A"],
                abstract="We evaluate collusion detectors under low false positive rate constraints.",
                year=2025,
                source="fixture",
                roles=["benchmark"],
            ),
            Paper(
                id="paper-2",
                title="Specificity in Screening Systems",
                authors=["B"],
                abstract="Specificity is discussed as metadata only without operator workload evidence.",
                year=2020,
                source="fixture",
                roles=["survey"],
            ),
        ]
    )
    state.paper_sections.extend(
        [
            PaperSection(
                id="section-method",
                paper_id="paper-1",
                title="Method",
                section_type="method",
                text="The benchmark calibrates detectors before deployment.",
                page_start=2,
                page_end=2,
                confidence="medium",
            ),
            PaperSection(
                id="section-results",
                paper_id="paper-1",
                title="Results",
                section_type="results",
                text="At one percent false positive rate, operator workload remains the limiting evaluation factor.",
                page_start=5,
                page_end=5,
                confidence="medium",
            ),
        ]
    )
    state.evidence_spans.append(
        EvidenceSpan(
            id="span-result",
            paper_id="paper-1",
            section_id="section-results",
            quote="At one percent false positive rate, operator workload remains the limiting evaluation factor.",
            locator="paper-1:Results:p5",
            evidence_type="result",
            confidence="medium",
        )
    )
    state.paper_notes.append(
        PaperNote(
            paper_id="paper-1",
            one_sentence_summary="Benchmark paper for low false-positive collusion detection.",
            main_results=["Operator workload remains limiting."],
            metrics=["false positive rate"],
            confidence="medium",
            source_basis="full text",
        )
    )
    state.claims.append(
        Claim(
            id="claim-1",
            text="Low false-positive evaluation needs operator workload evidence.",
            type="gap",
            confidence="medium",
            source_paper_ids=["paper-1"],
        )
    )
    state.novelty_dossiers.append(
        NoveltyDossier(
            target_id="gap-old",
            idea_summary="Low false-positive collusion benchmark",
            top_prior_work=["paper-1: Low False-Positive Collusion Detection Benchmark"],
            verdict="revise",
            confidence="medium",
        )
    )
    return state
